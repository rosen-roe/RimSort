from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.gui_info import GUIInfo


class SettingsDialog(QDialog):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.setWindowTitle("设置")
        self.setObjectName("settingsPanel")
        self.resize(800, 600)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Initialize the QTabWidget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Initialize the tabs
        self._do_locations_tab()
        self._do_databases_tab()
        self._do_sorting_tab()
        self._do_db_builder_tab()
        self._do_steamcmd_tab()
        self._do_todds_tab()
        self._do_advanced_tab()

        # Bottom buttons layout
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)

        # OK button
        self.global_ok_button = QPushButton("OK", self)
        self.global_ok_button.setDefault(True)
        button_layout.addWidget(self.global_ok_button)

        button_layout.addStretch(1)

        # Reset to defaults button
        self.global_reset_to_defaults_button = QPushButton("重置为默认值", self)
        button_layout.addWidget(self.global_reset_to_defaults_button)

        button_layout.addStretch(1)

        # Cancel button
        self.global_cancel_button = QPushButton("取消", self)
        button_layout.addWidget(self.global_cancel_button)

    def _do_locations_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "位置 ")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._do_game_location_area(tab_layout)
        self._do_config_folder_location_area(tab_layout)
        self._do_steam_mods_folder_location_area(tab_layout)
        self._do_local_mods_folder_location_area(tab_layout)

        # Set the tab order:
        # "Game location" → "Config location" → "Steam mods location" → "Local mods location"
        self.setTabOrder(self.game_location, self.config_folder_location)
        self.setTabOrder(self.config_folder_location, self.steam_mods_folder_location)
        self.setTabOrder(
            self.steam_mods_folder_location, self.local_mods_folder_location
        )

        # Create a QHBoxLayout for the buttons
        buttons_layout = QHBoxLayout()
        tab_layout.addLayout(buttons_layout)

        # Align the buttons to the Center
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # "Autodetect" button
        self.locations_autodetect_button = QPushButton("自动检测", tab)
        buttons_layout.addWidget(self.locations_autodetect_button)

        # "Clear" button"
        self.locations_clear_button = QPushButton("清空所有位置", tab)
        buttons_layout.addWidget(self.locations_clear_button)

    def _do_game_location_area(self, tab_layout: QVBoxLayout) -> None:
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        header_layout = QHBoxLayout()
        group_layout.addLayout(header_layout)

        section_label = QLabel("游戏位置")
        section_label.setFont(GUIInfo().emphasis_font)
        header_layout.addWidget(section_label)

        self.game_location_open_button = QToolButton()
        self.game_location_open_button.setText("打开…")
        header_layout.addWidget(self.game_location_open_button)

        self.game_location_choose_button = QToolButton()
        self.game_location_choose_button.setText("选择…")
        header_layout.addWidget(self.game_location_choose_button)

        self.game_location_clear_button = QToolButton()
        self.game_location_clear_button.setText("清除…")
        header_layout.addWidget(self.game_location_clear_button)

        self.game_location = QLineEdit()
        self.game_location.setTextMargins(GUIInfo().text_field_margins)
        self.game_location.setFixedHeight(GUIInfo().default_font_line_height * 2)
        group_layout.addWidget(self.game_location)

    def _do_config_folder_location_area(self, tab_layout: QVBoxLayout) -> None:
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        header_layout = QHBoxLayout()
        group_layout.addLayout(header_layout)

        section_label = QLabel("配置位置")
        section_label.setFont(GUIInfo().emphasis_font)
        header_layout.addWidget(section_label)

        self.config_folder_location_open_button = QToolButton()
        self.config_folder_location_open_button.setText("打开…")
        header_layout.addWidget(self.config_folder_location_open_button)

        self.config_folder_location_choose_button = QToolButton()
        self.config_folder_location_choose_button.setText("选择…")
        header_layout.addWidget(self.config_folder_location_choose_button)

        self.config_folder_location_clear_button = QToolButton()
        self.config_folder_location_clear_button.setText("清除…")
        header_layout.addWidget(self.config_folder_location_clear_button)

        self.config_folder_location = QLineEdit()
        self.config_folder_location.setTextMargins(GUIInfo().text_field_margins)
        self.config_folder_location.setFixedHeight(
            GUIInfo().default_font_line_height * 2
        )
        group_layout.addWidget(self.config_folder_location)

    def _do_steam_mods_folder_location_area(self, tab_layout: QVBoxLayout) -> None:
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        header_layout = QHBoxLayout()
        group_layout.addLayout(header_layout)

        section_label = QLabel("Steam 模组位置")
        section_label.setFont(GUIInfo().emphasis_font)
        header_layout.addWidget(section_label)

        self.steam_mods_folder_location_open_button = QToolButton()
        self.steam_mods_folder_location_open_button.setText("打开…")
        header_layout.addWidget(self.steam_mods_folder_location_open_button)

        self.steam_mods_folder_location_choose_button = QToolButton()
        self.steam_mods_folder_location_choose_button.setText("选择…")
        header_layout.addWidget(self.steam_mods_folder_location_choose_button)

        self.steam_mods_folder_location_clear_button = QToolButton()
        self.steam_mods_folder_location_clear_button.setText("清除…")
        header_layout.addWidget(self.steam_mods_folder_location_clear_button)

        self.steam_mods_folder_location = QLineEdit()
        self.steam_mods_folder_location.setTextMargins(GUIInfo().text_field_margins)
        self.steam_mods_folder_location.setFixedHeight(
            GUIInfo().default_font_line_height * 2
        )
        group_layout.addWidget(self.steam_mods_folder_location)

    def _do_local_mods_folder_location_area(self, tab_layout: QVBoxLayout) -> None:
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        header_layout = QHBoxLayout()
        group_layout.addLayout(header_layout)

        section_label = QLabel("本地模组位置")
        section_label.setFont(GUIInfo().emphasis_font)
        header_layout.addWidget(section_label)

        self.local_mods_folder_location_open_button = QToolButton()
        self.local_mods_folder_location_open_button.setText("打开…")
        header_layout.addWidget(self.local_mods_folder_location_open_button)

        self.local_mods_folder_location_choose_button = QToolButton()
        self.local_mods_folder_location_choose_button.setText("选择…")
        header_layout.addWidget(self.local_mods_folder_location_choose_button)

        self.local_mods_folder_location_clear_button = QToolButton()
        self.local_mods_folder_location_clear_button.setText("清除…")
        header_layout.addWidget(self.local_mods_folder_location_clear_button)

        self.local_mods_folder_location = QLineEdit()
        self.local_mods_folder_location.setTextMargins(GUIInfo().text_field_margins)
        self.local_mods_folder_location.setFixedHeight(
            GUIInfo().default_font_line_height * 2
        )
        group_layout.addWidget(self.local_mods_folder_location)

    def _do_databases_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "Databases")

        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        self._do_community_rules_db_group(tab_layout)
        self._do_steam_workshop_db_group(tab_layout)

    def __create_db_group(
        self, section_lbl: str, none_lbl: str, tab_layout: QBoxLayout
    ) -> tuple[
        QVBoxLayout,
        QRadioButton,
        QRadioButton,
        QLineEdit,
        QToolButton,
        QToolButton,
        QRadioButton,
        QLineEdit,
        QToolButton,
    ]:
        group = QGroupBox()
        tab_layout.addWidget(group, stretch=1)

        group_layout = QVBoxLayout()
        group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group.setLayout(group_layout)

        section_label = QLabel(section_lbl)
        section_label.setFont(GUIInfo().emphasis_font)
        section_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        group_layout.addWidget(section_label)

        section_layout = QVBoxLayout()
        section_layout.setSpacing(0)
        group_layout.addLayout(section_layout)

        item_layout = QHBoxLayout()
        section_layout.addLayout(item_layout, stretch=1)

        none_radio = QRadioButton("None")
        none_radio.setMinimumSize(0, GUIInfo().default_font_line_height * 2)
        none_radio.setChecked(True)
        item_layout.addWidget(none_radio, stretch=2)

        label = QLabel(f"No {none_lbl} will be used.")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        label.setEnabled(False)
        item_layout.addWidget(label, stretch=8)

        item_layout = QHBoxLayout()
        section_layout.addLayout(item_layout, stretch=1)

        github_radio = QRadioButton("GitHub")
        github_radio.setMinimumSize(0, GUIInfo().default_font_line_height * 2)
        item_layout.addWidget(github_radio, stretch=2)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(8)
        item_layout.addLayout(row_layout, stretch=8)

        github_url = QLineEdit()
        github_url.setFixedHeight(GUIInfo().default_font_line_height * 2)
        github_url.setTextMargins(GUIInfo().text_field_margins)
        github_url.setClearButtonEnabled(True)
        github_url.setEnabled(False)
        row_layout.addWidget(github_url)

        github_upload_button = QToolButton()
        github_upload_button.setText("上传…")
        github_upload_button.setEnabled(False)
        row_layout.addWidget(github_upload_button)

        github_download_button = QToolButton()
        github_download_button.setText("下载…")
        github_download_button.setEnabled(False)
        row_layout.addWidget(github_download_button)

        item_layout = QHBoxLayout()
        section_layout.addLayout(item_layout, stretch=1)
        local_file_radio = QRadioButton("本地文件")
        local_file_radio.setMinimumSize(0, GUIInfo().default_font_line_height * 2)
        item_layout.addWidget(local_file_radio, stretch=2)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(8)
        item_layout.addLayout(row_layout, stretch=8)

        local_file = QLineEdit()
        local_file.setFixedHeight(GUIInfo().default_font_line_height * 2)
        local_file.setTextMargins(GUIInfo().text_field_margins)
        local_file.setClearButtonEnabled(True)
        local_file.setEnabled(False)
        row_layout.addWidget(local_file)

        local_file_choose_button = QToolButton()
        local_file_choose_button.setText("选择…")
        local_file_choose_button.setEnabled(False)
        local_file_choose_button.setFixedWidth(
            github_download_button.sizeHint().width()
        )
        row_layout.addWidget(local_file_choose_button)

        section_layout.addStretch(1)

        item_layout = QHBoxLayout()
        section_layout.addLayout(item_layout, stretch=1)

        info_label = QLabel("")
        info_label.setWordWrap(True)
        item_layout.addWidget(info_label)

        return (
            group_layout,
            none_radio,
            github_radio,
            github_url,
            github_upload_button,
            github_download_button,
            local_file_radio,
            local_file,
            local_file_choose_button,
        )

    def _do_community_rules_db_group(self, tab_layout: QBoxLayout) -> None:
        section_lbl = "Community Rules database"
        none_lbl = "community rules database"

        (
            _,
            self.community_rules_db_none_radio,
            self.community_rules_db_github_radio,
            self.community_rules_db_github_url,
            self.community_rules_db_github_upload_button,
            self.community_rules_db_github_download_button,
            self.community_rules_db_local_file_radio,
            self.community_rules_db_local_file,
            self.community_rules_db_local_file_choose_button,
        ) = self.__create_db_group(section_lbl, none_lbl, tab_layout)

    def _do_steam_workshop_db_group(self, tab_layout: QBoxLayout) -> None:
        section_lbl = "Steam Workshop database"
        none_lbl = "Steam Workshop database"

        (
            group_layout,
            self.steam_workshop_db_none_radio,
            self.steam_workshop_db_github_radio,
            self.steam_workshop_db_github_url,
            self.steam_workshop_db_github_upload_button,
            self.steam_workshop_db_github_download_button,
            self.steam_workshop_db_local_file_radio,
            self.steam_workshop_db_local_file,
            self.steam_workshop_db_local_file_choose_button,
        ) = self.__create_db_group(section_lbl, none_lbl, tab_layout)

        database_expiry_label = QLabel("Steam Workshop database expiry in Epoch Time (Default is 7 Days) To Disable Notificatiom Use 0")
        database_expiry_label.setFont(GUIInfo().emphasis_font)
        group_layout.addWidget(database_expiry_label)

        self.database_expiry = QLineEdit()
        self.database_expiry.setTextMargins(GUIInfo().text_field_margins)
        self.database_expiry.setFixedHeight(GUIInfo().default_font_line_height * 2)
        group_layout.addWidget(self.database_expiry)

    def _do_sorting_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "Sorting")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_box_layout = QVBoxLayout()
        group_box.setLayout(group_box_layout)

        sorting_label = QLabel("排序模组")
        sorting_label.setFont(GUIInfo().emphasis_font)
        group_box_layout.addWidget(sorting_label)

        self.sorting_alphabetical_radio = QRadioButton("按字母顺序排列")
        group_box_layout.addWidget(self.sorting_alphabetical_radio)

        self.sorting_topological_radio = QRadioButton("按拓扑算法排列")
        group_box_layout.addWidget(self.sorting_topological_radio)

        tab_layout.addStretch()

        explanatory_text = ""
        explanatory_label = QLabel(explanatory_text)
        explanatory_label.setWordWrap(True)
        tab_layout.addWidget(explanatory_label)

    def _do_db_builder_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "数据库生成器")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # "When building the database:" radio buttons
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        when_building_database_label = QLabel("构建数据库时:")
        when_building_database_label.setFont(GUIInfo().emphasis_font)
        group_layout.addWidget(when_building_database_label)

        self.db_builder_include_all_radio = QRadioButton(
            "从本地安装的模组中获取已发布的文件ID。"
        )
        group_layout.addWidget(self.db_builder_include_all_radio)

        explanatory_label = QLabel(
            "您希望更新的模组必须已安装，"
            "因为初始数据库是通过包括模组About.xml文件中的数据来构建的。"
        )
        group_layout.addWidget(explanatory_label)

        self.db_builder_include_no_local_radio = QRadioButton(
            "从Steam创意工坊获取已发布的文件ID。"
        )
        group_layout.addWidget(self.db_builder_include_no_local_radio)

        explanatory_label = QLabel(
            "您希望更新的模组必须已安装，"
            "因为初始数据库是通过抓取Steam创意工坊来构建的。"
        )
        group_layout.addWidget(explanatory_label)

        # Checkboxes
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        self.db_builder_query_dlc_checkbox = QCheckBox(
            "使用Steamworks API查询DLC依赖数据"
        )
        group_layout.addWidget(self.db_builder_query_dlc_checkbox)

        self.db_builder_update_instead_of_overwriting_checkbox = QCheckBox(
            "更新数据库而，不是覆盖"
        )
        group_layout.addWidget(self.db_builder_update_instead_of_overwriting_checkbox)

        # Text fields
        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        grid_group_layout = QGridLayout()
        group_box.setLayout(grid_group_layout)

        steam_api_key_label = QLabel("Steam API key:")
        steam_api_key_label.setFont(GUIInfo().emphasis_font)
        grid_group_layout.addWidget(steam_api_key_label, 1, 0)

        self.db_builder_steam_api_key = QLineEdit()
        self.db_builder_steam_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_builder_steam_api_key.setTextMargins(GUIInfo().text_field_margins)
        self.db_builder_steam_api_key.setFixedHeight(
            GUIInfo().default_font_line_height * 2
        )
        grid_group_layout.addWidget(self.db_builder_steam_api_key, 1, 1)

        grid_group_layout.setColumnStretch(0, 0)
        grid_group_layout.setColumnStretch(1, 1)

        # "Warning note"
        item_layout = QHBoxLayout()
        tab_layout.addLayout(item_layout)

        item_label = QLabel(
            "WARNING \n Only Use If You Know What You Are Doing \n"
            "Please Read User Guide For More Information Before Proceeding. \n"
        )
        item_layout.addWidget(item_label)
        item_label.setFont(GUIInfo().emphasis_font)
        item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # "Download all workshop mods via" buttons
        item_layout = QHBoxLayout()
        tab_layout.addLayout(item_layout)

        item_label = QLabel("下载所有已发布的创意工坊模组，通过 :")
        item_layout.addWidget(item_label)
        item_label.setFont(GUIInfo().emphasis_font)

        self.db_builder_download_all_mods_via_steamcmd_button = QPushButton("SteamCMD")
        item_layout.addWidget(self.db_builder_download_all_mods_via_steamcmd_button)

        self.db_builder_download_all_mods_via_steam_button = QPushButton("Steam")
        item_layout.addWidget(self.db_builder_download_all_mods_via_steam_button)

        # Compare/Merge/Build database buttons
        item_layout = QHBoxLayout()
        tab_layout.addLayout(item_layout)

        item_label = QLabel("Database Operations :")
        item_layout.addWidget(item_label)
        item_label.setFont(GUIInfo().emphasis_font)

        self.db_builder_compare_databases_button = QPushButton("比较数据库")
        item_layout.addWidget(self.db_builder_compare_databases_button)

        self.db_builder_merge_databases_button = QPushButton("合并数据库")
        item_layout.addWidget(self.db_builder_merge_databases_button)

        self.db_builder_build_database_button = QPushButton("构建数据库")
        item_layout.addWidget(self.db_builder_build_database_button)

    def _do_steamcmd_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "SteamCMD")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        self.steamcmd_validate_downloads_checkbox = QCheckBox(
            "验证下载的模组"
        )
        group_layout.addWidget(self.steamcmd_validate_downloads_checkbox)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        header_layout = QHBoxLayout()
        group_layout.addLayout(header_layout)

        section_label = QLabel("SteamCMD 安装位置")
        section_label.setFont(GUIInfo().emphasis_font)
        header_layout.addWidget(section_label)

        self.steamcmd_install_location_choose_button = QToolButton()
        self.steamcmd_install_location_choose_button.setText("选择…")
        header_layout.addWidget(self.steamcmd_install_location_choose_button)

        self.steamcmd_install_location = QLineEdit()
        self.steamcmd_install_location.setTextMargins(GUIInfo().text_field_margins)
        self.steamcmd_install_location.setFixedHeight(
            GUIInfo().default_font_line_height * 2
        )
        group_layout.addWidget(self.steamcmd_install_location)

        button_layout = QHBoxLayout()
        tab_layout.addLayout(button_layout)

        self.steamcmd_import_acf_button = QPushButton("Import .acf")
        button_layout.addWidget(self.steamcmd_import_acf_button)

        self.steamcmd_delete_acf_button = QPushButton("Delete .acf")
        button_layout.addWidget(self.steamcmd_delete_acf_button)

        self.steamcmd_install_button = QPushButton("安装 SteamCMD")
        button_layout.addWidget(self.steamcmd_install_button)

    def _do_todds_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "todds")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        quality_preset_label = QLabel("质量预设")
        quality_preset_label.setFont(GUIInfo().emphasis_font)
        group_layout.addWidget(quality_preset_label)

        self.todds_preset_combobox = QComboBox()
        self.todds_preset_combobox.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        self.todds_preset_combobox.addItem("优化 - 推荐用于 RimWorld")
        group_layout.addWidget(self.todds_preset_combobox)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        when_optimizing_label = QLabel("优化纹理/贴图时")
        when_optimizing_label.setFont(GUIInfo().emphasis_font)
        group_layout.addWidget(when_optimizing_label)

        self.todds_active_mods_only_radio = QRadioButton("仅优化启用模组")
        group_layout.addWidget(self.todds_active_mods_only_radio)

        self.todds_all_mods_radio = QRadioButton("优化所有模组")
        group_layout.addWidget(self.todds_all_mods_radio)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        self.todds_dry_run_checkbox = QCheckBox("启用试运行模式")
        group_layout.addWidget(self.todds_dry_run_checkbox)

        self.todds_overwrite_checkbox = QCheckBox(
            "覆盖现有的优化纹理/贴图"
        )
        group_layout.addWidget(self.todds_overwrite_checkbox)

    def _do_advanced_tab(self) -> None:
        tab = QWidget()
        self.tab_widget.addTab(tab, "高级 ")

        tab_layout = QVBoxLayout(tab)
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_box = QGroupBox()
        tab_layout.addWidget(group_box)

        group_layout = QVBoxLayout()
        group_box.setLayout(group_layout)

        self.debug_logging_checkbox = QCheckBox("启用调试日志记录")
        group_layout.addWidget(self.debug_logging_checkbox)

        self.watchdog_checkbox = QCheckBox("启用监视器文件监控守护进程")
        group_layout.addWidget(self.watchdog_checkbox)

        self.mod_type_filter_checkbox = QCheckBox("启用模组类型过滤器")
        group_layout.addWidget(self.mod_type_filter_checkbox)

        self.show_duplicate_mods_warning_checkbox = QCheckBox(
            "显示重复模组警告"
        )
        group_layout.addWidget(self.show_duplicate_mods_warning_checkbox)

        self.show_mod_updates_checkbox = QCheckBox("刷新时检查模组更新")
        group_layout.addWidget(self.show_mod_updates_checkbox)

        self.steam_client_integration_checkbox = QCheckBox(
            "启用 Steam 客户端整合"
        )
        group_layout.addWidget(self.steam_client_integration_checkbox)

        self.download_missing_mods_checkbox = QCheckBox(
            "自动下载缺少的模组"
        )
        group_layout.addWidget(self.download_missing_mods_checkbox)

        github_identity_group = QGroupBox()
        tab_layout.addWidget(github_identity_group)

        github_identity_layout = QGridLayout()
        github_identity_group.setLayout(github_identity_layout)

        github_username_label = QLabel("GitHub 用户名:")
        github_username_label.setFont(GUIInfo().emphasis_font)
        github_identity_layout.addWidget(
            github_username_label, 0, 0, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.github_username = QLineEdit()
        self.github_username.setTextMargins(GUIInfo().text_field_margins)
        self.github_username.setFixedHeight(GUIInfo().default_font_line_height * 2)
        github_identity_layout.addWidget(self.github_username, 0, 1)

        github_token_label = QLabel("GitHub 个人访问令牌:")
        github_token_label.setFont(GUIInfo().emphasis_font)
        github_identity_layout.addWidget(
            github_token_label, 1, 0, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.github_token = QLineEdit()
        self.github_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token.setTextMargins(GUIInfo().text_field_margins)
        self.github_token.setFixedHeight(GUIInfo().default_font_line_height * 2)
        github_identity_layout.addWidget(self.github_token, 1, 1)

        self.setTabOrder(self.github_username, self.github_token)

        tab_layout.addStretch(1)

        buttons_layout = QHBoxLayout()
        tab_layout.addLayout(buttons_layout)

        buttons_layout.addStretch()

        run_args_group = QGroupBox()
        tab_layout.addWidget(run_args_group)

        run_args_layout = QGridLayout()
        run_args_group.setLayout(run_args_layout)

        run_args_info_layout = QHBoxLayout()

        self.run_args_info_label = QLabel(
            "Enter a comma separated list of arguments to pass to the Rimworld executable"
            "\n Example \n"
            "-logfile,/path/to/file.log,-savedatafolder=/path/to/savedata,-popupwindow"
        )
        self.run_args_info_label.setFixedHeight(GUIInfo().default_font_line_height * 6)
        run_args_info_layout.addWidget(self.run_args_info_label, 0)
        self.run_args_info_label.setFont(GUIInfo().emphasis_font)
        self.run_args_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        run_args_layout.addLayout(run_args_info_layout, 0, 0, 1, 2)

        run_args_label = QLabel("编辑游戏运行参数:")
        run_args_label.setFont(GUIInfo().emphasis_font)
        run_args_layout.addWidget(
            run_args_label, 1, 0, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.run_args = QLineEdit()
        self.run_args.setTextMargins(GUIInfo().text_field_margins)
        self.run_args.setFixedHeight(GUIInfo().default_font_line_height * 2)
        self.run_args.setFont(GUIInfo().emphasis_font)
        run_args_layout.addWidget(self.run_args, 1, 1)

        self.setTabOrder(self.run_args_info_label, self.run_args)

    def _find_tab_index(self, tab_name: str) -> int:
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                return i
        return -1  # Return -1 if no tab found

    def switch_to_tab(self, tab_name: str) -> None:
        """
        Switch to the specified tab by name if it exists.
        """
        index = self._find_tab_index(tab_name)
        if index and index != -1:
            self.tab_widget.setCurrentIndex(index)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.global_ok_button.setFocus()
