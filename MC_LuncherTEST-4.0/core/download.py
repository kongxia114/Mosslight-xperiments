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
# 模块：core/download.py  —— 下载器（Downloader：镜像替换/SHA1/批量/原版安装/natives 解压）
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

import json
import hashlib
import zipfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from core.util import get_natives_key, make_log_fn, rules_allow

class Downloader:
    def __init__(self, log_callback=None):
        self.log = make_log_fn(log_callback)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "DHML/1.0"})

    @staticmethod
    def replace_mirror(url):
        if not url:
            return url
        return (url
            .replace("piston-data.mojang.com", "bmclapi2.bangbang93.com")
            .replace("piston-meta.mojang.com", "bmclapi2.bangbang93.com")
            .replace("libraries.minecraft.net", "bmclapi2.bangbang93.com/maven")
            .replace("resources.download.minecraft.net", "bmclapi2.bangbang93.com/assets")
            .replace("launcher.mojang.com", "bmclapi2.bangbang93.com")
            .replace("launchermeta.mojang.com", "bmclapi2.bangbang93.com")
            .replace("maven.minecraftforge.net", "bmclapi2.bangbang93.com/maven")
            .replace("maven.neoforged.net", "bmclapi2.bangbang93.com/maven")
        )

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
                    return True
            except:
                pass

        save_path.parent.mkdir(parents=True, exist_ok=True)
        mirror_url = self.replace_mirror(url)
        urls_to_try = [mirror_url]
        if mirror_url != url:
            urls_to_try.append(url)

        last_error = None
        for target_url in urls_to_try:
            for attempt in range(retries):
                try:
                    r = self.session.get(target_url, stream=True, timeout=30)
                    r.raise_for_status()
                    tmp = save_path.with_suffix(save_path.suffix + ".tmp")
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                    if sha1:
                        actual = self.sha1_file(tmp)
                        if actual != sha1:
                            tmp.unlink()
                            self.log(f"❌ SHA1 不匹配: {save_path.name}")
                            continue
                    if save_path.exists():
                        save_path.unlink()
                    tmp.rename(save_path)
                    return True
                except requests.HTTPError as e:
                    last_error = e
                    if e.response.status_code == 404:
                        break
                except Exception as e:
                    last_error = e
                    if attempt == retries - 1:
                        break

        self.log(f"❌ 下载失败 {save_path.name}: {last_error}")
        return False

    def download_batch(self, tasks, max_workers=16, progress_cb=None):
        total = len(tasks)
        done = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.download_file, t["url"], t["path"], t.get("sha1")): t
                for t in tasks
            }
            for future in as_completed(futures):
                ok = future.result()
                done += 1
                if not ok:
                    failed += 1
                if progress_cb and (done % 20 == 0 or done == total):
                    progress_cb(done, total, failed)
        return done, failed

    def install_version(self, version_id, mc_dir, version_json_url, version_json_sha1=None, progress_cb=None):
        mc_dir = Path(mc_dir)

        self.log(f"[1/5] 下载版本 JSON...")
        version_dir = mc_dir / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        json_path = version_dir / f"{version_id}.json"

        if not self.download_file(version_json_url, json_path, version_json_sha1):
            raise RuntimeError("版本 JSON 下载失败")

        with open(json_path, "r", encoding="utf-8") as f:
            vj = json.load(f)

        self.log(f"[2/5] 收集下载任务...")
        tasks = []

        client = vj["downloads"]["client"]
        tasks.append({"url": client["url"], "path": version_dir / f"{version_id}.jar", "sha1": client["sha1"]})

        for lib in vj["libraries"]:
            if not rules_allow(lib.get("rules", [])):
                continue
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact:
                tasks.append({
                    "url": artifact["url"],
                    "path": mc_dir / "libraries" / artifact["path"],
                    "sha1": artifact["sha1"],
                })
            classifiers = downloads.get("classifiers", {})
            nk = get_natives_key(lib)
            if nk and nk in classifiers:
                nat = classifiers[nk]
                tasks.append({
                    "url": nat["url"],
                    "path": mc_dir / "libraries" / nat["path"],
                    "sha1": nat["sha1"],
                })

        ai = vj["assetIndex"]
        asset_index_path = mc_dir / "assets" / "indexes" / f"{ai['id']}.json"
        tasks.append({"url": ai["url"], "path": asset_index_path, "sha1": ai["sha1"]})

        if "logging" in vj:
            lf = vj["logging"]["client"]["file"]
            tasks.append({
                "url": lf["url"],
                "path": mc_dir / "assets" / "log_configs" / lf["id"],
                "sha1": lf["sha1"],
            })

        self.log(f"    共 {len(tasks)} 个文件")

        self.log(f"[3/5] 下载 libraries + client...")
        done, failed = self.download_batch(tasks, max_workers=16, progress_cb=progress_cb)
        self.log(f"    完成 {done}/{len(tasks)}, 失败 {failed}")
        if failed > len(tasks) * 0.1:
            raise RuntimeError(f"{failed}/{len(tasks)} 个文件失败，超过 10% 阈值")
        elif failed > 0:
            self.log(f"⚠ 有 {failed} 个文件失败，继续安装")

        self.log(f"[4/5] 下载资源文件（最慢）...")
        if asset_index_path.exists():
            with open(asset_index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
            asset_tasks = []
            for name, obj in index_data["objects"].items():
                h = obj["hash"]
                sub = h[:2]
                asset_tasks.append({
                    "url": f"https://resources.download.minecraft.net/{sub}/{h}",
                    "path": mc_dir / "assets" / "objects" / sub / h,
                    "sha1": h,
                })
            self.log(f"    共 {len(asset_tasks)} 个资源文件")
            done, failed = self.download_batch(asset_tasks, max_workers=32, progress_cb=progress_cb)
            self.log(f"    完成 {done}/{len(asset_tasks)}, 失败 {failed}")

        self.log(f"[5/5] 解压 natives...")
        self._extract_natives(vj, mc_dir, version_dir)

        self.log(f"✅ {version_id} 安装完成！")
        return version_dir

    def _extract_natives(self, vj, mc_dir, version_dir):
        natives_dir = version_dir / f"{version_dir.name}-natives"
        natives_dir.mkdir(parents=True, exist_ok=True)
        if any(natives_dir.glob("*.dll")):
            return
        for lib in vj["libraries"]:
            downloads = lib.get("downloads", {})
            classifiers = downloads.get("classifiers", {})
            nk = get_natives_key(lib)
            if nk and nk in classifiers:
                jar_path = mc_dir / "libraries" / classifiers[nk]["path"]
                if jar_path.exists():
                    try:
                        with zipfile.ZipFile(jar_path, "r") as z:
                            for name in z.namelist():
                                if name.startswith("META-INF/"):
                                    continue
                                z.extract(name, natives_dir)
                    except Exception as e:
                        self.log(f"⚠ 解压 {jar_path.name} 失败: {e}")
