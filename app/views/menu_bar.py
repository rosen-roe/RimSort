from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar

from app.utils.system_info import SystemInfo


class MenuBar(QObject):
    def __init__(self, menu_bar: QMenuBar) -> None:
        """
        Initialize the MenuBar object.

        Args:
            menu_bar (QMenuBar): The menu bar to which the menus and actions will be added.
        """
        super().__init__()

        self.menu_bar: QMenuBar = menu_bar

        # Declare actions and submenus as class variables
        # to be used by menu_bar_controller
        self.settings_action: QAction
        self.quit_action: QAction
        self.open_mod_list_action: QAction
        self.save_mod_list_action: QAction
        self.import_from_rentry_action: QAction
        self.import_from_workshop_collection_action: QAction
        self.export_to_clipboard_action: QAction
        self.export_to_rentry_action: QAction
        self.upload_rimsort_log_action: QAction
        self.upload_rimsort_old_log_action: QAction
        self.upload_rimworld_log_action: QAction
        self.open_app_directory_action: QAction
        self.open_settings_directory_action: QAction
        self.open_rimsort_logs_directory_action: QAction
        self.open_rimworld_logs_directory_action: QAction
        self.cut_action: QAction
        self.copy_action: QAction
        self.paste_action: QAction
        self.rule_editor_action: QAction
        self.add_git_mod_action: QAction
        self.browse_workshop_action: QAction
        self.update_workshop_mods_action: QAction
        self.backup_instance_action: QAction
        self.restore_instance_action: QAction
        self.clone_instance_action: QAction
        self.create_instance_action: QAction
        self.delete_instance_action: QAction
        self.optimize_textures_action: QAction
        self.delete_dds_textures_action: QAction
        self.wiki_action: QAction
        self.check_for_updates_action: QAction
        self.check_for_updates_on_startup_action: QAction
        self.validate_steam_client_action: QAction

        self.import_submenu: QMenu
        self.export_submenu: QMenu
        self.upload_submenu: QMenu
        self.shortcuts_submenu: QMenu
        self.instances_submenu: QMenu

        self._create_menu_bar()

    def _add_action(
        self,
        menu: QMenu,
        title: str,
        shortcut: Optional[str] = None,
        checkable: bool = False,
        role: Optional[QAction.MenuRole] = None,
    ) -> QAction:
        """
        Add an action to a menu.

        Args:
            menu (QMenu): The menu to which the action will be added.
            title (str): The title of the action.
            shortcut (Optional[str], optional): The keyboard shortcut for the action. Defaults to None.
            checkable (bool, optional): Whether the action is checkable. Defaults to False.
            role (Optional[QAction.MenuRole], optional): The menu role of the action. Defaults to None.

        Returns:
            QAction: The created action.
        """
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if checkable:
            action.setCheckable(True)
        if role:
            action.setMenuRole(role)
        menu.addAction(action)
        return action

    def _create_file_menu(self) -> QMenu:
        """
        Create the "File" menu and add its actions and submenus.

        Returns:
            QMenu: The created "File" menu.
        """
        file_menu = self.menu_bar.addMenu("文件")
        self.open_mod_list_action = self._add_action(
            file_menu, "导入模组排序…", "Ctrl+O"
        )
        file_menu.addSeparator()
        self.save_mod_list_action = self._add_action(
            file_menu, "保存模组排序…", "Ctrl+Shift+S"
        )
        file_menu.addSeparator()
        self.import_submenu = QMenu("导入")
        file_menu.addMenu(self.import_submenu)
        self.import_from_rentry_action = self._add_action(
            self.import_submenu, "从 Rentry.co"
        )
        self.import_from_workshop_collection_action = self._add_action(
            self.import_submenu, "从创意工坊集合"
        )
        self.export_submenu = QMenu("导出")
        file_menu.addMenu(self.export_submenu)
        self.export_to_clipboard_action = self._add_action(
            self.export_submenu, "到剪贴板…"
        )
        self.export_to_rentry_action = self._add_action(
            self.export_submenu, "到 Rentry.co…"
        )
        file_menu.addSeparator()
        self.upload_submenu = QMenu("上传日志")
        file_menu.addMenu(self.upload_submenu)
        self.upload_rimsort_log_action = self._add_action(
            self.upload_submenu, "RimSort.log"
        )
        self.upload_rimsort_old_log_action = self._add_action(
            self.upload_submenu, "RimSort.old.log"
        )
        self.upload_rimworld_log_action = self._add_action(
            self.upload_submenu, "RimWorld Player.log"
        )
        file_menu.addSeparator()
        self.shortcuts_submenu = QMenu("快捷方式")
        file_menu.addMenu(self.shortcuts_submenu)
        self.open_app_directory_action = self._add_action(
            self.shortcuts_submenu, "打开 RimSort 目录"
        )
        self.open_settings_directory_action = self._add_action(
            self.shortcuts_submenu, "打开 RimSort 用户文件"
        )
        self.open_rimsort_logs_directory_action = self._add_action(
            self.shortcuts_submenu, "打开 RimSort 日志目录"
        )
        self.open_rimworld_logs_directory_action = self._add_action(
            self.shortcuts_submenu, "打开 RimWorld 日志目录"
        )
        if SystemInfo().operating_system != SystemInfo.OperatingSystem.MACOS:
            file_menu.addSeparator()
            self.settings_action = self._add_action(file_menu, "设置…", "Ctrl+,")
            file_menu.addSeparator()
            self.quit_action = self._add_action(file_menu, "退出", "Ctrl+Q")
        return file_menu

    def _create_edit_menu(self) -> QMenu:
        """
        Create the "Edit" menu and add its actions.

        Returns:
            QMenu: The created "Edit" menu.
        """
        edit_menu = self.menu_bar.addMenu("编辑")
        self.cut_action = self._add_action(edit_menu, "剪切", "Ctrl+X")
        self.copy_action = self._add_action(edit_menu, "复制", "Ctrl+C")
        self.paste_action = self._add_action(edit_menu, "粘贴", "Ctrl+V")
        edit_menu.addSeparator()
        self.rule_editor_action = self._add_action(edit_menu, "规则编辑器…")
        return edit_menu

    def _create_download_menu(self) -> QMenu:
        """
        Create the "Download" menu and add its actions.

        Returns:
            QMenu: The created "Download" menu.
        """
        download_menu = self.menu_bar.addMenu("下载")
        self.add_git_mod_action = self._add_action(download_menu, "添加 Git 模组")
        download_menu.addSeparator()
        self.browse_workshop_action = self._add_action(download_menu, "浏览创意工坊")
        self.update_workshop_mods_action = self._add_action(
            download_menu, "更新创意工坊模组"
        )
        return download_menu

    def _create_instances_menu(self) -> QMenu:
        """
        Create the "Instances" menu and add its actions and submenus.

        Returns:
            QMenu: The created "Instances" menu.
        """
        instances_menu = self.menu_bar.addMenu("实例")
        self.instances_submenu = QMenu('当前: "默认"')
        instances_menu.addMenu(self.instances_submenu)
        instances_menu.addSeparator()
        self.backup_instance_action = self._add_action(
            instances_menu, "备份实例…"
        )
        self.restore_instance_action = self._add_action(
            instances_menu, "恢复实例…"
        )
        instances_menu.addSeparator()
        self.clone_instance_action = self._add_action(instances_menu, "克隆实例…")
        self.create_instance_action = self._add_action(
            instances_menu, "创建实例…"
        )
        self.delete_instance_action = self._add_action(
            instances_menu, "删除实例…"
        )
        return instances_menu

    def _create_texture_menu(self) -> QMenu:
        """
        Create the "Textures" menu and add its actions.

        Returns:
            QMenu: The created "Textures" menu.
        """
        texture_menu = self.menu_bar.addMenu("纹理/贴图")
        self.optimize_textures_action = self._add_action(
            texture_menu, "优化纹理/贴图"
        )
        texture_menu.addSeparator()
        self.delete_dds_textures_action = self._add_action(
            texture_menu, "删除.dds纹理/贴图"
        )
        return texture_menu

    def _create_help_menu(self) -> QMenu:
        """
        Create the "Help" menu and add its actions.

        Returns:
            QMenu: The created "Help" menu.
        """
        help_menu = self.menu_bar.addMenu("帮助")
        self.wiki_action = self._add_action(help_menu, "RimSort Wiki…")
        help_menu.addSeparator()
        # TODO: updates not implemented yet
        # self.check_for_updates_action = self._add_action(
        #     help_menu, "Check for Updates…"
        # )
        # self.check_for_updates_on_startup_action = self._add_action(
        #     help_menu, "Check for Updates on Startup", checkable=True
        # )
        # help_menu.addSeparator()
        self.validate_steam_client_action = self._add_action(
            help_menu, "验证 Steam 客户端模组"
        )
        return help_menu

    def _create_menu_bar(self) -> None:
        """
        Create the menu bar. On macOS, include the app menu.
        """
        if SystemInfo().operating_system == SystemInfo.OperatingSystem.MACOS:
            app_menu = self.menu_bar.addMenu("应用名称")
            app_menu.addSeparator()
            self.settings_action = self._add_action(
                app_menu,
                "设置...",
                shortcut="Ctrl+,",
                role=QAction.MenuRole.ApplicationSpecificRole,
            )
            app_menu.addSeparator()
            self.quit_action = self._add_action(app_menu, "退出")
        self._create_file_menu()
        self._create_edit_menu()
        self._create_download_menu()
        self._create_instances_menu()
        self._create_texture_menu()
        self._create_help_menu()
