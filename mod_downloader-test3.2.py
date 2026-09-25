"""
Modrinth 搜索界面
- 顶部：搜索框 + 版本 + 加载器 + 类型 + 搜索/重置
- 默认：显示热门推荐
- 搜索后：显示结果列表
"""

import sys
import json
import requests
from urllib.parse import quote
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QComboBox,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QByteArray, QUrl, QThread, pyqtSignal


HEADERS = {"User-Agent": "Mosslight-Launcher/1.0"}
API = "https://api.modrinth.com/v2"


# ============================================================
# 常量
# ============================================================
# 常用的 MC 版本（可以后面改成从 API 动态拉）
MC_VERSIONS = [
    "全部",
    "1.21.4", "1.21.3", "1.21.2", "1.21.1", "1.21",
    "1.20.6", "1.20.4", "1.20.2", "1.20.1", "1.20",
    "1.19.4", "1.19.2", "1.19",
    "1.18.2", "1.18.1",
    "1.17.1",
    "1.16.5", "1.16.4",
    "1.15.2", "1.14.4",
    "1.12.2", "1.7.10",
]

LOADERS = ["全部", "fabric", "forge", "neoforge", "quilt"]

CATEGORIES = [
    "全部",
    ("adventure", "冒险"),
    ("decoration", "装饰"),
    ("economy", "经济"),
    ("equipment", "装备"),
    ("food", "食物"),
    ("game-mechanics", "游戏机制"),
    ("library", "支持库"),
    ("magic", "魔法"),
    ("management", "管理"),
    ("minigame", "小游戏"),
    ("mobs", "生物"),
    ("optimization", "性能优化"),
    ("social", "社交"),
    ("storage", "存储"),
    ("technology", "科技"),
    ("transportation", "交通"),
    ("utility", "实用工具"),
    ("worldgen", "世界生成"),
]


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ============================================================
# 搜索线程
# ============================================================
class SearchWorker(QThread):
    """后台搜索 + 下载图标"""
    results = pyqtSignal(list, int)   # hits, total

    def __init__(self, query: str, mc_version: str = "全部",
                 loader: str = "全部", category: str = "全部",
                 sort: str = "relevance"):
        super().__init__()
        self.query = query
        self.mc_version = mc_version
        self.loader = loader
        self.category = category
        self.sort = sort

    def run(self):
        try:
            facets = []

            if self.mc_version and self.mc_version != "全部":
                facets.append([f"versions:{self.mc_version}"])

            if self.loader and self.loader != "全部":
                facets.append([f"categories:{self.loader}"])

            if self.category and self.category != "全部":
                facets.append([f"categories:{self.category}"])

            # 只搜 mod
            facets.append(["project_type:mod"])

            params = {
                "query": self.query if self.query else "",
                "facets": json.dumps(facets),
                "limit": 20,
                "index": self.sort,
            }

            # 空查询 + 默认排序 → 显示热门
            if not self.query and self.sort == "relevance":
                params["index"] = "downloads"

            r = requests.get(f"{API}/search", params=params,
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()

            hits = data.get("hits", [])
            total = data.get("total_hits", 0)

            # 给每个 hit 下载图标
            for hit in hits:
                icon_url = hit.get("icon_url", "")
                if icon_url:
                    try:
                        ir = requests.get(icon_url, headers=HEADERS, timeout=10)
                        if ir.status_code == 200:
                            hit["_icon_bytes"] = ir.content
                    except Exception:
                        pass

            self.results.emit(hits, total)

        except Exception as e:
            print(f"搜索失败: {e}")
            import traceback
            traceback.print_exc()
            self.results.emit([], 0)


# ============================================================
# 结果卡片
# ============================================================
class ModResultCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, hit: dict):
        super().__init__()
        self.hit = hit
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(96)
        self.setStyleSheet("""
            ModResultCard {
                background-color: #232428;
                border-radius: 10px;
                border: 1px solid #2e3034;
            }
            ModResultCard:hover {
                background-color: #2a2c30;
                border-color: #5ec269;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # 图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setStyleSheet("""
            background-color: #2a2c30;
            border-radius: 8px;
        """)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setText("?")
        icon_bytes = hit.get("_icon_bytes")
        if icon_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(QByteArray(icon_bytes))
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
        layout.addWidget(self.icon_label)

        # 中间：名字 + 描述 + 元信息
        mid = QVBoxLayout()
        mid.setSpacing(4)

        name_row = QHBoxLayout()
        title = QLabel(hit.get("title", ""))
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #fff;")
        name_row.addWidget(title)

        author = QLabel(f"by {hit.get('author', '')}")
        author.setStyleSheet("font-size: 11px; color: #888;")
        name_row.addWidget(author)
        name_row.addStretch()
        mid.addLayout(name_row)

        desc = QLabel(hit.get("description", ""))
        desc.setStyleSheet("font-size: 12px; color: #a0a1a7;")
        desc.setWordWrap(True)
        mid.addWidget(desc)

        # 元信息行：加载器 + 下载量 + 关注
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        # 显示分类（加载器）
        cats = hit.get("display_categories", []) or hit.get("categories", [])
        loaders_shown = [c for c in cats if c in ("fabric", "forge", "neoforge", "quilt")]
        for ld in loaders_shown[:3]:
            tag = QLabel(ld)
            tag.setStyleSheet("""
                background-color: #2f5d3a;
                color: #b6f0bf;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 10px;
            """)
            meta_row.addWidget(tag)

        # 支持的 MC 版本（取前 3 个）
        versions = hit.get("versions", [])
        if versions:
            v_text = ", ".join(versions[-3:])  # 最后几个通常是最新
            v_label = QLabel(f"🎮 {v_text}")
            v_label.setStyleSheet("font-size: 10px; color: #6e7076;")
            meta_row.addWidget(v_label)

        meta_row.addStretch()

        downloads = hit.get("downloads", 0)
        dl_label = QLabel(f"📥 {format_number(downloads)}")
        dl_label.setStyleSheet("font-size: 11px; color: #a0a1a7;")
        meta_row.addWidget(dl_label)

        follows = hit.get("follows", 0)
        fl_label = QLabel(f"⭐ {format_number(follows)}")
        fl_label.setStyleSheet("font-size: 11px; color: #a0a1a7;")
        meta_row.addWidget(fl_label)

        mid.addLayout(meta_row)

        layout.addLayout(mid, 1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.hit)


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modrinth 搜索 - Mosslight")
        self.resize(950, 750)
        self.setStyleSheet("""
            QMainWindow { background-color: #1b1c1f; }
            QLabel { color: #e9e9ec; }
            QLineEdit, QComboBox {
                background-color: #2a2c30; color: #e9e9ec;
                border: 1px solid #3a3c42; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #2a2c30;
                color: #e9e9ec;
                selection-background-color: #3f8f4b;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ========== 搜索栏 ==========
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模组名 / 关键词...")
        self.search_input.returnPressed.connect(self.do_search)
        search_row.addWidget(self.search_input, 3)

        # 版本
        search_row.addWidget(QLabel("版本:"))
        self.mc_combo = QComboBox()
        self.mc_combo.addItems(MC_VERSIONS)
        self.mc_combo.setFixedWidth(110)
        search_row.addWidget(self.mc_combo)

        # 加载器
        search_row.addWidget(QLabel("加载器:"))
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(LOADERS)
        self.loader_combo.setFixedWidth(100)
        search_row.addWidget(self.loader_combo)

        # 类型
        search_row.addWidget(QLabel("类型:"))
        self.cat_combo = QComboBox()
        for item in CATEGORIES:
            if isinstance(item, tuple):
                self.cat_combo.addItem(item[1], item[0])
            else:
                self.cat_combo.addItem(item, item)
        self.cat_combo.setFixedWidth(110)
        search_row.addWidget(self.cat_combo)

        layout.addLayout(search_row)

        # ========== 第二行：按钮 + 状态 ==========
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedHeight(34)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b; color: white;
                border: none; border-radius: 6px;
                padding: 0 22px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4da25a; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.search_btn.clicked.connect(self.do_search)
        btn_row.addWidget(self.search_btn)

        self.reset_btn = QPushButton("重置条件")
        self.reset_btn.setFixedHeight(34)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2c30; color: #e9e9ec;
                border: 1px solid #3a3c42; border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #34363a; }
        """)
        self.reset_btn.clicked.connect(self.do_reset)
        btn_row.addWidget(self.reset_btn)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888; font-size: 12px; padding-left: 12px;")
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        # ========== 结果列表 ==========
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.container)
        self.results_layout.setSpacing(8)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        # 首次进入 → 显示热门
        self.do_search()

    # ---------- 搜索 ----------
    def do_search(self):
        # 清空
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        query = self.search_input.text().strip()
        mc = self.mc_combo.currentText()
        loader = self.loader_combo.currentText()
        cat = self.cat_combo.currentData() or "全部"

        if not query:
            self.status_label.setText("加载热门推荐...")
        else:
            self.status_label.setText(f"搜索: {query} ...")

        self.search_btn.setEnabled(False)

        self.worker = SearchWorker(query, mc, loader, cat)
        self.worker.results.connect(self._on_results)
        self.worker.start()

    def _on_results(self, hits: list, total: int):
        self.search_btn.setEnabled(True)

        if not hits:
            lbl = QLabel("没有找到结果")
            lbl.setStyleSheet("color: #888; padding: 40px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.addWidget(lbl)
            self.results_layout.addStretch()
            self.status_label.setText("0 个结果")
            return

        for hit in hits:
            card = ModResultCard(hit)
            card.clicked.connect(self._on_card_clicked)
            self.results_layout.addWidget(card)

        self.results_layout.addStretch()

        if total > len(hits):
            self.status_label.setText(f"显示 {len(hits)} / 共 {total} 个结果")
        else:
            self.status_label.setText(f"✓ {len(hits)} 个结果")

    def _on_card_clicked(self, hit: dict):
        slug = hit.get("slug", "")
        url = f"https://modrinth.com/mod/{slug}"
        # 先简单：打开 Modrinth 网页
        QDesktopServices.openUrl(QUrl(url))

    def do_reset(self):
        self.search_input.clear()
        self.mc_combo.setCurrentIndex(0)
        self.loader_combo.setCurrentIndex(0)
        self.cat_combo.setCurrentIndex(0)
        self.do_search()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
