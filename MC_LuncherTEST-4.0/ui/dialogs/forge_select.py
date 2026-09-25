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
# 模块：ui/dialogs/forge_select.py  —— Forge 版本选择对话框
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QComboBox,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class ForgeSelectDialog(QDialog):
    def __init__(self, mc_version, forge_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"选择 Forge 版本 - MC {mc_version}")
        self.resize(480, 380)
        self.selected = None

        layout = QVBoxLayout(self)
        title = QLabel(f"MC {mc_version} 可用的 Forge 版本（{len(forge_list)} 个）")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        self.combo = QComboBox()
        for item in forge_list:
            label = f"{item['version']}  (build {item['build']})  {item.get('modified', '')[:10]}"
            self.combo.addItem(label, userData=item)
        layout.addWidget(self.combo)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.combo.currentIndexChanged.connect(self._on_change)
        self._on_change()
        layout.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_change(self):
        item = self.combo.currentData()
        if item:
            self.info.setText(
                f"MC 版本: {item['mcversion']}\n"
                f"Forge 版本: {item['version']}\n"
                f"Build: {item['build']}\n"
                f"发布时间: {item.get('modified', '')}"
            )

    def _on_ok(self):
        self.selected = self.combo.currentData()
        self.accept()
