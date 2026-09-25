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
# 模块：core/config.py  —— 默认配置 + 日志噪音过滤表
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

DEFAULT_MC_DIR = r"D:\DHML\.minecraft"
DEFAULT_JAVA = r"C:\Users\yexia\AppData\Roaming\.minecraft\runtime\java-runtime-delta\bin\java.exe"
DEFAULT_USERNAME = "BaBaLe"
DEFAULT_MEMORY = 8192

LOG_NOISE_PATTERNS = (
    "Saving chunks for level",
    "Saving and pausing game",
    "Time elapsed:",
    "Preparing spawn area",
    "Loaded 1271 advancements",
    "Loaded 0 advancements",
    "Loaded 1 advancements",
    "Loaded 2 advancements",
    "Loaded 3 advancements",
    "Loaded 4 advancements",
    "Loaded 5 advancements",
    "Loaded 6 advancements",
    "Loaded 7 advancements",
    "Loaded 8 advancements",
    "Loaded 9 advancements",
    "Loaded 0 recipes",
    "Loaded 1 recipes",
    "Loaded 2 recipes",
    "Loaded 3 recipes",
    "Loaded 4 recipes",
    "Loaded 5 recipes",
    "Loaded 6 recipes",
    "Loaded 7 recipes",
    "Loaded 8 recipes",
    "Loaded 9 recipes",
    "Started serving on",
    "Stopping server",
    "ThreadedAnvilChunkStorage",
)
