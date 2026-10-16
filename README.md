# Winsmith

Build your own Windows 11 ISO on **Windows or Linux**: pick an ISO, tick tweaks, answer setup in advance.

Your ISO's Windows image is not modified. Winsmith adds an `autounattend.xml` and a patch script;
the patches run once while Windows installs (log on the installed PC: `C:\Windows\Setup\Scripts\winsmith.log`).
No admin rights needed, a build takes about a minute.

## Download

**Windows**: get `Winsmith.exe` from the [latest release](https://github.com/nussico/winsmith/releases/latest) and run it.
No install, no Python needed.

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
- **Profiles**: save your patches and Setup answers as a profile, export it as `.json` and import it on another PC.
  The password is never saved.
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

Not yet: downloading Windows, winget apps, Wi-Fi.

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
Settings are kept in `%APPDATA%\Winsmith\config.json` (Linux: `~/.config/Winsmith/config.json`); the password is never saved.

Build the exe: `python build_exe.py` (Nuitka, writes `dist/Winsmith.exe`). Use Nuitka 4.4 or newer: 4.3 (the latest
on PyPI) builds an exe that crashes on start with Python 3.14 and PySide6, so build in a venv with a 4.4 release candidate.

## Tests

```
python -m unittest
```
