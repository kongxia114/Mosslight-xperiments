# MC_LuncherTEST-3.0 代码审查 · Bug 清单

> 本文只**记录**问题，不修改任何代码（本次任务只做模块化拆分）。
> 行号格式：`原文件:行号` = 拆分的来源 `MC_LuncherTEST-3.0.py`；`新文件:行号` = 拆分后位置。
> 全部结论来自逐行阅读 + AST 比对，未改动逻辑，因此**原文件里存在的 bug 在拆分后全部原样保留**。

---

## 结论摘要

| 级别 | 数量 | 说明 |
| --- | --- | --- |
| 🔴 严重 | 4 | 会直接导致存档/资源错乱、安装失败、需要手动才能恢复 |
| 🟠 中等 | 10 | 特定版本/网络/系统环境下出错，或静默失败难排查 |
| 🟡 轻微 | 9 | 体验、可维护性、健壮性问题 |

拆分本身**零逻辑改动**：41 个类/函数的正文与原始文件逐行相同（见 `build_report.txt` / `verify_report.txt`）。

---

# 🔴 严重

## BUG-01 `${game_directory}` 指向版本目录，导致存档 / 配置 / 截图全部塞进 versions 里

- `原文件:819` · `core/launch.py:233`
- 现象：`"${game_directory}": str(version_dir)`，而 `version_dir = mc_dir/versions/<版本名>`。
- 后果：
  - 存档写到 `versions/<版本名>/saves/`，不同版本互相看不到存档；
  - `options.txt`、截图、`resourcepacks`、`shaderpacks`、日志都落在版本目录里；
  - 玩家从官方启动器 / PCL 启动同一实例时**看不到自己的存档**，误以为"存档丢了"；
  - 版本隔离（Fabric 那个勾选项）想做的事被无条件强制了。
- 建议：`${game_directory}` 用 `str(mc_dir)`；需要版本隔离时再单独提供
  `--gameDir <versions/xxx>`（PCL 的"版本隔离"就是这个语义）。

## BUG-02 Fabric 安装的版本目录名与生态惯例不一致

- `原文件:545` · `core/fabric.py:74`
- 现象：`version_id = f"{mc_version}-Fabric {loader_version}"`，随后 `vj["id"] = version_id`
  写进 JSON，文件名取 `f"{version_id}.json"` → 实际落盘为 `1.20.1-Fabric 0.15.11.json`。
- 但官方启动器（以及大多数第三方启动器）安装 Fabric 时用的是
  `fabric-loader-{loader_version}-{mc_version}`，JSON 内 `id` 与文件名同值。
- 后果：
  - 用官方启动器 / PCL 打开同一 `.minecraft` 时**看不到这个 Fabric 实例**；
  - 若之后再被别的启动器安装一次，会出现两套一模一样的版本目录，`libraries` 重复下载。
- 建议：改用 `fabric-loader-{loader}-{mc}` 命名（当前 `id` 与文件名是自洽的，
  所以本启动器自己能启动，问题只在"跨启动器互操作"）。

## BUG-03 `_merge_version` 可能返回"父版 game 参数 + 子版 game 参数"双重拼接

- `原文件:717-720` · `core/launch.py:131-134`
- 现象：只有「父子都有 `arguments`」且「子版不同时具备 jvm+game」时，走 `parent + child` 拼接分支。
  如果子版本 JSON 只写了 `arguments.jvm`（没写 `game`），父版又同时有 jvm 和 game，
  那么 `parent_args.get("game") + child_args.get("game", [])` 会把父版的 `game` 参数**保留**，
  而子版本（Forge/Fabric）的 `arguments.game` 通常是"继承后替换"的语义 —— 结果就是
  `--username`、`--version`、`--gameDir`、`--assetsDir` 等被追加两次。
- 后果：轻则命令行重复参数（后者覆盖前者，多数能跑），重则
  `--uuid`/`--accessToken`/`--assetIndex` 取到父版旧值，出现"正版验证失败""资源索引不对"；
  少数加载器对重复 `--tweakClass` 会直接崩。
- 建议：按 Minecraft 官方规则合并 —— 同名参数子版覆盖父版，而不是简单列表相加
  （PCL 的 `ArgumentsBuilder` 就是这么做的）。

## BUG-04 半成品版本目录会被当成"已安装"

- `原文件:1412-1424, 453-477` · `ui/main_window.py:307-319`、`core/forge.py:59-83`
- 现象：`install_forge()` 用 `--installClient <mc_dir>` 运行 installer，installer 会在
  `versions/` 下生成新目录；中途失败（或用户强退）会留下**有 json 没 jar**的半成品。
  而 `_get_installed_versions()` 的判定条件只是「目录里有任意 `*.json`」，于是半成品被标成"已安装"。
- 后果：用户选中半成品条目启动 → `ClassNotFoundException` / `找不到主类`，
  而启动器日志里看不出"这个版本其实没装完"。
- 建议：判定条件收紧为「存在 `<版本名>.jar`，或其 `inheritsFrom` 父版本完整」；
  或在 Forge 安装完成后校验目标版本目录完整性。

---

# 🟠 中等

## BUG-05 `rules_allow` 对"非本平台规则"的默认返回值是 False，会把跨平台库误判为不允许

- `原文件:84-108` · `core/util.py:24-48`
- 现象：函数末尾 `return False`。当 `rules` 里全是"不匹配当前 OS"的 allow 规则时，
  会走到 `return False`，即"不允许"。
- 但官方语义是：规则不匹配 → 该条不适用 → 没有命中任何 disallow 就应当 **允许**。
- 后果：部分库（含 `rules` 但只写了 `os: {name: linux}` 的跨平台包）在 Windows 上被整体跳过 →
  启动时 `NoClassDefFoundError`。目前 1.20.x 原版刚好没踩到，属于**潜在**问题。
- 建议：`return False` 改成 `return True`，或显式实现"未命中任何规则 → 允许"。
- 注意：这是**行为等价拆分**里最敏感的一处，改动前请先跑通离线启动测试。

## BUG-06 `get_natives_key` 的 32/64 位判断把一切非 x86_64 机器当成 32 位

- `原文件:121` · `core/util.py:61`
- 现象：`arch = "64" if platform.machine() in ("AMD64","x86_64") else "32"`。
  ARM64（Windows on ARM / Apple Silicon / 树莓派 ARM64）会被判成 32 位，
  于是去找 `natives-windows-32` 之类不存在的 classifier。
- 后果：ARM 设备上下载 natives 404，或解压到错误架构的 dll → `UnsatisfiedLinkError`。
- 建议：用 `platform.machine()` 全量映射（`aarch64`/`arm64` → `arm64`），
  或直接读 `javaVersion` / `os.arch`。

## BUG-07 natives 解压"已完成"的判定只看 `*.dll`

- `原文件:373` · `core/download.py:214`
- 现象：`if any(natives_dir.glob("*.dll")): return`。
- 后果：
  - Linux/macOS 上永远找不到 `*.dll`，**每次启动前都会重新解压**；
  - Windows 上只要有一个 dll 残留就跳过，**后续新增的 natives 不会被解出来**。
- 建议：用"标记文件 + natives jar 的 SHA1 列表"判断，或按平台匹配 `*.so`/`*.dylib`。

## BUG-08 `download_file` 的 SHA1 校验失败后 `continue` 无效，且 404 只 `break` 内层循环

- `原文件:244-261` · `core/download.py:85-102`
- 现象 A：SHA1 不匹配时 `tmp.unlink(); continue` —— `continue` 走的是 `attempt` 循环，
  下一次尝试会**重新下载同一个 URL 再校验一遍**，2 次用完后直接判失败，
  不会尝试备用 URL（正确做法：SHA1 失败应视为"该镜像源文件脏"，换下一个 URL）。
- 现象 B：`requests.HTTPError` 且 404 时 `break` 只跳出 `attempt` 循环；
  若两个候选 URL 都 404，`last_error` 被覆盖，日志里看不出到底哪个源 404。
- 后果：镜像源抽风时表现为"下载失败但重试无意义"，报错信息也不指向真正原因。
- 建议：SHA1 不匹配 → 记 `last_error` 并进入下一个 URL；日志里带上 URL 与状态码。

## BUG-09 `_on_forge_progress` 的进度打印条件会重复/漏打

- `原文件:1637-1639` · `ui/main_window.py:522-524`
- 现象：`if done % (1024*1024) < 8192:` —— 每次 chunk 是 8192 字节，
  `done` 的增量不保证落在 `[0,8192)` 区间，因此会连续打印多次或整段不打印。
- 后果：只是日志观感问题，不影响安装。
- 建议：改成"每跨过 1MB 整数倍时打印一次"（记录上一次的值）。

## BUG-10 进度/完成信号缺少"当前 worker"校验，可能重入

- `原文件:895-921, 972-1001` · `core/workers.py:5-131`、`ui/main_window.py`
- 现象：`progress = pyqtSignal(...)` 由工作线程 emit，Qt 跨线程信号默认队列连接，**这点是安全的**；
  但 `finished` 槽里会调用 `self.load_manifest()`（又起线程）并操作控件，
  同时 `_on_download_finished` 没有"当前是否仍是同一个 worker"的判断。
- 后果：按钮 disable 的瞬间重入或连续两次安装，会让两个 worker 同时 emit `progress`，
  日志里进度数字来回跳，甚至 `_remembered_version_id` 被后一个覆盖。
- 建议：`_on_*_finished` 里校验 `sender()`，或给 worker 加"已结束"标志。

## BUG-11 Fabric API 版本列表没有分页

- `原文件:506-533` · `core/fabric.py:35-62`
- 现象：`GET /project/fabric-api/version?game_versions=[...]&loaders=["fabric"]` 没有 `limit`/`offset`，
  Modrinth 默认最多返回 100 条。
- 后果：老版本 MC 的 Fabric API 版本多于此，排序后可能拿不到最新那个，
  下拉框里"少了一截"。
- 建议：加 `limit`/`offset` 循环取全，或按 `game_versions` 精确取 `featured`。

## BUG-12 资源文件（assets）阶段完全没有失败阈值

- `原文件:342-362` · `core/download.py:180-200`
- 现象：libraries 阶段失败 >10% 才抛异常；assets 阶段（通常 3000+ 文件）
  **无论失败多少都不报错**，只 log 一行。
- 后果：网络差时资源大面积缺失，进游戏才报 `Failed to download asset`，
  而已弹出的"✅ 安装完成"会误导用户。
- 建议：assets 阶段也设阈值 / 返回失败清单，并把失败清单写进日志文件。

## BUG-13 下载没有取消机制，`stop` 只对游戏进程有效

- `原文件:670-674` · `core/launch.py:56-60`
- 现象：`Worker.stop()` 只 terminate 游戏进程；`Downloader.download_batch` 的
  `ThreadPoolExecutor` 没有 `shutdown(cancel_futures=True)`，也没有停止标志。
- 后果：点了"下载原版"后只能等它跑完（可能几 GB），关窗口也会因为线程没退干净而卡一下。
- 建议：`Downloader` 加 `threading.Event()`，在 chunk 循环里检查。

## BUG-14 启动时完全没有检查 `javaVersion` 是否匹配

- `原文件:774-866` · `core/launch.py:187-279`
- 现象：`_merge_version` 把 `javaVersion` 合并进了结果，但 `_build_command` **从未读取** `vj["javaVersion"]`。
- 后果：用 Java 8 启动 1.20.5（需要 21）会得到 `UnsupportedClassVersionError`，
  日志里只有一串 Java 异常，用户不知道要换 Java。且 `DEFAULT_JAVA` 是写死的绝对路径。
- 建议：把 `vj["javaVersion"]["majorVersion"]` 拿出来做提示（不一定要强制切换）。

---

# 🟡 轻微

## BUG-15 `classpath` 里的库文件不检查是否存在

- `原文件:787-803` · `core/launch.py:200-216`
- `_resolve_library_path` 返回路径后**不检查 `exists()`** 就塞进 classpath（只有 client jar 检查了）。
- 后果：缺库时不报错，直到 Java 侧 `NoClassDefFoundError`，排查困难。
- 建议：缺失库收集成列表，启动前一次性提示。

## BUG-16 `${clientid}` / `${auth_xuid}` 用空串替换

- `原文件:810-831` · `core/launch.py:224-245`
- `"${clientid}": ""`、`"${auth_xuid}": ""`、`"${user_type}": "legacy"`。
- 离线模式够用，但 `--clientId ""` 在某些加载器上会触参数解析错误。
- 建议：无 clientId 时直接不传该参数，而不是传空串。

## BUG-17 窗口关闭时不停止子进程

- `原文件:1155-1313` · `ui/main_window.py:31-189`
- 没有 `closeEvent` 覆写；游戏是 `subprocess.Popen` 子进程，关掉启动器后 MC 可能继续跑。
- 建议：`closeEvent` 里 `self.worker.stop()`。

## BUG-18 继承链深度限制不一致（5 vs 10）

- `原文件:683, 751` · `core/launch.py:90, 156`
- 正常版本不会触发，但两处上限不同，出错时提示会不一致。

## BUG-19 `libraries` 用 `name` 做 key，`name` 缺失时全部塌缩成一个键

- `原文件:705-708` · `core/launch.py:118-122`
- `libs_by_name[lib.get("name", "")] = lib` —— 若某库没有 `name`，会被后来的空 name 覆盖。

## BUG-20 空 `except:` 裸吞异常（3 处）

- `core/download.py:66`（SHA1 读取）、`core/launch.py:274`、
  `ui/main_window.py:318`（`_get_installed_versions`）
- 建议：至少 `except Exception:` 并 log；`_get_installed_versions` 的裸 except 会把
  权限错误等真问题伪装成"没有已安装版本"。

## BUG-21 `int(self.memory_input.text())` 未做保护

- `原文件:1457` · `ui/main_window.py:342`
- 输入非数字 → `ValueError` 直接冒泡到 Qt 事件循环，日志区不会有任何提示。
- 建议：try/except + 提示。

## BUG-22 版本清单没有本地缓存，断网时连本地版本都不显示

- `原文件:169-183` · `core/manifest.py`
- 断网时下拉框只有"（获取失败）"。
- 建议：缓存 `version_manifest_v2.json` 到 `.minecraft/`，失败时回退到缓存 + 扫描本地版本。

## BUG-23 `main.py` 的 `from core.config import *` 是值拷贝（拆分附带说明）

- `main.py:41-52`（拆分时新增的兼容转出，非原代码 bug）
- 语义提醒：`main.DEFAULT_MEMORY = x` **不会**影响 `core.config.DEFAULT_MEMORY`。
  要改常量请直接改 `core.config` 里的。

---

# 附：本次未触碰、但后续值得注意的设计问题

1. **`MainWindow` 里界面与业务混在一个类**（`on_download` / `on_install_forge` /
   `on_install_fabric` 都在做"校验输入 + 弹窗 + 起线程"三件事）。
   继续演进建议拆 `ui/pages/*` + `core/tasks.py`，但**本次按你的要求不动主体框架**。
2. **三个网络类各自持有 `requests.Session`**，镜像策略不统一：
   `Downloader` 做 BMCLAPI 替换，`ForgeDownloader` 走 BMCLAPI 自带地址，
   `FabricInstaller` 直连 `meta.fabricmc.net`（国内可能慢）。
3. **所有网络请求都没有代理配置**，`timeout=30` 对 GB 级资源偏小。
4. **没有日志落盘**，出问题只能靠复制文本框内容。

---

*生成方式：对 1754 行原文件逐行阅读 + AST 结构比对；未修改任何逻辑。*
