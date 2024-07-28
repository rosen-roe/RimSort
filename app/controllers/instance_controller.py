import os
import shutil
from pathlib import Path
from traceback import format_exc
from typing import Any, Callable, Self
from zipfile import ZipFile

import msgspec
from loguru import logger
from PySide6.QtCore import QObject

from app.models.instance import Instance
from app.utils.app_info import AppInfo
from app.views.dialogue import (
    show_fatal_error,
    show_warning,
)


class InvalidArchivePathError(ValueError):
    """Raised when the provided archive path is invalid"""

    def __init__(self, archive_path: str) -> None:
        super().__init__(f"存档路径无效: {archive_path}")


class InstanceController(QObject):
    """Controller for an Instance"""

    instance: Instance
    valid: bool = True

    @classmethod
    def _validate_archive_path(cls, archive_path: str) -> bool:
        """Validate the archive path"""
        # Check if the archive exists and is zip
        if not Path(archive_path).exists() or not archive_path.endswith(".zip"):
            return False
        return True

    def __new__(cls, instance: Instance | str) -> Self:
        if isinstance(instance, str):
            if not cls._validate_archive_path(instance):
                logger.error(f"存档路径无效: {instance}")
                show_warning(
                    title="存档路径无效",
                    text="提供的存档路径无效。",
                    information="请提供有效的存档路径。",
                )

                raise InvalidArchivePathError("存档路径无效")
        return super().__new__(cls)

    def __init__(self, instance: Instance | str):
        if isinstance(instance, str):
            self._init_from_archive(instance)
        else:
            self.instance = instance

    def _init_from_archive(self, archive_path: str) -> None:
        """Initialize the instance from the provided archive"""
        try:
            with ZipFile(archive_path, "r") as archive:
                self.from_bytes(archive.read("instance.json"))
        except Exception as e:
            logger.error(f"读取实例存档时出错: {e}")
            show_fatal_error(
                title="还原实例时出错",
                text=f"读取实例存档时出错: {e}",
                details=format_exc(),
            )

    def create_instance(
        self,
        instance_name: str,
        game_folder: str = "",
        config_folder: str = "",
        local_folder: str = "",
        workshop_folder: str = "",
        run_args: list[str] = [],
        steamcmd_install_path: str = "",
        steam_client_integration: bool = False,
    ) -> Instance:
        """
        Set the instance with the provided name and paths.
        """
        return Instance(
            name=instance_name,
            game_folder=game_folder,
            config_folder=config_folder,
            local_folder=local_folder,
            workshop_folder=workshop_folder,
            run_args=run_args,
            steamcmd_install_path=steamcmd_install_path,
            steam_client_integration=steam_client_integration,
        )

    def extract_from_archive(self, archive_path: str, delete_old: bool = True) -> None:
        """Extract the instance folder from the provided archive

        Will overwrite the instance folder if it already exists.

        :param archive_path: The path to the archive to extract
        :type archive_path: str
        """
        logger.info(f"从存档中提取实例文件夹: {archive_path}")
        # Extract instance folder from archive.
        # Parse the "instance.json" file to get the instance data.
        # Use the "name" key from the instance data to use as the instance folder.
        # Replace if exists.

        if os.path.exists(self.instance_folder_path) and delete_old:
            logger.info(
                "删除现有实例文件夹: {self.instance_folder_path}"
            )

            def ignore_extended_attributes(
                func: Callable[[Any], Any], filename: str, exc_info: Any
            ) -> None:
                is_meta_file = os.path.basename(filename).startswith("._")
                if not (func is os.unlink and is_meta_file):
                    raise

            try:
                shutil.rmtree(
                    self.instance_folder_path, onerror=ignore_extended_attributes
                )
            except Exception as e:
                logger.error(
                    f"删除现有实例文件夹时出错: {e}"
                )

        try:
            logger.info(f"从存档中提取实例文件夹: {archive_path}")
            logger.info(f"目标实例文件夹: {self.instance_folder_path}")
            with ZipFile(archive_path, "r") as archive:
                for info in archive.infolist():
                    if info.filename == "instance.json":
                        continue
                    logger.debug(f"正在提取文件: {info.filename}")
                    archive.extract(info, path=self.instance_folder_path)
        except Exception as e:
            logger.error(f"解压实例文件夹时出错: {e}")

    def compress_to_archive(self, output_path: str) -> None:
        # Compress instance folder to archive.
        # Preserve folder structure.
        # Overwrite if exists.
        if not output_path.endswith(".zip"):
            output_path += ".zip"

        try:
            logger.info(f"压缩实例文件夹存档: {output_path}")
            with ZipFile(output_path, "w") as archive:
                for root, dirs, files in os.walk(
                    self.instance_folder_path, topdown=True, followlinks=False
                ):
                    # Skip windows junctions (and symlinks)
                    if Path(root).absolute() != Path(root).resolve():
                        logger.debug(f"跳过符号链接目录: {root}")
                        # Prune the search
                        dirs.clear()
                        files.clear()
                        continue
                    for _dir in dirs:
                        dir_path = os.path.join(root, _dir)
                        archive.write(
                            dir_path,
                            os.path.relpath(dir_path, self.instance_folder_path),
                        )
                        logger.debug(f"将目录添加到存档中: {dir_path}")
                    for file in files:
                        file_path = os.path.join(root, file)
                        archive.write(
                            file_path,
                            os.path.relpath(file_path, self.instance_folder_path),
                        )
                        logger.debug(f"已将文件添加到存档: {file_path}")
                archive.writestr("instance.json", self.to_bytes())
                logger.debug(f"已将实例数据添加到存档: {self.instance}")
        except Exception as e:
            logger.error(f"压缩实例文件夹时出错: {e}")

    def validate_paths(self) -> list[str]:
        """Verify the paths of the instance

        :return: A list of invalid paths
        :rtype: list[str]
        """
        cleared_paths = self.instance.validate_paths()
        if "steamcmd_install_path" in cleared_paths:
            if os.path.exists(self.instance_folder_path / "steamcmd"):
                self.instance.steamcmd_install_path = str(self.instance_folder_path)

        return cleared_paths

    @property
    def instance_folder_path(self) -> Path:
        return AppInfo().app_storage_folder / "instances" / self.instance.name

    def to_bytes(self) -> bytes:
        """Encodes the instance to a JSON formatted bytes

        :return: The JSON formatted bytes
        :rtype: bytes
        """
        return msgspec.json.encode(self.instance)

    def from_bytes(self, instance_bytes: bytes) -> Instance:
        """Decodes the provided JSON formatted bytes to an instance

        Sets the controller instance to the decoded instance.
        :param instance_bytes: The JSON formatted bytes to be decoded
        :type instance_bytes: bytes
        :return: The decoded instance
        :rtype: Instance
        """
        self.instance = msgspec.json.decode(instance_bytes, type=Instance)
        return self.instance
