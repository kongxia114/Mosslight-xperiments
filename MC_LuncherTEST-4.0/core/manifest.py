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
# 模块：core/manifest.py  —— 版本清单拉取（ManifestFetcher）
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

import requests
from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)

class ManifestFetcher(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(list)

    def run(self):
        try:
            self.log.emit("正在获取版本清单...")
            url = "https://bmclapi2.bangbang93.com/mc/game/version_manifest_v2.json"
            r = requests.get(url, timeout=30, headers={"User-Agent": "DHML/1.0"})
            r.raise_for_status()
            data = r.json()
            versions = data.get("versions", [])
            self.log.emit(f"✓ 获取到 {len(versions)} 个版本")
            self.finished.emit(versions)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ 获取版本清单失败: {e}")
            self.log.emit(traceback.format_exc())
            self.finished.emit([])
