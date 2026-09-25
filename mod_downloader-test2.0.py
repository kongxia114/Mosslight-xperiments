"""
Modrinth 模组详情卡片
- 从 Modrinth API 拉取模组信息
- 显示图标、名字、分类、加载器、版本、下载量、更新时间
- 提供跳转按钮：Modrinth、MC 百科、复制名称
"""

import sys
import requests
from urllib.parse import quote
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QTextEdit
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QGuiApplication
from PyQt6.QtCore import Qt, QByteArray, QUrl, QThread, pyqtSignal


# ============================================================
# Modrinth API
# ============================================================
MODRINTH_API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "Mosslight-Launcher/1.0"}


def fetch_modrinth_project(mod_id: str) -> dict:
    """从 Modrinth 拉取模组信息（mod_id 可以是 slug 或 project_id）"""
    try:
        r = requests.get(f"{MODRINTH_API}/project/{mod_id}",
                         timeout=15, headers=HEADERS)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Modrinth 查询失败: {e}")
    return None


def search_mcmod_url(name: str) -> str:
    """MC 百科搜索链接"""
    return f"https://search.mcmod.cn/s?key={quote(name)}"


def format_number(n: int) -> str:
    """把下载量格式化成 1.2M / 123K 这样的形式"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_date(iso_str: str) -> str:
    """把 ISO 日期格式化成 YYYY-MM-DD"""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_str[:10] if iso_str else ""


# ============================================================
# 异步加载
# ============================================================
class ProjectLoader(QThread):
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, mod_id: str):
        super().__init__()
        self.mod_id = mod_id

    def run(self):
        data = fetch_modrinth_project(self.mod_id)
        if data:
            self.loaded.emit(data)
        else:
            self.failed.emit(self.mod_id)


# ============================================================
# Mod 详情卡片
# ============================================================
class ModDetailCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ModDetailCard {
                background-color: #232428;
                border-radius: 12px;
                border: 1px solid #2e3034;
            }
            QLabel { color: #e9e9ec; }
        """)

        # 主布局：左右两栏
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ========== 左：图标 ==========
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setStyleSheet("""
            border-radius: 12px;
            background-color: #2a2c30;
        """)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setText("?")
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # ========== 右：信息 ==========
        right = QVBoxLayout()
        right.setSpacing(6)

        # 名字行
        name_row = QHBoxLayout()
        self.name_label = QLabel("加载中...")
        self.name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #fff;")
        name_row.addWidget(self.name_label)

        self.name_en_label = QLabel("")
        self.name_en_label.setStyleSheet("font-size: 13px; color: #888;")
        name_row.addWidget(self.name_en_label)
        name_row.addStretch()
        right.addLayout(name_row)

        # 分类 + 加载器 + 平台
        meta_row = QHBoxLayout()
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("font-size: 12px; color: #a0a1a7;")
        meta_row.addWidget(self.meta_label)
        meta_row.addStretch()
        right.addLayout(meta_row)

        # 简介
        self.desc_label = QLabel("")
        self.desc_label.setStyleSheet("font-size: 12px; color: #b8b8b8;")
        self.desc_label.setWordWrap(True)
        right.addWidget(self.desc_label)

        # 统计行：下载量 | 更新时间
        stats_row = QHBoxLayout()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 12px; color: #a0a1a7;")
        stats_row.addWidget(self.stats_label)
        stats_row.addStretch()
        right.addLayout(stats_row)

        # 支持版本（占位，动态填充）
        self.versions_row = QHBoxLayout()
        self.versions_label = QLabel("")
        self.versions_label.setStyleSheet("font-size: 11px; color: #6e7076;")
        self.versions_label.setWordWrap(True)
        self.versions_row.addWidget(self.versions_label)
        self.versions_row.addStretch()
        right.addLayout(self.versions_row)

        right.addSpacing(6)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_modrinth = QPushButton("转到 Modrinth")
        self.btn_mcmod = QPushButton("转到 MC 百科")
        self.btn_copy = QPushButton("复制名称")

        for btn in (self.btn_modrinth, self.btn_mcmod, self.btn_copy):
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2c30;
                    color: #e9e9ec;
                    border: 1px solid #3a3c42;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #34363a;
                    border-color: #5ec269;
                    color: #5ec269;
                }
            """)
            btn_row.addWidget(btn)

        # 主按钮：Modrinth 用绿色
        self.btn_modrinth.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4da25a;
            }
        """)

        btn_row.addStretch()
        right.addLayout(btn_row)

        layout.addLayout(right, 1)

        # 按钮信号（占位，加载后覆盖）
        self.btn_modrinth.clicked.connect(lambda: None)
        self.btn_mcmod.clicked.connect(lambda: None)
        self.btn_copy.clicked.connect(lambda: None)

        # 当前数据
        self.data = None

    def load(self, mod_id: str):
        """异步加载 mod 信息"""
        self.name_label.setText("加载中...")
        self.loader = ProjectLoader(mod_id)
        self.loader.loaded.connect(self._on_loaded)
        self.loader.failed.connect(self._on_failed)
        self.loader.start()

    def _on_failed(self, mod_id: str):
        self.name_label.setText(f"❌ 未找到: {mod_id}")

    def _on_loaded(self, data: dict):
        self.data = data

        # 1. 图标
        icon_url = data.get("icon_url", "")
        if icon_url:
            try:
                r = requests.get(icon_url, timeout=10, headers=HEADERS)
                if r.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(r.content))
                    if not pixmap.isNull():
                        self.icon_label.setPixmap(pixmap.scaled(
                            96, 96,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        ))
            except Exception:
                pass

        # 2. 名字
        self.name_label.setText(data.get("title", ""))
        self.name_en_label.setText(f"|  {data.get('slug', '')}")

        # 3. 分类 + 加载器
        cats = data.get("categories", [])
        loaders = data.get("loaders", [])
        loader_text = " / ".join(l.capitalize() for l in loaders)
        cat_text = ", ".join(cats)
        self.meta_label.setText(f"📂 {cat_text}    ⚙ {loader_text}    🌐 Modrinth")

        # 4. 简介
        self.desc_label.setText(data.get("description", ""))

        # 5. 统计
        downloads = data.get("downloads", 0)
        updated = format_date(data.get("updated", ""))
        self.stats_label.setText(
            f"📥 下载量: {format_number(downloads)}    🕒 上次更新: {updated}"
        )

        # 6. 支持版本
        versions = data.get("game_versions", [])
        if versions:
            # 取前 8 个版本
            shown = versions[:8]
            text = ", ".join(shown)
            if len(versions) > 8:
                text += f" ... (共 {len(versions)} 个)"
            self.versions_label.setText(f"🎮 支持版本: {text}")
        else:
            self.versions_label.setText("")

        # 7. 按钮
        modrinth_url = f"https://modrinth.com/mod/{data.get('slug', '')}"
        self.btn_modrinth.clicked.disconnect()
        self.btn_modrinth.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(modrinth_url))
        )

        mcmod_url = search_mcmod_url(data.get("title", ""))
        self.btn_mcmod.clicked.disconnect()
        self.btn_mcmod.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(mcmod_url))
        )

        name = data.get("title", "")
        self.btn_copy.clicked.disconnect()
        self.btn_copy.clicked.connect(lambda: self._copy(name))

    def _copy(self, text: str):
        QGuiApplication.clipboard().setText(text)
        # 简单提示
        original = self.btn_copy.text()
        self.btn_copy.setText("已复制 ✓")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_copy.setText(original))


# ============================================================
# 主窗口（测试用）
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modrinth 模组详情")
        self.resize(820, 500)
        self.setStyleSheet("QMainWindow { background-color: #1b1c1f; }")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 顶部输入
        top = QHBoxLayout()
        top.addWidget(QLabel("Modrinth ID / Slug:"))
        self.input = QLineEdit("sodium")
        top.addWidget(self.input, 1)
        btn = QPushButton("加载")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b; color: white;
                border: none; border-radius: 6px;
                padding: 6px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4da25a; }
        """)
        btn.clicked.connect(self.load_mod)
        top.addWidget(btn)
        layout.addLayout(top)

        # 卡片
        self.card = ModDetailCard()
        layout.addWidget(self.card)

        layout.addStretch()

        # 自动加载 sodium
        self.load_mod()

    def load_mod(self):
        mod_id = self.input.text().strip()
        if mod_id:
            self.card.load(mod_id)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
