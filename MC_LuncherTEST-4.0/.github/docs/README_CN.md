[English](../README.md) | **中文**

# MC_LuncherTEST 模块化拆分

> 📁 你在看的是 `experiments/MC_LuncherTEST-4.0/`。
> 这里是 v3.0 单文件按职责切开之后的版本，**代码没改，只换了位置**。

## 这是什么

v3.0 的 `MC_LuncherTEST-3.0.py` 有 1754 行，改一处得翻半天。
所以按职责切成 `core/` + `ui/`，**每一段都是原文件的行区间原样切片**，
没有重写、没有改名、没有顺手优化。

原来有的 bug 也原样保留——清单在 `BUGS.md`。

## 文件夹结构

```
MC_LuncherTEST-4.0/
├─ main.py                      ← 入口：python main.py
├─ README.md                    ← 本文件
├─ BUGS.md                      ← 已知问题清单（23 条）
├─ STRUCTURE.md                 ← 拆分说明（行号对照表）
├─ build_report.txt             ← 拆分自检报告
├─ verify_report.txt            ← 独立运行验证报告
│
├─ core/                        ← 纯逻辑层
│   ├─ __init__.py
│   ├─ config.py                ← 默认配置 + 日志噪音表
│   ├─ util.py                  ← rules_allow / natives / maven 工具
│   ├─ manifest.py              ← 版本清单拉取
│   ├─ download.py              ← 原版下载（镜像、SHA1、批量、natives）
│   ├─ forge.py                 ← Forge 下载安装
│   ├─ fabric.py                ← Fabric 安装（loader + API）
│   ├─ launch.py                ← 启动命令拼装 + 进程管理 + inheritsFrom 合并
│   └─ workers.py               ← 三个后台线程封装
│
└─ ui/                          ← 界面层
    ├─ __init__.py
    ├─ main_window.py           ← 主窗口
    └─ dialogs/
        ├─ __init__.py
        ├─ forge_select.py      ← Forge 版本选择弹窗
        └─ fabric_select.py     ← Fabric 安装弹窗
```

> ⚠️ `__pycache__/` 是跑出来的字节码缓存，别提交。
> 根目录 `.gitignore` 里应该有 `__pycache__/` 和 `*.pyc`。

## 怎么跑

```powershell
cd "MC_LuncherTEST-4.0"
python main.py
```

> `main.py` 必须在**本文件夹下**运行（内部用 `core.*` / `ui.*` 绝对导入）。

## 想改哪里改哪里

| 想改什么 | 去哪个文件 |
|---|---|
| 默认 MC 目录 / Java 路径 / 玩家名 / 内存 | `core/config.py` |
| 日志噪音过滤规则 | `core/config.py` 的 `LOG_NOISE_PATTERNS` |
| 下载镜像、SHA1 校验、并发数 | `core/download.py` |
| 启动命令怎么拼 | `core/launch.py` 的 `_build_command` |
| 版本继承合并规则 | `core/launch.py` 的 `_merge_version` |
| Forge / Fabric 安装流程 | `core/forge.py` / `core/fabric.py` |
| 界面控件、按钮、日志框 | `ui/main_window.py` |
| 选择版本弹窗 | `ui/dialogs/` |

## 已知问题

看 `BUGS.md`，共 **23 条**（🔴 4 / 🟠 10 / 🟡 9）。
改代码之前建议先翻一遍，尤其是标红的 4 条。

## 为什么能确定代码没改

- 每个类/函数都是按 `原文件[start-1:end]` 直接切片搬过去的
- 五重自检全部通过：AST 序列一致、import 绑定齐全、符号无缺失、
  参数一致、正文逐行相同

细节看 `STRUCTURE.md` 和 `build_report.txt`。

## 功能说明

这个文件夹里的代码能干什么，看主文件那份 README。
**拆分前后功能完全一样**，这里不重复写。
```

---

这版就只管「**这个文件夹是啥、结构什么样、怎么跑、去哪里改**」，功能、里程碑、为什么有这个仓库这些**都交给主 README**。
