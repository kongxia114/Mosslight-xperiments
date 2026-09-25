"""
模组下载工具
- 从 Modrinth 搜索 mod
- 选择 mod → 选版本 → 下载到 mods 目录
- 显示版本发布时间、下载量等
"""

import sys
import json
import hashlib
import requests
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QComboBox, QGroupBox,
    QMessageBox, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QSplitter, QFormLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont


# ============================================================
# 默认配置
# ============================================================
DEFAULT_MC_DIR = r"D:\DHML\.minecraft"
# ============================================================


# ============================================================
# 工具
# ============================================================
def make_log_fn(log_callback):
    if log_callback is None:
        return print
    if hasattr(log_callback, "emit"):
        return log_callback.emit
    return log_callback


def bytes_human(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def downloads_human(n):
    if n < 1000:
        return str(n)
    if n < 1000 * 1000:
        return f"{n / 1000:.1f}K"
    if n < 1000 * 1000 * 1000:
        return f"{n / 1000 / 1000:.1f}M"
    return f"{n / 1000 / 1000 / 1000:.1f}B"


# ============================================================
# Downloader（保留，简化）
# ============================================================
class Downloader:
    def __init__(self, log_callback=None):
        self.log = make_log_fn(log_callback)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mosslight/1.0"})

    @staticmethod
    def sha1_file(path):
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def download_file(self, url, save_path, sha1=None, retries=2):
        save_path = Path(save_path)

        if save_path.exists() and sha1:
            try:
                if self.sha1_file(save_path) == sha1:
                    self.log(f"    已存在，跳过: {save_path.name}")
                    return True
            except:
                pass

        save_path.parent.mkdir(parents=True, exist_ok=True)

        last_error = None
        for attempt in range(retries):
            try:
                r = self.session.get(url, stream=True, timeout=60)
                r.raise_for_status()
                tmp = save_path.with_suffix(save_path.suffix + ".tmp")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                if sha1:
                    actual = self.sha1_file(tmp)
                    if actual != sha1:
                        tmp.unlink()
                        self.log(f"    ❌ SHA1 不匹配")
                        continue
                if save_path.exists():
                    save_path.unlink()
                tmp.rename(save_path)
                return True
            except Exception as e:
                last_error = e
                if attempt == retries - 1:
                    break

        self.log(f"    ❌ 下载失败: {last_error}")
        return False


# ============================================================
# Modrinth 客户端
# ============================================================
class ModrinthClient:
    BASE = "https://api.modrinth.com/v2"

    def __init__(self, log_callback=None):
        self.log = make_log_fn(log_callback)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mosslight/1.0 (contact: local)"})

    def search(self, query, loader=None, mc_version=None, limit=20, offset=0):
        """搜索 mod
        
        loader: "forge" / "fabric" / "neoforge" / "quilt" / None
        mc_version: "1.20.1" / None
        """
        facets = [["project_type:mod"]]
        if loader:
            facets.append([f"categories:{loader}"])
        if mc_version:
            facets.append([f"versions:{mc_version}"])

        params = {
            "query": query or "",
            "limit": limit,
            "offset": offset,
            "facets": json.dumps(facets),
        }
        r = self.session.get(f"{self.BASE}/search", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_versions(self, project_id, loader=None, mc_version=None):
        """拿某个 mod 的版本列表"""
        url = f"{self.BASE}/project/{project_id}/version"
        params = {}
        if mc_version:
            params["game_versions"] = json.dumps([mc_version])
        if loader:
            params["loaders"] = json.dumps([loader])

        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()


# ============================================================
# 搜索线程
# ============================================================
class SearchWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, query, loader, mc_version):
        super().__init__()
        self.query = query
        self.loader = loader
        self.mc_version = mc_version

    def run(self):
        try:
            self.log.emit(f"搜索: query='{self.query}' loader={self.loader} mc={self.mc_version}")
            client = ModrinthClient(log_callback=self.log)
            result = client.search(self.query, self.loader, self.mc_version)
            self.log.emit(f"✓ 找到 {result.get('total_hits', 0)} 个结果")
            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ 搜索失败: {e}")
            self.log.emit(traceback.format_exc())
            self.finished.emit({})


# ============================================================
# 版本列表线程
# ============================================================
class VersionsWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(list)

    def __init__(self, project_id, loader, mc_version):
        super().__init__()
        self.project_id = project_id
        self.loader = loader
        self.mc_version = mc_version

    def run(self):
        try:
            self.log.emit(f"获取 {self.project_id} 的版本列表...")
            client = ModrinthClient(log_callback=self.log)
            versions = client.get_versions(self.project_id, self.loader, self.mc_version)
            self.log.emit(f"✓ 找到 {len(versions)} 个版本")
            self.finished.emit(versions)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ 获取版本失败: {e}")
            self.log.emit(traceback.format_exc())
            self.finished.emit([])


# ============================================================
# 下载线程
# ============================================================
class DownloadWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, file_url, save_path, sha1=None):
        super().__init__()
        self.file_url = file_url
        self.save_path = save_path
        self.sha1 = sha1

    def run(self):
        try:
            dl = Downloader(log_callback=self.log)
            ok = dl.download_file(self.file_url, self.save_path, self.sha1)
            self.finished.emit(ok)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ 下载失败: {e}")
            self.log.emit(traceback.format_exc())
            self.finished.emit(False)


# ============================================================
# Mod 版本选择对话框
# ============================================================
class ModVersionsDialog(QDialog):
    def __init__(self, mod_info, versions, mc_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"选择版本 - {mod_info.get('title', mod_info.get('slug', ''))}")
        self.resize(720, 560)

        self.mod_info = mod_info
        self.versions = versions
        self.mc_dir = Path(mc_dir)
        self.selected_version = None

        layout = QVBoxLayout(self)

        # ===== mod 信息 =====
        info_box = QGroupBox("模组信息")
        info_form = QFormLayout(info_box)

        title_label = QLabel(mod_info.get("title", ""))
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        info_form.addRow("名称:", title_label)

        info_form.addRow("作者:", QLabel(mod_info.get("author", "?")))
        info_form.addRow("下载量:", QLabel(downloads_human(mod_info.get("downloads", 0))))

        desc_label = QLabel(mod_info.get("description", ""))
        desc_label.setWordWrap(True)
        info_form.addRow("简介:", desc_label)

        layout.addWidget(info_box)

        # ===== 版本列表 =====
        layout.addWidget(QLabel(f"可用版本（{len(versions)} 个）："))

        self.version_list = QListWidget()
        self.version_list.setFont(QFont("Consolas", 9))
        for v in versions:
            name = v.get("name") or v.get("version_number", "?")
            game_vers = ", ".join(v.get("game_versions", [])[:3])
            loaders = ", ".join(v.get("loaders", []))
            date = v.get("date_published", "")[:10]
            dl_count = downloads_human(v.get("downloads", 0))

            text = f"{name}  [{loaders}]  MC {game_vers}  |  {date}  |  ↓{dl_count}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, v)
            self.version_list.addItem(item)

        if self.version_list.count() > 0:
            self.version_list.setCurrentRow(0)

        self.version_list.currentItemChanged.connect(self._on_version_change)
        layout.addWidget(self.version_list, 1)

        # ===== 选中版本详情 =====
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.detail_label)

        # ===== 保存目录 =====
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("保存到:"))
        self.dir_label = QLabel(str(self.mc_dir / "mods"))
        self.dir_label.setStyleSheet("color: #5ec269;")
        dir_row.addWidget(self.dir_label)
        dir_row.addStretch()
        layout.addLayout(dir_row)

        # ===== 按钮 =====
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.download_btn = QPushButton("⬇  下载")
        self.download_btn.setFixedWidth(120)
        self.download_btn.setFixedHeight(36)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #3fa34d; color: white;
                font-weight: bold; border: none; border-radius: 6px;
            }
            QPushButton:hover { background-color: #4bb85a; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.download_btn.clicked.connect(self._on_download)

        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedWidth(80)
        self.close_btn.setFixedHeight(36)
        self.close_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self._on_version_change()

    def _on_version_change(self):
        item = self.version_list.currentItem()
        if not item:
            self.detail_label.setText("")
            return
        v = item.data(Qt.ItemDataRole.UserRole)
        files = v.get("files", [])
        primary = next((f for f in files if f.get("primary")), None)
        if not primary and files:
            primary = files[0]

        filename = primary.get("filename", "?") if primary else "?"
        size = primary.get("size", 0) if primary else 0

        detail = (
            f"版本号: {v.get('version_number', '?')}\n"
            f"发布时间: {v.get('date_published', '?')}\n"
            f"支持 MC: {', '.join(v.get('game_versions', []))}\n"
            f"加载器: {', '.join(v.get('loaders', []))}\n"
            f"文件名: {filename}\n"
            f"大小: {bytes_human(size)}"
        )
        self.detail_label.setText(detail)

    def _on_download(self):
        item = self.version_list.currentItem()
        if not item:
            return
        v = item.data(Qt.ItemDataRole.UserRole)
        files = v.get("files", [])
        primary = next((f for f in files if f.get("primary")), None)
        if not primary and files:
            primary = files[0]
        if not primary:
            QMessageBox.warning(self, "提示", "这个版本没有可下载的文件")
            return

        url = primary.get("url")
        filename = primary.get("filename", "mod.jar")
        sha1 = primary.get("hashes", {}).get("sha1")

        # 下载到 mods 目录
        mods_dir = self.mc_dir / "mods"
        save_path = mods_dir / filename

        # 让父窗口处理下载（避免在这里创建线程）
        self.selected_version = {
            "url": url,
            "filename": filename,
            "sha1": sha1,
            "save_path": save_path,
        }
        self.accept()


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("模组下载器")
        self.resize(1100, 720)

        self.search_result = {}
        self.search_worker = None
        self.versions_worker = None
        self.download_worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ========== 顶部：搜索区 ==========
        search_box = QGroupBox("搜索")
        search_layout = QVBoxLayout(search_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("关键词:"))
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("比如 JEI、Sodium、小地图...")
        self.query_input.returnPressed.connect(self.on_search)
        row1.addWidget(self.query_input, 1)

        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedWidth(100)
        self.search_btn.setFixedHeight(30)
        self.search_btn.clicked.connect(self.on_search)
        row1.addWidget(self.search_btn)
        search_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("加载器:"))
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["（全部）", "forge", "fabric", "neoforge", "quilt"])
        self.loader_combo.setFixedWidth(140)
        row2.addWidget(self.loader_combo)

        row2.addSpacing(20)
        row2.addWidget(QLabel("MC 版本:"))
        self.mc_version_input = QLineEdit("1.20.1")
        self.mc_version_input.setFixedWidth(100)
        self.mc_version_input.setPlaceholderText("留空则不限")
        row2.addWidget(self.mc_version_input)

        row2.addSpacing(20)
        row2.addWidget(QLabel("MC 目录:"))
        self.mc_dir_input = QLineEdit(DEFAULT_MC_DIR)
        row2.addWidget(self.mc_dir_input, 1)

        search_layout.addLayout(row2)
        layout.addWidget(search_box)

        # ========== 中间：结果列表 ==========
        layout.addWidget(QLabel("搜索结果（双击打开版本列表）："))

        self.result_list = QListWidget()
        self.result_list.setFont(QFont("Microsoft YaHei", 10))
        self.result_list.itemDoubleClicked.connect(self.on_item_double_click)
        layout.addWidget(self.result_list, 1)

        # ========== 底部：日志区 ==========
        layout.addWidget(QLabel("日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setFixedHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_text)

        self.log("就绪。输入关键词后点『搜索』")

    def log(self, msg):
        self.log_text.append(msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---------- 搜索 ----------
    def on_search(self):
        query = self.query_input.text().strip()
        loader = self.loader_combo.currentText()
        if loader == "（全部）":
            loader = None
        mc_version = self.mc_version_input.text().strip() or None

        self.result_list.clear()
        self.search_btn.setEnabled(False)
        self.search_btn.setText("搜索中...")

        self.search_worker = SearchWorker(query, loader, mc_version)
        self.search_worker.log.connect(self.log)
        self.search_worker.finished.connect(self._on_search_finished)
        threading.Thread(target=self.search_worker.run, daemon=True).start()

    def _on_search_finished(self, result):
        self.search_result = result
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 搜索")

        hits = result.get("hits", [])
        if not hits:
            self.log("未找到结果")
            return

        for h in hits:
            title = h.get("title", "?")
            author = h.get("author", "?")
            downloads = downloads_human(h.get("downloads", 0))
            desc = h.get("description", "")
            if len(desc) > 70:
                desc = desc[:70] + "..."

            text = f"{title}  ·  by {author}  ·  ↓{downloads}\n    {desc}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, h)
            self.result_list.addItem(item)

        self.log(f"✓ 显示 {len(hits)} 个结果")

    # ---------- 双击打开版本列表 ----------
    def on_item_double_click(self, item):
        mod_info = item.data(Qt.ItemDataRole.UserRole)
        project_id = mod_info.get("project_id")
        if not project_id:
            return

        loader = self.loader_combo.currentText()
        if loader == "（全部）":
            loader = None
        mc_version = self.mc_version_input.text().strip() or None

        self.log(f"打开 {mod_info.get('title')} 的版本列表...")

        # 用 dialog 显示 loading，等数据回来再填
        self.versions_worker = VersionsWorker(project_id, loader, mc_version)
        self.versions_worker.log.connect(self.log)
        self.versions_worker.finished.connect(
            lambda versions: self._on_versions_loaded(mod_info, versions)
        )
        threading.Thread(target=self.versions_worker.run, daemon=True).start()

    def _on_versions_loaded(self, mod_info, versions):
        if not versions:
            self.log("❌ 没有可用版本")
            QMessageBox.information(self, "提示", "这个 mod 没有匹配当前条件的版本")
            return

        mc_dir = self.mc_dir_input.text().strip()
        dlg = ModVersionsDialog(mod_info, versions, mc_dir, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_version:
            self._do_download(dlg.selected_version)

    # ---------- 下载 ----------
    def _do_download(self, version_info):
        url = version_info["url"]
        filename = version_info["filename"]
        sha1 = version_info.get("sha1")
        save_path = version_info["save_path"]

        self.log(f"开始下载: {filename}")
        self.log(f"    → {save_path}")

        self.download_worker = DownloadWorker(url, save_path, sha1)
        self.download_worker.log.connect(self.log)
        self.download_worker.finished.connect(self._on_download_finished)
        threading.Thread(target=self.download_worker.run, daemon=True).start()

    def _on_download_finished(self, ok):
        if ok:
            self.log("🎉 下载完成！")
            QMessageBox.information(self, "完成", "模组下载完成！")
        else:
            self.log("❌ 下载失败")
            QMessageBox.warning(self, "失败", "下载失败，请看日志")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
