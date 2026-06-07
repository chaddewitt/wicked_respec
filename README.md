# Wicked Respec

A tiny tool for *No Rest For The Wicked* that **resets your attributes to 10** and gives the
spent points back so you can re-allocate them. It makes a verified backup of your save first
and changes nothing else.

## Download
Go to the [latest release](https://github.com/chaddewitt/wicked_respec/releases/latest), open the
**Assets** section, and download:
- **Windows:** `Wicked-Respec-windows-x64.zip`
- **Linux:** `Wicked-Respec-linux-x86_64.tar.gz`

## Install and run
**Windows:** right-click the ZIP, choose **Extract All...**, open the extracted `Wicked Respec`
folder, and double-click **`Wicked Respec.exe`**. If you see a "Windows protected your PC" box,
click **More info** then **Run anyway** (the app isn't code-signed). Keep the folder intact: the
`.exe` needs the `_internal` folder beside it.

**Linux:** extract and run it from a terminal:
```
tar -xzf Wicked-Respec-linux-x86_64.tar.gz
./wicked-respec/wicked-respec
```
Double-clicking in a file manager may not work; if you get a permission error, run
`chmod +x wicked-respec/wicked-respec` first.

## Respec your character
1. **Fully close the game** (quit to desktop). It autosaves every ~20-30 s and will overwrite your edit if it's running.
2. **Start Wicked Respec.** Confirm the **character name** shown at the top is the right one. If your save isn't found, click **Browse...** and pick your `.cerimal` file.
3. **Review the table:** "Now" is your current attributes, "After" is what they become (all 10); it also shows the points refunded.
4. Click **Create backup & Respec** and confirm. A backup is saved next to your save under `_wicked_respec_backups\<timestamp>\`.
5. **Start the game.** If Steam shows a cloud/local sync conflict, choose **Local**, then confirm your attributes are 10 and the points are available to spend. If anything's wrong, copy your backup back.

## What it touches (and what it doesn't)
- It edits **only** the eight attribute values (Health, Stamina, Strength, Dexterity,
  Intelligence, Faith, Focus, Equip Load) back to 10. It writes **no** points pool, gold, XP,
  level, items, or anything else.
- No Rest for the Wicked derives your available attribute points from your level minus what
  you've spent, so lowering the attributes returns the points automatically - the tool can't
  grant power you didn't earn. (This is why there's nothing to "cheat" with.)
- Saves are a checksummed, Zstd-compressed container ("CERIMAL"). The tool decompresses,
  patches only the attribute bytes in place, and re-seals every checksum so the game accepts
  the file.

## Caveats
- **Steam Cloud - choose "Local".** Confirmed working: the edited save loads in-game and the
  respec sticks. But on launch Steam may report a **cloud / local sync conflict** - pick **Local**,
  or Steam will overwrite your edited save with the older cloud copy. (Verified on my own
  character; other accounts/realms may behave differently - keep your backup.)
- **Antivirus:** PyInstaller apps are sometimes flagged as false positives. If you don't trust
  the binary, build it yourself from source (below).
- **Keep the folder together / sharing:** the tool ships as a `Wicked Respec` folder (the `.exe`
  plus an `_internal` folder). Zip and share the whole folder; the `.exe` won't run on its own.
- **Save file size:** the respec'd save is written back uncompressed, so it gets a bit larger
  (e.g. ~11 KB -> ~17 KB). This is expected and the game loads it normally.
- **If it won't start:** a `wicked_respec_error.log` is written next to the `.exe` on a crash -
  check it (or send it over) to see what happened.

## Build from source
```
pip install -r requirements.txt
python -m pytest                      # run the test suite (engine is validated against real saves)
pyinstaller --onedir --windowed --name "Wicked Respec" --add-data "assets/cerimal_zstd.dict;." --paths . src/main.py
```
`--onedir` is used rather than `--onefile`: the single-file build unpacks itself into `%TEMP%`
on every launch, which fails on some machines with a *"could not create a temporary directory"*
error. `--onedir` has no unpack step and is more reliable to share.

**Linux:** the `--add-data` separator is `:` (not `;`). The helper `scripts/build_linux.sh`
does the whole Linux build (system Tk deps, venv, PyInstaller) and produces
`Wicked-Respec-linux-x86_64.tar.gz`. PyInstaller can't cross-compile, so build it on Linux
(a native box, WSL, or CI). Linux users can also just run from source (above) - Tkinter is
cross-platform.
### The Zstd dictionary
`assets/cerimal_zstd.dict` (needed to read saves) is **included in the repo**, so running from
source, building, and the packaged releases all just work - no setup. Safety net: if it's ever
missing, `python -m src.main` and `scripts/fetch_dict.py` re-download it. (The engine/golden tests
still need a real `.cerimal` save dropped in `tests/fixtures/` - those aren't committed.)

## How it's built
A clean-room reimplementation of the CERIMAL/Photon-Quantum save format (read + in-place patch
only), with a small Tkinter GUI. Layered so the format engine (`src/cerimal/`) is isolated and
unit-tested independently of the UI.
