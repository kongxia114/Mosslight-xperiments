# MC_LuncherTEST-3.0 模块化拆分说明

## 一句话

把 1754 行的单文件 `MC_LuncherTEST-3.0.py` **按职责切开**，原文件一行不改；
拆分后的每一段代码都是**按原文件行号区间原样切片**搬过去的，没有任何重写、改名或"顺手优化"。

---

## 目录结构

```
D:\DHML-src\experiments\MC_LuncherTEST-3.0\
├─ main.py                      ← 入口：python main.py 启动（原文件 1745-1754 行）
├─ MC_LuncherTEST-3.0.py        ← 兼容外壳：旧单文件的全部符号仍可从这里导入
├─ BUGS.md                      ← 代码审查 / bug 清单（23 条）
├─ STRUCTURE.md                 ← 本文件
├─ build_report.txt             ← 拆分自检报告（逐行等价校验结果）
├─ verify_report.txt            ← 独立运行时验证报告
│
├─ core/                        ← 纯逻辑层（除 workers/manifest 需要 pyqtSignal 外基本与界面无关）
│   ├─ __init__.py
│   ├─ config.py                ← 默认配置 + 日志噪音表            （原 41-78）
│   ├─ util.py                  ← rules_allow / natives / maven 工具（原 84-159）
│   ├─ manifest.py              ← ManifestFetcher 版本清单拉取      （原 165-183）
│   ├─ download.py              ← Downloader：镜像、SHA1、批量下载、natives（原 189-389）
│   ├─ forge.py                 ← ForgeDownloader                   （原 395-477）
│   ├─ fabric.py                ← FabricInstaller                   （原 483-614）
│   ├─ launch.py                ← Worker：继承合并 + 命令行拼装 + 进程（原 620-889）
│   └─ workers.py               ← 三个后台线程封装                   （原 895-1001）
│
└─ ui/                          ← 界面层
    ├─ __init__.py
    ├─ main_window.py           ← MainWindow 主窗口                 （原 1155-1742）
    └─ dialogs/
        ├─ __init__.py
        ├─ forge_select.py      ← ForgeSelectDialog                （原 1007-1051）
        └─ fabric_select.py     ← FabricSelectDialog               （原 1057-1149）
```

### 原文件行号 → 新文件对照

| 原文件行号 | 内容 | 新位置 |
| --- | --- | --- |
| 1–14 | 模块 docstring | 每个模块都保留一份（原文照搬） |
| 16–35 | 全部 import | 按需分发到各模块 |
| 41–44 | 默认配置 | `core/config.py` |
| 49–78 | 日志噪音表 | `core/config.py` |
| 84–108 | `rules_allow` | `core/util.py` |
| 111–123 | `get_natives_key` | `core/util.py` |
| 126–146 | `maven_to_path` | `core/util.py` |
| 149–154 | `make_log_fn` | `core/util.py` |
| 157–159 | `is_noise` | `core/util.py` |
| 165–183 | `ManifestFetcher` | `core/manifest.py` |
| 189–389 | `Downloader` | `core/download.py` |
| 395–477 | `ForgeDownloader` | `core/forge.py` |
| 483–614 | `FabricInstaller` | `core/fabric.py` |
| 620–889 | `Worker` | `core/launch.py` |
| 895–1001 | `DownloadWorker` / `ForgeInstallWorker` / `FabricInstallWorker` | `core/workers.py` |
| 1007–1051 | `ForgeSelectDialog` | `ui/dialogs/forge_select.py` |
| 1057–1149 | `FabricSelectDialog` | `ui/dialogs/fabric_select.py` |
| 1155–1742 | `MainWindow` | `ui/main_window.py` |
| 1745–1754 | `main()` + `__main__` | `main.py` |

---

## 怎么跑

```powershell
cd D:\DHML-src\experiments\MC_LuncherTEST-3.0
python main.py
```

- 依赖仍是 `PyQt6` + `requests`（没有新增任何第三方库）。
- `main.py` 必须在**本目录下**运行（内部用 `core.*` / `ui.*` 绝对导入）；
  跨目录运行时请先 `sys.path.insert(0, r"D:\DHML-src\experiments\MC_LuncherTEST-3.0")`。
- 旧用法 `python MC_LuncherTEST-3.0.py` 依然可用（它就是 `from main import *`）。

### 想改某个功能时改哪里

| 想改的东西 | 文件 |
| --- | --- |
| 默认 MC 目录 / Java 路径 / 玩家名 / 内存 | `core/config.py` |
| 日志噪音过滤规则 | `core/config.py` 的 `LOG_NOISE_PATTERNS` |
| 下载镜像、SHA1 校验、并发数 | `core/download.py` |
| 启动命令行怎么拼（JVM/游戏参数） | `core/launch.py` 的 `_build_command` |
| 版本继承合并规则 | `core/launch.py` 的 `_merge_version` |
| Forge / Fabric 安装流程 | `core/forge.py` / `core/fabric.py` |
| 界面控件、按钮、日志框 | `ui/main_window.py` |
| 选择版本弹窗 | `ui/dialogs/` |

---

## 拆分原则（为什么可以确信"核心代码没动"）

1. **机械切片**：每个类/函数体都是按 `原文件[start-1:end]` 直接切片写出的，
   生成脚本没有做任何字符串改写（`mod_build.py` 的思路就是"只搬运 + 只加 import"）。
2. **五重自检**（结果见 `build_report.txt`，全部 PASS）：
   - 校验 1：拆分后所有顶层节点（常量/类/函数/`if __name__`）的 AST 序列
     与原始文件**完全一致**（顺序、内容、数量）；
   - 校验 2：原始 **33 条 import 绑定**全部出现在新代码中，一条不少；
   - 校验 3：用 `symtable` 检查每个模块引用的全局名是否都有来源（防漏搬 import 造成 `NameError`）；
   - 校验 4：17 个类/函数的参数与基类**完全一致**；
   - 校验 5：17 个类/函数的正文与原始文件**逐行文本相同**（含缩进与注释）。
3. **独立运行时验证**（见 `verify_report.txt`，全部通过）：
   - 12 个模块全部可单独 import，无循环导入；
   - `main.py` 相对原文件**缺失符号 0 个**；
   - 41 个类/函数的 `inspect.getsource()` 文本与原文件逐字相同；
   - 常量值一致（含 28 条 `LOG_NOISE_PATTERNS`）；
   - 兼容外壳 `MC_LuncherTEST-3.0.py` 加载正常、符号齐全。

> 唯一"新增"的代码是各模块头部的 import 语句，以及 `main.py` 末尾的
> `from core.* import *` 兼容转出（那段不在任何函数/类的正文里，也不影响启动路径）。

---

## 本次**没有**做的事（按你的要求）

- ❌ 没有修任何 bug —— 23 条问题全部记在 `BUGS.md`，等你确认后再改。
- ❌ 没有动主体框架 —— `MainWindow` 依然是原来的一个类、原来的方法名、
  原来的信号连接方式、原来的启动流程。
- ❌ 没有重命名任何函数/类/变量，没有改任何默认值，没有加日志、没有加类型注解。
- ❌ 没有改原目录下的 `D:\DHML-src\experiments\MC_LuncherTEST-3.0.py`（原始单文件保持原样）。

---

## 之后建议的推进顺序

1. 先跑一次 `python main.py`，确认「启动 / 下载原版 / 装 Forge / 装 Fabric」四条链路都还正常
   （如果原版能跑，就一直能跑，因为代码文本一模一样）。
2. 按 `BUGS.md` 的 🔴 严重 4 条依次修（建议先修 BUG-01 存档目录，用户感知最强）。
3. 每修一条，在 `BUGS.md` 对应条目上打勾并注明修改文件与日期。
