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
# 模块：core/workers.py  —— 后台线程封装（DownloadWorker / ForgeInstallWorker / FabricInstallWorker）
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

from pathlib import Path
from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)
from core.download import Downloader
from core.fabric import FabricInstaller
from core.forge import ForgeDownloader

class DownloadWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int, int, int)

    def __init__(self, version_id, mc_dir, version_json_url, version_json_sha1):
        super().__init__()
        self.version_id = version_id
        self.mc_dir = mc_dir
        self.version_json_url = version_json_url
        self.version_json_sha1 = version_json_sha1

    def run(self):
        try:
            dl = Downloader(log_callback=self.log)
            dl.install_version(
                self.version_id, self.mc_dir,
                self.version_json_url, self.version_json_sha1,
                progress_cb=lambda d, t, f: self.progress.emit(d, t, f),
            )
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"❌ 下载失败: {type(e).__name__}: {e}")
            import traceback
            self.log.emit(traceback.format_exc())
            self.finished.emit(False)


# ============================================================
# Forge 安装线程
# ============================================================
class ForgeInstallWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int, int)

    def __init__(self, mc_version, forge_version, mc_dir, java_path):
        super().__init__()
        self.mc_version = mc_version
        self.forge_version = forge_version
        self.mc_dir = mc_dir
        self.java_path = java_path

    def run(self):
        try:
            dl = ForgeDownloader(log_callback=self.log)
            installer_name = f"forge-{self.mc_version}-{self.forge_version}-installer.jar"
            installer_path = Path(self.mc_dir) / "temp" / installer_name

            self.log.emit(f"[1/2] 下载 Forge installer...")
            dl.download_installer(
                self.mc_version, self.forge_version,
                installer_path,
                progress_cb=lambda d, t: self.progress.emit(d, t),
            )
            self.log.emit(f"    ✓ 下载完成: {installer_name}")

            self.log.emit(f"[2/2] 运行 Forge 安装器（可能几分钟）...")
            dl.install_forge(installer_path, Path(self.mc_dir), self.java_path)

            try:
                installer_path.unlink()
            except:
                pass

            self.log.emit(f"✅ Forge {self.forge_version} for {self.mc_version} 安装完成！")
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"❌ Forge 安装失败: {type(e).__name__}: {e}")
            import traceback
            self.log.emit(traceback.format_exc())
            self.finished.emit(False)


# ============================================================
# Fabric 安装线程
# ============================================================
class FabricInstallWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int, int, int)

    def __init__(self, mc_version, loader_version, mc_dir, api_info, isolated):
        super().__init__()
        self.mc_version = mc_version
        self.loader_version = loader_version
        self.mc_dir = mc_dir
        self.api_info = api_info
        self.isolated = isolated

    def run(self):
        try:
            installer = FabricInstaller(log_callback=self.log)
            installer.install(
                self.mc_version,
                self.loader_version,
                self.mc_dir,
                api_version_info=self.api_info,
                isolated=self.isolated,
                progress_cb=lambda d, t, f: self.progress.emit(d, t, f),
            )
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"❌ Fabric 安装失败: {type(e).__name__}: {e}")
            import traceback
            self.log.emit(traceback.format_exc())
            self.finished.emit(False)
