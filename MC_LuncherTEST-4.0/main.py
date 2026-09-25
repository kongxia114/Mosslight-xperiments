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
# 模块：main.py  —— 聚合入口：主窗口 MainWindow + main() + 全量符号转出
# 说明：本文件由 MC_LuncherTEST-3.0.py 机械拆分生成，代码体与原始文件逐行一致。
# ==========================================================

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# 旧版单文件兼容：把拆出去的全部顶层符号重新聚回本模块命名空间
from core.config import *          # noqa: F401,F403
from core.util import *            # noqa: F401,F403
from core.manifest import *        # noqa: F401,F403
from core.download import *        # noqa: F401,F403
from core.forge import *           # noqa: F401,F403
from core.fabric import *          # noqa: F401,F403
from core.launch import *          # noqa: F401,F403
from core.workers import *         # noqa: F401,F403
from ui.dialogs.forge_select import *   # noqa: F401,F403
from ui.dialogs.fabric_select import *  # noqa: F401,F403
from ui.main_window import *       # noqa: F401,F403
from core.config import LOG_NOISE_PATTERNS  # noqa: F401
