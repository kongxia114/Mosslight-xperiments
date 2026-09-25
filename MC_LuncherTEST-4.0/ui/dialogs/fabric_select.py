# -*- coding: utf-8 -*-
"""
MC 启动器测试窗口 v3.0 最终版
- 版本下拉框（BMCLAPI 官方 + 本地版本分组）
- 原版下载
- Forge 下载 + 安装
- Fabric 下载 + 安装（loader + API）
- 原版 + Forge + Fabric 启动（inheritsFrom 合并）
- 日志过滤（隐藏噪音）
- 实时显示日志

v3.0 变化：
- 恢复 Forge 按钮（与 Fabric 共存）
- 加日志过滤：隐藏"Saving chunks"、"Time elapsed"等噪音
"""

# ==========================================================
# 模块：ui/dialogs/fabric_select.py  —— Fabric 安装选择对话框
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
)
from PyQt6.QtGui import QFont

class FabricSelectDialog(QDialog):
    def __init__(self, mc_version, loader_list, api_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"安装 Fabric - MC {mc_version}")
        self.resize(540, 480)
        self.selected = None

        layout = QVBoxLayout(self)
        title = QLabel(f"安装 Fabric - MC {mc_version}")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        layout.addWidget(QLabel("Fabric Loader"))
        self.loader_combo = QComboBox()
        for item in loader_list:
            stable = " [稳定]" if item.get("stable") else ""
            self.loader_combo.addItem(f"{item['version']}{stable}", userData=item)
        layout.addWidget(self.loader_combo)

        self.loader_info = QLabel("")
        layout.addWidget(self.loader_info)

        layout.addWidget(QLabel("Fabric API"))
        self.api_combo = QComboBox()
        self.api_combo.addItem("（不安装 Fabric API）", userData=None)
        for item in api_list:
            date = item.get("date_published", "")[:10]
            label = f"{item['version_number']}  ({date})"
            self.api_combo.addItem(label, userData=item)
        layout.addWidget(self.api_combo)

        self.api_info = QLabel("")
        layout.addWidget(self.api_info)

        self.isolated_check = QCheckBox("启用版本隔离（mods 放到版本目录内）")
        self.isolated_check.setChecked(False)
        layout.addWidget(self.isolated_check)

        hint = QLabel(
            "提示：\n"
            "· 不开启版本隔离 → mods 放 .minecraft/mods/\n"
            "· 开启版本隔离 → mods 放 versions/版本名/mods/"
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.loader_combo.currentIndexChanged.connect(self._update_loader_info)
        self.api_combo.currentIndexChanged.connect(self._update_api_info)
        self._update_loader_info()
        self._update_api_info()

    def _update_loader_info(self):
        item = self.loader_combo.currentData()
        if item:
            self.loader_info.setText(
                f"  版本: {item['version']}\n"
                f"  稳定版: {'是' if item.get('stable') else '否'}"
            )

    def _update_api_info(self):
        item = self.api_combo.currentData()
        if item:
            size_mb = item.get("size", 0) / 1024 / 1024
            self.api_info.setText(
                f"  文件名: {item['filename']}\n"
                f"  大小: {size_mb:.1f} MB\n"
                f"  发布时间: {item.get('date_published', '')[:10]}"
            )
        else:
            self.api_info.setText("  （不安装 Fabric API）")

    def _on_ok(self):
        loader = self.loader_combo.currentData()
        api = self.api_combo.currentData()
        isolated = self.isolated_check.isChecked()
        if not loader:
            QMessageBox.warning(self, "提示", "请选择 Fabric Loader 版本")
            return
        self.selected = {
            "loader": loader,
            "api": api,
            "isolated": isolated,
        }
        self.accept()
