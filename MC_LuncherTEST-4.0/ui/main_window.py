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
# 模块：ui/main_window.py  —— 主窗口（界面装配 + 事件转发，逻辑未改）
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

import sys
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QComboBox,
    QDialog,
)
from PyQt6.QtGui import QFont
from core.config import DEFAULT_JAVA, DEFAULT_MC_DIR, DEFAULT_MEMORY, DEFAULT_USERNAME
from core.fabric import FabricInstaller
from core.forge import ForgeDownloader
from core.launch import Worker
from core.manifest import ManifestFetcher
from core.workers import DownloadWorker, FabricInstallWorker, ForgeInstallWorker
from ui.dialogs.fabric_select import FabricSelectDialog
from ui.dialogs.forge_select import ForgeSelectDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DHML 启动测试 v3.0")
        self.resize(1120, 780)

        self.manifest_versions = []
        self._remembered_version_id = None
        self.worker = None
        self.download_worker = None
        self.forge_worker = None
        self.fabric_worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ========== 配置区 ==========
        config_box = QGroupBox("配置")
        form = QFormLayout(config_box)

        self.mc_dir_input = QLineEdit(DEFAULT_MC_DIR)
        form.addRow("MC 目录:", self.mc_dir_input)

        self.java_input = QLineEdit(DEFAULT_JAVA)
        form.addRow("Java 路径:", self.java_input)

        row = QHBoxLayout()
        row.addWidget(QLabel("版本:"))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumWidth(380)
        self.version_combo.setEditable(False)
        row.addWidget(self.version_combo)

        self.reload_btn = QPushButton("🔄")
        self.reload_btn.setFixedSize(32, 32)
        self.reload_btn.setToolTip("重新拉取版本清单")
        self.reload_btn.clicked.connect(self.load_manifest)
        row.addWidget(self.reload_btn)

        row.addSpacing(15)
        row.addWidget(QLabel("玩家名:"))
        self.username_input = QLineEdit(DEFAULT_USERNAME)
        self.username_input.setFixedWidth(110)
        row.addWidget(self.username_input)

        row.addSpacing(15)
        row.addWidget(QLabel("内存(MB):"))
        self.memory_input = QLineEdit(str(DEFAULT_MEMORY))
        self.memory_input.setFixedWidth(80)
        row.addWidget(self.memory_input)
        row.addStretch()

        row_widget = QWidget()
        row_widget.setLayout(row)
        form.addRow("", row_widget)

        layout.addWidget(config_box)

        # ========== 按钮区 ==========
        btn_row = QHBoxLayout()

        self.launch_btn = QPushButton("▶  启动游戏")
        self.launch_btn.setFixedHeight(52)
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #3fa34d; color: white;
                font-size: 16px; font-weight: bold;
                border: none; border-radius: 8px;
            }
            QPushButton:hover { background-color: #4bb85a; }
            QPushButton:pressed { background-color: #348a40; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.launch_btn.clicked.connect(self.on_launch)

        self.download_btn = QPushButton("⬇  下载原版")
        self.download_btn.setFixedHeight(52)
        self.download_btn.setFixedWidth(120)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff; color: white;
                font-size: 14px; font-weight: bold;
                border: none; border-radius: 8px;
            }
            QPushButton:hover { background-color: #5aaeff; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.download_btn.clicked.connect(self.on_download)

        self.forge_btn = QPushButton("🔧  安装 Forge")
        self.forge_btn.setFixedHeight(52)
        self.forge_btn.setFixedWidth(140)
        self.forge_btn.setStyleSheet("""
            QPushButton {
                background-color: #d97706; color: white;
                font-size: 14px; font-weight: bold;
                border: none; border-radius: 8px;
            }
            QPushButton:hover { background-color: #ea8a17; }
            QPushButton:pressed { background-color: #b96305; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.forge_btn.clicked.connect(self.on_install_forge)

        self.fabric_btn = QPushButton("🧵  安装 Fabric")
        self.fabric_btn.setFixedHeight(52)
        self.fabric_btn.setFixedWidth(140)
        self.fabric_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed; color: white;
                font-size: 14px; font-weight: bold;
                border: none; border-radius: 8px;
            }
            QPushButton:hover { background-color: #8b4bf7; }
            QPushButton:pressed { background-color: #6b2ad8; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        self.fabric_btn.clicked.connect(self.on_install_fabric)

        self.stop_btn = QPushButton("■  停止")
        self.stop_btn.setFixedHeight(52)
        self.stop_btn.setFixedWidth(90)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.on_stop)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedHeight(52)
        self.clear_btn.setFixedWidth(70)
        self.clear_btn.clicked.connect(lambda: self.log_text.clear())

        btn_row.addWidget(self.launch_btn, 1)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.forge_btn)
        btn_row.addWidget(self.fabric_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        # ========== 日志区 ==========
        layout.addWidget(QLabel("日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_text, 1)

        self.log("就绪。v3.0：原版 / Forge / Fabric 共存")
        self.log(f"MC 目录: {DEFAULT_MC_DIR}")
        self.log(f"Java: {DEFAULT_JAVA}")

        self.load_manifest()

    def log(self, msg):
        self.log_text.append(msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---------- 版本清单 ----------
    def load_manifest(self):
        current = self._get_selected_version()
        self._remembered_version_id = current["id"] if current else None

        self.version_combo.clear()
        self.version_combo.addItem("（加载中...）")
        self.version_combo.setEnabled(False)

        self.manifest_fetcher = ManifestFetcher()
        self.manifest_fetcher.log.connect(self.log)
        self.manifest_fetcher.finished.connect(self._on_manifest_loaded)
        threading.Thread(target=self.manifest_fetcher.run, daemon=True).start()

    def _on_manifest_loaded(self, versions):
        self.manifest_versions = versions
        self.version_combo.clear()

        if not versions:
            self.version_combo.addItem("（获取失败）")
            return

        local_installed = self._get_installed_versions()
        official_ids = {v["id"] for v in versions}
        local_only = sorted(local_installed - official_ids)

        release_versions = [v for v in versions if v.get("type") == "release"]
        snapshot_versions = [v for v in versions if v.get("type") == "snapshot"]
        old_versions = [v for v in versions if v.get("type") in ("old_beta", "old_alpha")]
        release_versions.sort(key=lambda v: v.get("releaseTime", ""), reverse=True)
        snapshot_versions.sort(key=lambda v: v.get("releaseTime", ""), reverse=True)

        def add_group_title(label):
            self.version_combo.insertSeparator(self.version_combo.count())
            self.version_combo.addItem(f"── {label} ──")
            idx = self.version_combo.count() - 1
            self.version_combo.model().item(idx).setEnabled(False)

        if local_only:
            add_group_title("本地版本")
            for vid in local_only:
                self.version_combo.addItem(
                    vid,
                    userData={"id": vid, "_local": True},
                )
            self.version_combo.insertSeparator(self.version_combo.count())

        if release_versions:
            first = release_versions[0]
            mark = "  [已安装]" if first["id"] in local_installed else ""
            self.version_combo.addItem(f"{first['id']}{mark}", userData=first)

            if len(release_versions) > 1:
                add_group_title("正式版")
                for v in release_versions[1:]:
                    vid = v["id"]
                    mark = "  [已安装]" if vid in local_installed else ""
                    self.version_combo.addItem(f"{vid}{mark}", userData=v)
                self.version_combo.insertSeparator(self.version_combo.count())

        if snapshot_versions:
            add_group_title("快照")
            for v in snapshot_versions:
                vid = v["id"]
                mark = "  [已安装]" if vid in local_installed else ""
                self.version_combo.addItem(f"{vid}{mark}", userData=v)
            self.version_combo.insertSeparator(self.version_combo.count())

        if old_versions:
            add_group_title("远古版")
            for v in old_versions:
                vid = v["id"]
                mark = "  [已安装]" if vid in local_installed else ""
                self.version_combo.addItem(f"{vid}{mark}", userData=v)

        self.version_combo.setEnabled(True)

        restored = False
        remembered = self._remembered_version_id
        if remembered:
            for i in range(self.version_combo.count()):
                data = self.version_combo.itemData(i)
                if isinstance(data, dict) and data.get("id") == remembered:
                    self.version_combo.setCurrentIndex(i)
                    restored = True
                    self.log(f"✓ 已恢复选中版本: {remembered}")
                    break
        if not restored:
            self.version_combo.setCurrentIndex(0)

        self.log(f"✓ 版本下拉框已填充（{len(versions)} 个官方 + {len(local_only)} 个本地）")

    def _get_installed_versions(self):
        mc_dir = Path(self.mc_dir_input.text().strip())
        versions_dir = mc_dir / "versions"
        if not versions_dir.exists():
            return set()
        try:
            result = set()
            for p in versions_dir.iterdir():
                if p.is_dir() and list(p.glob("*.json")):
                    result.add(p.name)
            return result
        except:
            return set()

    def _get_selected_version(self):
        data = self.version_combo.currentData()
        if not data or not isinstance(data, dict):
            return None
        return data

    def _refresh_installed_marks(self):
        installed = self._get_installed_versions()
        for i in range(self.version_combo.count()):
            data = self.version_combo.itemData(i)
            if not isinstance(data, dict):
                continue
            if data.get("_local"):
                continue
            vid = data["id"]
            mark = "  [已安装]" if vid in installed else ""
            self.version_combo.setItemText(i, f"{vid}{mark}")

    # ---------- 启动 ----------
    def on_launch(self):
        vinfo = self._get_selected_version()
        if not vinfo:
            self.log("❌ 请先选择一个版本")
            return

        version = vinfo["id"]
        config = {
            "mc_dir": self.mc_dir_input.text().strip(),
            "java": self.java_input.text().strip(),
            "version": version,
            "username": self.username_input.text().strip(),
            "memory": int(self.memory_input.text().strip() or "2048"),
        }
        config["version_dir"] = Path(config["mc_dir"]) / "versions" / version

        if not Path(config["mc_dir"]).exists():
            self.log(f"❌ MC 目录不存在: {config['mc_dir']}")
            return
        json_path = config["version_dir"] / f"{version}.json"
        if not json_path.exists():
            self.log(f"❌ 版本 JSON 不存在: {json_path}")
            return
        if not Path(config["java"]).exists():
            self.log(f"❌ Java 不存在: {config['java']}")
            return

        self.launch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.forge_btn.setEnabled(False)
        self.fabric_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.worker = Worker(config)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self._on_launch_finished)
        threading.Thread(target=self.worker.launch, daemon=True).start()

    def _on_launch_finished(self):
        self.launch_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.forge_btn.setEnabled(True)
        self.fabric_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_stop(self):
        if self.worker:
            self.worker.stop()

    # ---------- 下载原版 ----------
    def on_download(self):
        vinfo = self._get_selected_version()
        if not vinfo:
            self.log("❌ 请先选择一个版本")
            return
        if vinfo.get("_local"):
            self.log("❌ 本地版本（Forge/Fabric）不需要下载原版")
            return
        if "url" not in vinfo:
            self.log("❌ 这个版本没有下载信息")
            return

        version = vinfo["id"]
        mc_dir = self.mc_dir_input.text().strip()

        if not Path(mc_dir).exists():
            self.log(f"❌ MC 目录不存在: {mc_dir}")
            return

        version_dir = Path(mc_dir) / "versions" / version
        if (version_dir / f"{version}.json").exists():
            reply = QMessageBox.question(
                self, "重新下载？",
                f"版本 {version} 已存在。\n要重新下载吗？（会覆盖）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            reply = QMessageBox.question(
                self, "确认下载",
                f"下载版本：{version}\n类型：{vinfo.get('type', 'unknown')}\n"
                f"发布时间：{vinfo.get('releaseTime', '')[:10]}\n\n"
                f"保存到：{mc_dir}\n"
                f"可能几百 MB ~ 几 GB，确定吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.launch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.forge_btn.setEnabled(False)
        self.fabric_btn.setEnabled(False)
        self.log("=" * 60)
        self.log(f"开始下载版本: {version}")

        self.download_worker = DownloadWorker(
            version, mc_dir, vinfo["url"], vinfo.get("sha1")
        )
        self.download_worker.log.connect(self.log)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        threading.Thread(target=self.download_worker.run, daemon=True).start()

    def _on_download_progress(self, done, total, failed):
        self.log(f"    进度: {done}/{total} (失败 {failed})")

    def _on_download_finished(self, success):
        self.launch_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.forge_btn.setEnabled(True)
        self.fabric_btn.setEnabled(True)
        if success:
            self.log("🎉 下载完成！")
            self._refresh_installed_marks()

    # ---------- 安装 Forge ----------
    def on_install_forge(self):
        vinfo = self._get_selected_version()
        if not vinfo:
            self.log("❌ 请先选择一个版本")
            return
        if vinfo.get("_local"):
            self.log("❌ 不能给本地版本（Forge/Fabric）装 Forge")
            self.log("   请先选一个官方原版版本")
            return

        mc_version = vinfo["id"]
        mc_dir = self.mc_dir_input.text().strip()
        java_path = self.java_input.text().strip()

        if not Path(mc_dir).exists():
            self.log(f"❌ MC 目录不存在: {mc_dir}")
            return
        if not Path(java_path).exists():
            self.log(f"❌ Java 不存在: {java_path}")
            return

        version_dir = Path(mc_dir) / "versions" / mc_version
        if not (version_dir / f"{mc_version}.json").exists():
            self.log(f"❌ 原版 {mc_version} 还没下载，请先下载原版")
            return

        self.log(f"正在获取 MC {mc_version} 的 Forge 列表...")
        try:
            downloader = ForgeDownloader(log_callback=self.log)
            forge_list = downloader.get_forge_versions(mc_version)
        except Exception as e:
            import traceback
            self.log(f"❌ 获取 Forge 列表失败: {e}")
            self.log(traceback.format_exc())
            return

        if not forge_list:
            self.log(f"❌ MC {mc_version} 没有可用的 Forge 版本")
            return

        self.log(f"✓ 找到 {len(forge_list)} 个 Forge 版本")

        dlg = ForgeSelectDialog(mc_version, forge_list, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not dlg.selected:
            return

        forge_version = dlg.selected["version"]
        reply = QMessageBox.question(
            self, "确认安装",
            f"即将安装：\n"
            f"MC 版本: {mc_version}\n"
            f"Forge 版本: {forge_version}\n"
            f"Build: {dlg.selected['build']}\n\n"
            f"安装器会自动下载依赖（几百 MB），确定吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.launch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.forge_btn.setEnabled(False)
        self.fabric_btn.setEnabled(False)
        self.log("=" * 60)
        self.log(f"开始安装 Forge {forge_version} for MC {mc_version}")

        self.forge_worker = ForgeInstallWorker(mc_version, forge_version, mc_dir, java_path)
        self.forge_worker.log.connect(self.log)
        self.forge_worker.progress.connect(self._on_forge_progress)
        self.forge_worker.finished.connect(self._on_forge_finished)
        threading.Thread(target=self.forge_worker.run, daemon=True).start()

    def _on_forge_progress(self, done, total):
        if done % (1024 * 1024) < 8192:
            self.log(f"    下载: {done / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB")

    def _on_forge_finished(self, success):
        self.launch_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.forge_btn.setEnabled(True)
        self.fabric_btn.setEnabled(True)
        if success:
            self.log("🎉 Forge 安装完成！刷新列表查看新版本")
            self.load_manifest()

    # ---------- 安装 Fabric ----------
    def on_install_fabric(self):
        vinfo = self._get_selected_version()
        if not vinfo:
            self.log("❌ 请先选择一个版本")
            return
        if vinfo.get("_local"):
            self.log("❌ 不能给本地版本（Forge/Fabric）装 Fabric")
            self.log("   请先选一个官方原版版本")
            return

        mc_version = vinfo["id"]
        mc_dir = self.mc_dir_input.text().strip()

        if not Path(mc_dir).exists():
            self.log(f"❌ MC 目录不存在: {mc_dir}")
            return

        version_dir = Path(mc_dir) / "versions" / mc_version
        if not (version_dir / f"{mc_version}.json").exists():
            self.log(f"❌ 原版 {mc_version} 还没下载，请先下载原版")
            return

        self.log(f"正在获取 MC {mc_version} 的 Fabric 版本...")
        try:
            installer = FabricInstaller(log_callback=self.log)
            loader_list = installer.get_loader_versions(mc_version)
            api_list = installer.get_api_versions(mc_version)
        except Exception as e:
            import traceback
            self.log(f"❌ 获取 Fabric 列表失败: {e}")
            self.log(traceback.format_exc())
            return

        if not loader_list:
            self.log(f"❌ MC {mc_version} 没有可用的 Fabric Loader")
            return

        self.log(f"✓ 找到 {len(loader_list)} 个 loader, {len(api_list)} 个 API")

        dlg = FabricSelectDialog(mc_version, loader_list, api_list, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not dlg.selected:
            return

        loader_version = dlg.selected["loader"]["version"]
        api_info = dlg.selected["api"]
        isolated = dlg.selected["isolated"]

        reply = QMessageBox.question(
            self, "确认安装",
            f"即将安装：\n"
            f"MC 版本: {mc_version}\n"
            f"Fabric Loader: {loader_version}\n"
            f"Fabric API: {api_info['version_number'] if api_info else '不安装'}\n"
            f"版本隔离: {'是' if isolated else '否'}\n\n"
            f"确定吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.launch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.forge_btn.setEnabled(False)
        self.fabric_btn.setEnabled(False)
        self.log("=" * 60)
        self.log(f"开始安装 Fabric {loader_version} for MC {mc_version}")

        self.fabric_worker = FabricInstallWorker(
            mc_version, loader_version, mc_dir, api_info, isolated
        )
        self.fabric_worker.log.connect(self.log)
        self.fabric_worker.progress.connect(self._on_fabric_progress)
        self.fabric_worker.finished.connect(self._on_fabric_finished)
        threading.Thread(target=self.fabric_worker.run, daemon=True).start()

    def _on_fabric_progress(self, done, total, failed):
        self.log(f"    进度: {done}/{total} (失败 {failed})")

    def _on_fabric_finished(self, success):
        self.launch_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.forge_btn.setEnabled(True)
        self.fabric_btn.setEnabled(True)
        if success:
            self.log("🎉 Fabric 安装完成！刷新列表查看新版本")
            if self.fabric_worker:
                fabric_version = f"{self.fabric_worker.mc_version}-Fabric {self.fabric_worker.loader_version}"
                self._remembered_version_id = fabric_version
                self.log(f"    → 刷新后自动选中: {fabric_version}")
            self.load_manifest()
