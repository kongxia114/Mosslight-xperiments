"""
Mod 列表示例 - 显示 mods 文件夹里的 mod，带图标和跳转
- 优先从 jar 里读图标（本地，快）
- 没有图标才走 Modrinth API（云端兜底）
- 点"查看"跳转到 Modrinth / MC 百科
"""

import sys
import json
import zipfile
import requests
from pathlib import Path
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QMessageBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QByteArray, QUrl, QThread, pyqtSignal


# ============================================================
# 配置：改成你的 mods 路径
# ============================================================
MODS_DIR = r"D:\DHML\.minecraft\mods"
# ============================================================


# ============================================================
# 从 jar 读 mod 信息
# ============================================================
def read_mod_info(jar_path: str) -> dict:
    """从 mod jar 读取信息"""
    info = {
        "file": str(jar_path),
        "id": "",
        "name": "",
        "version": "",
        "homepage": "",
        "loader": "",
        "icon_path": "",   # jar 内部图标路径
        "error": None,
    }

    try:
        with zipfile.ZipFile(jar_path, "r") as z:
            names = z.namelist()

            # ---------- Fabric ----------
            if "fabric.mod.json" in names:
                data = json.loads(z.read("fabric.mod.json").decode("utf-8"))
                info["id"] = data.get("id", "")
                info["name"] = data.get("name", info["id"])
                info["version"] = data.get("version", "")
                info["loader"] = "fabric"
                contact = data.get("contact", {})
                info["homepage"] = contact.get("homepage", "") or contact.get("sources", "")

                # icon 字段
                icon = data.get("icon")
                if isinstance(icon, dict):
                    # {"64": "xxx.png", "128": "yyy.png"} 取最大的
                    try:
                        keys = sorted(icon.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
                        icon = icon[keys[-1]]
                    except Exception:
                        icon = list(icon.values())[0] if icon else None
                if icon and icon in names:
                    info["icon_path"] = icon
                return info

            # ---------- Forge (1.13+) ----------
            if "META-INF/mods.toml" in names:
                text = z.read("META-INF/mods.toml").decode("utf-8", errors="replace")
                info["loader"] = "forge"
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("modId"):
                        info["id"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("displayName"):
                        info["name"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("version"):
                        info["version"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("displayURL"):
                        info["homepage"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("logoFile"):
                        logo = line.split("=", 1)[1].strip().strip('"')
                        if logo in names:
                            info["icon_path"] = logo
                return info

            # ---------- 旧版 Forge ----------
            if "mcmod.info" in names:
                data = json.loads(z.read("mcmod.info").decode("utf-8"))
                if isinstance(data, list) and data:
                    data = data[0]
                info["loader"] = "forge"
                info["id"] = data.get("modid", "")
                info["name"] = data.get("name", info["id"])
                info["version"] = data.get("version", "")
                info["homepage"] = data.get("url", "")
                logo = data.get("logoFile", "")
                if logo and logo in names:
                    info["icon_path"] = logo
                return info

    except Exception as e:
        info["error"] = str(e)

    return info


def read_mod_icon_from_jar(jar_path: str, icon_path: str):
    """从 jar 里读取图标字节"""
    if not icon_path:
        return None
    try:
        with zipfile.ZipFile(jar_path, "r") as z:
            return z.read(icon_path)
    except Exception:
        return None


# ============================================================
# 云端查询（Modrinth API）
# ============================================================
def query_modrinth(mod_id: str) -> dict:
    """用 mod id / slug 查 Modrinth"""
    try:
        r = requests.get(
            f"https://api.modrinth.com/v2/project/{mod_id}",
            timeout=10,
            headers={"User-Agent": "Mosslight-Launcher/1.0"}
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "icon": data.get("icon_url", ""),
                "url": f"https://modrinth.com/mod/{data.get('slug', mod_id)}",
                "name": data.get("title", ""),
            }
    except Exception:
        pass
    return None


def get_mcmod_search_url(name: str) -> str:
    """MC 百科搜索链接"""
    return f"https://search.mcmod.cn/s?key={quote(name)}"


# ============================================================
# 异步加载 mod（避免卡 UI）
# ============================================================
class ModLoader(QThread):
    """后台加载 mod 列表"""
    loaded = pyqtSignal(dict)      # 每个 mod 加载完成
    finished_all = pyqtSignal(int) # 全部完成，返回总数

    def __init__(self, mods_dir: str):
        super().__init__()
        self.mods_dir = mods_dir

    def run(self):
        mods_dir = Path(self.mods_dir)
        if not mods_dir.exists():
            self.finished_all.emit(0)
            return

        jars = sorted(mods_dir.glob("*.jar"))
        for jar in jars:
            # 1. 读元数据
            info = read_mod_info(str(jar))

            # 2. 尝试本地图标
            icon_bytes = read_mod_icon_from_jar(str(jar), info.get("icon_path", ""))
            icon_source = "local" if icon_bytes else ""

            # 3. 本地没有 → 查 Modrinth
            icon_url = ""
            target_url = info.get("homepage", "")

            if not icon_bytes and info.get("id"):
                mr = query_modrinth(info["id"])
                if mr:
                    if mr.get("icon"):
                        icon_url = mr["icon"]
                        icon_source = "cloud"
                    if mr.get("url"):
                        target_url = mr["url"]

            # 4. 最终链接兜底
            if not target_url:
                target_url = get_mcmod_search_url(info["name"] or info["id"])

            # 5. 打包结果
            result = {
                "info": info,
                "icon_bytes": icon_bytes,
                "icon_url": icon_url,
                "icon_source": icon_source,
                "target_url": target_url,
                "jar_name": jar.name,
            }
            self.loaded.emit(result)

        self.finished_all.emit(len(jars))


# ============================================================
# Mod 卡片
# ============================================================
class ModCard(QFrame):
    def __init__(self, data: dict):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # ---- 图标 ----
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(56, 56)
        self.icon_label.setStyleSheet("border: 1px solid #444; background: #222;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = self._load_icon(data)
        if pixmap and not pixmap.isNull():
            self.icon_label.setPixmap(pixmap.scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            self.icon_label.setText("?")
        layout.addWidget(self.icon_label)

        # ---- 文字 ----
        info = data["info"]
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        name_text = info["name"] or info["id"] or data["jar_name"]
        name_label = QLabel(name_text)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        text_layout.addWidget(name_label)

        sub_parts = []
        if info["id"]:
            sub_parts.append(info["id"])
        if info["version"]:
            sub_parts.append(info["version"])
        if info["loader"]:
            sub_parts.append(info["loader"])
        if data["icon_source"]:
            sub_parts.append(f"icon:{data['icon_source']}")
        sub_label = QLabel("  ·  ".join(sub_parts) if sub_parts else data["jar_name"])
        sub_label.setStyleSheet("color: #888; font-size: 11px;")
        text_layout.addWidget(sub_label)

        layout.addLayout(text_layout, 1)

        # ---- 按钮 ----
        if data["target_url"]:
            btn = QPushButton("查看")
            btn.setFixedWidth(70)
            btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(data["target_url"])))
            layout.addWidget(btn)

    def _load_icon(self, data: dict):
        """加载图标：优先本地字节，其次云端 URL"""
        pixmap = QPixmap()

        # 本地
        if data.get("icon_bytes"):
            pixmap.loadFromData(QByteArray(data["icon_bytes"]))
            if not pixmap.isNull():
                return pixmap

        # 云端
        if data.get("icon_url"):
            try:
                r = requests.get(data["icon_url"], timeout=10,
                                 headers={"User-Agent": "Mosslight-Launcher/1.0"})
                if r.status_code == 200:
                    pixmap.loadFromData(QByteArray(r.content))
                    if not pixmap.isNull():
                        return pixmap
            except Exception:
                pass

        return None


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mod 列表 - Mosslight Launcher")
        self.resize(700, 600)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel { color: #e0e0e0; }
            QPushButton {
                background-color: #3fa34d; color: white;
                border: none; border-radius: 6px;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #4bb85a; }
            QFrame[frameShape="4"] { background-color: #2a2a2a; border-radius: 8px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # ---- 顶部：路径输入 + 扫描按钮 ----
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Mods 目录:"))
        self.path_input = QLineEdit(MODS_DIR)
        top_row.addWidget(self.path_input, 1)
        self.scan_btn = QPushButton("🔍 扫描")
        self.scan_btn.clicked.connect(self.scan)
        top_row.addWidget(self.scan_btn)
        main_layout.addLayout(top_row)

        # ---- 状态栏 ----
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888; font-size: 12px; padding: 4px;")
        main_layout.addWidget(self.status_label)

        # ---- 滚动区 ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1e1e1e; }")
        self.container = QWidget()
        self.container.setStyleSheet("background: #1e1e1e;")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setSpacing(6)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.container)
        main_layout.addWidget(scroll, 1)

        # 自动扫描
        self.scan()

    def scan(self):
        # 清空
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        mods_dir = self.path_input.text().strip()
        if not Path(mods_dir).exists():
            self.status_label.setText(f"❌ 目录不存在: {mods_dir}")
            return

        self.status_label.setText("正在扫描...")
        self.scan_btn.setEnabled(False)

        self.loader = ModLoader(mods_dir)
        self.loader.loaded.connect(self._on_mod_loaded)
        self.loader.finished_all.connect(self._on_all_loaded)
        self.loader.start()

    def _on_mod_loaded(self, data: dict):
        card = ModCard(data)
        self.list_layout.addWidget(card)

    def _on_all_loaded(self, total: int):
        self.list_layout.addStretch()
        self.status_label.setText(f"✓ 共 {total} 个 mod")
        self.scan_btn.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
