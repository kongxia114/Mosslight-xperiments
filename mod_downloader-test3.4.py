"""
Modrinth 搜索界面（异步图标版）
- 顶部：搜索 + 版本 + 加载器 + 类型 + 项目类型
- 搜索结果：立即显示，图标异步加载
- 支持：mod / shader / resourcepack / datapack / modpack
- 内存 + 磁盘缓存
"""

import sys
import os
import json
import hashlib
import requests
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QComboBox,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QPainter, QColor, QFont
from PyQt6.QtCore import (
    Qt, QByteArray, QUrl, QThread, pyqtSignal, QThreadPool,
    QRunnable, QObject
)


HEADERS = {"User-Agent": "Mosslight-Launcher/1.0"}
API = "https://api.modrinth.com/v2"


# ============================================================
# 常量
# ============================================================
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

# 项目类型（对应 Modrinth 的 project_type）
PROJECT_TYPES = [
    ("mod", "模组"),
    ("shader", "光影"),
    ("resourcepack", "资源包"),
    ("datapack", "数据包"),
    ("modpack", "整合包"),
]

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


# ============================================================
# 缓存目录
# ============================================================
def get_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "Mosslight" / "cache" / "icons"
    d.mkdir(parents=True, exist_ok=True)
    return d


CACHE_DIR = get_cache_dir()


def cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def load_cached_icon(url: str):
    """从磁盘缓存读图标，返回 bytes 或 None"""
    if not url:
        return None
    path = CACHE_DIR / f"{cache_key(url)}.bin"
    if path.exists():
        try:
            return path.read_bytes()
        except Exception:
            return None
    return None


def save_icon_to_cache(url: str, data: bytes):
    if not url or not data:
        return
    path = CACHE_DIR / f"{cache_key(url)}.bin"
    try:
        path.write_bytes(data)
    except Exception:
        pass


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ============================================================
# 占位图
# ============================================================
def make_placeholder(size: int = 64, text: str = "?") -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor("#2a2c30"))
    painter = QPainter(pm)
    painter.setPen(QColor("#6e7076"))
    font = QFont()
    font.setPointSize(20)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pm


# ============================================================
# 图标下载任务（线程池）
# ============================================================
class IconSignals(QObject):
    finished = pyqtSignal(str, bytes)   # (url, data)
    failed = pyqtSignal(str)


class IconTask(QRunnable):
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.signals = IconSignals()

    def run(self):
        try:
            # 1. 先查磁盘缓存
            cached = load_cached_icon(self.url)
            if cached:
                self.signals.finished.emit(self.url, cached)
                return

            # 2. 网络下载
            r = requests.get(self.url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.content
            save_icon_to_cache(self.url, data)
            self.signals.finished.emit(self.url, data)
        except Exception:
            self.signals.failed.emit(self.url)


# ============================================================
# 搜索线程
# ============================================================
class SearchWorker(QThread):
    results = pyqtSignal(list, int)   # hits, total

    def __init__(self, query: str, mc_version: str = "全部",
                 loader: str = "全部", category: str = "全部",
                 project_type: str = "mod", sort: str = "relevance"):
        super().__init__()
        self.query = query
        self.mc_version = mc_version
        self.loader = loader
        self.category = category
        self.project_type = project_type
        self.sort = sort

    def run(self):
        try:
            facets = []

            # 项目类型（mod / shader / ...）
            facets.append([f"project_type:{self.project_type}"])

            if self.mc_version and self.mc_version != "全部":
                facets.append([f"versions:{self.mc_version}"])

            # 光影 / 资源包 / 数据包 没有加载器概念
            if self.loader and self.loader != "全部" and self.project_type == "mod":
                facets.append([f"categories:{self.loader}"])

            if self.category and self.category != "全部":
                facets.append([f"categories:{self.category}"])

            params = {
                "query": self.query if self.query else "",
                "facets": json.dumps(facets),
                "limit": 20,
                "index": self.sort,
            }

            # 空查询 → 按下载量推荐
            if not self.query and self.sort == "relevance":
                params["index"] = "downloads"

            r = requests.get(f"{API}/search", params=params,
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()

            hits = data.get("hits", [])
            total = data.get("total_hits", 0)
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
        self.setFixedHeight(100)
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

        # 图标（先占位）
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setPixmap(make_placeholder(64, "?"))
        layout.addWidget(self.icon_label)

        # 中间
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

        # 元信息
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        cats = hit.get("display_categories", []) or hit.get("categories", [])
        # 项目类型标签
        ptype = hit.get("project_type", "mod")
        ptype_label = {
            "mod": "模组",
            "shader": "光影",
            "resourcepack": "资源包",
            "datapack": "数据包",
            "modpack": "整合包",
        }.get(ptype, ptype)
        t = QLabel(ptype_label)
        t.setStyleSheet("""
            background-color: #3a3c42;
            color: #d0d0d0;
            border-radius: 3px;
            padding: 1px 6px;
            font-size: 10px;
        """)
        meta_row.addWidget(t)

        # 加载器标签（只对 mod）
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

        # 支持版本
        versions = hit.get("versions", [])
        if versions:
            v_text = ", ".join(versions[-3:])
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

    def set_icon(self, data: bytes):
        """图标下载完成后更新"""
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(data))
        if pixmap.isNull():
            return
        self.icon_label.setPixmap(pixmap.scaled(
            64, 64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

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
        self.resize(1000, 780)
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

        # 图标线程池
        self.icon_pool = QThreadPool()
        self.icon_pool.setMaxThreadCount(8)

        # 内存缓存：url -> bytes
        self.icon_memory_cache = {}
        # 当前 URL -> 卡片列表（同一个图标可能被多个卡片用，但这里简化处理）
        self.url_to_cards = {}

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ========== 第一行：搜索框 + 版本 + 加载器 ==========
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模组 / 光影 / 资源包 / 数据包 / 整合包...")
        self.search_input.returnPressed.connect(self.do_search)
        row1.addWidget(self.search_input, 3)

        row1.addWidget(QLabel("版本:"))
        self.mc_combo = QComboBox()
        self.mc_combo.addItems(MC_VERSIONS)
        self.mc_combo.setFixedWidth(110)
        row1.addWidget(self.mc_combo)

        row1.addWidget(QLabel("加载器:"))
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(LOADERS)
        self.loader_combo.setFixedWidth(100)
        row1.addWidget(self.loader_combo)

        layout.addLayout(row1)

        # ========== 第二行：项目类型 + 分类 + 按钮 ==========
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(QLabel("类型:"))
        self.ptype_combo = QComboBox()
        for key, label in PROJECT_TYPES:
            self.ptype_combo.addItem(label, key)
        self.ptype_combo.setFixedWidth(100)
        self.ptype_combo.currentIndexChanged.connect(self._on_ptype_changed)
        row2.addWidget(self.ptype_combo)

        row2.addWidget(QLabel("分类:"))
        self.cat_combo = QComboBox()
        for item in CATEGORIES:
            if isinstance(item, tuple):
                self.cat_combo.addItem(item[1], item[0])
            else:
                self.cat_combo.addItem(item, item)
        self.cat_combo.setFixedWidth(120)
        row2.addWidget(self.cat_combo)

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
        row2.addWidget(self.search_btn)

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
        row2.addWidget(self.reset_btn)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888; font-size: 12px; padding-left: 12px;")
        row2.addWidget(self.status_label)
        row2.addStretch()

        layout.addLayout(row2)

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

        # 首次进入 → 显示热门模组
        self.do_search()

    def _on_ptype_changed(self):
        """项目类型变化时，光影/资源包/数据包不支持加载器筛选"""
        ptype = self.ptype_combo.currentData()
        if ptype in ("shader", "resourcepack", "datapack"):
            self.loader_combo.setEnabled(False)
        else:
            self.loader_combo.setEnabled(True)

    # ---------- 搜索 ----------
    def do_search(self):
        # 清空
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.url_to_cards.clear()

        query = self.search_input.text().strip()
        mc = self.mc_combo.currentText()
        loader = self.loader_combo.currentText() if self.loader_combo.isEnabled() else "全部"
        cat = self.cat_combo.currentData() or "全部"
        ptype = self.ptype_combo.currentData() or "mod"

        if not query:
            self.status_label.setText("加载推荐...")
        else:
            self.status_label.setText(f"搜索: {query} ...")

        self.search_btn.setEnabled(False)

        self.worker = SearchWorker(query, mc, loader, cat, ptype)
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

        # 立即渲染所有卡片（图标占位）
        for hit in hits:
            card = ModResultCard(hit)
            card.clicked.connect(self._on_card_clicked)
            self.results_layout.addWidget(card)

            # 注册图标 URL → 卡片
            icon_url = hit.get("icon_url", "")
            if icon_url:
                if icon_url not in self.url_to_cards:
                    self.url_to_cards[icon_url] = []
                self.url_to_cards[icon_url].append(card)

        self.results_layout.addStretch()

        if total > len(hits):
            self.status_label.setText(f"显示 {len(hits)} / 共 {total} 个结果")
        else:
            self.status_label.setText(f"✓ {len(hits)} 个结果")

        # 启动图标异步加载
        self._load_icons_async()

    def _load_icons_async(self):
        """并发下载所有图标"""
        for url in list(self.url_to_cards.keys()):
            # 1. 内存缓存
            if url in self.icon_memory_cache:
                data = self.icon_memory_cache[url]
                for card in self.url_to_cards[url]:
                    card.set_icon(data)
                continue

            # 2. 磁盘缓存
            cached = load_cached_icon(url)
            if cached:
                self.icon_memory_cache[url] = cached
                for card in self.url_to_cards[url]:
                    card.set_icon(cached)
                continue

            # 3. 网络下载（线程池）
            task = IconTask(url)
            task.signals.finished.connect(self._on_icon_ready)
            task.signals.failed.connect(self._on_icon_failed)
            self.icon_pool.start(task)

    def _on_icon_ready(self, url: str, data: bytes):
        self.icon_memory_cache[url] = data
        for card in self.url_to_cards.get(url, []):
            card.set_icon(data)

    def _on_icon_failed(self, url: str):
        # 加载失败 → 保留占位符即可，不弹窗
        pass

    def _on_card_clicked(self, hit: dict):
        slug = hit.get("slug", "")
        url = f"https://modrinth.com/{hit.get('project_type', 'mod')}/{slug}"
        QDesktopServices.openUrl(QUrl(url))

    def do_reset(self):
        self.search_input.clear()
        self.mc_combo.setCurrentIndex(0)
        self.loader_combo.setCurrentIndex(0)
        self.cat_combo.setCurrentIndex(0)
        self.ptype_combo.setCurrentIndex(0)
        self.do_search()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
