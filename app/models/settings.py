import json
from json import JSONDecodeError
from os import path, rename
from pathlib import Path
from shutil import copytree, rmtree
from time import time
from typing import Any, Dict

from loguru import logger
from PySide6.QtCore import QObject

from app.models.instance import Instance
from app.utils.app_info import AppInfo
from app.utils.event_bus import EventBus


class Settings(QObject):
    def __init__(self) -> None:
        super().__init__()

        self._settings_file = AppInfo().app_storage_folder / "settings.json"
        self._debug_file = AppInfo().app_storage_folder / "DEBUG"

        self._debug_logging_enabled: bool = False
        self._check_for_update_startup: bool = False
        self._show_folder_rows: bool = False
        self._sorting_algorithm: str = ""
        self._external_steam_metadata_file_path: str = ""
        self._external_steam_metadata_repo: str = ""
        self._external_steam_metadata_source: str = ""
        self._external_community_rules_file_path: str = ""
        self._external_community_rules_repo: str = ""
        self._external_community_rules_metadata_source: str = ""
        self._db_builder_include: str = ""
        self._database_expiry: int = 0
        self._build_steam_database_dlc_data: bool = False
        self._build_steam_database_update_toggle: bool = False
        self._watchdog_toggle: bool = False
        self._mod_type_filter_toggle: bool = False
        self._duplicate_mods_warning: bool = False
        self._steam_mods_update_check: bool = False
        self._try_download_missing_mods: bool = False
        self._steamcmd_validate_downloads: bool = False
        self._todds_preset: str = ""
        self._todds_active_mods_target: bool = False
        self._todds_dry_run: bool = False
        self._todds_overwrite: bool = False
        self._current_instance: str = "Default"
        self._instances: dict[str, Instance] = {}
        self._github_username: str = ""
        self._github_token: str = ""
        self._steam_apikey: str = ""
        self.apply_default_settings()

    def apply_default_settings(self) -> None:
        self._debug_logging_enabled = False
        self._check_for_update_startup = False
        self._show_folder_rows = True
        self._sorting_algorithm = "Alphabetical"
        self._external_steam_metadata_file_path = str(
            AppInfo().app_storage_folder / "steamDB.json"
        )
        self._external_steam_metadata_repo = (
            "https://github.com/RimSort/Steam-Workshop-Database"
        )
        self._external_steam_metadata_source = "None"
        self._external_community_rules_file_path = str(
            AppInfo().app_storage_folder / "communityRules.json"
        )
        self._external_community_rules_repo = (
            "https://github.com/RimSort/Community-Rules-Database"
        )
        self.database_expiry: int = 604800  # 7 days

        # Sorting
        self.sorting_algorithm: SortMethod = SortMethod.TOPOLOGICAL

        # DB Builder
        self.db_builder_include: str = "all_mods"
        self.build_steam_database_dlc_data: bool = True
        self.build_steam_database_update_toggle: bool = False
        self.steam_apikey: str = ""

        # SteamCMD
        self.steamcmd_validate_downloads: bool = True

        # todds
        self.todds_preset: str = "optimized"
        self.todds_active_mods_target: bool = True
        self.todds_dry_run: bool = False
        self.todds_overwrite: bool = False

        # Advanced
        self.debug_logging_enabled: bool = False
        self.watchdog_toggle: bool = True
        self.mod_type_filter_toggle: bool = True
        self.duplicate_mods_warning: bool = False
        self.steam_mods_update_check: bool = False
        self.try_download_missing_mods: bool = False

        self.github_username: str = ""
        self.github_token: str = ""

        # Instances
        self.current_instance: str = "Default"
        self.instances: dict[str, Instance] = {"Default": Instance()}

    def __setattr__(self, key: str, value: Any) -> None:
        # If private attribute, set it normally
        if key.startswith("_"):
            super().__setattr__(key, value)
            return
        self._github_token = value
        EventBus().settings_have_changed.emit()

    @property
    def steam_apikey(self) -> str:
        return self._steam_apikey

    @steam_apikey.setter
    def steam_apikey(self, value: str) -> None:
        if value == self._steam_apikey:
            return
        self._steam_apikey = value
        EventBus().settings_have_changed.emit()

    def load(self) -> None:
        if self._debug_file.exists() and self._debug_file.is_file():
            self._debug_logging_enabled = True
        else:
            self._debug_logging_enabled = False

        try:
            with open(str(self._settings_file), "r") as file:
                data = json.load(file)
                mitigations = (
                    True  # Assume there are mitigations unless we reach else block
                )
                # Mitigate issues when "instances" key is not parsed, but the old path attributes are present
                if not data.get("instances"):
                    logger.debug(
                        "在 settings.json 中找不到实例key。执行缓解措施。"
                    )
                    steamcmd_prefix_default_instance_path = str(
                        Path(AppInfo().app_storage_folder / "instances" / "Default")
                    )
                    # Create Default instance
                    data["instances"] = {
                        "Default": Instance(
                            name="Default",
                            game_folder=data.get("game_folder", ""),
                            local_folder=data.get("local_folder", ""),
                            workshop_folder=data.get("workshop_folder", ""),
                            config_folder=data.get("config_folder", ""),
                            run_args=data.get("run_args", []),
                            steamcmd_install_path=steamcmd_prefix_default_instance_path,
                            steam_client_integration=False,
                        )
                    }
                    steamcmd_prefix_to_mitigate = data.get("steamcmd_install_path", "")
                    steamcmd_path_to_mitigate = str(
                        Path(steamcmd_prefix_to_mitigate) / "steamcmd"
                    )
                    steam_path_to_mitigate = str(
                        Path(steamcmd_prefix_to_mitigate) / "steam"
                    )
                    if steamcmd_prefix_to_mitigate and path.exists(
                        steamcmd_prefix_to_mitigate
                    ):
                        logger.debug(
                            "找到已配置的 SteamCMD 安装路径。尝试将其迁移到默认实例路径..."
                        )
                        steamcmd_prefix_steamcmd_path = str(
                            Path(steamcmd_prefix_default_instance_path) / "steamcmd"
                        )
                        steamcmd_prefix_steam_path = str(
                            Path(steamcmd_prefix_default_instance_path) / "steam"
                        )
                        try:
                            if path.exists(steamcmd_prefix_steamcmd_path):
                                current_timestamp = int(time())
                                rename(
                                    steamcmd_prefix_steamcmd_path,
                                    f"{steamcmd_prefix_steamcmd_path}_{current_timestamp}",
                                )
                            elif path.exists(steamcmd_prefix_steam_path):
                                current_timestamp = int(time())
                                rename(
                                    steamcmd_prefix_steam_path,
                                    f"{steamcmd_prefix_steam_path}_{current_timestamp}",
                                )
                            logger.info(
                                f"将 SteamCMD 安装路径从 {steamcmd_prefix_to_mitigate} 迁移到 {steamcmd_prefix_default_instance_path}"
                            )
                            copytree(
                                steamcmd_path_to_mitigate,
                                steamcmd_prefix_steamcmd_path,
                                symlinks=True,
                            )
                            logger.info(
                                f"删除旧的 SteamCMD 安装路径 {steamcmd_path_to_mitigate}..."
                            )
                            rmtree(steamcmd_path_to_mitigate)
                            logger.info(
                                f"将 SteamCMD 数据路径从 {steam_path_to_mitigate} 迁移到 {steamcmd_prefix_default_instance_path}"
                            )
                            copytree(
                                steam_path_to_mitigate,
                                steamcmd_prefix_steam_path,
                                symlinks=True,
                            )
                            logger.info(
                                f"删除旧的 SteamCMD 数据路径 {steam_path_to_mitigate}..."
                            )
                            rmtree(steam_path_to_mitigate)
                        except Exception as e:
                            logger.error(
                                f"迁移 SteamCMD 安装路径失败。报错: {e}"
                            )
                elif (
                    not data.get("current_instance")
                    or data["current_instance"] not in data["instances"]
                ):
                    logger.debug(
                        "在 settings.json 中找不到当前实例。执行缓解措施。"
                    )
                    data["current_instance"] = "Default"
                else:
                    # There was nothing to mitigate, so don't save the model to the file
                    mitigations = False
                # Parse data from settings.json into the model
                self._from_dict(data)
                # Save the model to the file if there were mitigations
                if mitigations:
                    self.save()
        except FileNotFoundError:
            self.save()
        except JSONDecodeError:
            raise

    def save(self) -> None:
        if self._debug_logging_enabled:
            self._debug_file.touch(exist_ok=True)
        else:
            self._debug_file.unlink(missing_ok=True)

        with open(str(self._settings_file), "w") as file:
            json.dump(self._to_dict(), file, indent=4)

    def _from_dict(self, data: Dict[str, Any]) -> None:
        if "show_folder_rows" in data:
            self.show_folder_rows = data["show_folder_rows"]
            del data["show_folder_rows"]

        if "check_for_update_startup" in data:
            self.check_for_update_startup = data["check_for_update_startup"]
            del data["check_for_update_startup"]

        if "sorting_algorithm" in data:
            self.sorting_algorithm = data["sorting_algorithm"]
            del data["sorting_algorithm"]

        if "external_steam_metadata_file_path" in data:
            self.external_steam_metadata_file_path = data[
                "external_steam_metadata_file_path"
            ]
            del data["external_steam_metadata_file_path"]

        if "external_steam_metadata_repo" in data:
            self.external_steam_metadata_repo = data["external_steam_metadata_repo"]
            del data["external_steam_metadata_repo"]

        if "external_steam_metadata_source" in data:
            self.external_steam_metadata_source = data["external_steam_metadata_source"]
            del data["external_steam_metadata_source"]

        if "external_community_rules_file_path" in data:
            self.external_community_rules_file_path = data[
                "external_community_rules_file_path"
            ]
            del data["external_community_rules_file_path"]

        if "external_community_rules_repo" in data:
            self.external_community_rules_repo = data["external_community_rules_repo"]
            del data["external_community_rules_repo"]

        if "external_community_rules_metadata_source" in data:
            self.external_community_rules_metadata_source = data[
                "external_community_rules_metadata_source"
            ]
            del data["external_community_rules_metadata_source"]

        if "db_builder_include" in data:
            self.db_builder_include = data["db_builder_include"]
            del data["db_builder_include"]

        if "database_expiry" in data:
            self.database_expiry = data["database_expiry"]
            del data["database_expiry"]

        if "build_steam_database_dlc_data" in data:
            self.build_steam_database_dlc_data = data["build_steam_database_dlc_data"]
            del data["build_steam_database_dlc_data"]

        if "build_steam_database_update_toggle" in data:
            self.build_steam_database_update_toggle = data[
                "build_steam_database_update_toggle"
            ]
            del data["build_steam_database_update_toggle"]

        if "watchdog_toggle" in data:
            self.watchdog_toggle = data["watchdog_toggle"]
            del data["watchdog_toggle"]

        if "mod_type_filter_toggle" in data:
            self.mod_type_filter_toggle = data["mod_type_filter_toggle"]
            del data["mod_type_filter_toggle"]

        if "duplicate_mods_warning" in data:
            self.duplicate_mods_warning = data["duplicate_mods_warning"]
            del data["duplicate_mods_warning"]

        if "steam_mods_update_check" in data:
            self.steam_mods_update_check = data["steam_mods_update_check"]
            del data["steam_mods_update_check"]

        if "try_download_missing_mods" in data:
            self.try_download_missing_mods = data["try_download_missing_mods"]
            del data["try_download_missing_mods"]

        if "steamcmd_validate_downloads" in data:
            self.steamcmd_validate_downloads = data["steamcmd_validate_downloads"]
            del data["steamcmd_validate_downloads"]

        if "todds_preset" in data:
            self.todds_preset = data["todds_preset"]
            del data["todds_preset"]

        if "todds_active_mods_target" in data:
            self.todds_active_mods_target = data["todds_active_mods_target"]
            del data["todds_active_mods_target"]

        if "todds_dry_run" in data:
            self.todds_dry_run = data["todds_dry_run"]
            del data["todds_dry_run"]

        if "todds_overwrite" in data:
            self.todds_overwrite = data["todds_overwrite"]
            del data["todds_overwrite"]

        if "current_instance" in data:
            self.current_instance = data["current_instance"]
            del data["current_instance"]

        if "instances" in data:
            # Convert to Instance objects
            instances = {}
            for instance_name, instance_data in data["instances"].items():
                if isinstance(instance_data, Instance):
                    instances[instance_name] = instance_data
                elif isinstance(instance_data, dict):
                    instances[instance_name] = Instance(**instance_data)
                else:
                    logger.warning(
                        f" {instance_name} 的实例数据不是有效类型: {type(instance_data)}"
                    )
            self.instances = instances
            del data["instances"]

        if "github_username" in data:
            self.github_username = data["github_username"]
            del data["github_username"]

        if "github_token" in data:
            self.github_token = data["github_token"]
            del data["github_token"]

        if "steam_apikey" in data:
            self.steam_apikey = data["steam_apikey"]
            del data["steam_apikey"]

    def _to_dict(self) -> Dict[str, Any]:
        data = {
            "check_for_update_startup": self.check_for_update_startup,
            "show_folder_rows": self.show_folder_rows,
            "sorting_algorithm": self.sorting_algorithm,
            "external_steam_metadata_file_path": self.external_steam_metadata_file_path,
            "external_steam_metadata_repo": self.external_steam_metadata_repo,
            "external_steam_metadata_source": self.external_steam_metadata_source,
            "external_community_rules_file_path": self.external_community_rules_file_path,
            "external_community_rules_repo": self.external_community_rules_repo,
            "external_community_rules_metadata_source": self.external_community_rules_metadata_source,
            "db_builder_include": self.db_builder_include,
            "database_expiry": self.database_expiry,
            "build_steam_database_dlc_data": self.build_steam_database_dlc_data,
            "build_steam_database_update_toggle": self.build_steam_database_update_toggle,
            "watchdog_toggle": self.watchdog_toggle,
            "mod_type_filter_toggle": self.mod_type_filter_toggle,
            "duplicate_mods_warning": self.duplicate_mods_warning,
            "steam_mods_update_check": self.steam_mods_update_check,
            "try_download_missing_mods": self.try_download_missing_mods,
            "steamcmd_validate_downloads": self.steamcmd_validate_downloads,
            "todds_preset": self.todds_preset,
            "todds_active_mods_target": self.todds_active_mods_target,
            "todds_dry_run": self.todds_dry_run,
            "todds_overwrite": self.todds_overwrite,
            "current_instance": self.current_instance,
            "instances": {
                name: instance.as_dict() for name, instance in self.instances.items()
            },
            "github_username": self.github_username,
            "github_token": self.github_token,
            "steam_apikey": self.steam_apikey,
        }
        return data
