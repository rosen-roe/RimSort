import os
import platform
import shutil
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Optional
from zipfile import ZipFile

import requests
from loguru import logger

from app.utils.event_bus import EventBus
from app.utils.system_info import SystemInfo
from app.views.dialogue import (
    show_dialogue_conditional,
    show_fatal_error,
    show_warning,
)
from app.windows.runner_panel import RunnerPanel


class SteamcmdInterface:
    """
    Create SteamcmdInterface object to provide an interface for SteamCMD functionality
    """

    _instance: Optional["SteamcmdInterface"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "SteamcmdInterface":
        if cls._instance is None:
            cls._instance = super(SteamcmdInterface, cls).__new__(cls)
        return cls._instance

    def __init__(self, steamcmd_prefix: str, validate: bool) -> None:
        if not hasattr(self, "初始化"):
            self.initialized = True
            self.setup = False
            self.steamcmd_prefix = steamcmd_prefix
            super(SteamcmdInterface, self).__init__()
            logger.debug("初始化 Steamcmd 接口")
            self.initialize_prefix(steamcmd_prefix, validate)
            logger.debug("完成 Steamcmd 接口初始化")

    def initialize_prefix(self, steamcmd_prefix: str, validate: bool) -> None:
        self.steamcmd_prefix = steamcmd_prefix
        self.steamcmd_install_path = str(Path(self.steamcmd_prefix) / "steamcmd")
        self.steamcmd_steam_path = str(Path(self.steamcmd_prefix) / "steam")
        self.system = platform.system()
        self.validate_downloads = validate

        if self.system == "Darwin":
            self.steamcmd_url = (
                "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_osx.tar.gz"
            )
            self.steamcmd = str((Path(self.steamcmd_install_path) / "steamcmd.sh"))
        elif self.system == "Linux":
            self.steamcmd_url = (
                "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
            )
            self.steamcmd = str((Path(self.steamcmd_install_path) / "steamcmd.sh"))
        elif self.system == "Windows":
            self.steamcmd_url = (
                "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
            )
            self.steamcmd = str((Path(self.steamcmd_install_path) / "steamcmd.exe"))
        else:
            show_fatal_error(
                "SteamcmdInterface",
                f"找到平台 {self.system} 。此平台不支持 Steamcmd 。",
            )
            return

        if not os.path.exists(self.steamcmd_install_path):
            os.makedirs(self.steamcmd_install_path)
            logger.debug(
                f"SteamCMD 不存在。创建安装路径: {self.steamcmd_install_path}"
            )

        if not os.path.exists(self.steamcmd_steam_path):
            os.makedirs(self.steamcmd_steam_path)
        self.steamcmd_appworkshop_acf_path = str(
            (
                Path(self.steamcmd_steam_path)
                / "steamapps"
                / "workshop"
                / "appworkshop_294100.acf"
            )
        )
        self.steamcmd_content_path = str(
            (Path(self.steamcmd_steam_path) / "steamapps" / "workshop" / "content")
        )

    @classmethod
    def instance(cls, *args: Any, **kwargs: Any) -> "SteamcmdInterface":
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        elif args or kwargs:
            raise ValueError("Steamcmd 接口实例已经初始化。")
        return cls._instance

    def check_symlink(self, link_path: str, target_local_folder: str) -> None:
        """Checks if the link path exists. If it does, recreate the link/junction to target_local_folder.
        Otherwise, create the link/junction.

        Requires the root of the link_path to exist.

        :param link_path: Where the symlink should be created
        :type link_path: str
        :param target_local_folder: Where the symlink/junction should point to
        :type target_local_folder: str
        """
        logger.debug(
            "检查 SteamCMD <-> Local mods 符号链接，如果存在，请重新创建"
        )
        logger.debug(f"链接路径: {link_path}")
        if os.path.exists(link_path):
            logger.debug(
                f"删除 {link_path} 处的现有链接并重新创建指向 {target_local_folder} 的链接"
            )
            # Remove by type
            if os.path.islink(link_path) or os.path.ismount(link_path):
                os.unlink(link_path)
            elif os.path.isdir(link_path):
                os.rmdir(link_path)
            else:
                os.remove(link_path)
        # Recreate the link
        if SystemInfo().operating_system != SystemInfo.OperatingSystem.WINDOWS:
            os.symlink(
                target_local_folder,
                link_path,
                target_is_directory=True,
            )
        elif sys.platform == "win32":
            from _winapi import CreateJunction

            CreateJunction(target_local_folder, link_path)

    def download_mods(self, publishedfileids: list[str], runner: RunnerPanel) -> None:
        """
        This function downloads a list of mods from a list publishedfileids

        https://developer.valvesoftware.com/wiki/SteamCMD

        :param appid: a Steam AppID to pass to steamcmd
        :param publishedfileids: list of publishedfileids
        :param runner: a RimSort RunnerPanel to interact with
        """
        runner.message("Checking for steamcmd...")
        if self.setup:
            runner.message(
                f"接受: {self.steamcmd}\n"
                + f"下载目录 {str(len(publishedfileids))} "
                + f"已发布的文件ID 路径设置为: {self.steamcmd_steam_path}"
            )
            script = [
                f'force_install_dir "{self.steamcmd_steam_path}"',
                "匿名登录",
            ]
            download_cmd = "workshop_download_item 294100"
            for publishedfileid in publishedfileids:
                if self.validate_downloads:
                    script.append(f"{download_cmd} {publishedfileid} 验证")
                else:
                    script.append(f"{download_cmd} {publishedfileid}")
            script.extend(["退出\n"])
            script_path = str((Path(gettempdir()) / "steamcmd_script.txt"))
            with open(script_path, "w", encoding="utf-8") as script_output:
                script_output.write("\n".join(script))
            runner.message(f"编译和使用脚本: {script_path}")
            runner.execute(
                self.steamcmd,
                [f'+运行脚本 "{script_path}"'],
                len(publishedfileids),
            )
        else:
            runner.message("找不到 SteamCMD。请先安装 SteamCMD！")
            self.on_steamcmd_not_found(runner=runner)

    def check_for_steamcmd(self, prefix: str) -> bool:
        executable_name = os.path.split(self.steamcmd)[1] if self.steamcmd else None
        if executable_name is None:
            return False
        return os.path.exists(str(Path(prefix) / "steamcmd" / executable_name))

    def on_steamcmd_not_found(self, runner: RunnerPanel | None = None) -> None:
        answer = show_dialogue_conditional(
            title="RimSort - SteamCMD 安装",
            text="RimSort 无法找到配置的前缀中安装的 SteamCMD:\n",
            information=f"{self.steamcmd_prefix if self.steamcmd_prefix else '<None>'}\n\n"
            + "您想安装 SteamCMD 吗？",
        )
        if answer == "&Yes":
            EventBus().do_install_steamcmd.emit()
        if runner:
            runner.close()

    def setup_steamcmd(
        self, symlink_source_path: str, reinstall: bool, runner: RunnerPanel
    ) -> None:
        installed = None
        if reinstall:
            runner.message("找到现有的 steamcmd 安装！")
            runner.message(
                f"正在删除现有安装: {self.steamcmd_install_path}"
            )
            shutil.rmtree(self.steamcmd_install_path)
            os.makedirs(self.steamcmd_install_path)
        if not self.check_for_steamcmd(prefix=self.steamcmd_prefix):
            try:
                runner.message(
                    f"正在下载并解压steamcmd发行版: {self.steamcmd_url}"
                )
                if ".zip" in self.steamcmd_url:
                    with ZipFile(
                        BytesIO(requests.get(self.steamcmd_url).content)
                    ) as zipobj:
                        zipobj.extractall(self.steamcmd_install_path)
                    runner.message("安装完成")
                    installed = True
                elif ".tar.gz" in self.steamcmd_url:
                    with (
                        requests.get(self.steamcmd_url, stream=True) as rx,
                        tarfile.open(fileobj=rx.raw, mode="r:gz") as tarobj,
                    ):
                        tarobj.extractall(self.steamcmd_install_path)
                    runner.message("安装完成")
                    installed = True
            except Exception as e:
                runner.message("Installation failed")
                show_fatal_error(
                    "SteamcmdInterface",
                    f"Failed to download steamcmd for {self.system}",
                    "Did the file/url change?\nDoes your environment have access to the internet?",
                    details=f"Error: {type(e).__name__}: {str(e)}",
                )
        else:
            runner.message("SteamCMD 已安装...")
            show_warning(
                "SteamcmdInterface",
                f"steamcmd 运行器已存在于: {self.steamcmd}",
            )
            answer = show_dialogue_conditional(
                "重新安装?",
                "您想重新安装 SteamCMD 吗？",
                f"现有的安装: {self.steamcmd_install_path}",
            )
            if answer == "&Yes":
                runner.message(f"重新安装 SteamCMD: {self.steamcmd_install_path}")
                self.setup_steamcmd(symlink_source_path, True, runner)
        if installed:
            if not os.path.exists(self.steamcmd_content_path):
                os.makedirs(self.steamcmd_content_path)
                runner.message(
                    f"创意工坊内容路径不存在。创建符号链接:\n\n{self.steamcmd_content_path}\n"
                )
            symlink_destination_path = str(
                (Path(self.steamcmd_content_path) / "294100")
            )
            runner.message(f"符号链接源 : {symlink_source_path}")
            runner.message(f"符号链接目标: {symlink_destination_path}")
            if os.path.exists(symlink_destination_path):
                runner.message(
                    f"符号链接目标已经存在！请删除现有目的地:\n\n{symlink_destination_path}\n"
                )
            else:
                answer = show_dialogue_conditional(
                    "创建符号链接？",
                    "是否要按如下方式创建符号链接？",
                    f"[{symlink_source_path}] -> " + symlink_destination_path,
                )
                if answer == "&Yes":
                    try:
                        runner.message(
                            f"[{symlink_source_path}] -> " + symlink_destination_path
                        )
                        if os.path.exists(symlink_destination_path):
                            logger.debug(
                                f"删除 {symlink_destination_path} 处的现有链接并重新创建指向  {symlink_source_path} 的链接"
                            )
                            # Remove by type
                            if os.path.islink(
                                symlink_destination_path
                            ) or os.path.ismount(symlink_destination_path):
                                os.unlink(symlink_destination_path)
                            elif os.path.isdir(symlink_destination_path):
                                os.rmdir(symlink_destination_path)
                            else:
                                os.remove(symlink_destination_path)
                        if self.system != "Windows":
                            os.symlink(
                                symlink_source_path,
                                symlink_destination_path,
                                target_is_directory=True,
                            )
                        elif sys.platform == "win32":
                            from _winapi import CreateJunction

                            CreateJunction(
                                symlink_source_path, symlink_destination_path
                            )
                        self.setup = True
                    except Exception as e:
                        runner.message(
                            f"无法创建符号链接。错误: {type(e).__name__}: {str(e)}"
                        )
                        show_fatal_error(
                            "SteamcmdInterface",
                            f"无法为 {self.system}创建符号链接",
                            f"错误: {type(e).__name__}: {str(e)}",
                        )


if __name__ == "__main__":
    sys.exit()
