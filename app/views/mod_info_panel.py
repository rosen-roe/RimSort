import os
from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from app.models.image_label import ImageLabel
from app.models.scroll_label import ScrollLabel
from app.utils.app_info import AppInfo
from app.utils.metadata import MetadataManager


class ModInfo:
    """
    This class controls the layout and functionality for the
    mod information panel on the GUI.
    """

    def __init__(self) -> None:
        """
        Initialize the class.
        """
        logger.debug("初始化模组信息")

        # Cache MetadataManager instance
        self.metadata_manager = MetadataManager.instance()

        # Base layout type
        self.panel = QVBoxLayout()
        self.info_panel_frame = QFrame()

        # Child layouts
        self.info_layout = QVBoxLayout()
        self.image_layout = QHBoxLayout()
        self.image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mod_info_layout = QVBoxLayout()
        self.mod_info_name = QHBoxLayout()
        self.scenario_info_summary = QHBoxLayout()
        self.mod_info_package_id = QHBoxLayout()
        self.mod_info_authors = QHBoxLayout()
        self.mod_info_mod_version = QHBoxLayout()
        self.mod_info_supported_versions = QHBoxLayout()
        self.mod_info_path = QHBoxLayout()
        self.description_layout = QHBoxLayout()

        # Add child layouts to base
        self.info_layout.addLayout(self.image_layout, 50)
        self.info_layout.addLayout(self.mod_info_layout, 20)
        self.info_layout.addLayout(self.description_layout, 30)
        self.info_panel_frame.setLayout(self.info_layout)
        self.panel.addWidget(self.info_panel_frame)

        # Create widgets
        self.missing_image_path = str(
            AppInfo().theme_data_folder / "default-icons" / "missing.png"
        )
        self.rimsort_image_a_path = str(
            AppInfo().theme_data_folder / "default-icons" / "AppIcon_a.png"
        )
        self.rimsort_image_b_path = str(
            AppInfo().theme_data_folder / "default-icons" / "AppIcon_b.png"
        )
        self.scenario_image_path = str(
            AppInfo().theme_data_folder / "default-icons" / "rimworld.png"
        )
        self.preview_picture = ImageLabel()
        self.preview_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_picture.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.preview_picture.setMinimumSize(1, 1)
        self.preview_picture.setPixmap(
            QPixmap(self.rimsort_image_a_path).scaled(
                self.preview_picture.size(), Qt.AspectRatioMode.KeepAspectRatio
            )
        )
        self.mod_info_name_label = QLabel("名字:")
        self.mod_info_name_label.setObjectName("summaryLabel")
        self.mod_info_name_value = QLabel()
        self.mod_info_name_value.setObjectName("summaryValue")
        self.mod_info_name_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mod_info_name_value.setWordWrap(True)
        self.scenario_info_summary_label = QLabel("总结:")
        self.scenario_info_summary_label.setObjectName("summaryLabel")
        self.scenario_info_summary_value = QLabel()
        self.scenario_info_summary_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.scenario_info_summary_value.setWordWrap(True)
        self.mod_info_package_id_label = QLabel("ID:")
        self.mod_info_package_id_label.setObjectName("summaryLabel")
        self.mod_info_package_id_value = QLabel()
        self.mod_info_package_id_value.setObjectName("summaryValue")
        self.mod_info_package_id_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mod_info_package_id_value.setWordWrap(True)
        self.mod_info_author_label = QLabel("作者:")
        self.mod_info_author_label.setObjectName("summaryLabel")
        self.mod_info_author_value = QLabel()
        self.mod_info_author_value.setObjectName("summaryValue")
        self.mod_info_author_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mod_info_author_value.setWordWrap(True)
        self.mod_info_mod_version_label = QLabel("模组版本:")
        self.mod_info_mod_version_label.setObjectName("summaryLabel")
        self.mod_info_mod_version_value = QLabel()
        self.mod_info_mod_version_value.setObjectName("summaryValue")
        self.mod_info_mod_version_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mod_info_mod_version_value.setWordWrap(True)
        self.mod_info_supported_versions_label = QLabel("支持的版本:")
        self.mod_info_supported_versions_label.setObjectName("summaryLabel")
        self.mod_info_supported_versions_value = QLabel()
        self.mod_info_supported_versions_value.setObjectName("summaryValue")
        self.mod_info_path_label = QLabel("路径:")
        self.mod_info_path_label.setObjectName("summaryLabel")
        self.mod_info_path_value = QLabel()
        self.mod_info_path_value.setObjectName("summaryValue")
        self.mod_info_path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mod_info_path_value.setWordWrap(True)
        self.description = ScrollLabel()
        self.description.setText("\n\n\n\n\t\t\t欢迎来到 RimSort (≧▽≦)!")
        # Add widgets to child layouts
        self.image_layout.addWidget(self.preview_picture)
        self.mod_info_name.addWidget(self.mod_info_name_label, 20)
        self.mod_info_name.addWidget(self.mod_info_name_value, 80)
        self.mod_info_path.addWidget(self.mod_info_path_label, 20)
        self.mod_info_path.addWidget(self.mod_info_path_value, 80)
        self.scenario_info_summary.addWidget(self.scenario_info_summary_label, 20)
        self.scenario_info_summary.addWidget(self.scenario_info_summary_value, 80)
        self.mod_info_package_id.addWidget(self.mod_info_package_id_label, 20)
        self.mod_info_package_id.addWidget(self.mod_info_package_id_value, 80)
        self.mod_info_authors.addWidget(self.mod_info_author_label, 20)
        self.mod_info_authors.addWidget(self.mod_info_author_value, 80)
        self.mod_info_mod_version.addWidget(self.mod_info_mod_version_label, 20)
        self.mod_info_mod_version.addWidget(self.mod_info_mod_version_value, 80)
        self.mod_info_supported_versions.addWidget(
            self.mod_info_supported_versions_label, 20
        )
        self.mod_info_supported_versions.addWidget(
            self.mod_info_supported_versions_value, 80
        )
        self.mod_info_layout.addLayout(self.mod_info_name)
        self.mod_info_layout.addLayout(self.scenario_info_summary)
        self.mod_info_layout.addLayout(self.mod_info_package_id)
        self.mod_info_layout.addLayout(self.mod_info_authors)
        self.mod_info_layout.addLayout(self.mod_info_mod_version)
        self.mod_info_layout.addLayout(self.mod_info_supported_versions)
        self.mod_info_layout.addLayout(self.mod_info_path)
        self.description_layout.addWidget(self.description)

        # Hide label/value by default
        self.essential_info_widgets = [
            self.mod_info_name_label,
            self.mod_info_name_value,
            self.mod_info_path_label,
            self.mod_info_path_value,
        ]

        self.base_mod_info_widgets = [
            self.mod_info_package_id_label,
            self.mod_info_package_id_value,
            self.mod_info_author_label,
            self.mod_info_author_value,
            self.mod_info_mod_version_label,
            self.mod_info_mod_version_value,
            self.mod_info_supported_versions_label,
            self.mod_info_supported_versions_value,
        ]

        self.scenario_info_widgets = [
            self.scenario_info_summary_label,
            self.scenario_info_summary_value,
        ]

        # Hide all widgets by default
        for widget in (
            self.essential_info_widgets
            + self.base_mod_info_widgets
            + self.scenario_info_widgets
        ):
            widget.hide()

        logger.debug("完成模组信息初始化")

    def display_mod_info(self, uuid: str) -> None:
        """
        This slot receives a the complete mod data json for
        the mod that was just clicked on. It will set the relevant
        information on the info panel.

        :param mod_info: complete json info for the mod
        """
        mod_info = self.metadata_manager.internal_local_metadata.get(uuid, {})
        # Style summary values based on validity
        if mod_info and mod_info.get("invalid"):
            # Set invalid value style
            for widget in (
                self.mod_info_name_value,
                self.mod_info_path_value,
                self.mod_info_author_value,
                self.mod_info_package_id_value,
            ):
                widget.setObjectName("summaryValueInvalid")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        else:
            # Set valid value style
            for widget in (
                self.mod_info_name_value,
                self.mod_info_path_value,
                self.mod_info_author_value,
                self.mod_info_package_id_value,
            ):
                widget.setObjectName("summaryValue")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        # Set name value
        self.mod_info_name_value.setText(mod_info.get("name", "Not specified"))
        # Show essential info widgets
        for widget in self.essential_info_widgets:
            if not widget.isVisible():
                widget.show()
        # If it's not invalid, and it's not a scenario, it must be a mod!
        if not mod_info.get("invalid") and not mod_info.get("scenario"):
            # Show valid-mod-specific fields, hide scenario summary
            for widget in self.base_mod_info_widgets:
                widget.show()

            for widget in self.scenario_info_widgets:
                widget.hide()

            # Populate values from metadata

            # Set package ID
            self.mod_info_package_id_value.setText(
                mod_info.get("packageid", "Not specified")
            )

            # Set authors
            authors_tag = mod_info.get("authors", "Not specified")
            if isinstance(authors_tag, dict) and authors_tag.get("li"):
                list_of_authors = authors_tag["li"]
                authors_text = ", ".join(list_of_authors)
                self.mod_info_author_value.setText(authors_text)
            else:
                self.mod_info_author_value.setText(
                    authors_tag if authors_tag else "Not specified"
                )

            # Set mod version
            mod_version = mod_info.get("modversion", {})
            if isinstance(mod_version, dict):
                self.mod_info_mod_version_value.setText(
                    mod_version.get("#text", "Not specified")
                )
            else:
                self.mod_info_mod_version_value.setText(mod_version)

            # Set supported versions
            supported_versions_tag = mod_info.get("supportedversions", {})
            supported_versions_list = supported_versions_tag.get("li")
            if isinstance(supported_versions_list, list):
                supported_versions_text = ", ".join(supported_versions_list)
                self.mod_info_supported_versions_value.setText(supported_versions_text)
            else:
                self.mod_info_supported_versions_value.setText(
                    supported_versions_list
                    if supported_versions_list
                    else "Not specified"
                )
        elif mod_info.get("scenario"):  # Hide mod-specific widgets, show scenario
            for widget in self.base_mod_info_widgets:
                widget.hide()

            for widget in self.scenario_info_widgets:
                widget.show()

            self.scenario_info_summary_value.setText(
                mod_info.get("summary", "Not specified")
            )
        elif mod_info.get("invalid"):  # Hide all except bare minimum if invalid
            for widget in self.base_mod_info_widgets + self.scenario_info_widgets:
                widget.hide()

        self.mod_info_path_value.setText(mod_info.get("path"))
        # Set the scrolling description for the Mod Info Panel
        self.description.setText("")
        if "description" in mod_info:
            if mod_info["description"] is not None:
                if isinstance(mod_info["description"], str):
                    self.description.setText(mod_info["description"])
                else:
                    logger.error(
                        f"[description] tag is not a string: {mod_info['description']}"
                    )
        # It is OK for the description value to be None (was not provided)
        # It is OK for the description key to not be in mod_info
        if mod_info.get("scenario"):
            pixmap = QPixmap(self.scenario_image_path)
            self.preview_picture.setPixmap(
                pixmap.scaled(
                    self.preview_picture.size(), Qt.AspectRatioMode.KeepAspectRatio
                )
            )
        else:
            # Get Preview.png
            workshop_folder_path = mod_info.get("path", "")
            logger.debug(
                f"检索到的mod路径以解析预览图像: {workshop_folder_path}"
            )
            if os.path.exists(workshop_folder_path):
                about_folder_name = "About"
                about_folder_target_path = str(
                    (Path(workshop_folder_path) / about_folder_name)
                )
                if os.path.exists(about_folder_target_path):
                    # Look for a case-insensitive About folder
                    invalid_folder_path_found = True
                    for temp_file in os.scandir(workshop_folder_path):
                        if (
                            temp_file.name.lower() == about_folder_name.lower()
                            and temp_file.is_dir()
                        ):
                            about_folder_name = temp_file.name
                            invalid_folder_path_found = False
                            break
                    # Look for a case-insensitive "Preview.png" file
                    invalid_file_path_found = True
                    preview_file_name = "Preview.png"
                    for temp_file in os.scandir(
                        str((Path(workshop_folder_path) / about_folder_name))
                    ):
                        if (
                            temp_file.name.lower() == preview_file_name.lower()
                            and temp_file.is_file()
                        ):
                            preview_file_name = temp_file.name
                            invalid_file_path_found = False
                            break
                    # If there was an issue getting the expected path, track and exit
                    if invalid_folder_path_found or invalid_file_path_found:
                        logger.debug("未找到该模组的预览图像")
                        pixmap = QPixmap(self.missing_image_path)
                        self.preview_picture.setPixmap(
                            pixmap.scaled(
                                self.preview_picture.size(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                            )
                        )
                    else:
                        logger.debug("找到的预览图像")
                        image_path = str(
                            (
                                Path(workshop_folder_path)
                                / about_folder_name
                                / preview_file_name
                            )
                        )
                        pixmap = QPixmap(image_path)
                        self.preview_picture.setPixmap(
                            pixmap.scaled(
                                self.preview_picture.size(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                            )
                        )
                else:
                    pixmap = QPixmap(self.missing_image_path)
                    self.preview_picture.setPixmap(
                        pixmap.scaled(
                            self.preview_picture.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                        )
                    )
        logger.debug("已完成模组信息的显示")
