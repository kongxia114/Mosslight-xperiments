"""
Modrinth 下载界面
- 用户选 MC 版本 + 加载器
- 从 Modrinth 拉取兼容的 mod 版本
- 显示列表，可以下载
"""

import sys
import json
import requests
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QScrollArea, QFrame,
    QLineEdit, QMessageBox, QProgressBar
)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QByteArray, QUrl, QThread, pyqtSignal


HEADERS = {"User-Agent": "Mosslight-Launcher/1.0"}


# ============================================================
# Modrinth API
# ============================================================
def to_slug(name: str) -> str:
    """把显示名转成 slug"""
    import re
    s = name.lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def fetch_project(project_id: str) -> dict:
    try:
        r = requests.get(
            f"https://api.modrinth.com/v2/project/{project_id}",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_versions(project_id: str, mc_version: str = None, loader: str = None) -> list:
    params = {}
    if mc_version:
        params["game_versions"] = json.dumps([mc_version])
    if loader:
        params["loaders"] = json.dumps([loader])
    try:
        r = requests.get(
            f"https://api.modrinth.com/v2/project/{project_id}/version",
            params=params, headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


# ============================================================
# 后台加载
# ============================================================
class VersionsLoader(QThread):
    loaded = pyqtSignal(dict, list)   # (project, versions)

    def __init__(self, project_id, mc_version=None, loader=None):
        super().__init__()
        self.project_id = project_id
        self.mc_version = mc_version
        self.loader = loader

    def run(self):
        # 尝试用原始输入
        project = fetch_project(self.project_id)
        # 失败 → 尝试转 slug
        if not project:
            slug = to_slug(self.project_id)
            if slug != self.project_id:
                project = fetch_project(slug)
        if not project:
            self.loaded.emit({}, [])
            return
        # 用正确的 slug 查版本
        versions = fetch_versions(project["slug"], self.mc_version, self.loader)
        self.loaded.emit(project, versions)


# ============================================================
# 版本卡片
# ============================================================
class VersionCard(QFrame):
    download_requested = pyqtSignal(dict)   # 发出"下载"信号

    def __init__(self, version: dict):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.version = version
        self.setStyleSheet("""
            VersionCard {
                background-color: #232428;
                border-radius: 8px;
                border: 1px solid #2e3034;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # 左侧：版本名 + 标签
        left = QVBoxLayout()
        left.setSpacing(4)

        name_row = QHBoxLayout()
        name = QLabel(version["name"])
        name.setStyleSheet("font-size: 13px; font-weight: bold; color: #fff;")
        name_row.addWidget(name)

        # 类型标签
        vtype = version.get("version_type", "release")
        type_color = {
            "release": "#3f8f4b",
            "beta": "#d97706",
            "alpha": "#b91c1c",
        }.get(vtype, "#555")
        type_label = QLabel(vtype.capitalize())
        type_label.setStyleSheet(f"""
            background-color: {type_color};
            color: white;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 10px;
        """)
        name_row.addWidget(type_label)

        # 支持的 MC 版本
        for gv in version.get("game_versions", [])[:3]:
            tag = QLabel(gv)
            tag.setStyleSheet("""
                background-color: #2a2c30;
                color: #a0a1a7;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
            """)
            name_row.addWidget(tag)
        name_row.addStretch()
        left.addLayout(name_row)

        # 副信息
        date = version.get("date_published", "")[:10]
        downloads = version.get("downloads", 0)
        sub = QLabel(f"{date}  ·  {downloads:,} 次下载  ·  {version['version_number']}")
        sub.setStyleSheet("font-size: 11px; color: #6e7076;")
        left.addWidget(sub)

        layout.addLayout(left, 1)

        # 右侧：下载按钮
        btn = QPushButton("⬇  下载")
        btn.setFixedSize(90, 32)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b; color: white;
                border: none; border-radius: 6px;
                font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #4da25a; }
        """)
        btn.clicked.connect(lambda: self.download_requested.emit(version))
        layout.addWidget(btn)


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modrinth 下载 - Mosslight")
        self.resize(820, 700)
        self.setStyleSheet("""
            QMainWindow { background-color: #1b1c1f; }
            QLabel { color: #e9e9ec; }
            QLineEdit, QComboBox {
                background-color: #2a2c30; color: #e9e9ec;
                border: 1px solid #3a3c42; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ---- 顶部：搜索 + 过滤 ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Mod:"))
        self.mod_input = QLineEdit("Fabric API")   # 测试带空格
        top.addWidget(self.mod_input, 2)

        top.addWidget(QLabel("MC:"))
        self.mc_combo = QComboBox()
        self.mc_combo.addItems(["1.21.4", "1.21.3", "1.21.2", "1.21.1", "1.20.4", "1.20.1"])
        self.mc_combo.setCurrentText("1.21.2")
        top.addWidget(self.mc_combo)

        top.addWidget(QLabel("加载器:"))
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["fabric", "forge", "neoforge", "quilt"])
        top.addWidget(self.loader_combo)

        btn = QPushButton("🔍 查询")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b; color: white;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-weight: bold;
            }
        """)
        btn.clicked.connect(self.search)
        top.addWidget(btn)
        layout.addLayout(top)

        # ---- Mod 信息 ----
        self.mod_info = QLabel("")
        self.mod_info.setStyleSheet("color: #a0a1a7; font-size: 12px;")
        self.mod_info.setWordWrap(True)
        layout.addWidget(self.mod_info)

        # ---- 版本列表 ----
        layout.addWidget(QLabel("可用版本（已按 MC 版本 + 加载器过滤）:"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setSpacing(6)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        # 自动搜索
        self.search()

    def search(self):
        # 清空
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        mod = self.mod_input.text().strip()
        mc = self.mc_combo.currentText()
        loader = self.loader_combo.currentText()

        self.mod_info.setText("正在查询...")

        self.loader = VersionsLoader(mod, mc_version=mc, loader=loader)
        self.loader.loaded.connect(self._on_loaded)
        self.loader.start()

    def _on_loaded(self, project: dict, versions: list):
        if not project:
            self.mod_info.setText(f"❌ 未找到 mod: {self.mod_input.text()}")
            return

        # Mod 信息
        name = project.get("title", "")
        slug = project.get("slug", "")
        desc = project.get("description", "")
        downloads = project.get("downloads", 0)
        self.mod_info.setText(
            f"<b>{name}</b> ({slug})  ·  {downloads:,} 次下载<br>{desc}"
        )

        if not versions:
            self.list_layout.addWidget(QLabel("没有兼容的版本"))
            self.list_layout.addStretch()
            return

        # 按类型排序：release > beta > alpha，然后按时间倒序
        type_order = {"release": 0, "beta": 1, "alpha": 2}
        versions.sort(key=lambda v: (
            type_order.get(v.get("version_type"), 9),
            v.get("date_published", "")
        ), reverse=False)
        # 时间再倒序
        versions.sort(key=lambda v: (
            type_order.get(v.get("version_type"), 9),
        ))
        # 保持 release 优先，内部时间倒序

        for v in versions:
            card = VersionCard(v)
            card.download_requested.connect(self.download_version)
            self.list_layout.addWidget(card)

        self.list_layout.addStretch()
        self.mod_info.setText(self.mod_info.text() + f"  ·  找到 {len(versions)} 个兼容版本")

    def download_version(self, version: dict):
        # 找到主文件
        primary = None
        for f in version.get("files", []):
            if f.get("primary"):
                primary = f
                break
        if not primary and version.get("files"):
            primary = version["files"][0]

        if not primary:
            QMessageBox.warning(self, "错误", "没有可下载的文件")
            return

        url = primary["url"]
        filename = primary["filename"]
        size_mb = primary.get("size", 0) / 1024 / 1024

        reply = QMessageBox.question(
            self, "确认下载",
            f"文件: {filename}\n"
            f"大小: {size_mb:.2f} MB\n\n"
            f"要下载吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 选择保存目录
        from PyQt6.QtWidgets import QFileDialog
        save_dir = QFileDialog.getExistingDirectory(self, "保存到")
        if not save_dir:
            return

        save_path = Path(save_dir) / filename

        # 下载
        self.mod_info.setText(f"下载中: {filename} ...")
        try:
            r = requests.get(url, headers=HEADERS, stream=True, timeout=60)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            self.mod_info.setText(f"✓ 已下载: {save_path}")
            QMessageBox.information(self, "完成", f"已保存到:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "下载失败", str(e))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
