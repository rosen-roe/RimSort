import datetime
import json
import os
import platform
import subprocess
import sys
import time
import traceback
import webbrowser
from toposort import CircularDependencyError
from functools import partial
from gc import collect
from io import BytesIO
from math import ceil
from multiprocessing import Pool, cpu_count
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, Self
from urllib.parse import urlparse
from zipfile import ZipFile

from loguru import logger

# GitPython depends on git executable being available in PATH
try:
    from git import Repo
    from git.exc import GitCommandError

    GIT_EXISTS = True
except ImportError:
    logger.warning(
        "git not detected in your PATH! Do you have git installed...? git integration will be disabled! You may need to restart the app if you installed it."
    )
    GIT_EXISTS = False

from github import Github
from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QProcess,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from requests import get as requests_get

import app.models.dialogue as dialogue
import app.sort.alphabetical_sort as alpha_sort
import app.sort.dependencies as deps_sort
import app.sort.topo_sort as topo_sort
import app.utils.constants as app_constants
import app.utils.metadata as metadata
from app.models.animations import LoadingAnimation
from app.utils.app_info import AppInfo
from app.utils.event_bus import EventBus
from app.utils.generic import (
    chunks,
    copy_to_clipboard_safely,
    delete_files_except_extension,
    launch_game_process,
    open_url_browser,
    platform_specific_open,
    upload_data_to_0x0_st,
)
from app.utils.metadata import MetadataManager, SettingsController
from app.utils.rentry.wrapper import RentryImport, RentryUpload
from app.utils.schema import generate_rimworld_mods_list
from app.utils.steam.browser import SteamBrowser
from app.utils.steam.steamcmd.wrapper import SteamcmdInterface
from app.utils.steam.steamworks.wrapper import (
    SteamworksGameLaunch,
    SteamworksSubscriptionHandler,
)
from app.utils.steam.webapi.wrapper import (
    CollectionImport,
    ISteamRemoteStorage_GetPublishedFileDetails,
)
from app.utils.todds.wrapper import ToddsInterface
from app.utils.xml import json_to_xml_write
from app.views.mod_info_panel import ModInfo
from app.views.mods_panel import ModListWidget, ModsPanel, ModsPanelSortKey
from app.windows.missing_mods_panel import MissingModsPrompt
from app.windows.rule_editor_panel import RuleEditor
from app.windows.runner_panel import RunnerPanel
from app.windows.workshop_mod_updater_panel import ModUpdaterPrompt


class MainContent(QObject):
    """
    This class controls the layout and functionality of the main content
    panel of the GUI, containing the mod information display, inactive and
    active mod lists, and the action button panel. Additionally, it acts
    as the main temporary datastore of the app, caching workshop mod information
    and their dependencies.
    """

    _instance: Self | None = None

    disable_enable_widgets_signal = Signal(bool)
    status_signal = Signal(str)
    stop_watchdog_signal = Signal()

    def __new__(cls, *args: Any, **kwargs: Any) -> "MainContent":
        if cls._instance is None:
            cls._instance = super(MainContent, cls).__new__(cls)
        return cls._instance

    def __init__(
        self, settings_controller: SettingsController, version_string: str
    ) -> None:
        """
        Initialize the main content panel.

        :param settings_controller: the settings controller for the application
        """
        if not hasattr(self, "initialized"):
            super(MainContent, self).__init__()
            logger.debug("初始化主要内容")

            self.settings_controller = settings_controller
            self.version_string = version_string

            EventBus().settings_have_changed.connect(self._on_settings_have_changed)
            EventBus().do_check_for_application_update.connect(
                self._do_check_for_update
            )
            EventBus().do_validate_steam_client.connect(self._do_validate_steam_client)
            EventBus().do_open_mod_list.connect(self._do_import_list_file_xml)
            EventBus().do_import_mod_list_from_rentry.connect(
                self._do_import_list_rentry
            )
            EventBus().do_import_mod_list_from_workshop_collection.connect(
                self._do_import_list_workshop_collection
            )
            EventBus().do_save_mod_list_as.connect(self._do_export_list_file_xml)
            EventBus().do_export_mod_list_to_clipboard.connect(
                self._do_export_list_clipboard
            )
            EventBus().do_export_mod_list_to_rentry.connect(self._do_upload_list_rentry)
            EventBus().do_upload_community_rules_db_to_github.connect(
                self._on_do_upload_community_db_to_github
            )
            EventBus().do_download_community_rules_db_from_github.connect(
                self._on_do_download_community_db_from_github
            )
            EventBus().do_upload_steam_workshop_db_to_github.connect(
                self._on_do_upload_steam_workshop_db_to_github
            )
            EventBus().do_download_steam_workshop_db_from_github.connect(
                self._on_do_download_steam_workshop_db_from_github
            )
            EventBus().do_upload_rimsort_log.connect(self._on_do_upload_rimsort_log)
            EventBus().do_upload_rimsort_old_log.connect(
                self._on_do_upload_rimsort_old_log
            )
            EventBus().do_upload_rimworld_log.connect(self._on_do_upload_rimworld_log)
            EventBus().do_download_all_mods_via_steamcmd.connect(
                self._on_do_download_all_mods_via_steamcmd
            )
            EventBus().do_download_all_mods_via_steam.connect(
                self._on_do_download_all_mods_via_steam
            )
            EventBus().do_compare_steam_workshop_databases.connect(
                self._do_generate_metadata_comparison_report
            )
            EventBus().do_merge_steam_workshop_databases.connect(
                self._do_merge_databases
            )
            EventBus().do_build_steam_workshop_database.connect(
                self._on_do_build_steam_workshop_database
            )
            EventBus().do_import_acf.connect(
                lambda: self.actions_slot("import_steamcmd_acf_data")
            )
            EventBus().do_delete_acf.connect(
                lambda: self.actions_slot("reset_steamcmd_acf_data")
            )
            EventBus().do_install_steamcmd.connect(self._do_setup_steamcmd)

            EventBus().do_refresh_mods_lists.connect(self._do_refresh)
            EventBus().do_clear_active_mods_list.connect(self._do_clear)
            EventBus().do_restore_active_mods_list.connect(self._do_restore)
            EventBus().do_sort_active_mods_list.connect(self._do_sort)
            EventBus().do_save_active_mods_list.connect(self._do_save)
            EventBus().do_run_game.connect(self._do_run_game)

            # Edit Menu bar Eventbus
            EventBus().do_rule_editor.connect(
                lambda: self.actions_slot("open_community_rules_with_rule_editor")
            )

            # Download Menu bar Eventbus
            EventBus().do_add_git_mod.connect(self._do_add_git_mod)
            EventBus().do_browse_workshop.connect(self._do_browse_workshop)
            EventBus().do_check_for_workshop_updates.connect(
                self._do_check_for_workshop_updates
            )

            # Textures Menu bar Eventbus
            EventBus().do_optimize_textures.connect(
                lambda: self.actions_slot("optimize_textures")
            )
            EventBus().do_delete_dds_textures.connect(
                lambda: self.actions_slot("delete_textures")
            )

            # INITIALIZE WIDGETS
            # Initialize Steam(CMD) integrations
            self.steam_browser: SteamBrowser | None = None
            self.steamcmd_runner: RunnerPanel | None = None
            self.steamcmd_wrapper = SteamcmdInterface.instance()

            # Initialize MetadataManager
            self.metadata_manager = metadata.MetadataManager.instance()

            # BASE LAYOUT
            self.main_layout = QHBoxLayout()
            self.main_layout.setContentsMargins(
                5, 5, 5, 5
            )  # Space between widgets and Frame border
            self.main_layout.setSpacing(5)  # Space between mod lists and action buttons

            # FRAME REQUIRED - to allow for styling
            self.main_layout_frame = QFrame()
            self.main_layout_frame.setObjectName("主面板")
            self.main_layout_frame.setLayout(self.main_layout)

            # INSTANTIATE WIDGETS
            self.mod_info_panel = ModInfo()
            self.mods_panel = ModsPanel(
                settings_controller=self.settings_controller,
            )

            # WIDGETS INTO BASE LAYOUT
            self.main_layout.addLayout(self.mod_info_panel.panel, 50)
            self.main_layout.addLayout(self.mods_panel.panel, 50)

            # SIGNALS AND SLOTS
            self.metadata_manager.mod_created_signal.connect(
                self.mods_panel.on_mod_created  # Connect MetadataManager to ModPanel for mod creation
            )
            self.metadata_manager.mod_deleted_signal.connect(
                self.mods_panel.on_mod_deleted  # Connect MetadataManager to ModPanel for mod deletion
            )
            self.metadata_manager.mod_metadata_updated_signal.connect(
                self.mods_panel.on_mod_metadata_updated  # Connect MetadataManager to ModPanel for mod metadata updates
            )
            self.mods_panel.active_mods_list.key_press_signal.connect(
                self.__handle_active_mod_key_press
            )
            self.mods_panel.inactive_mods_list.key_press_signal.connect(
                self.__handle_inactive_mod_key_press
            )
            self.mods_panel.active_mods_list.mod_info_signal.connect(
                self.__mod_list_slot
            )
            self.mods_panel.inactive_mods_list.mod_info_signal.connect(
                self.__mod_list_slot
            )
            self.mods_panel.active_mods_list.item_added_signal.connect(
                self.mods_panel.inactive_mods_list.handle_other_list_row_added
            )
            self.mods_panel.inactive_mods_list.item_added_signal.connect(
                self.mods_panel.active_mods_list.handle_other_list_row_added
            )
            self.mods_panel.active_mods_list.edit_rules_signal.connect(
                self._do_open_rule_editor
            )
            self.mods_panel.inactive_mods_list.edit_rules_signal.connect(
                self._do_open_rule_editor
            )
            self.mods_panel.active_mods_list.update_git_mods_signal.connect(
                self._check_git_repos_for_update
            )
            self.mods_panel.inactive_mods_list.update_git_mods_signal.connect(
                self._check_git_repos_for_update
            )
            self.mods_panel.active_mods_list.steamcmd_downloader_signal.connect(
                self._do_download_mods_with_steamcmd
            )
            self.mods_panel.inactive_mods_list.steamcmd_downloader_signal.connect(
                self._do_download_mods_with_steamcmd
            )
            self.mods_panel.active_mods_list.steamworks_subscription_signal.connect(
                self._do_steamworks_api_call_animated
            )
            self.mods_panel.inactive_mods_list.steamworks_subscription_signal.connect(
                self._do_steamworks_api_call_animated
            )
            self.mods_panel.active_mods_list.steamdb_blacklist_signal.connect(
                self._do_blacklist_action_steamdb
            )
            self.mods_panel.inactive_mods_list.steamdb_blacklist_signal.connect(
                self._do_blacklist_action_steamdb
            )
            self.mods_panel.active_mods_list.refresh_signal.connect(self._do_refresh)
            self.mods_panel.inactive_mods_list.refresh_signal.connect(self._do_refresh)
            # Restore cache initially set to empty
            self.active_mods_uuids_last_save: list[str] = []
            self.active_mods_uuids_restore_state: list[str] = []
            self.inactive_mods_uuids_restore_state: list[str] = []

            # Store duplicate_mods for global access
            self.duplicate_mods = {}

            # Instantiate query runner
            self.query_runner: RunnerPanel | None = None

            # Steamworks bool - use this to check any Steamworks processes you try to initialize
            self.steamworks_in_use = False

            # Instantiate todds runner
            self.todds_runner: RunnerPanel | None = None

            logger.info("已完成主线内容初始化")
            self.initialized = True

    @classmethod
    def instance(cls, *args: Any, **kwargs: Any) -> "MainContent":
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        elif args or kwargs:
            raise ValueError("主内容实例已初始化。")
        return cls._instance

    def check_if_essential_paths_are_set(self, prompt: bool = True) -> bool:
        """
        When the user starts the app for the first time, none
        of the paths will be set. We should check for this and
        not throw a fatal error trying to load mods until the
        user has had a chance to set paths.
        """
        current_instance = self.settings_controller.settings.current_instance
        game_folder_path = self.settings_controller.settings.instances[
            current_instance
        ].game_folder
        config_folder_path = self.settings_controller.settings.instances[
            current_instance
        ].config_folder
        logger.debug(f"游戏文件夹: {game_folder_path}")
        logger.debug(f"配置文件夹: {config_folder_path}")
        if (
            game_folder_path
            and config_folder_path
            and os.path.exists(game_folder_path)
            and os.path.exists(config_folder_path)
        ):
            logger.info("基本路径设置!")
            return True
        else:
            logger.warning("基本路径无效或未设置!")
            answer = dialogue.show_dialogue_conditional(
                title="基本路径",
                text="基本路径无效或未设置\n",
                information=(
                    "RimSort 至少需要设置游戏文件夹和"
                    "配置文件夹路径，并且路径都存在。请设置"
                    "这两种路径都可以手动或使用自动检测功能。\n\n"
                    "您现在要配置它们吗?"
                ),
            )
            if answer == "&Yes":
                self.settings_controller.show_settings_dialog("位置")
            return False

    def ___get_relative_middle(self, some_list: ModListWidget) -> int:
        rect = some_list.contentsRect()
        top = some_list.indexAt(rect.topLeft())
        if top.isValid():
            bottom = some_list.indexAt(rect.bottomLeft())
            if not bottom.isValid():
                bottom = some_list.model().index(some_list.count() - 1, 0)
            return int((top.row() + bottom.row() + 1) / 2)
        return 0

    def __handle_active_mod_key_press(self, key: str) -> None:
        """
        If the Left Arrow key is pressed while the user is focused on the
        Active Mods List, the focus is shifted to the Inactive Mods List.
        If no Inactive Mod was previously selected, the middle (relative)
        one is selected. `__mod_list_slot` is also called to update the
        Mod Info Panel.

        If the Return or Space button is pressed the selected mods in the
        current list are deleted from the current list and inserted
        into the other list.
        """
        aml = self.mods_panel.active_mods_list
        iml = self.mods_panel.inactive_mods_list
        if key == "Left":
            iml.setFocus()
            if not iml.selectedIndexes():
                iml.setCurrentRow(self.___get_relative_middle(iml))
            data = iml.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
            uuid = data["uuid"]
            self.__mod_list_slot(uuid)

        elif key == "Return" or key == "Space" or key == "DoubleClick":
            # TODO: graphical bug where if you hold down the key, items are
            # inserted too quickly and become empty items

            items_to_move = aml.selectedItems().copy()
            if items_to_move:
                first_selected = sorted(aml.row(i) for i in items_to_move)[0]

                # Remove items from current list
                for item in items_to_move:
                    data = item.data(Qt.ItemDataRole.UserRole)
                    uuid = data["uuid"]
                    aml.uuids.remove(uuid)
                    aml.takeItem(aml.row(item))
                if aml.count():
                    if aml.count() == first_selected:
                        aml.setCurrentRow(aml.count() - 1)
                    else:
                        aml.setCurrentRow(first_selected)

                # Insert items into other list
                if not iml.selectedIndexes():
                    count = self.___get_relative_middle(iml)
                else:
                    count = iml.row(iml.selectedItems()[-1]) + 1
                for item in items_to_move:
                    iml.insertItem(count, item)
                    count += 1
            self.mods_panel.active_mods_list.recalculate_warnings_signal.emit()
            self.mods_panel.inactive_mods_list.recalculate_warnings_signal.emit()

    def __handle_inactive_mod_key_press(self, key: str) -> None:
        """
        If the Right Arrow key is pressed while the user is focused on the
        Inactive Mods List, the focus is shifted to the Active Mods List.
        If no Active Mod was previously selected, the middle (relative)
        one is selected. `__mod_list_slot` is also called to update the
        Mod Info Panel.

        If the Return or Space button is pressed the selected mods in the
        current list are deleted from the current list and inserted
        into the other list.
        """

        aml = self.mods_panel.active_mods_list
        iml = self.mods_panel.inactive_mods_list
        if key == "Right":
            aml.setFocus()
            if not aml.selectedIndexes():
                aml.setCurrentRow(self.___get_relative_middle(aml))
            data = aml.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
            uuid = data["uuid"]
            self.__mod_list_slot(uuid)

        elif key == "Return" or key == "Space" or key == "DoubleClick":
            # TODO: graphical bug where if you hold down the key, items are
            # inserted too quickly and become empty items

            items_to_move = iml.selectedItems().copy()
            if items_to_move:
                first_selected = sorted(iml.row(i) for i in items_to_move)[0]

                # Remove items from current list
                for item in items_to_move:
                    data = item.data(Qt.ItemDataRole.UserRole)
                    uuid = data["uuid"]
                    iml.uuids.remove(uuid)
                    iml.takeItem(iml.row(item))
                if iml.count():
                    if iml.count() == first_selected:
                        iml.setCurrentRow(iml.count() - 1)
                    else:
                        iml.setCurrentRow(first_selected)

                # Insert items into other list
                if not aml.selectedIndexes():
                    count = self.___get_relative_middle(aml)
                else:
                    count = aml.row(aml.selectedItems()[-1]) + 1
                for item in items_to_move:
                    aml.insertItem(count, item)
                    count += 1
            self.mods_panel.active_mods_list.recalculate_warnings_signal.emit()
            self.mods_panel.inactive_mods_list.recalculate_warnings_signal.emit()

    def __insert_data_into_lists(
        self, active_mods_uuids: list[str], inactive_mods_uuids: list[str]
    ) -> None:
        """
        Insert active mods and inactive mods into respective mod list widgets.

        :param active_mods_uuids: list of active mod uuids
        :param inactive_mods_uuids: list of inactive mod uuids
        """
        logger.info(
            f"将模组数据插入到启用的[{len(active_mods_uuids)}]模组列表和非启用的[{len(inactive_mods_uuids)}]模组列表"
        )
        self.mods_panel.active_mods_list.recreate_mod_list(
            list_type="active", uuids=active_mods_uuids
        )
        self.mods_panel.inactive_mods_list.recreate_mod_list_and_sort(
            list_type="inactive",
            uuids=inactive_mods_uuids,
            key=ModsPanelSortKey.MODNAME,
        )
        logger.info(
            f"已完成模组数据插入到启用的[{len(active_mods_uuids)}]模组列表和非启用的[{len(inactive_mods_uuids)}]模组列表"
        )
        # Recalculate warnings for both lists
        # self.mods_panel.active_mods_list.recalculate_warnings_signal.emit()
        # self.mods_panel.inactive_mods_list.recalculate_warnings_signal.emit()

    def __duplicate_mods_prompt(self) -> None:
        list_of_duplicate_mods = "\n".join(
            [f"* {mod}" for mod in self.duplicate_mods.keys()]
        )
        dialogue.show_warning(
            title="找到了重复的模组",
            text="在启用模组列表中找到的ID重复的模组",
            information=(
                "以下模组列表已在您的模组配置文件中设置为启用状态"
                "并在您的模组数据源中发现了这些模组的重复实例。"
                "原版游戏将使用特定模组ID的第一个 “本地模组” "
                "游戏本身如此，所以RimSort也会遵循这个逻辑。"
            ),
            details=list_of_duplicate_mods,
        )

    def __missing_mods_prompt(self) -> None:
        logger.debug(f"无法找到{len(self.missing_mods)}启用模组的数据")
        if (  # User configuration
            self.settings_controller.settings.try_download_missing_mods
            and self.metadata_manager.external_steam_metadata
        ):  # Do we even have metadata to lookup...?
            self.missing_mods_prompt = MissingModsPrompt(
                packageids=self.missing_mods,
                steam_workshop_metadata=self.metadata_manager.external_steam_metadata,
            )
            self.missing_mods_prompt._populate_from_metadata()
            self.missing_mods_prompt.steamcmd_downloader_signal.connect(
                self._do_download_mods_with_steamcmd
            )
            self.missing_mods_prompt.steamworks_subscription_signal.connect(
                self._do_steamworks_api_call_animated
            )
            self.missing_mods_prompt.setWindowModality(
                Qt.WindowModality.ApplicationModal
            )
            self.missing_mods_prompt.show()
        else:
            list_of_missing_mods = "\n".join([f"* {mod}" for mod in self.missing_mods])
            dialogue.show_information(
                text="找不到一些模组的数据!",
                information=(
                    "下面的模组列表在你的模组列表中被设置为启用的，"
                    "但是在本地/创意工坊的模组路径中找不到这些模组的数据。"
                    "\n\n你的游戏配置路径是否正确?"
                ),
                details=list_of_missing_mods,
            )

    def __mod_list_slot(self, uuid: str) -> None:
        """
        This slot method is triggered when the user clicks on an item
        on a mod list. It takes the internal uuid and gets the
        complete json mod info for that internal uuid. It passes
        this information to the mod info panel to display.

        :param uuid: uuid of mod
        """
        self.mod_info_panel.display_mod_info(uuid=uuid)

    def __repopulate_lists(self, is_initial: bool = False) -> None:
        """
        Get active and inactive mod lists based on the config path
        and write them to the list widgets. is_initial indicates if
        this function is running at app initialization. If is_initial is
        true, then write the active_mods_data and inactive_mods_data to
        restore variables.
        """
        logger.info("重新填充模组列表")
        (
            active_mods_uuids,
            inactive_mods_uuids,
            self.duplicate_mods,
            self.missing_mods,
        ) = metadata.get_mods_from_list(
            mod_list=str(
                (
                    Path(
                        self.settings_controller.settings.instances[
                            self.settings_controller.settings.current_instance
                        ].config_folder
                    )
                    / "ModsConfig.xml"
                )
            )
        )
        self.active_mods_uuids_last_save = active_mods_uuids
        if is_initial:
            logger.info("缓存初始启用/非启用模组列表")
            self.active_mods_uuids_restore_state = active_mods_uuids
            self.inactive_mods_uuids_restore_state = inactive_mods_uuids

        self.__insert_data_into_lists(active_mods_uuids, inactive_mods_uuids)

    #########
    # SLOTS # Can this be cleaned up & moved to own module...?
    #########

    # ACTIONS PANEL ACTIONS

    def actions_slot(self, action: str) -> None:
        """
        Slot for the `actions_signal` signals

        :param action: string indicating action
        """
        logger.info(f"USER ACTION: 接收到的操作{action}")
        # game configuration panel actions
        if action == "check_for_update":
            self._do_check_for_update()
        # actions panel actions
        if action == "refresh":
            self._do_refresh()
        if action == "clear":
            self._do_clear()
        if action == "restore":
            self._do_restore()
        if action == "sort":
            self._do_sort()
        if "textures" in action:
            logger.debug("启动新的 todds 操作...")
            # Setup Environment
            todds_txt_path = str((Path(gettempdir()) / "todds.txt"))
            if os.path.exists(todds_txt_path):
                os.remove(todds_txt_path)
            if not self.settings_controller.settings.todds_active_mods_target:
                local_mods_target = self.settings_controller.settings.instances[
                    self.settings_controller.settings.current_instance
                ].local_folder
                if local_mods_target and local_mods_target != "":
                    with open(todds_txt_path, "a", encoding="utf-8") as todds_txt_file:
                        todds_txt_file.write(local_mods_target + "\n")
                workshop_mods_target = self.settings_controller.settings.instances[
                    self.settings_controller.settings.current_instance
                ].workshop_folder
                if workshop_mods_target and workshop_mods_target != "":
                    with open(todds_txt_path, "a", encoding="utf-8") as todds_txt_file:
                        todds_txt_file.write(workshop_mods_target + "\n")
            else:
                with open(todds_txt_path, "a", encoding="utf-8") as todds_txt_file:
                    for uuid in self.mods_panel.active_mods_list.uuids:
                        todds_txt_file.write(
                            self.metadata_manager.internal_local_metadata[uuid]["path"]
                            + "\n"
                        )
            if action == "optimize_textures":
                self._do_optimize_textures(todds_txt_path)
            if action == "delete_textures":
                self._do_delete_dds_textures(todds_txt_path)
        if action == "add_git_mod":
            self._do_add_git_mod()
        if action == "browse_workshop":
            self._do_browse_workshop()
        if action == "import_steamcmd_acf_data":
            metadata.import_steamcmd_acf_data(
                rimsort_storage_path=str(AppInfo().app_storage_folder),
                steamcmd_appworkshop_acf_path=self.steamcmd_wrapper.steamcmd_appworkshop_acf_path,
            )
        if action == "reset_steamcmd_acf_data":
            if os.path.exists(self.steamcmd_wrapper.steamcmd_appworkshop_acf_path):
                logger.debug(
                    f"删除SteamCMD ACF数据: {self.steamcmd_wrapper.steamcmd_appworkshop_acf_path}"
                )
                os.remove(self.steamcmd_wrapper.steamcmd_appworkshop_acf_path)
            else:
                logger.debug("SteamCMD ACF数据不存在。跳过行动。")
        if action == "update_workshop_mods":
            self._do_check_for_workshop_updates()
        if action == "import_list_file_xml":
            self._do_import_list_file_xml()
        if action == "import_list_rentry":
            self._do_import_list_rentry()
        if action == "export_list_file_xml":
            self._do_export_list_file_xml()
        if action == "export_list_clipboard":
            self._do_export_list_clipboard()
        if action == "upload_list_rentry":
            self._do_upload_list_rentry()
        if action == "save":
            self._do_save()
        # settings panel actions
        if action == "configure_github_identity":
            self._do_configure_github_identity()
        if action == "configure_steam_database_path":
            self._do_configure_steam_db_file_path()
        if action == "configure_steam_database_repo":
            self._do_configure_steam_database_repo()
        if action == "download_steam_database":
            if GIT_EXISTS:
                self._do_clone_repo_to_path(
                    base_path=str(AppInfo().databases_folder),
                    repo_url=self.settings_controller.settings.external_steam_metadata_repo,
                )
            else:
                self._do_notify_no_git()
        if action == "upload_steam_database":
            if GIT_EXISTS:
                self._do_upload_db_to_repo(
                    repo_url=self.settings_controller.settings.external_steam_metadata_repo,
                    file_name="steamDB.json",
                )
            else:
                self._do_notify_no_git()
        if action == "configure_community_rules_db_path":
            self._do_configure_community_rules_db_file_path()
        if action == "configure_community_rules_db_repo":
            self._do_configure_community_rules_db_repo()
        if action == "download_community_rules_database":
            if GIT_EXISTS:
                self._do_clone_repo_to_path(
                    base_path=str(AppInfo().databases_folder),
                    repo_url=self.settings_controller.settings.external_community_rules_repo,
                )
            else:
                self._do_notify_no_git()
        if action == "open_community_rules_with_rule_editor":
            self._do_open_rule_editor(compact=False, initial_mode="community_rules")
        if action == "upload_community_rules_database":
            if GIT_EXISTS:
                self._do_upload_db_to_repo(
                    repo_url=self.settings_controller.settings.external_community_rules_repo,
                    file_name="communityRules.json",
                )
            else:
                self._do_notify_no_git()
        if action == "build_steam_database_thread":
            self._do_build_database_thread()
        if "download_entire_workshop" in action:
            self._do_download_entire_workshop(action)
        if action == "merge_databases":
            self._do_merge_databases()
        if action == "set_database_expiry":
            self._do_set_database_expiry()
        if action == "edit_steam_webapi_key":
            self._do_edit_steam_webapi_key()
        if action == "comparison_report":
            self._do_generate_metadata_comparison_report()

    # GAME CONFIGURATION PANEL

    def _do_check_for_update(self) -> None:
        logger.debug("跳过更新检查...")
        return
        # NOT NUITKA
        if "__compiled__" not in globals():
            logger.debug(
                "You are running from Python interpreter. Skipping update check..."
            )
            dialogue.show_warning(
                title="Update skipped",
                text="You are running from Python interpreter.",
                information="Skipping update check...",
            )
            return
        # NUITKA
        logger.debug("Checking for RimSort update...")
        current_version = self.metadata_manager.game_version
        try:
            json_response = self.__do_get_github_release_info()
        except Exception as e:
            logger.warning(
                f"Unable to retrieve latest release information due to exception: {e.__class__}"
            )
            return
        tag_name = json_response["tag_name"]
        tag_name_updated = tag_name.replace("alpha", "Alpha")
        install_path = os.getcwd()
        logger.debug(f"Current RimSort release found: {tag_name}")
        logger.debug(f"Current RimSort version found: {current_version}")
        if current_version != tag_name:
            answer = dialogue.show_dialogue_conditional(
                title="RimSort update found",
                text=f"An update to RimSort has been released: {tag_name}",
                information=f"You are running RimSort {current_version}\nDo you want to update now?",
            )
            if answer == "&Yes":
                # Setup environment
                ARCH = platform.architecture()[0]
                CWD = os.getcwd()
                PROCESSOR = platform.processor()
                if PROCESSOR == "":
                    PROCESSOR = platform.machine()
                SYSTEM = platform.system()

                current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

                if SYSTEM == "Darwin":
                    current_dir = os.path.split(
                        os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))[0]
                    )[0]
                    executable_name = "RimSort.app"
                    if PROCESSOR == "i386" or PROCESSOR == "arm":
                        logger.warning(
                            f"Darwin/MacOS system detected with a {ARCH} {PROCESSOR} CPU..."
                        )
                        target_archive = (
                            f"RimSort-{tag_name_updated}_{SYSTEM}_{PROCESSOR}.zip"
                        )
                    else:
                        logger.warning(
                            f"Unsupported processor {SYSTEM} {ARCH} {PROCESSOR}"
                        )
                        return
                elif SYSTEM == "Linux":
                    executable_name = "RimSort.bin"
                    logger.warning(
                        f"Linux system detected with a {ARCH} {PROCESSOR} CPU..."
                    )
                    target_archive = (
                        f"RimSort-{tag_name_updated}_{SYSTEM}_{PROCESSOR}.zip"
                    )
                elif SYSTEM == "Windows":
                    executable_name = "RimSort.exe"
                    logger.warning(
                        f"Windows system detected with a {ARCH} {PROCESSOR} CPU..."
                    )
                    target_archive = f"RimSort-{tag_name_updated}_{SYSTEM}.zip"
                else:
                    logger.warning(f"Unsupported system {SYSTEM} {ARCH} {PROCESSOR}")
                    return
                # Try to find a valid release from our generated archive name
                for asset in json_response["assets"]:
                    if asset["name"] == target_archive:
                        browser_download_url = asset["browser_download_url"]
                # If we don't have it from our query...
                if "browser_download_url" not in locals():
                    dialogue.show_warning(
                        title="Unable to complete update",
                        text=f"Failed to find valid RimSort release for {SYSTEM} {ARCH} {PROCESSOR}",
                    )
                    return
                target_archive_extracted = target_archive.replace(".zip", "")
                try:
                    logger.debug(
                        f"Downloading & extracting RimSort release from: {browser_download_url}"
                    )
                    self.do_threaded_loading_animation(
                        gif_path=str(
                            AppInfo().theme_data_folder
                            / "default-icons"
                            / "refresh.gif"
                        ),
                        target=partial(
                            self.__do_download_extract_release_to_tempdir,
                            url=browser_download_url,
                        ),
                        text=f"RimSort update found. Downloading RimSort {tag_name_updated} release...",
                    )
                    temp_dir = "RimSort" if not SYSTEM == "Darwin" else "RimSort.app"
                    answer = dialogue.show_dialogue_conditional(
                        title="Update downloaded",
                        text="Do you want to proceed with the update?",
                        information=f"\nSuccessfully retrieved latest release. The update will be installed from: {os.path.join(gettempdir(), temp_dir)}",
                    )
                    if not answer == "&Yes":
                        return
                except Exception:
                    stacktrace = traceback.format_exc()
                    dialogue.show_warning(
                        title="Failed to download update",
                        text="Failed to download latest RimSort release!",
                        information="Did the file/url change? "
                        + "Does your environment have access to the Internet?\n"
                        + f"URL: {browser_download_url}",
                        details=stacktrace,
                    )
                    return
                # Stop watchdog
                logger.info("Stopping watchdog Observer thread before update...")
                self.stop_watchdog_signal.emit()
                # https://stackoverflow.com/a/21805723
                if SYSTEM == "Darwin":  # MacOS
                    popen_args = [
                        "/bin/bash",
                        str((Path(current_dir) / "Contents" / "MacOS" / "update.sh")),
                    ]
                    p = subprocess.Popen(popen_args)
                else:
                    try:
                        subprocess.CREATE_NEW_PROCESS_GROUP
                    except AttributeError:  # not Windows, so assume POSIX; if not, we'll get a usable exception
                        popen_args = [
                            "/bin/bash",
                            str((AppInfo().application_folder / "update.sh")),
                        ]
                        p = subprocess.Popen(
                            popen_args,
                            start_new_session=True,
                        )
                    else:  # Windows
                        popen_args = [
                            "start",
                            "/wait",
                            "cmd",
                            "/c",
                            str(
                                (
                                    AppInfo.application_folder,
                                    "update.bat",
                                )
                            ),
                        ]
                        p = subprocess.Popen(
                            popen_args,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                            shell=True,
                        )
                logger.debug(f"External updater script launched with PID: {p.pid}")
                logger.debug(f"Arguments used: {popen_args}")
                sys.exit()
        else:
            logger.debug("Up to date!")
            dialogue.show_information(
                title="RimSort is up to date!",
                text=f"You are already running the latest release: {tag_name}",
            )

    def _do_validate_steam_client(self) -> None:
        platform_specific_open("steam://validate/294100")

    def __do_download_extract_release_to_tempdir(self, url: str) -> None:
        with ZipFile(BytesIO(requests_get(url).content)) as zipobj:
            zipobj.extractall(gettempdir())

    def __do_get_github_release_info(self) -> dict[str, Any]:
        # Parse latest release
        raw = requests_get(
            "https://api.github.com/repos/RimSort/RimSort/releases/latest"
        )
        return raw.json()

    # INFO PANEL ANIMATIONS

    def do_threaded_loading_animation(
        self, gif_path: str, target: Callable[..., Any], text: str | None = None
    ) -> Any:
        loading_animation_text_label = None
        # Hide the info panel widgets
        self.mod_info_panel.info_panel_frame.hide()
        # Disable widgets while loading
        self.disable_enable_widgets_signal.emit(False)
        # Encapsulate mod parsing inside a nice lil animation
        loading_animation = LoadingAnimation(
            gif_path=gif_path,
            target=target,
        )
        self.mod_info_panel.panel.addWidget(loading_animation)
        # If any text message specified, pass it to the info panel as well
        if text:
            loading_animation_text_label = QLabel(text)
            loading_animation_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading_animation_text_label.setObjectName("loadingAnimationString")
            self.mod_info_panel.panel.addWidget(loading_animation_text_label)
        loop = QEventLoop()
        loading_animation.finished.connect(loop.quit)
        loop.exec_()
        data = loading_animation.data
        # Remove text label if it was passed
        if text:
            self.mod_info_panel.panel.removeWidget(loading_animation_text_label)
            loading_animation_text_label.close()
        # Enable widgets again after loading
        self.disable_enable_widgets_signal.emit(True)
        # Show the info panel widgets
        self.mod_info_panel.info_panel_frame.show()
        logger.debug(f"Returning {type(data)}")
        return data

    # ACTIONS PANEL

    def _do_refresh(self, is_initial: bool = False) -> None:
        """
        Refresh expensive calculations & repopulate lists with that refreshed data
        """
        EventBus().refresh_started.emit()
        EventBus().do_save_button_animation_stop.emit()
        # If we are refreshing cache from user action
        if not is_initial:
            self.mods_panel.list_updated = False
            # Reset the data source filters to default and clear searches
            self.mods_panel.active_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_clear_search(list_type="Active")
            self.mods_panel.inactive_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_clear_search(list_type="Inactive")
            self.mods_panel.active_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_clear_search(list_type="Active")
            self.mods_panel.inactive_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_clear_search(list_type="Inactive")
        # Check if paths are set
        if self.check_if_essential_paths_are_set(prompt=is_initial):
            # Run expensive calculations to set cache data
            self.do_threaded_loading_animation(
                gif_path=str(
                    AppInfo().theme_data_folder / "default-icons" / "rimsort.gif"
                ),
                target=partial(
                    self.metadata_manager.refresh_cache, is_initial=is_initial
                ),
                text="扫描模组资源并填充元数据...",
            )

            # Insert mod data into list
            self.__repopulate_lists(is_initial=is_initial)

            # If we have duplicate mods, prompt user
            if (
                self.settings_controller.settings.duplicate_mods_warning
                and self.duplicate_mods
                and len(self.duplicate_mods) > 0
            ):
                self.__duplicate_mods_prompt()
            elif not self.settings_controller.settings.duplicate_mods_warning:
                logger.debug(
                    "用户首选项未配置为显示重复的模组。跳过..."
                )

            # If we have missing mods, prompt user
            if self.missing_mods and len(self.missing_mods) > 0:
                self.__missing_mods_prompt()

            # Check Workshop mods for updates if configured
            if (
                self.settings_controller.settings.steam_mods_update_check
            ):  # Check SteamCMD/Steam mods for updates if configured
                logger.info(
                    "用户首选项配置为检查创意工节模组是否有更新。检查创意工坊模组更新..."
                )
                self._do_check_for_workshop_updates()
            else:
                logger.info(
                    "用户首选项未配置为检查 Steam 模组是否有更新。跳过..."
                )
        else:
            self.__insert_data_into_lists([], [])
            logger.warning(
                "基本路径尚未确定。请刷新和重置模组列表"
            )
            # Wait for settings dialog to be closed before continuing.
            # This is to ensure steamcmd check and other ops are done after the user has a chance to set paths
            if not self.settings_controller.settings_dialog.isHidden():
                loop = QEventLoop()
                self.settings_controller.settings_dialog.finished.connect(loop.quit)
                loop.exec_()
                logger.debug("“设置”对话框已关闭。继续刷新...")

        EventBus().refresh_finished.emit()

    def _do_clear(self) -> None:
        """
        Method to clear all the non-base, non-DLC mods from the active
        list widget and put them all into the inactive list widget.
        """
        self.mods_panel.active_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_clear_search(list_type="Active")
        self.mods_panel.inactive_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_clear_search(list_type="Inactive")
        # Metadata to insert
        active_mods_uuids = []
        inactive_mods_uuids = []
        logger.info("Clearing mods from active mod list")
        # Define the order of the DLC package IDs
        package_id_order = [
            app_constants.RIMWORLD_DLC_METADATA["294100"]["packageid"],
            app_constants.RIMWORLD_DLC_METADATA["1149640"]["packageid"],
            app_constants.RIMWORLD_DLC_METADATA["1392840"]["packageid"],
            app_constants.RIMWORLD_DLC_METADATA["1826140"]["packageid"],
            app_constants.RIMWORLD_DLC_METADATA["2380740"]["packageid"],
        ]
        # Create a set of all package IDs from mod_data
        package_ids_set = set(
            mod_data["packageid"]
            for mod_data in self.metadata_manager.internal_local_metadata.values()
        )
        # Iterate over the DLC package IDs in the correct order
        for package_id in package_id_order:
            if package_id in package_ids_set:
                # Append the UUIDs to active_mods_uuids if the package ID exists in mod_data
                active_mods_uuids.extend(
                    uuid
                    for uuid, mod_data in self.metadata_manager.internal_local_metadata.items()
                    if mod_data["data_source"] == "expansion"
                    and mod_data["packageid"] == package_id
                )
        # Append the remaining UUIDs to inactive_mods_uuids
        inactive_mods_uuids.extend(
            uuid
            for uuid in self.metadata_manager.internal_local_metadata.keys()
            if uuid not in active_mods_uuids
        )
        # Disable widgets while inserting
        self.disable_enable_widgets_signal.emit(False)
        # Insert data into lists
        self.__insert_data_into_lists(active_mods_uuids, inactive_mods_uuids)
        # Re-enable widgets after inserting
        self.disable_enable_widgets_signal.emit(True)

    def _do_sort(self) -> None:
        """
        Trigger sorting of all active mods using user-configured algorithm
        & all available & configured metadata
        """
        # Get the live list of active and inactive mods. This is because the user
        # will likely sort before saving.
        logger.debug("开始排序模组")
        self.mods_panel.signal_clear_search(list_type="Active")
        self.mods_panel.active_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.on_active_mods_search_data_source_filter()
        self.mods_panel.signal_clear_search(list_type="Inactive")
        self.mods_panel.inactive_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.on_inactive_mods_search_data_source_filter()
        active_mod_ids = list()
        for uuid in self.mods_panel.active_mods_list.uuids:
            active_mod_ids.append(
                self.metadata_manager.internal_local_metadata[uuid]["packageid"]
            )

        # Get the current order of active mods list
        current_order = self.mods_panel.active_mods_list.uuids.copy()

        # Get all active mods and their dependencies (if also active mod)
        dependencies_graph = deps_sort.gen_deps_graph(
            self.mods_panel.active_mods_list.uuids, active_mod_ids
        )

        # Get all active mods and their reverse dependencies
        reverse_dependencies_graph = deps_sort.gen_rev_deps_graph(
            self.mods_panel.active_mods_list.uuids, active_mod_ids
        )

        # Get dependencies graph for tier one mods (load at top mods)
        tier_one_dependency_graph, tier_one_mods = deps_sort.gen_tier_one_deps_graph(
            dependencies_graph
        )

        # Get dependencies graph for tier three mods (load at bottom mods)
        tier_three_dependency_graph, tier_three_mods = (
            deps_sort.gen_tier_three_deps_graph(
                dependencies_graph,
                reverse_dependencies_graph,
                self.mods_panel.active_mods_list.uuids,
            )
        )

        # Get dependencies graph for tier two mods (load in middle)
        tier_two_dependency_graph = deps_sort.gen_tier_two_deps_graph(
            self.mods_panel.active_mods_list.uuids,
            active_mod_ids,
            tier_one_mods,
            tier_three_mods,
        )

        # Depending on the selected algorithm, sort all tiers with Alphabetical
        # mimic algorithm or toposort
        sorting_algorithm = self.settings_controller.settings.sorting_algorithm

        if sorting_algorithm == "Alphabetical":
            logger.info("选择按字母顺序排序算法")
            reordered_tier_one_sorted = alpha_sort.do_alphabetical_sort(
                tier_one_dependency_graph, self.mods_panel.active_mods_list.uuids
            )
            reordered_tier_three_sorted = alpha_sort.do_alphabetical_sort(
                tier_three_dependency_graph,
                self.mods_panel.active_mods_list.uuids,
            )
            reordered_tier_two_sorted = alpha_sort.do_alphabetical_sort(
                tier_two_dependency_graph, self.mods_panel.active_mods_list.uuids
            )
        else:
            logger.info("选择拓扑排序算法")
            try:
                # Sort tier one mods
                reordered_tier_one_sorted = topo_sort.do_topo_sort(
                    tier_one_dependency_graph, self.mods_panel.active_mods_list.uuids
                )
                # Sort tier three mods
                reordered_tier_three_sorted = topo_sort.do_topo_sort(
                    tier_three_dependency_graph,
                    self.mods_panel.active_mods_list.uuids,
                )
                # Sort tier two mods
                reordered_tier_two_sorted = topo_sort.do_topo_sort(
                    tier_two_dependency_graph, self.mods_panel.active_mods_list.uuids
                )
            except CircularDependencyError:
                # Propagated from topo_sort.py
                # Indicates we should forego sorting altogther
                logger.info("检测到循环依赖关系，放弃排序")
                return

        logger.info(f"排序的一级模组: {len(reordered_tier_one_sorted)}")
        logger.info(f"排序的二级模组: {len(reordered_tier_two_sorted)}")
        logger.info(f"排序的三级模组: {len(reordered_tier_three_sorted)}")

        # Add Tier 1, 2, 3 in order
        combined_mods = {}
        for uuid in (
            reordered_tier_one_sorted
            + reordered_tier_two_sorted
            + reordered_tier_three_sorted
        ):
            combined_mods[uuid] = self.metadata_manager.internal_local_metadata[uuid]

        new_order = list(combined_mods.keys())

        # Check if the order has changed
        if new_order == current_order:
            logger.info(
                "列表中模组的顺序没有改变。跳过插入。"
            )
        else:
            logger.info(
                "完成了所有等级的模组组合。插入模组列表！"
            )
            # Disable widgets while inserting
            self.disable_enable_widgets_signal.emit(False)
            # Insert data into lists
            self.__insert_data_into_lists(
                combined_mods,
                {
                    uuid: self.metadata_manager.internal_local_metadata[uuid]
                    for uuid in self.metadata_manager.internal_local_metadata
                    if uuid
                    not in set(
                        reordered_tier_one_sorted
                        + reordered_tier_two_sorted
                        + reordered_tier_three_sorted
                    )
                },
            )
            # Enable widgets again after inserting
            self.disable_enable_widgets_signal.emit(True)

    def _do_import_list_file_xml(self) -> None:
        """
        Open a user-selected XML file. Calculate
        and display active and inactive lists based on this file.
        """
        logger.info("打开文件对话框以选择输入文件")
        file_path = dialogue.show_dialogue_file(
            mode="open",
            caption="Open RimWorld mod list",
            _dir=str(AppInfo().app_storage_folder),
            _filter="RimWorld mod list (*.rml *.rws *.xml)",
        )
        logger.info(f"所选路径: {file_path}")
        if file_path:
            self.mods_panel.signal_clear_search(list_type="Active")
            self.mods_panel.active_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_search_source_filter(list_type="Active")
            self.mods_panel.signal_clear_search(list_type="Inactive")
            self.mods_panel.inactive_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.signal_search_source_filter(list_type="Inactive")
            logger.info(f"尝试从XML导入模组列表: {file_path}")
            (
                active_mods_uuids,
                inactive_mods_uuids,
                self.duplicate_mods,
                self.missing_mods,
            ) = metadata.get_mods_from_list(mod_list=file_path)
            logger.info("根据导入的XML获得新的模组")
            self.__insert_data_into_lists(active_mods_uuids, inactive_mods_uuids)
            # If we have duplicate mods, prompt user
            if (
                self.settings_controller.settings.duplicate_mods_warning
                and self.duplicate_mods
                and len(self.duplicate_mods) > 0
            ):
                self.__duplicate_mods_prompt()
            elif not self.settings_controller.settings.duplicate_mods_warning:
                logger.debug(
                    "用户首选项未配置为显示重复的模组。跳过..."
                )
            # If we have missing mods, prompt user
            if self.missing_mods and len(self.missing_mods) >= 1:
                self.__missing_mods_prompt()
        else:
            logger.debug("USER ACTION: 按取消，通过")

    def _do_export_list_file_xml(self) -> None:
        """
        Export the current list of active mods to a user-designated
        file. The current list does not need to have been saved.
        """
        logger.info("打开文件对话框以指定输出文件")
        file_path = dialogue.show_dialogue_file(
            mode="save",
            caption="Save mod list",
            _dir=str(AppInfo().app_storage_folder),
            _filter="XML (*.xml)",
        )
        logger.info(f"所选路径: {file_path}")
        if file_path:
            logger.info("将当前活动模组导出为ModsConfig.xml格式")
            active_mods = []
            for uuid in self.mods_panel.active_mods_list.uuids:
                package_id = self.metadata_manager.internal_local_metadata[uuid][
                    "packageid"
                ]
                if package_id in active_mods:  # This should NOT be happening
                    logger.critical(
                        f"尝试将多个相同的模组ID导出到同一模组列表。跳过重复的 {package_id}"
                    )
                    continue
                else:  # Otherwise, proceed with adding the mod package_id
                    if (
                        package_id in self.duplicate_mods.keys()
                    ):  # Check if mod has duplicates
                        if (
                            self.metadata_manager.internal_local_metadata[uuid][
                                "data_source"
                            ]
                            == "workshop"
                        ):
                            active_mods.append(package_id + "_steam")
                            continue  # Append `_steam` suffix if Steam mod, continue to next mod
                    active_mods.append(package_id)
            logger.info(f"已搜集{len(active_mods)}个启用模组以供导出")
            mods_config_data = generate_rimworld_mods_list(
                self.metadata_manager.game_version, active_mods
            )
            try:
                logger.info(
                    f"将生成ModsConfig.xml样式列表保存到所选路径: {file_path}"
                )
                if not file_path.endswith(".xml"):
                    json_to_xml_write(mods_config_data, file_path + ".xml")
                else:
                    json_to_xml_write(mods_config_data, file_path)
            except Exception:
                dialogue.show_fatal_error(
                    title="无法导出文件",
                    text="无法将启用模组排序导出到文件:",
                    information=f"{file_path}",
                    details=traceback.format_exc(),
                )
        else:
            logger.debug("USER ACTION: 按取消，通过")

    def _do_import_list_rentry(self) -> None:
        # Create an instance of RentryImport
        rentry_import = RentryImport()
        # Open the RentryImport dialogue
        rentry_import.import_rentry_link()
        # Exit if user cancels or no package IDs
        if not rentry_import.package_ids:
            logger.debug("USER ACTION: 按取消或无模组ID，通过")
            return
        # Clear Active and Inactive search and data source filter
        self.mods_panel.signal_clear_search(list_type="Active")
        self.mods_panel.active_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_search_source_filter(list_type="Active")
        self.mods_panel.signal_clear_search(list_type="Inactive")
        self.mods_panel.inactive_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_search_source_filter(list_type="Inactive")

        # Log the attempt to import mods list from Rentry.co
        logger.info(
            f"尝试从 Rentry.co 列表中导入{len(rentry_import.package_ids)}个模组"
        )

        # Generate uuids based on existing mods, calculate duplicates, and missing mods
        (
            active_mods_uuids,
            inactive_mods_uuids,
            self.duplicate_mods,
            self.missing_mods,
        ) = metadata.get_mods_from_list(mod_list=rentry_import.package_ids)

        # Insert data into lists
        self.__insert_data_into_lists(active_mods_uuids, inactive_mods_uuids)
        logger.info("根据导入的 Rentry.co 获得新模组")

        # If we have duplicate mods and user preference is configured to display them, prompt user
        if (
            self.settings_controller.settings.duplicate_mods_warning
            and self.duplicate_mods
            and len(self.duplicate_mods) > 0
        ):
            self.__duplicate_mods_prompt()
        elif not self.settings_controller.settings.duplicate_mods_warning:
            logger.debug(
                "用户首选项未配置为显示重复的模组。跳过..."
            )

        # If we have missing mods, prompt the user
        if self.missing_mods and len(self.missing_mods) >= 1:
            self.__missing_mods_prompt()

    def _do_import_list_workshop_collection(self) -> None:
        # Create an instance of collection_import
        collection_import = CollectionImport(metadata_manager=self.metadata_manager)

        # Trigger the import dialogue and get the result
        collection_import.import_collection_link()

        # Exit if user cancels or no package IDs
        if not collection_import.package_ids:
            logger.debug("USER ACTION: 按取消或无模组ID，通过")
            return
        # Clear Active and Inactive search and data source filter
        self.mods_panel.signal_clear_search(list_type="Active")
        self.mods_panel.active_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_search_source_filter(list_type="Active")
        self.mods_panel.signal_clear_search(list_type="Inactive")
        self.mods_panel.inactive_mods_filter_data_source_index = len(
            self.mods_panel.data_source_filter_icons
        )
        self.mods_panel.signal_search_source_filter(list_type="Inactive")

        # Log the attempt to import mods list from Workshop collection
        logger.info(
            f"尝试从创意工坊集合列表中导入{len(collection_import.package_ids)}个模组"
        )

        # Generate uuids based on existing mods, calculate duplicates, and missing mods
        (
            active_mods_uuids,
            inactive_mods_uuids,
            self.duplicate_mods,
            self.missing_mods,
        ) = metadata.get_mods_from_list(mod_list=collection_import.package_ids)

        # Insert data into lists
        self.__insert_data_into_lists(active_mods_uuids, inactive_mods_uuids)
        logger.info("根据导入的创意工坊集合获得新模组")

        # If we have duplicate mods and user preference is configured to display them, prompt user
        if (
            self.settings_controller.settings.duplicate_mods_warning
            and self.duplicate_mods
            and len(self.duplicate_mods) > 0
        ):
            self.__duplicate_mods_prompt()
        elif not self.settings_controller.settings.duplicate_mods_warning:
            logger.debug(
                "用户首选项未配置为显示重复的模组。跳过..."
            )

        # If we have missing mods, prompt the user
        if self.missing_mods and len(self.missing_mods) >= 1:
            self.__missing_mods_prompt()

    def _do_export_list_clipboard(self) -> None:
        """
        Export the current list of active mods to the clipboard in a
        readable format. The current list does not need to have been saved.
        """
        logger.info("生成报告以将模组列表导出到剪贴板")
        # Build our lists
        active_mods = []
        active_mods_packageid_to_uuid = {}
        for uuid in self.mods_panel.active_mods_list.uuids:
            package_id = self.metadata_manager.internal_local_metadata[uuid][
                "packageid"
            ]
            if package_id in active_mods:  # This should NOT be happening
                logger.critical(
                    "尝试将多个相同的模组ID导出到同一模组列表。"
                    + f"跳过重复项{package_id}"
                )
                continue
            else:  # Otherwise, proceed with adding the mod package_id
                active_mods.append(package_id)
                active_mods_packageid_to_uuid[package_id] = uuid
        logger.info(f"已搜集{len(active_mods)}个启用模组以供导出")
        # Build our report
        active_mods_clipboard_report = (
            f"由 RimSort 创建，版本{self.version_string}"
            + f"\n创建此列表的 RimWorld 游戏版本: {self.metadata_manager.game_version}"
            + f"\n启用模组的总数: {len(active_mods)}\n"
        )
        for package_id in active_mods:
            uuid = active_mods_packageid_to_uuid[package_id]
            if self.metadata_manager.internal_local_metadata[uuid].get("name"):
                name = self.metadata_manager.internal_local_metadata[uuid]["name"]
            else:
                name = "未指定名称"
            if self.metadata_manager.internal_local_metadata[uuid].get("url"):
                url = self.metadata_manager.internal_local_metadata[uuid]["url"]
            elif self.metadata_manager.internal_local_metadata[uuid].get("steam_url"):
                url = self.metadata_manager.internal_local_metadata[uuid]["steam_url"]
            else:
                url = "未指定网址"
            active_mods_clipboard_report = (
                active_mods_clipboard_report
                + f"\n{name} "
                + f"[{package_id}]"
                + f"[{url}]"
            )
        # Copy report to clipboard
        dialogue.show_information(
            title="导出启用模组列表",
            text="将启用模组列表报告复制到剪贴板...",
            information='点击 “显示详情” 查看完整报告！',
            details=f"{active_mods_clipboard_report}",
        )
        copy_to_clipboard_safely(active_mods_clipboard_report)

    def _do_upload_list_rentry(self) -> None:
        """
        Export the current list of active mods to the clipboard in a
        readable format. The current list does not need to have been saved.
        """
        # Define our lists
        active_mods = []
        active_mods_packageid_to_uuid = {}
        active_steam_mods_packageid_to_pfid = {}
        active_steam_mods_pfid_to_preview_url = {}
        pfids = []
        # Build our lists
        for uuid in self.mods_panel.active_mods_list.uuids:
            package_id = MetadataManager.instance().internal_local_metadata[uuid][
                "packageid"
            ]
            if package_id in active_mods:  # This should NOT be happening
                logger.critical(
                    "尝试将多个相同的模组ID导出到同一模组列表。"
                    + f"跳过重复项{package_id}"
                )
                continue
            else:  # Otherwise, proceed with adding the mod package_id
                active_mods.append(package_id)
                active_mods_packageid_to_uuid[package_id] = uuid
                if (
                    self.metadata_manager.internal_local_metadata[uuid].get("steamcmd")
                    or self.metadata_manager.internal_local_metadata[uuid][
                        "data_source"
                    ]
                    == "workshop"
                ) and self.metadata_manager.internal_local_metadata[uuid].get(
                    "publishedfileid"
                ):
                    publishedfileid = self.metadata_manager.internal_local_metadata[
                        uuid
                    ]["publishedfileid"]
                    active_steam_mods_packageid_to_pfid[package_id] = publishedfileid
                    pfids.append(publishedfileid)
        logger.info(f"已搜集{len(active_mods)}个启用模组以供导出")
        if len(pfids) > 0:  # No empty queries...
            # Compile list of Steam Workshop publishing preview images that correspond
            # to a Steam mod in the active mod list
            webapi_response = ISteamRemoteStorage_GetPublishedFileDetails(pfids)
            for metadata in webapi_response:
                pfid = metadata["publishedfileid"]
                if metadata["result"] != 1:
                    logger.warning("导出 Rentry.co :无法获取模组的数据！")
                    logger.warning(
                        f"从 WebAPI 返回的模组{pfid}的结果无效"
                    )
                else:
                    # Retrieve the preview image URL from the response
                    active_steam_mods_pfid_to_preview_url[pfid] = metadata[
                        "preview_url"
                    ]
        # Build our report
        active_mods_rentry_report = (
            "# RimWorld 模组列表      ![](https://github.com/RimSort/RimSort/blob/main/docs/rentry_preview.png?raw=true)"
            + f"\n由 RimSort 创建，版本{self.version_string}"
            + f"\n创建此列表的 RimWorld 游戏版本: `{self.metadata_manager.game_version}`"
            + "\n!!! 信息：本地模组以黄色标签标记，括号内显示其模组ID"
            + f"\n\n\n\n!!! 注意模组列表的的启用数量: `{len(active_mods)}`\n"
        )
        # Add a line for each mod
        for package_id in active_mods:
            count = active_mods.index(package_id) + 1
            uuid = active_mods_packageid_to_uuid[package_id]
            if self.metadata_manager.internal_local_metadata[uuid].get("name"):
                name = self.metadata_manager.internal_local_metadata[uuid]["name"]
            else:
                name = "未指定名称"
            if (
                self.metadata_manager.internal_local_metadata[uuid].get("steamcmd")
                or self.metadata_manager.internal_local_metadata[uuid]["data_source"]
                == "workshop"
            ) and active_steam_mods_packageid_to_pfid.get(package_id):
                pfid = active_steam_mods_packageid_to_pfid[package_id]
                if active_steam_mods_pfid_to_preview_url.get(pfid):
                    preview_url = (
                        active_steam_mods_pfid_to_preview_url[pfid]
                        + "?imw=100&imh=100&impolicy=Letterbox"
                    )
                else:
                    preview_url = "https://github.com/RimSort/RimSort/blob/main/docs/rentry_steam_icon.png?raw=true"
                if self.metadata_manager.internal_local_metadata[uuid].get("steam_url"):
                    url = self.metadata_manager.internal_local_metadata[uuid][
                        "steam_url"
                    ]
                elif self.metadata_manager.internal_local_metadata[uuid].get("url"):
                    url = self.metadata_manager.internal_local_metadata[uuid]["url"]
                else:
                    url is None
                if url is None:
                    if package_id in active_steam_mods_packageid_to_pfid.keys():
                        active_mods_rentry_report = (
                            active_mods_rentry_report
                            + f"\n{str(count) + '.'} ![]({preview_url}) {name} packageid: {package_id}"
                        )
                else:
                    if package_id in active_steam_mods_packageid_to_pfid.keys():
                        active_mods_rentry_report = (
                            active_mods_rentry_report
                            + f"\n{str(count) + '.'} ![]({preview_url}) [{name}]({url} packageid: {package_id})"
                        )
            # if active_mods_json[uuid]["data_source"] == "expansion" or (
            #     active_mods_json[uuid]["data_source"] == "local"
            #     and not active_mods_json[uuid].get("steamcmd")
            # ):
            else:
                if self.metadata_manager.internal_local_metadata[uuid].get("url"):
                    url = self.metadata_manager.internal_local_metadata[uuid]["url"]
                elif self.metadata_manager.internal_local_metadata[uuid].get(
                    "steam_url"
                ):
                    url = self.metadata_manager.internal_local_metadata[uuid][
                        "steam_url"
                    ]
                else:
                    url = None
                if url is None:
                    active_mods_rentry_report = (
                        active_mods_rentry_report
                        + f"\n!!! 警告{str(count) + '.'} {name} "
                        + "{"
                        + f"模组ID: {package_id}"
                        + "} "
                    )
                else:
                    active_mods_rentry_report = (
                        active_mods_rentry_report
                        + f"\n!!! 警告 {str(count) + '.'} [{name}]({url}) "
                        + "{"
                        + f"模组ID: {package_id}"
                        + "} "
                    )
        # Upload the report to Rentry.co
        rentry_uploader = RentryUpload(active_mods_rentry_report)
        successful = rentry_uploader.upload_success
        host = urlparse(rentry_uploader.url).hostname if successful else None
        if rentry_uploader.url and host and host.endswith("rentry.co"):  # type: ignore
            copy_to_clipboard_safely(rentry_uploader.url)
            dialogue.show_information(
                title="上传启用的模组列表",
                text=f"已将活动模组列表报告上传至 Rentry.co ！ 网站已复制到剪贴板:\n\n{rentry_uploader.url}",
                information='点击 “显示详情” 查看完整报告！',
                details=f"{active_mods_rentry_report}",
            )
        else:
            dialogue.show_warning(
                title="上传失败",
                text="无法将导出的启用模组列表上传到 Rentry.co",
            )

    @Slot()
    def _on_do_upload_rimsort_log(self) -> None:
        self._upload_log(AppInfo().user_log_folder / "RimSort.log")

    @Slot()
    def _on_do_upload_rimsort_old_log(self) -> None:
        self._upload_log(AppInfo().user_log_folder / "RimSort.old.log")

    @Slot()
    def _on_do_upload_rimworld_log(self) -> None:
        player_log_path = (
            Path(
                self.settings_controller.settings.instances[
                    self.settings_controller.settings.current_instance
                ].config_folder
            ).parent
            / "Player.log"
        )

        self._upload_log(player_log_path)

    def _upload_log(self, path: Path) -> None:
        if not os.path.exists(path):
            dialogue.show_warning(
                title="找不到文件",
                text="您尝试上传的文件不存在。",
                information=f"文件: {path}",
            )
            return

        success, ret = self.do_threaded_loading_animation(
            gif_path=str(AppInfo().theme_data_folder / "default-icons" / "rimsort.gif"),
            target=partial(upload_data_to_0x0_st, str(path)),
            text=f"将 {path.name} 上传到 0x0.st...",
        )

        if success:
            copy_to_clipboard_safely(ret)
            dialogue.show_information(
                title="已上传文件",
                text=f"已将 {path.name} 上传到 http://0x0.st/",
                information=f"网址已复制到剪贴板:\n\n{ret}",
            )
            webbrowser.open(ret)
        else:
            dialogue.show_warning(
                title="上传文件失败。",
                text="无法将文件上传到 0x0.st",
                information=ret,
            )

    def _do_save(self) -> None:
        """
        Method save the current list of active mods to the selected ModsConfig.xml
        """
        logger.info("Saving current active mods to ModsConfig.xml")
        active_mods = []
        for uuid in self.mods_panel.active_mods_list.uuids:
            package_id = self.metadata_manager.internal_local_metadata[uuid][
                "packageid"
            ]
            if package_id in active_mods:  # This should NOT be happening
                logger.critical(
                    f"尝试将多个相同的模组ID 导出到同一模组列表。跳过重复项{package_id}"
                )
                continue
            else:  # Otherwise, proceed with adding the mod package_id
                if (
                    package_id in self.duplicate_mods.keys()
                ):  # Check if mod has duplicates
                    if (
                        self.metadata_manager.internal_local_metadata[uuid][
                            "data_source"
                        ]
                        == "workshop"
                    ):
                        active_mods.append(package_id + "_steam")
                        continue  # Append `_steam` suffix if Steam mod, continue to next mod
                active_mods.append(package_id)
        logger.info(f"已搜集{len(active_mods)}个启用模组以保存")

        mods_config_data = generate_rimworld_mods_list(
            self.metadata_manager.game_version, active_mods
        )
        mods_config_path = str(
            Path(
                self.settings_controller.settings.instances[
                    self.settings_controller.settings.current_instance
                ].config_folder
            )
            / "ModsConfig.xml"
        )
        try:
            json_to_xml_write(mods_config_data, mods_config_path)
        except Exception:
            logger.error("无法保存启用模组")
            dialogue.show_fatal_error(
                title="无法保存启用模组",
                text="无法将启用模组列表保存到文件:",
                information=f"{mods_config_path}",
                details=traceback.format_exc(),
            )
        EventBus().do_save_button_animation_stop.emit()
        logger.info("已完成启用模组的保存")

    def _do_restore(self) -> None:
        """
        Method to restore the mod lists to the last saved state.
        TODO: restoring after clearing will cause a few harmless lines of
        'Inactive mod count changed to: 0' to appear.
        """
        if (
            self.active_mods_uuids_restore_state
            and self.inactive_mods_uuids_restore_state
        ):
            self.mods_panel.signal_clear_search("Active")
            self.mods_panel.active_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.on_active_mods_search_data_source_filter()
            self.mods_panel.signal_clear_search("Inactive")
            self.mods_panel.inactive_mods_filter_data_source_index = len(
                self.mods_panel.data_source_filter_icons
            )
            self.mods_panel.on_inactive_mods_search_data_source_filter()
            logger.info(
                f"恢复缓存的启用模组列表[{len(self.active_mods_uuids_restore_state)}]和非启用模组列表[{len(self.inactive_mods_uuids_restore_state)}]"
            )
            # Disable widgets while inserting
            self.disable_enable_widgets_signal.emit(False)
            # Insert items into lists
            self.__insert_data_into_lists(
                self.active_mods_uuids_restore_state,
                self.inactive_mods_uuids_restore_state,
            )
            # Reenable widgets after inserting
            self.disable_enable_widgets_signal.emit(True)
        else:
            logger.warning(
                "由于客户端启动不正确，未设置恢复功能的缓存模组列表。请通过还原列表..."
            )

    def _do_edit_run_args(self) -> None:
        """
        Opens a QDialogInput that allows the user to edit the run args
        that are configured to be passed to the Rimworld executable
        """
        args, ok = dialogue.show_dialogue_input(
            title="编辑运行参数",
            label="输入要传递给 Rimworld 可执行文件的逗号分隔参数列表\n\n"
            + "示例: \n-popupwindow,-logfile,/path/to/file.log",
            text=",".join(self.settings_controller.settings.run_args),
        )
        if ok:
            self.settings_controller.settings.run_args = args.split(",")
            self.settings_controller.settings.save()

    # TODDS ACTIONS

    def _do_optimize_textures(self, todds_txt_path: str) -> None:
        # Setup environment
        todds_interface = ToddsInterface(
            preset=self.settings_controller.settings.todds_preset,
            dry_run=self.settings_controller.settings.todds_dry_run,
            overwrite=self.settings_controller.settings.todds_overwrite,
        )

        # UI
        self.todds_runner = RunnerPanel(
            todds_dry_run_support=self.settings_controller.settings.todds_dry_run
        )
        self.todds_runner.setWindowTitle("RimSort - todds 纹理/贴图编码器")
        self.todds_runner.show()

        todds_interface.execute_todds_cmd(todds_txt_path, self.todds_runner)

    def _do_delete_dds_textures(self, todds_txt_path: str) -> None:
        todds_interface = ToddsInterface(
            preset="clean",
            dry_run=self.settings_controller.settings.todds_dry_run,
        )

        # UI
        self.todds_runner = RunnerPanel(
            todds_dry_run_support=self.settings_controller.settings.todds_dry_run
        )
        self.todds_runner.setWindowTitle("RimSort - todds 纹理/贴图编码器")
        self.todds_runner.show()

        # Delete all .dds textures using todds
        todds_interface.execute_todds_cmd(todds_txt_path, self.todds_runner)

    # STEAM{CMD, WORKS} ACTIONS

    def _do_browse_workshop(self) -> None:
        self.steam_browser = SteamBrowser(
            "https://steamcommunity.com/app/294100/workshop/"
        )
        self.steam_browser.steamcmd_downloader_signal.connect(
            self._do_download_mods_with_steamcmd
        )
        self.steam_browser.steamworks_subscription_signal.connect(
            self._do_steamworks_api_call_animated
        )
        self.steam_browser.show()

    def _do_check_for_workshop_updates(self) -> None:
        # Query Workshop for update data
        updates_checked = self.do_threaded_loading_animation(
            gif_path=str(
                AppInfo().theme_data_folder / "default-icons" / "steam_api.gif"
            ),
            target=partial(
                metadata.query_workshop_update_data,
                mods=self.metadata_manager.internal_local_metadata,
            ),
            text="检查 Steam 创意工坊模组是否有更新...",
        )
        # If we failed to check for updates, skip the comparison(s) & UI prompt
        if updates_checked == "failed":
            dialogue.show_warning(
                title="无法检查更新",
                text="RimSort 无法查询 Steam WebAPI 以获取更新信息！\n",
                information="您是否已连接到 Internet？",
            )
            return
        self.workshop_mod_updater = ModUpdaterPrompt(
            internal_mod_metadata=self.metadata_manager.internal_local_metadata
        )
        self.workshop_mod_updater._populate_from_metadata()
        if self.workshop_mod_updater.updates_found:
            logger.debug("显示潜在的创意工坊模组更新")
            self.workshop_mod_updater.steamcmd_downloader_signal.connect(
                self._do_download_mods_with_steamcmd
            )
            self.workshop_mod_updater.steamworks_subscription_signal.connect(
                self._do_steamworks_api_call_animated
            )
            self.workshop_mod_updater.show()
        else:
            self.status_signal.emit("所有创意工坊模组都是最新的！")
            self.workshop_mod_updater = None

    def _do_setup_steamcmd(self) -> None:
        if (
            self.steamcmd_runner
            and self.steamcmd_runner.process
            and self.steamcmd_runner.process.state() == QProcess.ProcessState.Running
        ):
            dialogue.show_warning(
                title="RimSort - SteamCMD setup",
                text="无法创建 SteamCMD 运行程序！",
                information="有一个活动进程已经在运行！",
                details=f"PID {self.steamcmd_runner.process.processId()} : "
                + self.steamcmd_runner.process.program(),
            )
            return
        local_mods_path = self.settings_controller.settings.instances[
            self.settings_controller.settings.current_instance
        ].local_folder
        if local_mods_path and os.path.exists(local_mods_path):
            self.steamcmd_runner = RunnerPanel()
            self.steamcmd_runner.setWindowTitle("RimSort - SteamCMD setup")
            self.steamcmd_runner.show()
            self.steamcmd_runner.message("设置 steamcmd...")
            self.steamcmd_wrapper.setup_steamcmd(
                local_mods_path,
                False,
                self.steamcmd_runner,
            )
        else:
            dialogue.show_warning(
                title="RimSort - SteamCMD setup",
                text="无法启动 SteamCMD 安装。本地模组路径未设置！",
                information="在尝试安装之前，请在“设置”中配置本地模组路径。",
            )

    def _do_download_mods_with_steamcmd(self, publishedfileids: list[str]) -> None:
        logger.debug(
            f"正在尝试使用 SteamCMD 下载{len(publishedfileids)}个模组"
        )
        # Check for blacklisted mods
        if self.metadata_manager.external_steam_metadata is not None:
            publishedfileids = metadata.check_if_pfids_blacklisted(
                publishedfileids=publishedfileids,
                steamdb=self.metadata_manager.external_steam_metadata,
            )
        # No empty publishedfileids
        if not len(publishedfileids) > 0:
            dialogue.show_warning(
                title="RimSort",
                text="操作中未提供任何模组ID。",
                information="在尝试下载之前，请将模组添加到列表中。",
            )
            return
        # Check for existing steamcmd_runner process
        if (
            self.steamcmd_runner
            and self.steamcmd_runner.process
            and self.steamcmd_runner.process.state() == QProcess.ProcessState.Running
        ):
            dialogue.show_warning(
                title="RimSort",
                text="无法创建 SteamCMD 运行程序！",
                information="有一个活动进程已经在运行！",
                details=f"PID {self.steamcmd_runner.process.processId()} : "
                + self.steamcmd_runner.process.program(),
            )
            return
        # Check for SteamCMD executable
        if self.steamcmd_wrapper.steamcmd and os.path.exists(
            self.steamcmd_wrapper.steamcmd
        ):
            if self.steam_browser:
                self.steam_browser.close()
            self.steamcmd_runner = RunnerPanel(
                steamcmd_download_tracking=publishedfileids,
                steam_db=self.metadata_manager.external_steam_metadata,
            )
            self.steamcmd_runner.steamcmd_downloader_signal.connect(
                self._do_download_mods_with_steamcmd
            )
            self.steamcmd_runner.setWindowTitle("RimSort - SteamCMD 下载器")
            self.steamcmd_runner.show()
            self.steamcmd_runner.message(
                f"使用 SteamCMD 下载{len(publishedfileids)}个模组..."
            )
            self.steamcmd_wrapper.download_mods(
                publishedfileids=publishedfileids, runner=self.steamcmd_runner
            )
        else:
            dialogue.show_warning(
                title="找不到 SteamCMD",
                text="找不到 SteamCMD 可执行文件。",
                information='请设置现有的 SteamCMD 前缀，或使用“设置 SteamCMD”设置新前缀。',
            )

    def _do_steamworks_api_call(self, instruction: list[Any]) -> None:
        """
        Create & launch Steamworks API process to handle instructions received from connected signals

        FOR subscription_actions[]...
        :param instruction: a list where:
            instruction[0] is a string that corresponds with the following supported_actions[]
            instruction[1] is an int that corresponds with a subscribed Steam mod's PublishedFileId
                        OR is a list of int that corresponds with multiple subscribed Steam mod's PublishedFileId
        FOR "launch_game_process"...
        :param instruction: a list where:
            instruction[0] is a string that corresponds with the following supported_actions[]
            instruction[1] is a list containing [game_folder_path: str, args: list] respectively
        """
        logger.info(f"Received Steamworks API instruction: {instruction}")
        if not self.steamworks_in_use:
            subscription_actions = ["重新订阅", "订阅", "取消订阅"]
            supported_actions = ["launch_game_process"]
            supported_actions.extend(subscription_actions)
            if (
                instruction[0] in supported_actions
            ):  # Actions can be added as multiprocessing.Process; implemented in util.steam.steamworks.wrapper
                if instruction[0] == "launch_game_process":  # SW API init + game launch
                    self.steamworks_in_use = True
                    steamworks_api_process = SteamworksGameLaunch(
                        game_install_path=instruction[1][0],
                        args=instruction[1][1],
                        _libs=str((AppInfo().application_folder / "libs")),
                    )
                    # Start the Steamworks API Process
                    steamworks_api_process.start()
                    logger.info(
                        f"Steamworks API进程包装器已完成处理: {steamworks_api_process.pid}"
                    )
                    steamworks_api_process.join()
                    logger.info(
                        f"Steamworks API进程包装器已完成处理: {steamworks_api_process.pid}"
                    )
                    self.steamworks_in_use = False
                elif (
                    instruction[0] in subscription_actions
                    and not len(instruction[1]) < 1
                ):  # ISteamUGC/{SubscribeItem/UnsubscribeItem}
                    logger.info(
                        f"根据指令{instruction}创建Steamworks API进程"
                    )
                    self.steamworks_in_use = True
                    # Maximum processes
                    num_processes = cpu_count()
                    # Chunk the publishedfileids
                    pfids_chunked = list(
                        chunks(
                            _list=instruction[1],
                            limit=ceil(len(instruction[1]) / num_processes),
                        )
                    )
                    # Create a pool of worker processes
                    with Pool(processes=num_processes) as pool:
                        # Create instances of SteamworksSubscriptionHandler for each chunk
                        actions = [
                            SteamworksSubscriptionHandler(
                                action=instruction[0],
                                pfid_or_pfids=chunk,
                                interval=1,
                                _libs=str((AppInfo().application_folder / "libs")),
                            )
                            for chunk in pfids_chunked
                        ]
                        # Map the execution of the subscription actions to the pool of processes
                        pool.map(SteamworksSubscriptionHandler.run, actions)
                    self.steamworks_in_use = False
                else:
                    logger.warning(
                        "跳过Steamworks API调用 - 同时只允许进行一次Steamworks API初始化！！"
                    )
            else:
                logger.error(f"不支持的指令{instruction}")
                return
        else:
            logger.warning(
                "Steamworks API已经初始化！我们不需要多次交互。跳过指令..."
            )

    def _do_steamworks_api_call_animated(self, instruction: list) -> None:
        publishedfileids = instruction[1]
        logger.debug(f"Attempting to download {len(publishedfileids)} mods with Steam")
        # Check for blacklisted mods for subscription actions
        if instruction[0] == "subscribe":
            publishedfileids = metadata.check_if_pfids_blacklisted(
                publishedfileids=publishedfileids,
                steamdb=self.metadata_manager.external_steam_metadata,
            )
        # No empty publishedfileids
        if not len(publishedfileids) > 0:
            dialogue.show_warning(
                title="RimSort",
                text="操作中未提供任何模组ID。",
                information="请在尝试下载之前将模组添加到列表中。",
            )
            return
        # Close browser if open
        if self.steam_browser:
            self.steam_browser.close()
        # Process API call
        self.do_threaded_loading_animation(
            gif_path=str(AppInfo().theme_data_folder / "default-icons" / "steam.gif"),
            target=partial(self._do_steamworks_api_call, instruction=instruction),
            text="正在通过Steamworks API处理Steam订阅操作...",
        )
        # self._do_refresh()

    # GIT MOD ACTIONS

    def _do_add_git_mod(self) -> None:
        """
        Opens a QDialogInput that allows the user to edit the run args
        that are configured to be passed to the Rimworld executable
        """
        args, ok = dialogue.show_dialogue_input(
            title="输入Git仓库地址",
            label="请输入Git仓库的URL（http/https）以克隆到本地模组目录:",
        )
        if ok:
            self._do_clone_repo_to_path(
                base_path=self.settings_controller.settings.instances[
                    self.settings_controller.settings.current_instance
                ].local_folder,
                repo_url=args,
            )
        else:
            logger.debug("取消操作。")

    # EXTERNAL METADATA ACTIONS

    def _do_configure_github_identity(self) -> None:
        """
        Opens a QDialogInput that allows user to edit their Github token
        This token is used for DB repo related actions, as well as any
        "Github mod" related actions
        """
        args, ok = dialogue.show_dialogue_input(
            title="编辑用户名",
            label="输入您的 Github 用户名:",
            text=self.settings_controller.settings.github_username,
        )
        if ok:
            self.settings_controller.settings.github_username = args
            self.settings_controller.settings.save()
        else:
            logger.debug("USER ACTION: 取消输入！")
            return
        args, ok = dialogue.show_dialogue_input(
            title="编辑令牌",
            label="在此处输入您的 Github 个人访问令牌 (ghp_*):",
            text=self.settings_controller.settings.github_token,
        )
        if ok:
            self.settings_controller.settings.github_token = args
            self.settings_controller.settings.save()
        else:
            logger.debug("USER ACTION: 取消输入！")
            return

    def _do_cleanup_gitpython(self, repo: "Repo") -> None:
        # Cleanup GitPython
        collect()
        repo.git.clear_cache()
        del repo

    def _check_git_repos_for_update(self, repo_paths: list) -> None:
        if GIT_EXISTS:
            # Track summary of repo updates
            updates_summary = {}
            for repo_path in repo_paths:
                logger.info(f"检查 git 存储库的更新，网址为: {repo_path}")
                if os.path.exists(repo_path):
                    repo = Repo(repo_path)
                    try:
                        # Fetch the latest changes from the remote
                        origin = repo.remote(name="origin")
                        origin.fetch()

                        # Get the local and remote refs
                        local_ref = repo.head.reference
                        remote_ref = repo.refs[f"origin/{local_ref.name}"]

                        # Check if the local branch is behind the remote branch
                        if local_ref.commit != remote_ref.commit:
                            local_name = local_ref.name
                            remote_name = remote_ref.name
                            logger.info(
                                f"本地分支{local_name}与远程分支{remote_name}不同步。正在强制更新。"
                            )
                            # Create a summary of the changes that will be made for the repo to be updated
                            updates_summary[repo_path] = {
                                "HEAD~1": local_ref.commit.hexsha[:7],
                            }
                            # Force pull the latest changes
                            repo.git.reset("--hard", remote_ref.name)
                            repo.git.clean("-fdx")  # Remove untracked files
                            origin.pull(local_ref.name, rebase=True)
                            updates_summary[repo_path].update(
                                {
                                    "HEAD": remote_ref.commit.hexsha[:7],
                                    "message": remote_ref.commit.message,
                                }
                            )
                        else:
                            logger.info("本地仓库已经是最新版本。")
                    except GitCommandError:
                        stacktrace = traceback.format_exc()
                        dialogue.show_warning(
                            title="更新仓库失败！",
                            text=f"位于[{repo_path}]的仓库更新失败！\n"
                            + "您是否已连接到 Internet ？"
                            + "提供的仓库地址是否有效？",
                            information=(
                                f"指定的仓库: {repo.remotes.origin.url}"
                                if repo
                                and repo.remotes
                                and repo.remotes.origin
                                and repo.remotes.origin.url
                                else None
                            ),
                            details=stacktrace,
                        )
                    finally:
                        self._do_cleanup_gitpython(repo)
            # If any updates were found, notify the user
            if updates_summary:
                repos_updated = "\n".join(
                    list(os.path.split(k)[1] for k in updates_summary.keys())
                )
                updates_summarized = "\n".join(
                    [
                        f"[{os.path.split(k)[1]}]: {v['HEAD~1']  + '...' + v['HEAD']}\n"
                        + f"{v['message']}\n"
                        for k, v in updates_summary.items()
                    ]
                )
                dialogue.show_information(
                    title="Git仓库已更新",
                    text="以下仓库已从远程拉取了更新:",
                    information=repos_updated,
                    details=updates_summarized,
                )
            else:
                dialogue.show_information(
                    title="Git仓库未更新",
                    text="未发现更新。",
                )
        else:
            self._do_notify_no_git()

    def _do_clone_repo_to_path(self, base_path: str, repo_url: str) -> None:
        """
        Checks validity of configured git repo, as well as if it exists
        Handles possible existing repo, and prompts (re)download of repo
        Otherwise it just clones the repo and notifies user
        """
        # Check if git is installed
        if not GIT_EXISTS:
            self._do_notify_no_git()
            return

        if (
            repo_url
            and repo_url != ""
            and repo_url.startswith("http://")
            or repo_url.startswith("https://")
        ):
            # Calculate folder name from provided URL
            repo_folder_name = os.path.split(repo_url)[1]
            # Calculate path from generated folder name
            repo_path = str((Path(base_path) / repo_folder_name))
            if os.path.exists(repo_path):  # If local repo does exist
                # Prompt to user to handle
                answer = dialogue.show_dialogue_conditional(
                    title="已找到现有仓库",
                    text="已找到与此仓库相匹配的现有本地仓库:",
                    information=(
                        f"{repo_path}\n\n"
                        + "您希望如何处理？请选择选项:\n"
                        + "\n1) 克隆新仓库（删除现有仓库并替换）"
                        + "\n2) 原地更新现有仓库（强制覆盖本地更改）"
                    ),
                    button_text_override=[
                        "克隆新仓库",
                        "更新现有仓库",
                    ],
                )
                if answer == "取消":
                    logger.debug(
                        f"用户取消，跳过 {repo_folder_name} 仓库操作。"
                    )
                    return
                elif answer == "克隆新仓库":
                    logger.info(f"正在删除本地Git仓库于: {repo_path}")
                    delete_files_except_extension(directory=repo_path, extension=".dds")
                elif answer == "更新现有仓库":
                    self._do_force_update_existing_repo(
                        base_path=base_path, repo_url=repo_url
                    )
                    return
            # Clone the repo to storage path and notify user
            logger.info(f"正在将 {repo_url} 克隆到: {repo_path}")
            try:
                Repo.clone_from(repo_url, repo_path)
                dialogue.show_information(
                    title="仓库已获取",
                    text="已克隆配置好的仓库！",
                    information=f"{repo_url} ->\n" + f"{repo_path}",
                )
            except GitCommandError:
                try:
                    # Initialize a new Git repository
                    repo = Repo.init(repo_path)
                    # Add the origin remote
                    origin_remote = repo.create_remote("origin", repo_url)
                    # Fetch the remote branches
                    origin_remote.fetch()
                    # Determine the target branch name
                    target_branch = None
                    for ref in repo.remotes.origin.refs:
                        if ref.remote_head in ("main", "master"):
                            target_branch = ref.remote_head
                            break

                    if target_branch:
                        # Checkout the target branch
                        repo.git.checkout(
                            f"origin/{target_branch}", b=target_branch, force=True
                        )
                    else:
                        # Handle the case when the target branch is not found
                        logger.warning("目标分支未找到。")
                    dialogue.show_information(
                        title="仓库已获取",
                        text="配置好的仓库已使用现有文件重新初始化！（可能是遗留的.dds纹理/贴图文件）",
                        information=f"{repo_url} ->\n" + f"{repo_path}",
                    )
                except GitCommandError:
                    stacktrace = traceback.format_exc()
                    dialogue.show_warning(
                        title="克隆仓库失败！",
                        text="配置好的仓库克隆/初始化失败！ "
                        + "您是否已连接到 Internet？ "
                        + "您配置的仓库是否有效？",
                        information=f"已配置的仓库: {repo_url}",
                        details=stacktrace,
                    )
        else:
            # Warn the user so they know to configure in settings
            dialogue.show_warning(
                title="无效的仓库",
                text="已检测到无效的仓库！",
                information="请在设置中重新配置一个仓库！\n"
                + "一个有效的仓库URL必须是非空的，\n"
                + '并且必须以"http://"或"https://"为前缀。',
            )

    def _do_force_update_existing_repo(self, base_path: str, repo_url: str) -> None:
        """
        Checks validity of configured git repo, as well as if it exists
        Handles possible existing repo, and prompts (re)download of repo
        Otherwise it just clones the repo and notifies user
        """
        if (
            repo_url
            and repo_url != ""
            and repo_url.startswith("http://")
            or repo_url.startswith("https://")
        ):
            # Calculate folder name from provided URL
            repo_folder_name = os.path.split(repo_url)[1]
            # Calculate path from generated folder name
            repo_path = str((Path(base_path) / repo_folder_name))
            if os.path.exists(repo_path):  # If local repo does exists
                # Clone the repo to storage path and notify user
                logger.info(f"正在强制更新Git仓库，位于: {repo_path}")
                try:
                    # Open repo
                    repo = Repo(repo_path)
                    # Determine the target branch name
                    target_branch = None
                    for ref in repo.remotes.origin.refs:
                        if ref.remote_head in ("main", "master"):
                            target_branch = ref.remote_head
                            break
                    if target_branch:
                        # Checkout the target branch
                        repo.git.checkout(target_branch)
                    else:
                        # Handle the case when the target branch is not found
                        logger.warning("目标分支未找到。")
                    # Reset the repository to HEAD in case of changes not committed
                    repo.head.reset(index=True, working_tree=True)
                    # Perform a pull with rebase
                    origin = repo.remotes.origin
                    origin.pull(rebase=True)
                    # Notify user
                    dialogue.show_information(
                        title="仓库已强制更新",
                        text="配置好的仓库已更新！",
                        information=f"{repo_path} ->\n "
                        + f"{repo.head.commit.message.decode() if isinstance(repo.head.commit.message, bytes) else repo.head.commit.message}",
                    )
                    # Cleanup
                    self._do_cleanup_gitpython(repo=repo)
                except GitCommandError:
                    stacktrace = traceback.format_exc()
                    dialogue.show_warning(
                        title="更新仓库失败！",
                        text="配置好的仓库更新失败！ "
                        + "您是否已连接到 Internet？ "
                        + "您配置的仓库是否有效？",
                        information=f"已配置的仓库: {repo_url}",
                        details=stacktrace,
                    )
            else:
                answer = dialogue.show_dialogue_conditional(
                    title="仓库不存在”",
                    text="尝试更新一个不存在的Git仓库！",
                    information="您是否希望克隆这个仓库的一个新副本？",
                )
                if answer == "&Yes":
                    if GIT_EXISTS:
                        self._do_clone_repo_to_path(
                            base_path=base_path,
                            repo_url=repo_url,
                        )
                    else:
                        self._do_notify_no_git()
        else:
            # Warn the user so they know to configure in settings
            dialogue.show_warning(
                title="无效的存储库",
                text="已检测到无效的仓库！",
                information="请在设置中重新配置一个仓库！\n"
                + "一个有效的仓库URL必须是非空的，\n"
                + '并且必须以"http://"或"https://"为前缀。',
            )

    def _do_upload_db_to_repo(self, repo_url: str, file_name: str) -> None:
        """
        Checks validity of configured git repo, as well as if it exists
        Commits file & submits PR based on version tag found in DB
        """
        if (
            repo_url
            and repo_url != ""
            and (repo_url.startswith("http://") or repo_url.startswith("https://"))
        ):
            # Calculate folder name from provided URL
            repo_user_or_org = os.path.split(os.path.split(repo_url)[0])[1]
            repo_folder_name = os.path.split(repo_url)[1]
            # Calculate path from generated folder name
            repo_path = str((AppInfo().databases_folder / repo_folder_name))
            if os.path.exists(repo_path):  # If local repo exists
                # Update the file, commit + PR to repo
                logger.info(
                    f"正在尝试将针对{file_name}的更改提交到Git仓库: {repo_path}"
                )
                try:
                    # Specify the file path relative to the local repository
                    file_full_path = str((Path(repo_path) / file_name))
                    if os.path.exists(file_full_path):
                        # Load JSON data
                        with open(file_full_path, encoding="utf-8") as f:
                            json_string = f.read()
                            logger.debug("正在读取信息...")
                            database = json.loads(json_string)
                            logger.debug("已检索数据库...")
                        if database.get("version"):
                            database_version = (
                                database["version"]
                                - self.settings_controller.settings.database_expiry
                            )
                        elif database.get("timestamp"):
                            database_version = database["timestamp"]
                        else:
                            logger.error(
                                "无法从数据库中解析版本信息或时间戳。取消上传。"
                            )
                        # Get the abbreviated timezone
                        timezone_abbreviation = (
                            datetime.datetime.now(datetime.timezone.utc)
                            .astimezone()
                            .tzinfo
                        )
                        database_version_human_readable = (
                            time.strftime(
                                "%Y-%m-%d %H:%M:%S", time.localtime(database_version)
                            )
                            + f" {timezone_abbreviation}"
                        )
                    else:
                        dialogue.show_warning(
                            title="文件不存在",
                            text="请确保文件存在，然后再次尝试上传！",
                            information=f"文件未找到:\n{file_full_path}\n仓库:\n{repo_url}",
                        )
                        return

                    # Create a GitHub instance
                    g = Github(
                        self.settings_controller.settings.github_username,
                        self.settings_controller.settings.github_token,
                    )

                    # Specify the repository
                    repo = g.get_repo(f"{repo_user_or_org}/{repo_folder_name}")

                    # Specify the branch names
                    base_branch = "main"
                    new_branch_name = f"{database_version}"

                    # Specify commit message
                    commit_message = f"数据库更新: {database_version_human_readable}"

                    # Specify the Pull Request fields
                    pull_request_title = f"数据库更新 {database_version}"
                    pull_request_body = f"Steam 创意工坊 {commit_message}"

                    # Open repo
                    local_repo = Repo(repo_path)

                    # Create our new branch and checkout
                    new_branch = local_repo.create_head(new_branch_name)
                    local_repo.head.reference = new_branch

                    # Add the file to the index on our new branch
                    local_repo.index.add([file_full_path])

                    # Commit changes to the new branch
                    local_repo.index.commit(commit_message)
                    try:
                        # Push the changes to the remote repository and create a pull request from new_branch
                        origin = local_repo.remote()
                        origin.push(new_branch)
                    except Exception:
                        stacktrace = traceback.format_exc()
                        dialogue.show_warning(
                            title="无法将新分支推送到仓库！",
                            text=f"F无法将新分支 {new_branch_name} 推送到 {repo_folder_name} 仓库! "
                            + "尝试手动推送并创建拉取请求。如果不行，请切换到主分支（main）再试一次！",
                            information=f"已配置的仓库: {repo_url}",
                            details=stacktrace,
                        )
                    try:
                        # Create the pull request
                        pull_request = repo.create_pull(
                            title=pull_request_title,
                            body=pull_request_body,
                            base=base_branch,
                            head=f"{repo_user_or_org}:{new_branch_name}",
                        )
                        pull_request_url = pull_request.html_url
                    except Exception:
                        stacktrace = traceback.format_exc()
                        dialogue.show_warning(
                            title="无法创建拉取请求！",
                            text=f"无法为分支 {base_branch} 从 {new_branch_name} 创建拉取请求！!\n"
                            + "该分支应该被推送。检查GitHub ，看看你是否可以在那里"
                            + "手动创建一个拉取请求！否则，切换到主分支并再试一次！",
                            information=f"已配置的仓库: {repo_url}",
                            details=stacktrace,
                        )
                    # Cleanup
                    self._do_cleanup_gitpython(repo=local_repo)
                    # Notify the pull request URL
                    answer = dialogue.show_dialogue_conditional(
                        title="拉取请求已创建",
                        text="成功创建了拉取请求！",
                        information="你想尝试在你的网页浏览器中打开它吗？\n\n"
                        + f"URL: {pull_request_url}",
                    )
                    if answer == "&Yes":
                        # Open the url in user's web browser
                        open_url_browser(url=pull_request_url)
                except Exception:
                    stacktrace = traceback.format_exc()
                    dialogue.show_warning(
                        title="更新仓库失败！",
                        text=f"配置的仓库更新失败！\n文件名: {file_name}",
                        information=f"已配置的仓库: {repo_url}",
                        details=stacktrace,
                    )
            else:
                answer = dialogue.show_dialogue_conditional(
                    title="仓库不存在",
                    text="尝试更新一个不存在的Git仓库！",
                    information="你想克隆这个仓库的一个新副本吗？",
                )
                if answer == "&Yes":
                    if GIT_EXISTS:
                        self._do_clone_repo_to_path(
                            base_path=str(AppInfo().databases_folder),
                            repo_url=repo_url,
                        )
                    else:
                        self._do_notify_no_git()
        else:
            # Warn the user so they know to configure in settings
            dialogue.show_warning(
                title="无效的仓库",
                text="检测到了一个无效的仓库！",
                information="Please reconfigure a repository in settings!\n"
                + '一个有效的仓库是指一个不为空的仓库URL，且该URL以 "http://" 或 "https://" 为前缀。',
            )

    def _do_notify_no_git(self) -> None:
        answer = dialogue.show_dialogue_conditional(  # We import last so we can use gui + utils
            title="找不到git",
            text="在PATH 环境变量中未找到 git 可执行文件！",
            information=(
                "没有安装 Git 的话，Git 集成将无法使用！您是否想打开 Git 的下载页面？\n\n"
                "如果你刚刚安装了Git，请重启RimSort以使PATH变更生效。"
            ),
        )
        if answer == "&Yes":
            open_url_browser("https://git-scm.com/downloads")

    def _do_open_rule_editor(
        self, compact: bool, initial_mode: str, packageid: Any | None = None
    ) -> None:
        self.rule_editor = RuleEditor(
            # Initialization options
            compact=compact,
            edit_packageid=packageid,
            initial_mode=initial_mode,
        )
        self.rule_editor._populate_from_metadata()
        self.rule_editor.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.rule_editor.update_database_signal.connect(self._do_update_rules_database)
        self.rule_editor.show()

    def _do_configure_steam_db_file_path(self) -> None:
        # Input file
        logger.info("打开文件对话框以指定 Steam 数据库")
        input_path = dialogue.show_dialogue_file(
            mode="open",
            caption="Choose Steam Workshop Database",
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {input_path}")
        if input_path and os.path.exists(input_path):
            self.settings_controller.settings.external_steam_metadata_file_path = (
                input_path
            )
            self.settings_controller.settings.save()
        else:
            logger.debug("USER ACTION: 取消选择！")
            return

    def _do_configure_community_rules_db_file_path(self) -> None:
        # Input file
        logger.info("打开文件对话框以指定社区规则数据库")
        input_path = dialogue.show_dialogue_file(
            mode="打开",
            caption="选择社区规则数据库",
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"Selected path: {input_path}")
        if input_path and os.path.exists(input_path):
            self.settings_controller.settings.external_community_rules_file_path = (
                input_path
            )
            self.settings_controller.settings.save()
        else:
            logger.debug("USER ACTION: 取消选择！")
            return

    def _do_configure_steam_database_repo(self) -> None:
        """
        Opens a QDialogInput that allows user to edit their Steam DB repo
        This URL is used for Steam DB repo related actions.
        """
        args, ok = dialogue.show_dialogue_input(
            title="编辑Steam数据库仓库",
            label="进入 URL (https://github.com/AccountName/RepositoryName):",
            text=self.settings_controller.settings.external_steam_metadata_repo,
        )
        if ok:
            self.settings_controller.settings.external_steam_metadata_repo = args
            self.settings_controller.settings.save()

    def _do_configure_community_rules_db_repo(self) -> None:
        """
        Opens a QDialogInput that allows user to edit their Community Rules
        DB repo. This URL is used for Steam DB repo related actions.
        """
        args, ok = dialogue.show_dialogue_input(
            title="编辑社区规则数据库仓库",
            label="进入 URL (https://github.com/AccountName/RepositoryName):",
            text=self.settings_controller.settings.external_community_rules_repo,
        )
        if ok:
            self.settings_controller.settings.external_community_rules_repo = args
            self.settings_controller.settings.save()

    def _do_build_database_thread(self) -> None:
        # Prompt user file dialog to choose/create new DB
        logger.info("打开文件对话框以指定输出文件")
        output_path = dialogue.show_dialogue_file(
            mode="保存",
            caption="指定输出路径",
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        # Check file path and launch DB Builder with user configured mode
        if output_path:  # If output path was returned
            logger.info(f"所选路径: {output_path}")
            if not output_path.endswith(".json"):
                output_path += ".json"  # Handle file extension if needed
            # RimWorld Workshop contains 30,000+ PublishedFileIDs (mods) as of 2023!
            # "No": Produce accurate, complete DB by QueryFiles via WebAPI
            # Queries ALL available PublishedFileIDs (mods) it can find via Steam WebAPI.
            # Does not use metadata from locally available mods. This means no packageids!
            if self.settings_controller.settings.db_builder_include == "no_local":
                self.db_builder = metadata.SteamDatabaseBuilder(
                    apikey=self.settings_controller.settings.steam_apikey,
                    appid=294100,
                    database_expiry=self.settings_controller.settings.database_expiry,
                    mode=self.settings_controller.settings.db_builder_include,
                    output_database_path=output_path,
                    get_appid_deps=self.settings_controller.settings.build_steam_database_dlc_data,
                    update=self.settings_controller.settings.build_steam_database_update_toggle,
                )
            # "Yes": Produce accurate, possibly semi-incomplete DB without QueryFiles via API
            # CAN produce a complete DB! Only includes metadata parsed from mods you have downloaded.
            # Produces DB which contains metadata from locally available mods. Includes packageids!
            elif self.settings_controller.settings.db_builder_include == "all_mods":
                self.db_builder = metadata.SteamDatabaseBuilder(
                    apikey=self.settings_controller.settings.steam_apikey,
                    appid=294100,
                    database_expiry=self.settings_controller.settings.database_expiry,
                    mode=self.settings_controller.settings.db_builder_include,
                    output_database_path=output_path,
                    get_appid_deps=self.settings_controller.settings.build_steam_database_dlc_data,
                    mods=self.metadata_manager.internal_local_metadata,
                    update=self.settings_controller.settings.build_steam_database_update_toggle,
                )
            # Create query runner
            self.query_runner = RunnerPanel()
            self.query_runner.closing_signal.connect(self.db_builder.terminate)
            self.query_runner.setWindowTitle(
                f"RimSort - 数据库生成器 ({self.settings_controller.settings.db_builder_include})"
            )
            self.query_runner.progress_bar.show()
            self.query_runner.show()
            # Connect message signal
            self.db_builder.db_builder_message_output_signal.connect(
                self.query_runner.message
            )
            # Start DB builder
            self.db_builder.start()
        else:
            logger.debug("USER ACTION: 取消的选区...")

    def _do_blacklist_action_steamdb(self, instruction: list) -> None:
        if (
            self.metadata_manager.external_steam_metadata_path
            and self.metadata_manager.external_steam_metadata
            and len(self.metadata_manager.external_steam_metadata.keys()) > 0
        ):
            logger.info(f"更新Steam数据库中项目的黑名单状态: {instruction}")
            # Retrieve instruction passed from signal
            publishedfileid = instruction[0]
            blacklist = instruction[1]
            if blacklist:  # Only deal with comment if we are adding a mod to blacklist
                comment = instruction[2]
            else:
                comment = None
            # Check if our DB has an entry for the mod we are editing
            if not self.metadata_manager.external_steam_metadata.get(publishedfileid):
                self.metadata_manager.external_steam_metadata.setdefault(
                    publishedfileid, {}
                )
            # Edit our metadata
            if blacklist and comment:
                self.metadata_manager.external_steam_metadata[publishedfileid][
                    "blacklist"
                ] = {
                    "value": blacklist,
                    "comment": comment,
                }
            else:
                self.metadata_manager.external_steam_metadata[publishedfileid].pop(
                    "blacklist", None
                )
            logger.debug("使用新的元数据更新先前的数据库...\n")
            with open(
                self.metadata_manager.external_steam_metadata_path,
                "w",
                encoding="utf-8",
            ) as output:
                json.dump(
                    {
                        "version": int(
                            time.time()
                            + self.settings_controller.settings.database_expiry
                        ),
                        "database": self.metadata_manager.external_steam_metadata,
                    },
                    output,
                    indent=4,
                )
            self._do_refresh()

    def _do_download_entire_workshop(self, action: str) -> None:
        # DB Builder is used to run DQ and grab entirety of
        # any available Steam Workshop PublishedFileIDs
        self.db_builder = metadata.SteamDatabaseBuilder(
            apikey=self.settings_controller.settings.steam_apikey,
            appid=294100,
            database_expiry=self.settings_controller.settings.database_expiry,
            mode="pfids_by_appid",
        )
        # Create query runner
        self.query_runner = RunnerPanel()
        self.query_runner.closing_signal.connect(self.db_builder.terminate)
        self.query_runner.setWindowTitle("RimSort - 数据库生成器已发布文件ID查询")
        self.query_runner.progress_bar.show()
        self.query_runner.show()
        # Connect message signal
        self.db_builder.db_builder_message_output_signal.connect(
            self.query_runner.message
        )
        # Start DB builder
        self.db_builder.start()
        loop = QEventLoop()
        self.db_builder.finished.connect(loop.quit)
        loop.exec_()
        if not len(self.db_builder.publishedfileids) > 0:
            dialogue.show_warning(
                title="没有已发布模组的ID",
                text="数据库生成器的查询没有返回任何已发布模组的ID！",
                information="这通常是由于无效的/缺失的Steam WebAPI密钥，或者与Steam WebAPI的连接问题所导致的。\n"
                + "从Steam检索模组时，需要已发布模组ID（PublishedFileIDs）!",
            )
        else:
            self.query_runner.close()
            self.query_runner = None
            if "steamcmd" in action:
                # Filter out existing SteamCMD mods
                mod_pfid = None
                for (
                    metadata_values
                ) in self.metadata_manager.internal_local_metadata.values():
                    if metadata_values.get("steamcmd"):
                        mod_pfid = metadata_values.get("publishedfileid")
                    if mod_pfid and mod_pfid in self.db_builder.publishedfileids:
                        logger.debug(
                            f"跳过已存在的Steam模组下载: {mod_pfid}"
                        )
                        self.db_builder.publishedfileids.remove(mod_pfid)
                self._do_download_mods_with_steamcmd(self.db_builder.publishedfileids)
            elif "steamworks" in action:
                answer = dialogue.show_dialogue_conditional(
                    title="是否确定？",
                    text="可能有风险",
                    information="警告: 不建议一次性通过Steam订阅如此多的模组。"
                    + "Steam对API订阅设有限制，这些限制看似有意为之，也可能非故意设置。"
                    + "强烈建议您使用SteamCMD将这些模组下载到SteamCMD前缀中。"
                    + "由于速率限制，这个过程可能需要更长的时间。但如果您不想通过RimSort匿名下载，"
                    + "您也可以使用RimSort生成的脚本与另一个经过身份验证的SteamCMD实例配合使用。",
                )
                if answer == "&Yes":
                    for (
                        metadata_values
                    ) in self.metadata_manager.internal_local_metadata.values():
                        mod_pfid = metadata_values.get("publishedfileid")
                        if (
                            metadata_values["data_source"] == "workshop"
                            and mod_pfid
                            and mod_pfid in self.db_builder.publishedfileids
                        ):
                            logger.warning(
                                f"跳过已存在的Steam模组下载: {mod_pfid}"
                            )
                            self.db_builder.publishedfileids.remove(mod_pfid)
                    self._do_steamworks_api_call_animated(
                        [
                            "订阅",
                            [
                                eval(str_pfid)
                                for str_pfid in self.db_builder.publishedfileids
                            ],
                        ]
                    )

    def _do_edit_steam_webapi_key(self) -> None:
        """
        Opens a QDialogInput that allows the user to edit their Steam API-key
        that are configured to be passed to the "Dynamic Query" feature for
        the Steam Workshop metadata needed for sorting
        """
        args, ok = dialogue.show_dialogue_input(
            title="编辑Steam WebAPI密钥",
            label="在这里输入您的个人32位Steam WebAPI密钥:",
            text=self.settings_controller.settings.steam_apikey,
        )
        if ok:
            self.settings_controller.settings.steam_apikey = args
            self.settings_controller.settings.save()

    def _do_generate_metadata_comparison_report(self) -> None:
        """
        Open a user-selected JSON file. Calculate and display discrepancies
        found between database and this file.
        """
        # TODO: Refactor this...
        discrepancies: list[str] = []
        database_a_deps: dict[str, Any] = {}
        database_b_deps: dict[str, Any] = {}
        # Notify user
        dialogue.show_information(
            title="Steam 数据库生成器",
            text="此操作将比较两个数据库A和B，通过检查A中的依赖项与B中的依赖项来进行比较。",
            information="- 这将生成两个Steam数据库之间依赖数据的准确比较。\n"
            + "生成了差异报告。系统将提示您输入这些路径，以便进行进一步的操作。:\n"
            + "\n\t1) 选择输入A"
            + "\n\t2) 选择输入B",
        )
        # Input A
        logger.info("打开文件对话框以指定输入文件A")
        input_path_a = dialogue.show_dialogue_file(
            mode="打开",
            caption='输入“待更新”数据库，即输入A',
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {input_path_a}")
        if input_path_a and os.path.exists(input_path_a):
            with open(input_path_a, encoding="utf-8") as f:
                json_string = f.read()
                logger.debug("阅读信息...")
                db_input_a = json.loads(json_string)
                logger.debug("已检索数据库A...")
        else:
            logger.warning("Steam 数据库生成器: 用户取消选择...")
            return
        # Input B
        logger.info("打开文件对话框以指定输入文件B")
        input_path_b = dialogue.show_dialogue_file(
            mode="打开",
            caption='输入“待更新”数据库，即输入A',
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {input_path_b}")
        if input_path_b and os.path.exists(input_path_b):
            with open(input_path_b, encoding="utf-8") as f:
                json_string = f.read()
                logger.debug("阅读信息...")
                db_input_b = json.loads(json_string)
                logger.debug("已检索数据库B...")
        else:
            logger.debug("Steam 数据库生成器: 用户取消选择...")
            return
        for k, v in db_input_a["database"].items():
            # print(k, v['dependencies'])
            database_b_deps[k] = set()
            if v.get("dependencies"):
                for dep_key in v["dependencies"]:
                    database_b_deps[k].add(dep_key)
        for k, v in db_input_b["database"].items():
            # print(k, v['dependencies'])
            if k in database_b_deps:
                database_a_deps[k] = set()
                if v.get("dependencies"):
                    for dep_key in v["dependencies"]:
                        database_a_deps[k].add(dep_key)
        no_deps_str = "*no explicit dependencies listed*"
        database_a_total_deps = len(database_a_deps)
        database_b_total_deps = len(database_b_deps)
        report = (
            "\nSteam DB comparison report:\n"
            + "\nTotal # of deps from database A:\n"
            + f"{database_a_total_deps}"
            + "\nTotal # of deps from database B:\n"
            + f"{database_b_total_deps}"
            + f"\nTotal # of discrepancies:\n{len(discrepancies)}"
        )
        comparison_skipped = []
        for k, v in database_b_deps.items():
            if db_input_a["database"][k].get("unpublished"):
                comparison_skipped.append(k)
                # logger.debug(f"Skipping comparison for unpublished mod: {k}")
            else:
                # If the deps are different...
                if v != database_a_deps.get(k):
                    pp = database_a_deps.get(k)
                    if pp:
                        # Normalize here (get rid of core/dlc deps)
                        if v != pp:
                            discrepancies.append(k)
                            pp_total = len(pp)
                            v_total = len(v)
                            if v == set():
                                v = no_deps_str
                            if pp == set():
                                pp = no_deps_str
                            mod_name = db_input_b["database"][k]["name"]
                            report += f"\n\nDISCREPANCY FOUND for {k}:"
                            report += f"\nhttps://steamcommunity.com/sharedfiles/filedetails/?id={k}"
                            report += f"\nMod name: {mod_name}"
                            report += (
                                f"\n\nDatabase A:\n{v_total} dependencies found:\n{v}"
                            )
                            report += (
                                f"\n\nDatabase B:\n{pp_total} dependencies found:\n{pp}"
                            )
        logger.debug(
            f"Comparison skipped for {len(comparison_skipped)} unpublished mods: {comparison_skipped}"
        )
        dialogue.show_information(
            title="Steam 数据库生成器",
            text=f"Steam 数据库比较报告: 发现{len(discrepancies)}项差异",
            information="点击“显示详情”以查看完整报告！",
            details=report,
        )

    def _do_merge_databases(self) -> None:
        # Notify user
        dialogue.show_information(
            title="Steam 数据库生成器",
            text="此操作将通过递归地使用B来更新A（排除异常情况），来合并两个数据库A和B。",
            information="- 这将有效地通过递归方式将B的键值对覆盖到A的键值对上，以生成最终的数据库。\n"
            + "- 但需要注意的是，异常情况不会被递归更新。相反，它们将完全使用B的键来覆盖。\n"
            + "- 将做出以下例外情况:\n"
            + f"\n\t{app_constants.DB_BUILDER_RECURSE_EXCEPTIONS}\n\n"
            + "生成的数据库C将被保存到用户指定的路径。您将会按顺序被提示输入这些路径。:\n"
            + "\n\t1) 选择输入A（待更新的数据库）"
            + "\n\t2) 选择输入B（更新源）"
            + "\n\t3) 选择输出C（结果数据库）",
        )
        # Input A
        logger.info("打开文件对话框以指定输入文件A")
        input_path_a = dialogue.show_dialogue_file(
            mode="打开",
            caption='输入“待更新”数据库，即输入A',
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {input_path_a}")
        if input_path_a and os.path.exists(input_path_a):
            with open(input_path_a, encoding="utf-8") as f:
                json_string = f.read()
                logger.debug("阅读信息...")
                db_input_a = json.loads(json_string)
                logger.debug("已检索数据库A...")
        else:
            logger.warning("Steam 数据库生成器: 用户取消选择...")
            return
        # Input B
        logger.info("打开文件对话框以指定输入文件B")
        input_path_b = dialogue.show_dialogue_file(
            mode="打开",
            caption='输入“待更新”数据库，即输入A',
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {input_path_b}")
        if input_path_b and os.path.exists(input_path_b):
            with open(input_path_b, encoding="utf-8") as f:
                json_string = f.read()
                logger.debug("阅读信息...")
                db_input_b = json.loads(json_string)
                logger.debug("已检索数据库B...")
        else:
            logger.debug("Steam 数据库生成器: 用户取消选择...")
            return
        # Output C
        db_output_c = db_input_a.copy()
        metadata.recursively_update_dict(
            db_output_c,
            db_input_b,
            prune_exceptions=app_constants.DB_BUILDER_PRUNE_EXCEPTIONS,
            recurse_exceptions=app_constants.DB_BUILDER_RECURSE_EXCEPTIONS,
        )
        logger.info("已使用数据库B的数据更新数据库A！")
        logger.debug(db_output_c)
        logger.info("打开文件对话框以指定输出文件")
        output_path = dialogue.show_dialogue_file(
            mode="保存",
            caption="为结果数据库指定输出路径:",
            _dir=str(AppInfo().app_storage_folder),
            _filter="JSON (*.json)",
        )
        logger.info(f"所选路径: {output_path}")
        if output_path:
            if not output_path.endswith(".json"):
                output_path += ".json"  # Handle file extension if needed
            with open(output_path, "w", encoding="utf-8") as output:
                json.dump(db_output_c, output, indent=4)
        else:
            logger.warning("Steam 数据库生成器: 用户取消选择...")
            return

    def _do_update_rules_database(self, instruction: list) -> None:
        rules_source = instruction[0]
        rules_data = instruction[1]
        # Get path based on rules source
        if (
            rules_source == "社区规则"
            and self.metadata_manager.external_community_rules_path
        ):
            path = self.metadata_manager.external_community_rules_path
        elif rules_source == "用户规则" and str(
            AppInfo().databases_folder / "userRules.json"
        ):
            path = str(AppInfo().databases_folder / "userRules.json")
        else:
            logger.warning(
                f"未设置 {rules_source} 文件路径。未配置要更新的数据库！"
            )
            return
        # Retrieve original database
        try:
            with open(path, encoding="utf-8") as f:
                json_string = f.read()
                logger.debug("阅读信息...")
                db_input_a = json.loads(json_string)
                logger.debug(
                    f"已检索到现有 {rules_source} 数据库的副本以进行更新。"
                )
        except Exception:
            logger.error("无法从现有数据库中读取信息")
        db_input_b = {"时间戳": int(time.time()), "规则": rules_data}
        db_output_c = db_input_a.copy()
        # Update database in place
        metadata.recursively_update_dict(
            db_output_c,
            db_input_b,
            prune_exceptions=app_constants.DB_BUILDER_PRUNE_EXCEPTIONS,
            recurse_exceptions=app_constants.DB_BUILDER_RECURSE_EXCEPTIONS,
        )
        # Overwrite rules database
        answer = dialogue.show_dialogue_conditional(
            title="RimSort - 数据库生成器",
            text="是否要继续？",
            information=f"此操作将覆盖 {rules_source} 数据库，位于以下路径的:\n\n{path}",
        )
        if answer == "&Yes":
            with open(path, "w", encoding="utf-8") as output:
                json.dump(db_output_c, output, indent=4)
            self._do_refresh()
        else:
            logger.debug("USER ACTION: 拒绝继续规则数据库更新。")

    def _do_set_database_expiry(self) -> None:
        """
        Opens a QDialogInput that allows the user to edit their preferred
        WebAPI Query Expiry (in seconds)
        """
        args, ok = dialogue.show_dialogue_input(
            title="更新Steam数据库的有效期:",
            label="请输入您偏好的过期时长（以秒为单位）（默认为1周/604800秒）:",
            text=str(self.settings_controller.settings.database_expiry),
        )
        if ok:
            try:
                self.settings_controller.settings.database_expiry = int(args)
                self.settings_controller.settings.save()
            except ValueError:
                dialogue.show_warning(
                    "尝试使用非整数值配置动态查询。",
                    "请重新配置过期值，使用从UNIX时间戳的起始点开始计算的秒数整数，以确定您希望查询过期的具体时间。",
                )

    @Slot()
    def _on_settings_have_changed(self) -> None:
        instance = self.settings_controller.settings.instances.get(
            self.settings_controller.settings.current_instance
        )
        if not instance:
            logger.warning(
                f"尝试访问不存在的实例 {self.settings_controller.settings.current_instance} !"
            )
            return None

        steamcmd_prefix = instance.steamcmd_install_path

        if steamcmd_prefix:
            self.steamcmd_wrapper.initialize_prefix(
                steamcmd_prefix=str(steamcmd_prefix),
                validate=self.settings_controller.settings.steamcmd_validate_downloads,
            )
        self.steamcmd_wrapper.validate_downloads = (
            self.settings_controller.settings.steamcmd_validate_downloads
        )

    @Slot()
    def _on_do_upload_community_db_to_github(self) -> None:
        self._do_upload_db_to_repo(
            repo_url=self.settings_controller.settings.external_community_rules_repo,
            file_name="communityRules.json",
        )

    @Slot()
    def _on_do_download_community_db_from_github(self) -> None:
        if GIT_EXISTS:
            self._do_clone_repo_to_path(
                base_path=str(AppInfo().databases_folder),
                repo_url=self.settings_controller.settings.external_community_rules_repo,
            )
        else:
            self._do_notify_no_git()

    @Slot()
    def _on_do_upload_steam_workshop_db_to_github(self) -> None:
        self._do_upload_db_to_repo(
            repo_url=self.settings_controller.settings.external_steam_metadata_repo,
            file_name="steamDB.json",
        )

    @Slot()
    def _on_do_download_steam_workshop_db_from_github(self) -> None:
        self._do_clone_repo_to_path(
            base_path=str(AppInfo().databases_folder),
            repo_url=self.settings_controller.settings.external_steam_metadata_repo,
        )

    @Slot()
    def _on_do_upload_log(self) -> None:
        self._upload_log(AppInfo().user_log_folder / (AppInfo().app_name + ".log"))

    @Slot()
    def _on_do_download_all_mods_via_steamcmd(self) -> None:
        self._do_download_entire_workshop("download_entire_workshop_steamcmd")

    @Slot()
    def _on_do_download_all_mods_via_steam(self) -> None:
        self._do_download_entire_workshop("download_entire_workshop_steamworks")

    @Slot()
    def _on_do_build_steam_workshop_database(self) -> None:
        self._do_build_database_thread()

    @Slot()
    def _do_run_game(self) -> None:
        current_instance = self.settings_controller.settings.current_instance
        game_install_path = Path(
            self.settings_controller.settings.instances[current_instance].game_folder
        )
        # Run args is inconsistent and is sometimes a string and sometimes a list
        run_args: list[str] | str = self.settings_controller.settings.instances[
            current_instance
        ].run_args

        run_args = [run_args] if isinstance(run_args, str) else run_args

        steam_client_integration = self.settings_controller.settings.instances[
            current_instance
        ].steam_client_integration

        # If integration is enabled, check for file called "steam_appid.txt" in game folder.
        # in the game folder. If not, create one and add the Steam App ID to it.
        # The Steam App ID is "294100" for RimWorld.
        steam_appid_file_exists = os.path.exists(game_install_path / "steam_appid.txt")
        if steam_client_integration and not steam_appid_file_exists:
            with open(
                game_install_path / "steam_appid.txt", "w", encoding="utf-8"
            ) as f:
                f.write("294100")
        elif not steam_client_integration and steam_appid_file_exists:
            os.remove(game_install_path / "steam_appid.txt")

        # Launch independent game process without Steamworks API
        launch_game_process(game_install_path=game_install_path, args=run_args)
