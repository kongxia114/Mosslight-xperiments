"""
Modrinth 模组详情 + 分组下载
- 上方：模组信息卡片（图标、名字、分类、加载器、下载量、更新时间、按钮）
- 下方：按"游戏版本 + 加载器 + 正式/预览"分组的折叠列表
- 点击分组展开 → 显示具体版本 + 下载按钮（懒渲染）
"""

import re
import sys
import json
import requests
from urllib.parse import quote
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QToolButton,
    QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QGuiApplication
from PyQt6.QtCore import Qt, QByteArray, QUrl, QThread, pyqtSignal, QTimer


# ============================================================
# Modrinth API
# ============================================================
MODRINTH_API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "Mosslight-Launcher/1.0"}


def fetch_modrinth_project(mod_id: str) -> dict:
    """拉取模组信息（slug 或 project_id）"""
    try:
        r = requests.get(f"{MODRINTH_API}/project/{mod_id}",
                         timeout=15, headers=HEADERS)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Modrinth 查询失败: {e}")
    return None


def fetch_all_versions(slug: str) -> list:
    """拉取模组所有版本（不做过滤，前端自己分组）"""
    try:
        r = requests.get(f"{MODRINTH_API}/project/{slug}/version",
                         timeout=20, headers=HEADERS)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"版本查询失败: {e}")
    return []


def search_mcmod_url(name: str) -> str:
    return f"https://search.mcmod.cn/s?key={quote(name)}"


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return (iso_str or "")[:10]


def parse_version_tuple(v: str):
    """把 "1.21.2" 转成 (1, 21, 2)，用于排序
    快照如 "24w14a" → 解析失败时返回 (0,)"""
    nums = re.findall(r"\d+", v)
    if nums:
        return tuple(int(x) for x in nums)
    return (0,)


# 加载器排序（越靠前越先显示）
LOADER_ORDER = {"neoforge": 0, "fabric": 1, "forge": 2, "quilt": 3}
LOADER_LABEL = {
    "neoforge": "NeoForge",
    "fabric": "Fabric",
    "forge": "Forge",
    "quilt": "Quilt",
}


# ============================================================
# 异步加载
# ============================================================
class ProjectLoader(QThread):
    """后台：拉 project + 所有版本"""
    loaded = pyqtSignal(dict, list)
    failed = pyqtSignal(str)

    def __init__(self, mod_id: str):
        super().__init__()
        self.mod_id = mod_id

    def run(self):
        # 1. 拿 project
        project = fetch_modrinth_project(self.mod_id)
        if not project:
            # 尝试把显示名转 slug
            import re as _re
            slug = _re.sub(r"[^a-z0-9\-]", "", self.mod_id.lower().replace(" ", "-"))
            if slug and slug != self.mod_id:
                project = fetch_modrinth_project(slug)
        if not project:
            self.failed.emit(self.mod_id)
            return

        # 2. 拿所有版本
        versions = fetch_all_versions(project["slug"])
        self.loaded.emit(project, versions)


# ============================================================
# 分组逻辑
# ============================================================
def group_versions(versions: list) -> list:
    """按 (game_version, loader, is_prerelease) 分组
    
    返回：[{key, title, versions, sort_key}, ...]，已排序
    """
    groups = {}  # key -> {versions: []}

    for v in versions:
        vtype = v.get("version_type", "release")
        is_prerelease = vtype in ("beta", "alpha")

        for gv in v.get("game_versions", []):
            for loader in v.get("loaders", []):
                key = (gv, loader, is_prerelease)
                if key not in groups:
                    groups[key] = []
                groups[key].append(v)

    # 组装
    result = []
    for (gv, loader, is_prerelease), vs in groups.items():
        loader_label = LOADER_LABEL.get(loader, loader.capitalize())
        title = f"{loader_label} {gv}"
        if is_prerelease:
            title += " 预览版"

        # 组内按时间倒序
        vs_sorted = sorted(vs, key=lambda x: x.get("date_published", ""), reverse=True)

        # 排序 key：游戏版本倒序 → 正式版优先 → loader 顺序
        sort_key = (
            tuple(-x for x in parse_version_tuple(gv)),   # 版本倒序
            1 if is_prerelease else 0,                     # 正式版优先
            LOADER_ORDER.get(loader, 99),                  # loader 顺序
        )

        result.append({
            "key": (gv, loader, is_prerelease),
            "title": title,
            "versions": vs_sorted,
            "sort_key": sort_key,
        })

    result.sort(key=lambda x: x["sort_key"])
    return result


# ============================================================
# 模组详情卡片
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ---- 图标 ----
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setStyleSheet("border-radius: 12px; background-color: #2a2c30;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setText("?")
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # ---- 右：信息 ----
        right = QVBoxLayout()
        right.setSpacing(6)

        # 名字
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
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("font-size: 12px; color: #a0a1a7;")
        right.addWidget(self.meta_label)

        # 简介
        self.desc_label = QLabel("")
        self.desc_label.setStyleSheet("font-size: 12px; color: #b8b8b8;")
        self.desc_label.setWordWrap(True)
        right.addWidget(self.desc_label)

        # 统计
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 12px; color: #a0a1a7;")
        right.addWidget(self.stats_label)

        right.addSpacing(6)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_modrinth = QPushButton("转到 Modrinth")
        self.btn_mcmod = QPushButton("转到 MC 百科")
        self.btn_copy = QPushButton("复制名称")

        for btn in (self.btn_modrinth, self.btn_mcmod, self.btn_copy):
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        # Modrinth 主按钮用绿色
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
            QPushButton:hover { background-color: #4da25a; }
        """)

        btn_row.addStretch()
        right.addLayout(btn_row)

        layout.addLayout(right, 1)

        self.data = None

    def load(self, data: dict):
        self.data = data

        # 图标
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

        # 名字
        self.name_label.setText(data.get("title", ""))
        self.name_en_label.setText(f"|  {data.get('slug', '')}")

        # 分类 + 加载器
        cats = data.get("categories", [])
        loaders = data.get("loaders", [])
        loader_text = " / ".join(LOADER_LABEL.get(l, l.capitalize()) for l in loaders)
        cat_text = ", ".join(cats)
        self.meta_label.setText(f"📂 {cat_text}    ⚙ {loader_text}    🌐 Modrinth")

        # 简介
        self.desc_label.setText(data.get("description", ""))

        # 统计
        downloads = data.get("downloads", 0)
        updated = format_date(data.get("updated", ""))
        self.stats_label.setText(
            f"📥 下载量: {format_number(downloads)}    🕒 上次更新: {updated}"
        )

        # 按钮
        slug = data.get("slug", "")
        self.btn_modrinth.clicked.disconnect()
        self.btn_modrinth.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://modrinth.com/mod/{slug}"))
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
        original = self.btn_copy.text()
        self.btn_copy.setText("已复制 ✓")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText(original))


# ============================================================
# 具体版本卡片
# ============================================================
class VersionCard(QFrame):
    download_requested = pyqtSignal(dict)

    def __init__(self, version: dict):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.version = version
        self.setStyleSheet("""
            VersionCard {
                background-color: #1f2023;
                border-radius: 8px;
                border: 1px solid #2a2c30;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        name_row = QHBoxLayout()
        name = QLabel(version.get("name", version.get("version_number", "")))
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
        name_row.addStretch()
        left.addLayout(name_row)

        # 副信息
        date = format_date(version.get("date_published", ""))
        downloads = version.get("downloads", 0)
        sub = QLabel(f"{date}  ·  {downloads:,} 次下载  ·  {version.get('version_number', '')}")
        sub.setStyleSheet("font-size: 11px; color: #6e7076;")
        left.addWidget(sub)

        layout.addLayout(left, 1)

        # 下载按钮
        btn = QPushButton("⬇  下载")
        btn.setFixedSize(90, 32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
# 可折叠分组
# ============================================================
class CollapsibleGroup(QWidget):
    download_requested = pyqtSignal(dict)

    def __init__(self, title: str, versions: list):
        super().__init__()
        self.versions = versions
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头（可点击）
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText(title)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_btn.setStyleSheet("""
            QToolButton {
                background-color: #232428;
                color: #e9e9ec;
                border: 1px solid #2e3034;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                text-align: left;
            }
            QToolButton:hover {
                background-color: #2a2c30;
                border-color: #5ec269;
            }
            QToolButton:checked {
                background-color: #26282d;
                border-color: #3a3c42;
            }
        """)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        # 内容区（懒加载）
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 6, 0, 6)
        self.content_layout.setSpacing(6)
        self.content.setVisible(False)
        layout.addWidget(self.content)

    def _on_toggle(self):
        checked = self.toggle_btn.isChecked()
        if checked:
            self.toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
            if not self._loaded:
                self._load_content()
            self.content.setVisible(True)
        else:
            self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
            self.content.setVisible(False)

    def _load_content(self):
        """展开时才渲染具体版本"""
        for v in self.versions:
            card = VersionCard(v)
            card.download_requested.connect(self.download_requested.emit)
            self.content_layout.addWidget(card)
        self._loaded = True


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modrinth 模组详情 - Mosslight")
        self.resize(880, 750)
        self.setStyleSheet("""
            QMainWindow { background-color: #1b1c1f; }
            QLabel { color: #e9e9ec; }
            QLineEdit {
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

        # ---- 顶部 ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Modrinth ID / Slug:"))
        self.input = QLineEdit("sodium")
        self.input.returnPressed.connect(self.load_mod)
        top.addWidget(self.input, 1)

        btn = QPushButton("加载")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3f8f4b; color: white;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4da25a; }
        """)
        btn.clicked.connect(self.load_mod)
        top.addWidget(btn)
        layout.addLayout(top)

        # ---- 滚动区 ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(10)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        # ---- Mod 详情卡片（固定上方） ----
        self.detail_card = ModDetailCard()
        self.container_layout.addWidget(self.detail_card)

        # ---- 分组列表容器 ----
        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setSpacing(6)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.addWidget(self.groups_container)

        self.container_layout.addStretch()

        # 自动加载
        self.load_mod()

    def load_mod(self):
        mod_id = self.input.text().strip()
        if not mod_id:
            return

        # 清空分组
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 加载
        self.loader = ProjectLoader(mod_id)
        self.loader.loaded.connect(self._on_loaded)
        self.loader.failed.connect(self._on_failed)
        self.loader.start()

    def _on_failed(self, mod_id: str):
        QMessageBox.warning(self, "未找到", f"未找到 mod: {mod_id}")

    def _on_loaded(self, project: dict, versions: list):
        # 1. 填 mod 详情
        self.detail_card.load(project)

        # 2. 分组
        groups = group_versions(versions)

        if not groups:
            lbl = QLabel("没有可用版本")
            lbl.setStyleSheet("color: #888; padding: 20px;")
            self.groups_layout.addWidget(lbl)
            return

        # 3. 每个分组一个 CollapsibleGroup
        for g in groups:
            group_widget = CollapsibleGroup(g["title"], g["versions"])
            group_widget.download_requested.connect(self._download_version)
            self.groups_layout.addWidget(group_widget)

    def _download_version(self, version: dict):
        # 找主文件
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

        # 保存到 mods 目录（可改成 QFileDialog）
        from PyQt6.QtWidgets import QFileDialog
        save_dir = QFileDialog.getExistingDirectory(self, "保存到 mods 目录")
        if not save_dir:
            return

        from pathlib import Path
        save_path = Path(save_dir) / filename

        # 下载（简单同步，生产环境应异步）
        try:
            reply = QMessageBox.information(self, "开始下载",
                                            f"开始下载到：\n{save_path}")
            r = requests.get(url, headers=HEADERS, stream=True, timeout=60)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
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
