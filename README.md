# Winsmith

Build your own Windows 11 ISO on **Windows or Linux**: pick an ISO, tick tweaks, answer setup in advance.

Your ISO's Windows image is not modified. Winsmith adds an `autounattend.xml` and a patch script;
the patches run once while Windows installs (log on the installed PC: `C:\Windows\Setup\Scripts\winsmith.log`).
No admin rights needed, a build takes about a minute.

## Download

**Windows**: get `Winsmith.exe` from the [latest release](https://github.com/nussico/winsmith/releases/latest) and run it.
No install, no Python needed.

Winsmith checks GitHub for a newer release once a day. A banner offers **Update**: it downloads the new exe,
replaces the old one and restarts. Python installs only show the update command.

## Install with Python

**Windows** (PowerShell):

```
irm https://raw.githubusercontent.com/nussico/winsmith/main/install.ps1 | iex
```

**Linux**:

```
curl -fsSL https://raw.githubusercontent.com/nussico/winsmith/main/install.sh | sh
```

Then start it with `winsmith`. Run the same command again to update.

Already have [pipx](https://pipx.pypa.io) or [uv](https://docs.astral.sh/uv/)?

```
pipx install https://github.com/nussico/winsmith/archive/refs/heads/main.zip
uv tool install https://github.com/nussico/winsmith/archive/refs/heads/main.zip
```

Writing the ISO also needs:

| OS | Tools |
|---|---|
| Windows | `oscdimg` from the Windows ADK, Deployment Tools feature only: `winget install -e --id Microsoft.WindowsADK --override "/quiet /norestart /features OptionId.DeploymentTools"` |
| Linux | `7z` (`apt install 7zip`) and `xorriso` (`apt install xorriso`) |

Winsmith shows what is missing on the Build page. On Windows, **Install it for me** runs the winget command
with only the Deployment Tools feature (Windows asks for admin rights). The install gives up after 20 minutes
and shows the error if it fails. oscdimg is also found in x86 and ARM64 ADK installs.

## What it does

- **Setup**: answers Windows Setup in advance: local user (default `User`) + password, computer name, language,
  keyboard, time zone, edition, skip setup screens.
- **Automatic install** (optional): installs on the best SSD (skips USB and disks under 64 GB) or on disk 0
  without asking. This **wipes that disk**; the Build page shows which disk it would pick on this PC.
- **Apps**: search winget (or type an ID like `Mozilla.Firefox`) and the apps install after the first sign-in.
  The PC needs internet then; progress is in `C:\Windows\Setup\Scripts\winsmith-apps.log`. Searching needs winget
  on the PC running Winsmith, otherwise type the ID.
- **Wi-Fi**: the PC joins your network on its own (WPA2, WPA3 or open, hidden networks too). Leave the name empty to skip.
- **ISO name**: the file name and the disc label carry the date and Winsmith version, e.g. `Winsmith_Win11_v0.2.5_2026-10-19.iso`.
- **Profiles**: save your patches and Setup answers as a profile, export it as `.json` and import it on another PC.
  Passwords are left out unless you answer Yes when asked.
- **Patches**: 28 tweaks in 8 groups, all checked on a real Windows 11 install. Safe only: nothing turns off
  Defender, the firewall, UAC or Windows Update.

| Group | Patches |
|---|---|
| Install | skip TPM/CPU/RAM checks, local account, skip privacy screens, no automatic BitLocker |
| Apps | remove bloat apps, Xbox app, OneDrive, widgets |
| AI | Copilot, Recall and Click to Do off |
| Privacy | less tracking, no ads/tips, no Bing in search, quiet Edge |
| Taskbar & Start | left taskbar, End task, no search box / task view |
| Explorer | classic right-click menu, file extensions, hidden files, open to This PC |
| System & Updates | dark mode, no fast startup, long paths, no update sharing, no auto-reboot |
| Gaming | no background recording, no mouse acceleration, no sticky keys prompt |

Presets: **Basic** (Install group, default), **Recommended** (Basic + less bloat, tracking, Copilot and ads), **Everything**.
Store, winget, Calculator, Photos, Xbox login and Game Bar are never removed.
Per-user tweaks are applied again at each new user's first logon, because Windows resets some of them.

Not yet: downloading Windows.

## Security notes

- The account password is stored base64-encoded in `autounattend.xml`. That is not encryption.
- The Wi-Fi password is stored in plain text in `winsmith-wifi.ps1` on the ISO. The script deletes itself after the
  first sign-in; if that fails (for example a non-admin first user) it says so in `winsmith.log`.
- Profiles keep passwords only if you say Yes, and then in plain text. Share exported profiles with care.
- Winsmith's own settings (`config.json`) hold only the ISO path and the time of the last update check, never passwords.
- Anyone with the ISO can read these, so keep it private.
- `Winsmith.exe` is not code-signed, so Windows Defender may warn about it (for example `Bearfoos.A!ml`). That is a
  false positive of its heuristics; you can check the file against the release page or run from source instead.

## Check an installed PC

Generate a check script, run it on the installed PC as the user Setup created:

```
python -m winsmith.verify > verify_patches.ps1        # all patches, or list patch ids
powershell -ExecutionPolicy Bypass -File verify_patches.ps1
```

It prints PASS/FAIL per registry value and removed app and saves `verify.txt` to the desktop.

## Run from source

```
pip install -r requirements.txt
python main.py
```

Needs Python 3.9+. The GUI uses Qt (PySide6); on some minimal Linux setups Qt also needs `libxcb-cursor0`.
Winsmith starts clean every time. Only your profiles and the base ISO path are remembered: the ISO path (and the last update check) in
`%APPDATA%\Winsmith\config.json` (Linux: `~/.config/Winsmith/config.json`), profiles in the `profiles` folder next to it.

Build the exe: `python build_exe.py` (Nuitka, writes `dist/Winsmith.exe`). Use Nuitka 4.4 or newer: 4.3 (the latest
on PyPI) builds an exe that crashes on start with Python 3.14 and PySide6, so build in a venv with a 4.4 release candidate.

## Tests

```
python -m unittest
```
