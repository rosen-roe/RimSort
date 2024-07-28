import os
from functools import partial
from pathlib import Path
from shutil import copytree, rmtree
from traceback import format_exc
from typing import Any, Optional

from loguru import logger
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.controllers.instance_controller import (
    InstanceController,
    InvalidArchivePathError,
)
from app.controllers.menu_bar_controller import MenuBarController
from app.controllers.settings_controller import (
    SettingsController,
)
from app.utils.app_info import AppInfo
from app.utils.event_bus import EventBus
from app.utils.gui_info import GUIInfo
from app.utils.steam.steamcmd.wrapper import SteamcmdInterface
from app.utils.watchdog import WatchdogHandler
from app.views.dialogue import (
    show_dialogue_conditional,
    show_dialogue_confirmation,
    show_dialogue_file,
    show_dialogue_input,
    show_fatal_error,
    show_warning,
)
from app.views.main_content_panel import MainContent
from app.views.menu_bar import MenuBar
from app.views.status_panel import Status


class MainWindow(QMainWindow):
    """
    Subclass QMainWindow to customize the main application window.
    """

    def __init__(
        self, settings_controller: SettingsController, debug_mode: bool = False
    ) -> None:
        """
        Initialize the main application window. Construct the layout,
        add the three main views, and set up relevant signals and slots.
        """
        logger.info("Initializing MainWindow")
        super(MainWindow, self).__init__()

        self.settings_controller = settings_controller

        # Create the main application window
        self.DEBUG_MODE = debug_mode
        # SteamCMDInterface
        self.steamcmd_wrapper = SteamcmdInterface.instance()
        # Content initialization should only fire on startup. Otherwise, this is handled by Refresh button

        # Watchdog
        self.watchdog_event_handler: Optional[WatchdogHandler] = None

        # Set up the window
        self.setWindowTitle(f"RimSort {AppInfo().app_version}")
        self.setMinimumSize(QSize(1024, 768))

        # Create the window layout
        app_layout = QVBoxLayout()
        app_layout.setContentsMargins(0, 0, 0, 0)  # Space from main layout to border
        app_layout.setSpacing(0)  # Space between widgets

        # Create various panels on the application GUI
        self.main_content_panel = MainContent(
            settings_controller=self.settings_controller
        )
        self.main_content_panel.disable_enable_widgets_signal.connect(
            self.__disable_enable_widgets
        )
        self.bottom_panel = Status()

        # Arrange all panels vertically on the main window layout
        app_layout.addWidget(self.main_content_panel.main_layout_frame)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(12, 12, 12, 12)
        button_layout.setSpacing(12)
        app_layout.addLayout(button_layout)

        self.game_version_label = QLabel()
        self.game_version_label.setFont(GUIInfo().smaller_font)
        self.game_version_label.setEnabled(False)
        button_layout.addWidget(self.game_version_label)

        button_layout.addStretch()

        # Define button attributes
        self.refresh_button = QPushButton("刷新列表")
        self.clear_button = QPushButton("清除启用")
        self.restore_button = QPushButton("还原列表")
        self.sort_button = QPushButton("自动排序")
        self.save_button = QPushButton("保存排序")
        self.run_button = QPushButton("缘神启动！")

        buttons = [
            self.refresh_button,
            self.clear_button,
            self.restore_button,
            self.sort_button,
            self.save_button,
            self.run_button,
        ]

        for button in buttons:
            button.setMinimumWidth(100)
            button_layout.addWidget(button)

        # Save button flashing animation
        self.save_button_flashing_animation = QTimer()
        self.save_button_flashing_animation.timeout.connect(
            partial(EventBus().do_button_animation.emit, self.save_button)
        )

        # Create the bottom panel
        app_layout.addWidget(self.bottom_panel.frame)

        # Display all items
        widget = QWidget()
        widget.setLayout(app_layout)
        self.setCentralWidget(widget)

        self.menu_bar = MenuBar(menu_bar=self.menuBar())
        self.menu_bar_controller = MenuBarController(
            view=self.menu_bar, settings_controller=self.settings_controller
        )
        # Connect Instances Menu Bar signals
        EventBus().do_activate_current_instance.connect(self.__switch_to_instance)
        EventBus().do_backup_existing_instance.connect(self.__backup_existing_instance)
        EventBus().do_clone_existing_instance.connect(self.__clone_existing_instance)
        EventBus().do_create_new_instance.connect(self.__create_new_instance)
        EventBus().do_delete_current_instance.connect(self.__delete_current_instance)
        EventBus().do_restore_instance_from_archive.connect(
            self.__restore_instance_from_archive
        )

        self.setGeometry(100, 100, 1024, 768)
        logger.debug("完成主窗口初始化")

    def __disable_enable_widgets(self, enable: bool) -> None:
        # Disable widgets
        q_app = QApplication.instance()
        if q_app is None:
            return
        for widget in q_app.allWidgets():  # type: ignore # Broken pyside stub
            widget.setEnabled(enable)

    def showEvent(self, event: QShowEvent) -> None:
        # Call the original showEvent handler
        super().showEvent(event)

    def initialize_content(self, is_initial: bool = True) -> None:
        # POPULATE INSTANCES SUBMENU
        self.menu_bar_controller._on_instances_submenu_population(
            instance_names=list(self.settings_controller.settings.instances.keys())
        )
        self.menu_bar_controller._on_set_current_instance(
            self.settings_controller.settings.current_instance
        )
        # IF CHECK FOR UPDATE ON STARTUP...
        if self.settings_controller.settings.check_for_update_startup:
            self.main_content_panel.actions_slot("check_for_update")
        # REFRESH CONFIGURED METADATA
        self.main_content_panel._do_refresh(is_initial=is_initial)
        # CHECK FOR STEAMCMD SETUP
        if not os.path.exists(
            self.steamcmd_wrapper.steamcmd_prefix
        ) or not self.steamcmd_wrapper.check_for_steamcmd(
            prefix=self.steamcmd_wrapper.steamcmd_prefix
        ):
            self.steamcmd_wrapper.on_steamcmd_not_found()
        else:
            self.steamcmd_wrapper.setup = True
        # CHECK USER PREFERENCE FOR WATCHDOG
        if self.settings_controller.settings.watchdog_toggle:
            # Setup watchdog
            self.initialize_watchdog()

    def __ask_for_new_instance_name(self) -> str | None:
        instance_name, ok = show_dialogue_input(
            title="创建新实例",
            label="输入尚未使用的新实例的唯一名称:",
        )
        return instance_name.strip() if ok else None

    def __ask_for_non_default_instance_name(self) -> str | None:
        while True:
            instance_name, ok = show_dialogue_input(
                title="提供实例名称",
                label='非“默认”的备份实例输入唯一名称',
            )
            if ok and instance_name.lower() != "default":
                return instance_name
            else:
                return None

    def __ask_how_to_workshop_mods(
        self, existing_instance_name: str, existing_instance_workshop_folder: str
    ) -> str:
        answer = show_dialogue_conditional(
            title=f"克隆实例 [{existing_instance_name}]",
            text=(
                "您想对配置的创意工坊模组文件夹执行什么操作?"
            ),
            information=(
                f"创意工坊文件夹: {existing_instance_workshop_folder}\n\n"
                + "RimSort  可以将所有创意工坊模组复制到新实例的本地模组文件夹中。这将有效地将\n\n"
                + "任何已存在的Steam客户端模组转换为SteamCMD模组，然后您可以在新实例中管理这些模组\n\n"
                + "或者，您可以保留旧的Steam创意工坊文件夹偏好。您可以随时在以后的设置中更改此设置\n\n"
                + "您希望如何进行?"
            ),
            button_text_override=[
                "转换为SteamCMD",
                "保留创意工坊文件",
            ],
        )
        return answer or "取消"

    def __backup_existing_instance(self, instance_name: str) -> None:
        # Get instance data from Settings
        instance = self.settings_controller.settings.instances.get(instance_name)

        # If the instance_name is "Default", prompt the user for a new instance name.
        if instance_name == "Default":
            new_instance_name = self.__ask_for_non_default_instance_name()
            if not new_instance_name:
                logger.info("用户取消操作")
                return
            instance_name = new_instance_name

        # Determine instance data to save
        if instance is None:
            logger.error(f"实例[{instance_name}]在设置中找不到")
            return

        instance_controller = InstanceController(instance)
        # Prompt user to select output path for instance archive
        output_path = show_dialogue_file(
            mode="保存",
            caption="选择实例存档的输出路径",
            _dir=str(AppInfo().app_storage_folder),
            _filter="Zip files (*.zip)",
        )
        logger.info(f"所选路径: {output_path}")
        if output_path:
            try:
                self.main_content_panel.do_threaded_loading_animation(
                    gif_path=str(
                        AppInfo().theme_data_folder / "default-icons" / "rimsort.gif"
                    ),
                    target=partial(
                        instance_controller.compress_to_archive,
                        output_path,
                    ),
                    text=f"压缩[{instance_name}]要存档的实例文件夹...",
                )
            except Exception as e:
                show_fatal_error(
                    title="压缩实例时出错",
                    text=f"压缩实例文件夹时出错: {e}",
                    information="请查看日志以获取更多信息。",
                    details=format_exc(),
                )
        else:
            logger.warning("备份已取消：用户取消选择...")
            return

    def __restore_instance_from_archive(self) -> None:
        # Prompt user to select input path for instance archive
        input_path = show_dialogue_file(
            mode="打开",
            caption="选择实例存档的输入路径",
            _dir=str(AppInfo().app_storage_folder),
            _filter="Zip files (*.zip)",
        )

        if input_path is None:
            logger.info("用户取消的操作。输入路径为“无”")
            return
        logger.info(f"所选路径: {input_path}")

        if not os.path.exists(input_path):
            logger.error(f"在路径中找不到存档: {input_path}")
            show_warning(
                title="还原实例时出错",
                text=f"在路径中找不到存档: {input_path}",
            )
            return

        # Grab the instance name from the archive's "instance.json" file and extract archive
        try:
            instance_controller = InstanceController(input_path)
        except InvalidArchivePathError as _:
            # Handled in controller. Gracefully fail.
            return
        except Exception as e:
            logger.error(f"读取实例存档时出错: {e}")
            show_fatal_error(
                title="还原实例时出错",
                text=f"读取实例存档时出错: {e}",
                details=format_exc(),
            )
            return

        if os.path.exists(instance_controller.instance_folder_path):
            answer = show_dialogue_conditional(
                title="实例文件夹存在",
                text=f"实例文件夹已存在: {instance_controller.instance_folder_path}",
                information="是否要继续并替换已存在实例文件夹？",
                button_text_override=[
                    "替换",
                ],
            )

            if answer != "替换":
                logger.info("用户取消了实例提取。")
                return

        self.main_content_panel.do_threaded_loading_animation(
            target=partial(
                instance_controller.extract_from_archive,
                input_path,
            ),
            gif_path=str(AppInfo().theme_data_folder / "default-icons" / "rimsort.gif"),
            text=f"从存档还原实例[{instance_controller.instance.name}]...",
        )

        # Check that the instance folder exists. If it does, update Settings with the instance data
        if os.path.exists(instance_controller.instance_folder_path):
            cleared_paths = instance_controller.validate_paths()
            if cleared_paths:
                logger.warning(
                    f"找不到实例文件夹路径: {', '.join(cleared_paths)}"
                )
                show_warning(
                    title="无效的实例文件夹路径",
                    text="无效的实例文件夹路径",
                    information="还原实例中的某些文件夹路径无效，可能已被清除。请在设置中重新配置它们",
                    details=f"无效路径: {', '.join(cleared_paths)}",
                )

            steamcmd_link_path = str(
                Path(instance_controller.instance.steamcmd_install_path)
                / "steam"
                / "steamapps"
                / "workshop"
                / "content"
                / "294100"
            )

            if (
                os.path.exists(steamcmd_link_path)
                and instance_controller.instance.local_folder != ""
            ):
                logger.info("恢复steamcmd符号链接...")
                self.steamcmd_wrapper.check_symlink(
                    steamcmd_link_path, instance_controller.instance.local_folder
                )
            elif not os.path.exists(steamcmd_link_path):
                logger.info("跳过steamcmd符号链接修复")
            else:
                show_warning(
                    title="无法修复steamcmd符号链接/连接",
                    text="无法修复steamcmd符号链接/连接",
                    information="由于本地文件夹未设置或无效，因此无法修复steamcmd符号链接/连接。需要手动重新创建符号链接/连接。",
                )
                logger.warning(
                    "跳过steamcmd符号链接修复：未设置本地文件夹。符号链接需要手动更新。"
                )

            self.settings_controller.set_instance(instance_controller.instance)
            self.__switch_to_instance(instance_controller.instance.name)
        else:
            show_warning(
                title="还原实例时出错",
                text=f"还原实例时出错[{instance_controller.instance.name}].",
                information="解压缩存档后未找到实例文件夹。存档可能已损坏或实例名称无效。",
            )

            logger.warning(
                "还原已取消：提取后未找到实例文件夹..."
            )

    def __clone_existing_instance(self, existing_instance_name: str) -> None:
        def copy_game_folder(
            existing_instance_game_folder: str, target_game_folder: str
        ) -> None:
            try:
                if os.path.exists(target_game_folder) and os.path.isdir(
                    target_game_folder
                ):
                    logger.info(
                        f"替换{target_game_folder}处的已存在游戏文件夹"
                    )
                    rmtree(target_game_folder)
                logger.info(
                    f"将游戏文件夹从{existing_instance_game_folder}复制到{target_game_folder}"
                )
                copytree(
                    existing_instance_game_folder, target_game_folder, symlinks=True
                )
            except Exception as e:
                logger.error(f"复制游戏文件夹时出错: {e}")

        def copy_config_folder(
            existing_instance_config_folder: str, target_config_folder: str
        ) -> None:
            try:
                if os.path.exists(target_config_folder) and os.path.isdir(
                    target_config_folder
                ):
                    logger.info(
                        f"替换{target_config_folder}处的已存在配置文件夹"
                    )
                    rmtree(target_config_folder)
                logger.info(
                    f"将配置文件夹从{existing_instance_config_folder}复制到{target_config_folder}"
                )
                copytree(
                    existing_instance_config_folder,
                    target_config_folder,
                    symlinks=True,
                )
            except Exception as e:
                logger.error(f"复制配置文件夹时出错: {e}")

        def copy_local_folder(
            existing_instance_local_folder: str, target_local_folder: str
        ) -> None:
            try:
                if os.path.exists(target_local_folder) and os.path.isdir(
                    target_local_folder
                ):
                    logger.info(
                        f"替换{target_local_folder}处的已存在本地文件夹"
                    )
                    rmtree(target_local_folder)
                logger.info(
                    f"将本地文件夹从{existing_instance_local_folder}复制到{target_local_folder}"
                )
                copytree(
                    existing_instance_local_folder,
                    target_local_folder,
                    symlinks=True,
                )
            except Exception as e:
                logger.error(f"复制本地文件夹时出错: {e}")

        def copy_workshop_mods_to_local(
            existing_instance_workshop_folder: str, target_local_folder: str
        ) -> None:
            try:
                if not os.path.exists(target_local_folder):
                    os.mkdir(target_local_folder)
                logger.info(
                    f"将创意工坊模组从{existing_instance_workshop_folder}克隆到{target_local_folder}"
                )
                # Copy each subdirectory of the existing Workshop folder to the new local mods folder
                for subdir in os.listdir(existing_instance_workshop_folder):
                    if os.path.isdir(
                        os.path.join(existing_instance_workshop_folder, subdir)
                    ):
                        logger.debug(f"克隆创意工坊模组: {subdir}")
                        copytree(
                            os.path.join(existing_instance_workshop_folder, subdir),
                            os.path.join(target_local_folder, subdir),
                            symlinks=True,
                        )
            except Exception as e:
                logger.error(f"克隆创意工坊模组时出错: {e}")

        def clone_essential_paths(
            existing_instance_game_folder: str,
            target_game_folder: str,
            existing_instance_config_folder: str,
            target_config_folder: str,
        ) -> None:
            # Clone the existing game_folder to the new instance
            if os.path.exists(existing_instance_game_folder) and os.path.isdir(
                existing_instance_game_folder
            ):
                copy_game_folder(existing_instance_game_folder, target_game_folder)
            # Clone the existing config_folder to the new instance
            if os.path.exists(existing_instance_config_folder) and os.path.isdir(
                existing_instance_config_folder
            ):
                copy_config_folder(
                    existing_instance_config_folder, target_config_folder
                )

        # Check if paths are set. We can't clone if they aren't set
        if not self.main_content_panel.check_if_essential_paths_are_set(prompt=True):
            return
        # Get instance data from Settings
        current_instances = list(self.settings_controller.settings.instances.keys())
        existing_instance_game_folder = self.settings_controller.settings.instances[
            existing_instance_name
        ].game_folder
        game_folder_name = os.path.split(existing_instance_game_folder)[1]
        existing_instance_local_folder = self.settings_controller.settings.instances[
            existing_instance_name
        ].local_folder
        local_folder_name = os.path.split(existing_instance_local_folder)[1]
        existing_instance_workshop_folder = self.settings_controller.settings.instances[
            existing_instance_name
        ].workshop_folder
        existing_instance_config_folder = self.settings_controller.settings.instances[
            existing_instance_name
        ].config_folder
        existing_instance_run_args = self.settings_controller.settings.instances[
            existing_instance_name
        ].run_args
        existing_instance_steamcmd_install_path = (
            self.settings_controller.settings.instances[
                existing_instance_name
            ].steamcmd_install_path
        )
        existing_instance_steam_client_integration = (
            self.settings_controller.settings.instances[
                existing_instance_name
            ].steam_client_integration
        )
        # Sanitize the input so that it does not produce any KeyError down the road
        new_instance_name = self.__ask_for_new_instance_name()
        if (
            new_instance_name
            and new_instance_name != "Default"
            and new_instance_name not in current_instances
        ):
            new_instance_path = str(
                Path(AppInfo().app_storage_folder) / "实例" / new_instance_name
            )
            # Prompt user with the existing instance configuration and confirm that they would like to clone it
            answer = show_dialogue_confirmation(
                title=f"克隆实例[{existing_instance_name}]",
                text=f"是否要克隆实例[{existing_instance_name}]以创建新实例[{new_instance_name}]?\n"
                + "这将克隆实例的数据!"
                + "\n\n",
                information=f"游戏文件夹:\n{existing_instance_game_folder if existing_instance_game_folder else '<None>'}\n"
                + f"\n本地文件夹:\n{existing_instance_local_folder if existing_instance_local_folder else '<None>'}\n"
                + f"\n创意工坊文件夹:\n{existing_instance_workshop_folder if existing_instance_workshop_folder else '<None>'}\n"
                + f"\n配置文件夹:\n{existing_instance_config_folder if existing_instance_config_folder else '<None>'}\n"
                + f"\n运行参数:\n{'[' + ' '.join(existing_instance_run_args) + ']' if existing_instance_run_args else '<None>'}\n"
                + "\nSteamCMD 安装路径（steamcmd + steam 文件夹将被克隆）:"
                + f"\n{existing_instance_steamcmd_install_path if existing_instance_steamcmd_install_path else '<None>'}\n",
            )
            if answer == "&Yes":
                target_game_folder = str(Path(new_instance_path) / game_folder_name)
                target_local_folder = str(
                    Path(new_instance_path) / game_folder_name / local_folder_name
                )
                target_workshop_folder = ""
                target_config_folder = str(
                    Path(new_instance_path) / "InstanceData" / "Config"
                )
                self.main_content_panel.do_threaded_loading_animation(
                    gif_path=str(
                        AppInfo().theme_data_folder / "default-icons" / "rimworld.gif"
                    ),
                    target=partial(
                        clone_essential_paths,
                        existing_instance_game_folder,
                        target_game_folder,
                        existing_instance_config_folder,
                        target_config_folder,
                    ),
                    text=f"将 RimWorld 游戏/配置文件夹从[{existing_instance_name}]实例克隆到[{new_instance_name}]实例...",
                )
                # Clone the existing local_folder to the new instance
                if existing_instance_local_folder:
                    if os.path.exists(existing_instance_local_folder) and os.path.isdir(
                        existing_instance_local_folder
                    ):
                        self.main_content_panel.do_threaded_loading_animation(
                            gif_path=str(
                                AppInfo().theme_data_folder
                                / "default-icons"
                                / "rimworld.gif"
                            ),
                            target=partial(
                                copy_local_folder,
                                existing_instance_local_folder,
                                target_local_folder,
                            ),
                            text=f"将本地模组文件夹从[{existing_instance_name}]实例克隆到[{new_instance_name}]实例...",
                        )
                # Clone the existing workshop_folder to the new instance's local mods folder
                if existing_instance_workshop_folder:
                    # Prompt user to confirm before initiating the procedure
                    answer = self.__ask_how_to_workshop_mods(
                        existing_instance_name=existing_instance_name,
                        existing_instance_workshop_folder=existing_instance_workshop_folder,
                    )
                    if answer == "转换为SteamCMD":
                        if os.path.exists(
                            existing_instance_workshop_folder
                        ) and os.path.isdir(existing_instance_workshop_folder):
                            self.main_content_panel.do_threaded_loading_animation(
                                gif_path=str(
                                    AppInfo().theme_data_folder
                                    / "default-icons"
                                    / "steam_api.gif"
                                ),
                                target=partial(
                                    copy_workshop_mods_to_local,
                                    existing_instance_workshop_folder,
                                    target_local_folder,
                                ),
                                text=f"将创意工坊从[{existing_instance_name}]实例克隆到[{new_instance_name}]实例的本地模组...",
                            )
                        else:
                            show_warning(
                                title="未找到创意工坊模组",
                                text=f"找不到[{existing_instance_workshop_folder}]处的创意工坊模组文件夹。",
                            )
                    elif answer == "保留创意工坊文件夹":
                        target_workshop_folder = str(existing_instance_workshop_folder)
                # If the instance has a 'steamcmd' folder, clone it to the new instance
                steamcmd_install_path = str(
                    Path(existing_instance_steamcmd_install_path) / "steamcmd"
                )
                if os.path.exists(steamcmd_install_path) and os.path.isdir(
                    steamcmd_install_path
                ):
                    target_steamcmd_install_path = str(
                        Path(new_instance_path) / "steamcmd"
                    )
                    if os.path.exists(target_steamcmd_install_path) and os.path.isdir(
                        target_steamcmd_install_path
                    ):
                        logger.info(
                            f"替换{target_steamcmd_install_path}处的已存在steamcmd文件夹"
                        )
                        rmtree(target_steamcmd_install_path)
                    logger.info(
                        f"将steamcmd文件夹从 {steamcmd_install_path} 复制到 {target_steamcmd_install_path}"
                    )
                    copytree(
                        steamcmd_install_path,
                        target_steamcmd_install_path,
                        symlinks=True,
                    )
                # If the instance has a 'steam' folder, clone it to the new instance
                steam_install_path = str(
                    Path(existing_instance_steamcmd_install_path) / "steam"
                )
                if os.path.exists(steam_install_path) and os.path.isdir(
                    steam_install_path
                ):
                    target_steam_install_path = str(Path(new_instance_path) / "steam")
                    if os.path.exists(target_steam_install_path) and os.path.isdir(
                        target_steam_install_path
                    ):
                        logger.info(
                            f"替换{target_steam_install_path}处的已存在 Steam 文件夹"
                        )
                        rmtree(target_steam_install_path)
                    logger.info(
                        f"将steam文件夹从{steam_install_path}复制到{target_steam_install_path}"
                    )
                    copytree(
                        steam_install_path, target_steam_install_path, symlinks=True
                    )
                    # Unlink steam/workshop/content/294100 symlink if it exists, and relink it to our new target local mods folder
                    link_path = str(
                        Path(target_steam_install_path)
                        / "steamapps"
                        / "workshop"
                        / "content"
                        / "294100"
                    )
                    self.steamcmd_wrapper.check_symlink(link_path, target_local_folder)
                # Create the new instance for our cloned instance
                self.__create_new_instance(
                    instance_name=new_instance_name,
                    instance_data={
                        "game_folder": target_game_folder,
                        "local_folder": target_local_folder,
                        "workshop_folder": target_workshop_folder,
                        "config_folder": target_config_folder,
                        "run_args": existing_instance_run_args or [],
                        "steamcmd_install_path": str(
                            AppInfo().app_storage_folder
                            / "instances"
                            / new_instance_name
                        ),
                        "steam_client_integration": existing_instance_steam_client_integration,
                    },
                )
        elif new_instance_name:
            show_warning(
                title="克隆实例时出错",
                text="无法克隆实例。",
                information="请输入有效且唯一的实例名称。它不能是“默认”或空。",
            )
        else:
            logger.debug("用户取消克隆操作")

    def __create_new_instance(
        self, instance_name: str = "", instance_data: dict[str, Any] = {}
    ) -> None:
        if not instance_name:
            # Sanitize the input so that it does not produce any KeyError down the road
            new_instance_name = self.__ask_for_new_instance_name()
            if not new_instance_name:
                logger.info("用户取消操作")
                return
            instance_name = new_instance_name
        current_instances = list(self.settings_controller.settings.instances.keys())
        if (
            instance_name
            and instance_name != "Default"
            and instance_name not in current_instances
        ):
            if not instance_data:
                instance_data = {}
            # Create new instance folder if it does not exist
            instance_path = str(
                Path(AppInfo().app_storage_folder) / "instances" / instance_name
            )
            if not os.path.exists(instance_path):
                os.makedirs(instance_path)
            # Get run args from instance data, autogenerate additional config items if desired
            run_args = []
            generated_instance_run_args = []
            if instance_data.get("game_folder") and instance_data.get("config_folder"):
                # Prompt the user if they would like to automatically generate run args for the instance
                answer = show_dialogue_conditional(
                    title=f"创建新实例[{instance_name}]",
                    text="是否要为新实例自动生成运行参数？",
                    information="这将尝试根据配置的游戏/配置文件夹为新实例生成运行参数。",
                )
                if answer == "&Yes":
                    # Append new run args to the existing run args
                    generated_instance_run_args = [
                        "-logfile",
                        str(Path(instance_path) / "RimWorld.log"),
                        f'-savedatafolder={str(Path(instance_path) / "InstanceData")}',
                    ]
                run_args.extend(generated_instance_run_args)
                run_args.extend(instance_data.get("run_args", []))
            # Add new instance to Settings
            self.settings_controller.create_instance(
                instance_name=instance_name,
                game_folder=instance_data.get("game_folder", ""),
                local_folder=instance_data.get("local_folder", ""),
                workshop_folder=instance_data.get("workshop_folder", ""),
                config_folder=instance_data.get("config_folder", ""),
                run_args=run_args,
                steamcmd_install_path=instance_path,
                steam_client_integration=instance_data.get(
                    "steam_client_integration", False
                ),
            )

            # Save settings
            self.settings_controller.settings.save()
            # Switch to new instance and initialize content
            self.__switch_to_instance(instance_name)
        else:
            show_warning(
                title="创建实例时出错",
                text="无法创建新实例。",
                information="请输入有效且唯一的实例名称。它不能是“默认”或空。",
            )

    def __delete_current_instance(self) -> None:
        if self.settings_controller.settings.current_instance == "Default":
            show_warning(
                title="删除实例时出现问题",
                text=f"无法删除实例 {self.settings_controller.settings.current_instance} 。",
                information="无法删除默认实例。",
            )
            return
        elif not self.settings_controller.settings.instances.get(
            self.settings_controller.settings.current_instance
        ):
            show_fatal_error(
                title="删除实例时出错",
                text=f"无法删除实例 {self.settings_controller.settings.current_instance} 。",
                information="所选实例不存在。",
            )
            return
        else:
            answer = show_dialogue_confirmation(
                title=f"删除实例{self.settings_controller.settings.current_instance}",
                text="是否确实要删除所选实例及其所有数据？",
                information="此操作无法撤消。",
            )
            if answer == "&Yes":
                try:
                    rmtree(
                        str(
                            Path(
                                AppInfo().app_storage_folder
                                / "实例"
                                / self.settings_controller.settings.current_instance
                            )
                        )
                    )
                except Exception as e:
                    logger.error(f"删除实例时出错: {e}")
                # Remove instance from settings and reset to Default
                self.settings_controller.settings.instances.pop(
                    self.settings_controller.settings.current_instance
                )
                self.__switch_to_instance("默认")

    def __switch_to_instance(self, instance: str) -> None:
        self.stop_watchdog_if_running()
        # Set current instance
        self.settings_controller.settings.current_instance = instance
        # Save settings
        self.settings_controller.settings.save()
        # Initialize content
        self.initialize_content(is_initial=False)

    def initialize_watchdog(self) -> None:
        logger.info("初始化文件系统观察者")
        # INITIALIZE WATCHDOG - WE WAIT TO START UNTIL DONE PARSING MOD LIST
        # Instantiate event handler
        # Pass a mapper of metadata-containing About.xml or Scenario.rsc files to their mod uuids
        current_instance = self.settings_controller.settings.current_instance
        self.watchdog_event_handler = WatchdogHandler(
            settings_controller=self.settings_controller,
            targets=[
                str(
                    Path(
                        self.settings_controller.settings.instances[
                            current_instance
                        ].game_folder
                    )
                    / "Data"
                ),
                self.settings_controller.settings.instances[
                    current_instance
                ].local_folder,
                self.settings_controller.settings.instances[
                    current_instance
                ].workshop_folder,
            ],
        )
        # Connect watchdog to MetadataManager
        self.watchdog_event_handler.mod_created.connect(
            self.main_content_panel.metadata_manager.process_creation
        )
        self.watchdog_event_handler.mod_deleted.connect(
            self.main_content_panel.metadata_manager.process_deletion
        )
        self.watchdog_event_handler.mod_updated.connect(
            self.main_content_panel.metadata_manager.process_update
        )
        # Connect main content signal so it can stop watchdog
        self.main_content_panel.stop_watchdog_signal.connect(self.shutdown_watchdog)
        # Start watchdog
        try:
            if self.watchdog_event_handler.watchdog_observer is not None:
                self.watchdog_event_handler.watchdog_observer.start()  # type: ignore #Upstream not typed
            else:
                logger.warning("文件系统观察者为空，无法启动")
        except Exception as e:
            logger.warning(
                f"由于异常，无法初始化文件系统观察者: {str(e)}"
            )

    def stop_watchdog_if_running(self) -> None:
        # STOP WATCHDOG IF IT IS ALREADY RUNNING
        if (
            self.watchdog_event_handler
            and self.watchdog_event_handler.watchdog_observer
            and self.watchdog_event_handler.watchdog_observer.is_alive()
        ):
            self.shutdown_watchdog()

    def shutdown_watchdog(self) -> None:
        if (
            self.watchdog_event_handler
            and self.watchdog_event_handler.watchdog_observer
            and self.watchdog_event_handler.watchdog_observer.is_alive()
        ):
            self.watchdog_event_handler.watchdog_observer.stop()  # type: ignore #Upstream not typed
            self.watchdog_event_handler.watchdog_observer.join()
            self.watchdog_event_handler.watchdog_observer = None
            for timer in self.watchdog_event_handler.cooldown_timers.values():
                timer.cancel()
            self.watchdog_event_handler = None
