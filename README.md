# Winsmith

Build your own Windows 11 ISO on **Windows or Linux**: pick an ISO, tick tweaks, answer setup in advance.

Your ISO's Windows image is not modified. Winsmith adds an `autounattend.xml` and a patch script;
the patches run once while Windows installs (log on the installed PC: `C:\Windows\Setup\Scripts\winsmith.log`).
No admin rights needed, a build takes about a minute.

## Install

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
| Windows | `oscdimg` from the Windows ADK: `winget install Microsoft.WindowsADK` (Deployment Tools) |
| Linux | `7z` (`apt install 7zip`) and `xorriso` (`apt install xorriso`) |

Winsmith shows what is missing on the Build page.

## Run from source

```
pip install -r requirements.txt
python main.py
```

Needs Python 3.9+. The GUI uses Qt (PySide6); on some minimal Linux setups Qt also needs `libxcb-cursor0`.
Settings are kept in `%APPDATA%\Winsmith\config.json` (Linux: `~/.config/Winsmith/config.json`); the password is never saved.

## What it does

- **Patches**: skip TPM/CPU/RAM checks, local account, no BitLocker, remove bloat apps / OneDrive / widgets,
  Copilot and Recall off, less tracking and ads, quiet Edge, taskbar, Explorer, system and gaming tweaks. Presets: Basic (default), Recommended, Everything.
  Store, winget, Calculator, Photos, Xbox login and Game Bar are never removed.
- **Setup**: answers Windows Setup in advance: local user (default `User`) + password, computer name, language,
  keyboard, time zone, edition, skip setup screens.
- **Profiles**: save your patches and Setup answers as a profile, export it as `.json` and import it on another PC.
  The password is never saved.

Not yet: downloading Windows, disk auto-install, winget apps, Wi-Fi.

## Tests

```
python -m unittest
```
