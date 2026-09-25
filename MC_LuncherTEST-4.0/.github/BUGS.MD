**English** | [中文](./docs/BUGS_CN.md)

# MC_LuncherTEST-3.0 Code Review · Bug List

> This document only **records** issues; no code is modified
> (the only task this round was the modular split).
> Line format: `original:line` = source `MC_LuncherTEST-3.0.py`;
> `new:line` = location after the split.
> All findings come from line-by-line reading + AST comparison. Logic was not
> touched, so **every bug present in the original file survives the split unchanged**.

---

## Summary

| Severity | Count | Description |
| --- | --- | --- |
| 🔴 Critical | 4 | Directly breaks saves/resources or installs; requires manual recovery |
| 🟠 Moderate | 10 | Fails under specific versions / networks / OSes, or fails silently and is hard to debug |
| 🟡 Minor | 9 | UX, maintainability, robustness |

The split itself is a **zero-logic-change**: 41 classes/functions have
byte-identical bodies to the original (see `build_report.txt` / `verify_report.txt`).

---

# 🔴 Critical

## BUG-01 `${game_directory}` points at the version dir, dumping saves / configs / screenshots into `versions/`

- `original:819` · `core/launch.py:233`
- Symptom: `"${game_directory}": str(version_dir)`, where
  `version_dir = mc_dir/versions/<version name>`.
- Consequences:
  - Saves go to `versions/<name>/saves/`; different versions can't see each other's saves.
  - `options.txt`, screenshots, `resourcepacks`, `shaderpacks`, logs all land in the version dir.
  - Launching the same instance from the official launcher / PCL shows **no saves** —
    users think their saves are gone.
  - Version isolation (the Fabric checkbox) is force-enabled unconditionally.
- Fix: use `str(mc_dir)` for `${game_directory}`; add `--gameDir <versions/xxx>`
  only when isolation is requested (this is what PCL's "version isolation" means).

## BUG-02 Fabric version directory name doesn't match ecosystem convention

- `original:545` · `core/fabric.py:74`
- Symptom: `version_id = f"{mc_version}-Fabric {loader_version}"`, then
  `vj["id"] = version_id` is written into the JSON and the file is named
  `f"{version_id}.json"` → lands as `1.20.1-Fabric 0.15.11.json`.
- But the official launcher (and most third-party launchers) use
  `fabric-loader-{loader_version}-{mc_version}`, with `id` equal to the filename.
- Consequences:
  - Opening the same `.minecraft` from the official launcher / PCL shows
    **no such Fabric instance**.
  - If another launcher installs Fabric later, you get two identical version dirs
    and duplicated `libraries` downloads.
- Fix: use `fabric-loader-{loader}-{mc}` (`id` and filename are currently
  self-consistent, so this launcher can start it; the issue is cross-launcher interop).

## BUG-03 `_merge_version` can concatenate parent and child `game` args twice

- `original:717-720` · `core/launch.py:131-134`
- Symptom: only when both parent and child have `arguments` **and** the child
  lacks one of jvm/game does the `parent + child` branch run. If the child JSON
  only defines `arguments.jvm` and the parent has both, then
  `parent_args.get("game") + child_args.get("game", [])` **keeps** the parent's
  `game` args, while a loader's `arguments.game` is normally "inherited then
  replaced" — so `--username`, `--version`, `--gameDir`, `--assetsDir` etc.
  end up duplicated.
- Consequences: usually just duplicate args (last one wins, still runs); in bad
  cases `--uuid` / `--accessToken` / `--assetIndex` take the parent's stale
  values → "auth failed" / "wrong asset index". Some loaders crash outright on
  duplicate `--tweakClass`.
- Fix: follow Minecraft's official rule — same-name args are overridden by the
  child, not appended (PCL's `ArgumentsBuilder` does exactly this).

## BUG-04 Half-installed version dirs are treated as "installed"

- `original:1412-1424, 453-477` · `ui/main_window.py:307-319`, `core/forge.py:59-83`
- Symptom: `install_forge()` runs the installer with `--installClient <mc_dir>`,
  which creates a new dir under `versions/`. If it fails midway (or the user
  force-quits), you're left with a **json but no jar**. Yet
  `_get_installed_versions()` only checks "the dir contains any `*.json`",
  so the half-installed entry is marked "installed".
- Consequences: selecting it and launching gives `ClassNotFoundException` /
  "main class not found", and the launcher log gives no hint that it was never
  fully installed.
- Fix: tighten the check to "`<name>.jar` exists, or its `inheritsFrom` parent
  is complete"; or validate the target version dir after the Forge install.

---

# 🟠 Moderate

## BUG-05 `rules_allow` defaults to False for "rules not matching this platform", skipping cross-platform libs

- `original:84-108` · `core/util.py:24-48`
- Symptom: the function ends with `return False`. When all rules are "allow"
  entries that don't match the current OS, it falls through to `return False`,
  i.e. "not allowed".
- But the official semantics are: a rule that doesn't match is simply inapplicable
  → if no disallow matched, it should be **allowed**.
- Consequences: some libs (those with `rules` listing only `os: {name: linux}`)
  get skipped entirely on Windows → `NoClassDefFoundError` at launch. Vanilla
  1.20.x happens not to hit this today; it's a **latent** issue.
- Fix: change `return False` to `return True`, or explicitly implement
  "no rule matched → allow".
- Note: this is the **most sensitive spot** in a behavior-preserving split;
  run an offline-launch test before changing it.

## BUG-06 `get_natives_key`'s 32/64-bit check treats every non-x86_64 machine as 32-bit

- `original:121` · `core/util.py:61`
- Symptom: `arch = "64" if platform.machine() in ("AMD64","x86_64") else "32"`.
  ARM64 (Windows on ARM / Apple Silicon / ARM64 Raspberry Pi) is classified as
  32-bit, so it looks for a nonexistent classifier like `natives-windows-32`.
- Consequences: on ARM, natives downloads 404, or the wrong-arch dlls are
  extracted → `UnsatisfiedLinkError`.
- Fix: map `platform.machine()` fully (`aarch64`/`arm64` → `arm64`), or read
  `javaVersion` / `os.arch` directly.

## BUG-07 Natives extraction "already done" check only looks for `*.dll`

- `original:373` · `core/download.py:214`
- Symptom: `if any(natives_dir.glob("*.dll")): return`.
- Consequences:
  - On Linux/macOS, `*.dll` is never found, so **extraction reruns before every launch**.
  - On Windows, one stale dll makes it skip, so **newly added natives never get extracted**.
- Fix: use a "marker file + SHA1 list of natives jars" check, or match
  `*.so`/`*.dylib` per platform.

## BUG-08 `download_file`'s SHA1-failure `continue` is ineffective, and 404 only breaks the inner loop

- `original:244-261` · `core/download.py:85-102`
- Case A: on SHA1 mismatch, `tmp.unlink(); continue` — the `continue` goes back
  to the `attempt` loop, so the next try **re-downloads the same URL and
  re-checks**, exhausting the 2 retries and failing without ever trying the
  fallback URL. (Correct behavior: SHA1 failure = that mirror served a dirty
  file; move on to the next URL.)
- Case B: on `requests.HTTPError` with 404, `break` only exits the `attempt`
  loop; if both candidate URLs 404, `last_error` gets overwritten and the log
  doesn't say which source 404'd.
- Consequences: a flaky mirror looks like "download failed but retries are
  pointless", and the error doesn't point at the real cause.
- Fix: on SHA1 mismatch, record `last_error` and move to the next URL; include
  URL and status code in the log.

## BUG-09 `_on_forge_progress`'s print condition repeats / drops lines

- `original:1637-1639` · `ui/main_window.py:522-524`
- Symptom: `if done % (1024*1024) < 8192:` — chunks are 8192 bytes, so `done`
  won't reliably land inside `[0,8192)`. It prints several times in a row or
  skips whole stretches.
- Consequences: log cosmetics only, install is unaffected.
- Fix: print once per 1 MB boundary (remember the previous value).

## BUG-10 Progress/finished signals lack a "current worker" check, enabling re-entry

- `original:895-921, 972-1001` · `core/workers.py:5-131`, `ui/main_window.py`
- Symptom: `progress = pyqtSignal(...)` is emitted from worker threads; Qt's
  cross-thread signals default to queued connections, **so that part is safe**.
  But the `finished` slot calls `self.load_manifest()` (spins up another thread)
  and touches widgets, and `_on_download_finished` doesn't check "am I still
  the same worker?".
- Consequences: re-entry at the moment buttons are disabled, or two installs in
  a row, lets two workers emit `progress` at once — the progress numbers bounce
  back and forth in the log, and `_remembered_version_id` can be overwritten
  by the later one.
- Fix: check `sender()` in `_on_*_finished`, or give the worker a "finished" flag.

## BUG-11 Fabric API version list isn't paginated

- `original:506-533` · `core/fabric.py:35-62`
- Symptom: `GET /project/fabric-api/version?game_versions=[...]&loaders=["fabric"]`
  has no `limit`/`offset`; Modrinth returns at most 100 by default.
- Consequences: for older MC versions with more entries, the newest one may not
  make it into the sorted list — the dropdown is "short a chunk".
- Fix: add a `limit`/`offset` loop, or query `featured` scoped by `game_versions`.

## BUG-12 The assets phase has no failure threshold at all

- `original:342-362` · `core/download.py:180-200`
- Symptom: the libraries phase throws only if >10% fail; the assets phase
  (typically 3000+ files) **never errors no matter how many fail**, it just
  logs one line.
- Consequences: on a bad network, assets go missing en masse; the game then
  reports `Failed to download asset`, while the already-shown "✅ install
  complete" misleads the user.
- Fix: add a threshold for assets too, return a failure list, and write that
  list to a log file.

## BUG-13 Downloads can't be cancelled; `stop` only affects the game process

- `original:670-674` · `core/launch.py:56-60`
- Symptom: `Worker.stop()` only terminates the game process;
  `Downloader.download_batch`'s `ThreadPoolExecutor` has no
  `shutdown(cancel_futures=True)` and no stop flag.
- Consequences: once you hit "download vanilla", you wait it out (possibly GBs);
  closing the window also stutters because threads haven't exited cleanly.
- Fix: give `Downloader` a `threading.Event()` and check it inside the chunk loop.

## BUG-14 No `javaVersion` compatibility check at launch

- `original:774-866` · `core/launch.py:187-279`
- Symptom: `_merge_version` merges `javaVersion` into the result, but
  `_build_command` **never reads** `vj["javaVersion"]`.
- Consequences: launching 1.20.5 (needs 21) on Java 8 gives
  `UnsupportedClassVersionError`; the log just shows a raw Java exception and
  the user doesn't know to switch Java. Also, `DEFAULT_JAVA` is a hardcoded
  absolute path.
- Fix: surface `vj["javaVersion"]["majorVersion"]` as a hint (not necessarily
  as a forced switch).

---

# 🟡 Minor

## BUG-15 No existence check on classpath lib files

- `original:787-803` · `core/launch.py:200-216`
- `_resolve_library_path` returns a path that's **not checked with `exists()`**
  before being put on the classpath (only the client jar is checked).
- Consequences: missing libs surface as a Java-side `NoClassDefFoundError`,
  which is painful to debug.
- Fix: collect missing libs into a list and warn once before launch.

## BUG-16 `${clientid}` / `${auth_xuid}` are replaced with empty strings

- `original:810-831` · `core/launch.py:224-245`
- `"${clientid}": ""`, `"${auth_xuid}": ""`, `"${user_type}": "legacy"`.
- Fine for offline mode, but `--clientId ""` trips argument parsing on some
  loaders.
- Fix: omit the argument entirely when there's no clientId, instead of passing
  an empty string.

## BUG-17 Child process isn't stopped when the window closes

- `original:1155-1313` · `ui/main_window.py:31-189`
- No `closeEvent` override; the game is a `subprocess.Popen` child, so MC can
  keep running after the launcher closes.
- Fix: call `self.worker.stop()` from `closeEvent`.

## BUG-18 Inheritance-chain depth limits are inconsistent (5 vs 10)

- `original:683, 751` · `core/launch.py:90, 156`
- Normal versions won't hit this, but the two limits differ, so the error
  message is inconsistent when it does.

## BUG-19 `libraries` keyed by `name`; missing `name` collapses all entries into one key

- `original:705-708` · `core/launch.py:118-122`
- `libs_by_name[lib.get("name", "")] = lib` — if a lib has no `name`, later
  empty-name entries overwrite earlier ones.

## BUG-20 Bare `except:` swallowing exceptions (3 spots)

- `core/download.py:66` (SHA1 read), `core/launch.py:274`,
  `ui/main_window.py:318` (`_get_installed_versions`)
- Fix: at least use `except Exception:` and log; the bare except in
  `_get_installed_versions` hides real problems (e.g. permission errors) as
  "no installed versions".

## BUG-21 `int(self.memory_input.text())` is unguarded

- `original:1457` · `ui/main_window.py:342`
- Non-numeric input → `ValueError` bubbles up into the Qt event loop; nothing
  is shown in the log area.
- Fix: try/except + a hint.

## BUG-22 No local cache for the version manifest; offline shows nothing, not even local versions

- `original:169-183` · `core/manifest.py`
- Offline, the dropdown just shows "（获取失败）" (fetch failed).
- Fix: cache `version_manifest_v2.json` under `.minecraft/`; on failure fall
  back to the cache + a local version scan.

## BUG-23 `main.py`'s `from core.config import *` is a value copy (split-side note)

- `main.py:41-52` (added during the split for compatibility; not an original bug)
- Semantics reminder: `main.DEFAULT_MEMORY = x` does **not** affect
  `core.config.DEFAULT_MEMORY`. To change constants, edit `core.config` directly.

---

# Appendix: design issues not touched this round, but worth noting later

1. **UI and business logic are mixed in `MainWindow`** (`on_download` /
   `on_install_forge` / `on_install_fabric` each do "validate input + dialog +
   start thread"). For future work, consider splitting into `ui/pages/*` +
   `core/tasks.py` — but **per your request, the main framework was left alone this round**.
2. **The three network classes each hold their own `requests.Session`**, with
   inconsistent mirror strategies: `Downloader` does BMCLAPI substitution,
   `ForgeDownloader` uses BMCLAPI's own URLs, `FabricInstaller` hits
   `meta.fabricmc.net` directly (can be slow in mainland China).
3. **No proxy configuration for any request**, and `timeout=30` is small for
   GB-scale assets.
4. **No logs on disk** — debugging means copy-pasting from the text box.

---

*Method: line-by-line reading of the 1754-line original + AST structure comparison; no logic modified.*
