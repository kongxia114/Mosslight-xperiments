好，这是对应那版精简中文的**英文版**，语气保持一致——不翻译腔，就是正常英文 README 的写法：

```markdown
# MC_LuncherTEST — Modular Split

> 📁 You're looking at `experiments/MC_LuncherTEST-4.0/`.
> This is v3.0's single-file code split by responsibility. **Same code, different files.**

## What this is

`MC_LuncherTEST-3.0.py` was 1754 lines in one file — changing one thing meant
digging through all of it. So it got split into `core/` + `ui/`, where
**every chunk is a literal line-range slice of the original**. No rewrites,
no renames, no opportunistic cleanup.

The bugs that were there are still there — see `BUGS.md`.

## Folder layout

```
MC_LuncherTEST-4.0/
├─ main.py                      ← entry point: python main.py
├─ README.md                    ← this file
├─ BUGS.md                      ← known issues (23 entries)
├─ STRUCTURE.md                 ← split notes (line-number mapping)
├─ build_report.txt             ← split self-check report
├─ verify_report.txt            ← standalone-run verification report
│
├─ core/                        ← pure logic layer
│   ├─ __init__.py
│   ├─ config.py                ← default config + log noise patterns
│   ├─ util.py                  ← rules_allow / natives / maven helpers
│   ├─ manifest.py              ← version manifest fetcher
│   ├─ download.py              ← vanilla download (mirrors, SHA1, batches, natives)
│   ├─ forge.py                 ← Forge download + install
│   ├─ fabric.py                ← Fabric install (loader + API)
│   ├─ launch.py                ← command building + process + inheritsFrom merge
│   └─ workers.py               ← the three background worker wrappers
│
└─ ui/                          ← UI layer
    ├─ __init__.py
    ├─ main_window.py           ← main window
    └─ dialogs/
        ├─ __init__.py
        ├─ forge_select.py      ← Forge version picker
        └─ fabric_select.py     ← Fabric install dialog
```

> ⚠️ `__pycache__/` is bytecode cache generated at runtime — don't commit it.
> Your root `.gitignore` should have `__pycache__/` and `*.pyc`.

## How to run

```powershell
cd "MC_LuncherTEST-4.0"
python main.py
```

> `main.py` must be run **from inside this folder** (it uses `core.*` / `ui.*`
> absolute imports).

## Where to change what

| Want to change | File |
|---|---|
| Default MC dir / Java path / username / memory | `core/config.py` |
| Log noise filter rules | `core/config.py` → `LOG_NOISE_PATTERNS` |
| Download mirrors, SHA1 check, concurrency | `core/download.py` |
| How the launch command is built | `core/launch.py` → `_build_command` |
| Version inheritance merge rules | `core/launch.py` → `_merge_version` |
| Forge / Fabric install flow | `core/forge.py` / `core/fabric.py` |
| UI widgets, buttons, log box | `ui/main_window.py` |
| Version picker dialogs | `ui/dialogs/` |

## Known issues

See `BUGS.md` — **23 entries** (🔴 4 / 🟠 10 / 🟡 9).
Worth a read before touching the code, especially the 4 marked red.

## Why the code is guaranteed unchanged

- Every class/function is a literal `original[start-1:end]` slice
- Five self-checks all pass: identical AST sequence, complete import bindings,
  no missing symbols, matching signatures, byte-identical bodies

Details in `STRUCTURE.md` and `build_report.txt`.

## Features

What this code actually does is documented in the main README.
**Nothing changed functionally** — this is purely a structural split.
```
