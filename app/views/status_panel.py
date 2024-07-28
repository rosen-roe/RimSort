from loguru import logger
from PySide6.QtWidgets import QFrame, QHBoxLayout

from app.models.animations import AnimationLabel


class Status:
    """
    This class controls the layout and functionality for
    the Status view on the bottom of the GUI.
    """

    def __init__(self) -> None:
        """
        Initialize the Status view. Construct the layout
        add the single fading text widget.
        """
        logger.info("初始化状态")

        # This view is contained within a QFrame to allow for styling
        self.frame = QFrame()
        self.frame.setObjectName("StatusPanel")

        # Create the main layout for the view
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(10, 1, 0, 2)

        # The main layout is contained inside the QFrame
        self.frame.setLayout(self.layout)

        # Create the single fading text widget
        self.status_text = AnimationLabel()
        self.status_text.setObjectName("StatusLabel")

        # Add the widget to the base layout
        self.layout.addWidget(self.status_text)

        logger.debug("完成状态初始化")

    def actions_slot(self, action: str) -> None:
        """
        Slot connecting to the action panel's `actions_signal`.
        Responsible for displaying the action that was just
        triggered on the bottom status bar and fading the text
        after some time.

        :param action: the specific action being triggered
        """
        logger.info(f"为操作显示渐隐文本: {action}")
        if action == "check_for_rs_update":
            self.status_text.start_pause_fade("检查 RimSort 更新")
        # actions panel actions
        elif action == "refresh":
            self.status_text.start_pause_fade(
                "刷新本地元数据并从外部元数据重新填充信息"
            )
        elif action == "clear":
            self.status_text.start_pause_fade("清除启用模组")
        elif action == "restore":
            self.status_text.start_pause_fade(
                "模组列表恢复到上次保存的ModsConfig.xml状态"
            )
        elif action == "sort":
            self.status_text.start_pause_fade("排序启用模组列表")
        elif action == "optimize_textures":
            self.status_text.start_pause_fade("使用 todds 优化纹理/贴图")
        elif action == "delete_textures":
            self.status_text.start_pause_fade("使用 todds 删除.dds纹理/贴图")
        elif action == "add_git_mod":
            self.status_text.start_pause_fade("将 git模组仓库添加到本地模组中")
        elif action == "browse_workshop":
            self.status_text.start_pause_fade("启动Steam创意工坊浏览器")
        elif action == "setup_steamcmd":
            self.status_text.start_pause_fade("SteamCMD 设置完成")
        elif action == "import_steamcmd_acf_data":
            self.status_text.start_pause_fade(
                "从另一个 SteamCMD 实例导入数据"
            )
        elif action == "reset_steamcmd_acf_data":
            self.status_text.start_pause_fade("删除的 SteamCMD ACF 数据")
        elif "import_list" in action:
            self.status_text.start_pause_fade("导入的启用模组列表")
        elif "export_list" in action:
            self.status_text.start_pause_fade("导出的启用模组列表")
        elif action == "upload_list_rentry":
            self.status_text.start_pause_fade(
                "将模组报告复制到剪贴板;上传到 http://rentry.co"
            )
        elif action == "save":
            self.status_text.start_pause_fade("启用模组保存到 ModsConfig.xml")
        elif action == "run":
            self.status_text.start_pause_fade("启动 RimWorld")
        # settings panel actions
        elif action == "configure_github_identity":
            self.status_text.start_pause_fade("已配置的GitHub身份")
        elif action == "configure_steam_database_path":
            self.status_text.start_pause_fade("已配置的Steam数据库文件路径")
        elif action == "configure_steam_database_repo":
            self.status_text.start_pause_fade("已配置的Steam数据库仓库")
        elif action == "download_steam_database":
            self.status_text.start_pause_fade(
                "已从配置的仓库中下载了Steam数据库"
            )
        elif action == "upload_steam_database":
            self.status_text.start_pause_fade(
                "将Steam数据库数据上传到已配置的仓库"
            )
        elif action == "configure_community_rules_db_path":
            self.status_text.start_pause_fade("已配置的社区规则数据库文件路径")
        elif action == "configure_community_rules_db_repo":
            self.status_text.start_pause_fade(
                "已配置的社区规则数据库存储库"
            )
        elif action == "download_community_rules_database":
            self.status_text.start_pause_fade(
                "已从配置的存储库下载社区规则数据库"
            )
        elif action == "open_community_rules_with_rule_editor":
            self.status_text.start_pause_fade(
                "使用社区规则数据库环境打开规则编辑器"
            )
        elif action == "upload_community_rules_database":
            self.status_text.start_pause_fade(
                "将社区规则数据库上传到配置的存储库"
            )
        elif action == "build_steam_database_thread":
            self.status_text.start_pause_fade("使用数据库生成器构建 Steam数据库")
        elif action == "merge_databases":
            self.status_text.start_pause_fade("成功合并提供的 Steam数据库")
        elif action == "set_database_expiry":
            self.status_text.start_pause_fade("已编辑配置的 Steam数据有效时间...")
        elif action == "edit_steam_webapi_key":
            self.status_text.start_pause_fade("已编辑配置的 Steam WebAPI 密钥...")
        elif action == "comparison_report":
            self.status_text.start_pause_fade("创建 Steam数据库比较报告")
        elif "download_entire_workshop" in action:
            if "steamcmd" in action:
                self.status_text.start_pause_fade(
                    "尝试使用SteamCMD下载所有创意工坊模组"
                )
            elif "steamworks" in action:
                self.status_text.start_pause_fade(
                    "尝试使用Steam订阅所有创意工坊模组"
                )
        else:  # Otherwise, just display whatever text is passed
            self.status_text.start_pause_fade(action)
