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
# 模块：core/forge.py  —— Forge 下载与安装（ForgeDownloader）
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

import sys
import subprocess
import requests
from pathlib import Path
from core.util import make_log_fn

class ForgeDownloader:
    BMCLAPI = "https://bmclapi2.bangbang93.com"

    def __init__(self, log_callback=None):
        self.log = make_log_fn(log_callback)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "DHML/1.0"})

    def get_forge_versions(self, mc_version):
        url = f"{self.BMCLAPI}/forge/minecraft/{mc_version}"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        result = []
        for item in data:
            forge_ver = item.get("version", "")
            build = item.get("build", 0)
            modified = item.get("modified", "")
            installer = None
            for f in item.get("files", []):
                if f.get("category") == "installer" and f.get("format") == "jar":
                    installer = f
                    break
            result.append({
                "mcversion": mc_version,
                "version": forge_ver,
                "build": build,
                "modified": modified,
                "installer_hash": installer.get("hash") if installer else None,
            })
        result.sort(key=lambda x: x["build"], reverse=True)
        return result

    def download_installer(self, mc_version, forge_version, save_path, progress_cb=None):
        url = f"{self.BMCLAPI}/forge/download"
        params = {
            "mcversion": mc_version,
            "version": forge_version,
            "category": "installer",
            "format": "jar",
        }
        r = self.session.get(url, params=params, stream=True, timeout=60)
        r.raise_for_status()

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
                done += len(chunk)
                if progress_cb and total:
                    progress_cb(done, total)
        return save_path

    def install_forge(self, installer_jar, mc_dir, java_path):
        cmd = [
            java_path,
            "-jar", str(installer_jar),
            "--installClient", str(mc_dir),
        ]
        self.log(f"运行安装器: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(installer_jar.parent),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for line in process.stdout:
            line = line.rstrip()
            if line:
                self.log(f"[Forge] {line}")
        rc = process.wait()
        if rc != 0:
            raise RuntimeError(f"Forge 安装器返回码: {rc}")
        return rc
