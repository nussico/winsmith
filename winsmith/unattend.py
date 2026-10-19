"""autounattend.xml and the patch script that runs during Windows setup."""
import base64
import fnmatch
import re
from xml.sax.saxutils import escape

from .patches import PATCHES, PROTECTED_APPS

SCRIPTS_DIR = r"C:\Windows\Setup\Scripts"
SCRIPT_NAME = "winsmith.ps1"
USER_SCRIPT = "winsmith-user.ps1"
APPS_SCRIPT = "winsmith-apps.ps1"
WIFI_SCRIPT = "winsmith-wifi.ps1"
SECRET_KEYS = ("password", "wifi_password")  # never saved to settings or profiles

# Generic install keys: they only pick the edition, they do not activate.
GENERIC_KEYS = {
    "Home": "YTMG3-N6DKC-DKB77-7M9GH-8HVX7",
    "Pro": "VK7JG-NPHTM-C97JM-9MPGT-3V66T",
    "Education": "YNMGQ-8RYV3-4PGQ3-C8XTP-7CFBY",
    "Enterprise": "XGVPP-NMH47-7TTHJ-W3FW7-8HV2C",
}

DEFAULTS = {
    "unattended": True,  # False = Setup asks everything; only what the patches need is written
    "user": "", "password": "", "admin": True, "computer": "", "skip_oobe": True,
    "language": "en-US", "keyboard": "en-US", "timezone": "W. Europe Standard Time",
    "edition": "",  # "" = ask during setup
    "auto_install": "off",  # off | best_ssd | disk0: install without asking which disk (wipes it)
    "wifi": False, "wifi_ssid": "", "wifi_password": "", "wifi_security": "WPA2", "wifi_hidden": False,
    "apps": [],  # winget package IDs, installed after the first sign-in
}
AUTO_INSTALL = ("off", "best_ssd", "disk0")
AUTO_SCRIPT = "autoinstall.js"

# Disk 0 mode: wipe disk 0, GPT with EFI + MSR + Windows, install there.
_DISK0 = ('<DiskConfiguration><Disk wcm:action="add"><DiskID>0</DiskID><WillWipeDisk>true</WillWipeDisk><CreatePartitions>'
          '<CreatePartition wcm:action="add"><Order>1</Order><Type>EFI</Type><Size>300</Size></CreatePartition>'
          '<CreatePartition wcm:action="add"><Order>2</Order><Type>MSR</Type><Size>16</Size></CreatePartition>'
          '<CreatePartition wcm:action="add"><Order>3</Order><Type>Primary</Type><Extend>true</Extend></CreatePartition>'
          '</CreatePartitions><ModifyPartitions>'
          '<ModifyPartition wcm:action="add"><Order>1</Order><PartitionID>1</PartitionID><Format>FAT32</Format><Label>System</Label></ModifyPartition>'
          '<ModifyPartition wcm:action="add"><Order>2</Order><PartitionID>2</PartitionID></ModifyPartition>'
          '<ModifyPartition wcm:action="add"><Order>3</Order><PartitionID>3</PartitionID><Format>NTFS</Format><Label>Windows</Label><Letter>C</Letter></ModifyPartition>'
          '</ModifyPartitions></Disk></DiskConfiguration>'
          '<ImageInstall><OSImage><InstallTo><DiskID>0</DiskID><PartitionID>3</PartitionID></InstallTo></OSImage></ImageInstall>')

_RESERVED = {"administrator", "guest", "defaultaccount", "wdagutilityaccount", "system", "none", "users", "administrators"}


def account_error(user, computer="", admin=True, skip_oobe=False):
    """Returns a problem with the account settings (Setup fails late on them), or None."""
    n, computer = user.strip(), computer.strip()
    if len(n) > 20:
        return "Username can have at most 20 characters."
    if re.search(r'["/\\\[\]:;|=,+*?<>@%]', n) or n.endswith("."):
        return 'Username cannot contain " / \\ [ ] : ; | = , + * ? < > @ % or end with a dot.'
    if n.lower() in _RESERVED:
        return f"'{n}' is reserved by Windows; pick another username."
    if computer:
        if not re.fullmatch(r"[A-Za-z0-9-]{1,15}", computer) or computer.isdigit():
            return "Computer name: 1 to 15 letters, digits or dashes, not only digits."
        if computer.lower() == n.lower():
            return "Computer name and username must differ."
    if n and not admin and skip_oobe:
        return "With the setup screens skipped this would be the only account, so it must be an administrator."
    return None


APP_ID = re.compile(r"[A-Za-z0-9][\w+-]*(\.[\w+-]+)+")


def app_id_ok(app):
    """A winget package ID like Mozilla.Firefox. Anything else could break out of the script."""
    return isinstance(app, str) and APP_ID.fullmatch(app) is not None


def valid_apps(cfg):
    """The apps to install: valid IDs only, no duplicates, in the order given."""
    seen = []
    for a in {**DEFAULTS, **cfg}["apps"]:
        if app_id_ok(a) and a not in seen:
            seen.append(a)
    return seen


WIFI_SECURITY = {"WPA2": ("WPA2PSK", "WPA2-Personal"), "WPA3": ("WPA3SAE", "WPA3-Personal"), "open": ("open", "Open")}


def wifi_error(ssid, password, security="WPA2"):
    """Returns a problem with the Wi-Fi settings, or None. An empty name means no Wi-Fi."""
    ssid = ssid.strip()
    if not ssid:
        return None
    bad = r"[\x00-\x1f\x7f-\x9f  ]"
    if len(ssid.encode("utf-8")) > 32 or re.search(bad, ssid):
        return "Network name can have at most 32 bytes and no control characters."
    if security not in WIFI_SECURITY:
        return "Choose the Wi-Fi security type."
    if security == "open":
        return None
    hex_key = security == "WPA2" and re.fullmatch(r"[0-9A-Fa-f]{64}", password)  # WPA3 takes no raw key
    if not (8 <= len(password) <= 63 or hex_key) or re.search(bad, password):
        return "Wi-Fi password needs 8 to 63 characters."
    return None


def wifi_on(cfg):
    u = {**DEFAULTS, **cfg}
    return (bool(u["wifi"]) and bool(u["wifi_ssid"].strip()) and u["wifi_security"] in WIFI_SECURITY
            and wifi_error(u["wifi_ssid"], u["wifi_password"], u["wifi_security"]) is None)


def auto_mode(cfg):
    """The automatic-install mode that really applies ("off" unless setup answers are on)."""
    u = {**DEFAULTS, **cfg}
    return u["auto_install"] if u["unattended"] and u["auto_install"] in AUTO_INSTALL else "off"


def auto_install_error(cfg):
    """Best SSD applies the image by name with DISM, so it has to know the edition."""
    u = {**DEFAULTS, **cfg}
    if auto_mode(u) == "best_ssd" and u["edition"] not in GENERIC_KEYS:
        return "Best SSD install needs an edition. Pick one under Edition."
    return None


_LOCALE = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})+")
_KEYBOARD = re.compile(r"[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}")


def region_error(language, keyboard):
    """Returns a problem with the language/keyboard (Setup stops on unknown values), or None."""
    if not _LOCALE.fullmatch(language.strip()):
        return "Windows language must be a locale like en-US or de-DE."
    k = keyboard.strip()
    if not (_LOCALE.fullmatch(k) or _KEYBOARD.fullmatch(k)):
        return "Keyboard must be a locale like de-DE or a layout ID like 0407:00000407."
    return None


def encode_password(pw, suffix="Password"):
    """Unattend 'obfuscation' (base64 of UTF-16LE). Not encryption."""
    return base64.b64encode((pw + suffix).encode("utf-16-le")).decode()


def _comp(name, body):
    return (f'<component name="{name}" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" '
            f'language="neutral" versionScope="nonSxS">{body}</component>')


def _commands(tag, field, cmds):
    items = "".join(f'<{tag} wcm:action="add"><Order>{i}</Order><{field}>{escape(c)}</{field}></{tag}>'
                    for i, c in enumerate(cmds, 1))
    return items


def make_unattend(cfg, patch_ids):
    u = {**DEFAULTS, **cfg}
    wifi = wifi_on(u)  # judged before stripping, exactly as iso.build does
    u = {k: v.strip() if isinstance(v, str) else v for k, v in u.items()}
    on = u["unattended"]
    lang = escape(u["language"])
    intl = (f"<InputLocale>{escape(u['keyboard'])}</InputLocale><SystemLocale>{lang}</SystemLocale>"
            f"<UILanguage>{lang}</UILanguage><UserLocale>{lang}</UserLocale>")

    # windowsPE: Setup checks the PC before anything is installed, so the bypass must happen here.
    pe_cmds = []
    if "hwchecks" in patch_ids:
        for e in PATCHES["hwchecks"]["reg"]:
            key, name, value = e.split("|")
            if key.startswith("SYSTEM\\Setup\\LabConfig"):
                pe_cmds.append(f"reg add HKLM\\{key} /v {name} /t REG_DWORD /d {value} /f")
    pe = ""
    if on:
        key = GENERIC_KEYS.get(u["edition"])
        pe = "<UserData>"
        if key:
            pe += f"<ProductKey><Key>{key}</Key><WillShowUI>OnError</WillShowUI></ProductKey>"
        pe += "<AcceptEula>true</AcceptEula></UserData>"
    mode = auto_mode(u)
    if mode == "disk0":
        pe += _DISK0
    elif mode == "best_ssd":
        # The script picks the disk and installs; if it exits without rebooting, normal Setup continues.
        pe_cmds.append("cmd /c for %d in (C D E F G H I J K L M N O P Q R T U V Y Z) do if exist "
                       f'%d:\\sources\\{AUTO_SCRIPT} cscript //nologo %d:\\sources\\{AUTO_SCRIPT} "Windows 11 {u["edition"]}"')
    if pe_cmds:
        pe += "<RunSynchronous>" + _commands("RunSynchronousCommand", "Path", pe_cmds) + "</RunSynchronous>"

    # specialize: runs as SYSTEM before any user exists, so DEFAULT-profile tweaks reach every user.
    spec = _comp("Microsoft-Windows-Shell-Setup", f"<ComputerName>{escape(u['computer']) or '*'}</ComputerName>") if on else ""
    ps = f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File {SCRIPTS_DIR}"
    spec_cmds = []
    if patch_ids:
        spec_cmds.append(rf"{ps}\{SCRIPT_NAME}")
    if wifi:  # the network is up before the first sign-in, so apps and updates can use it
        spec_cmds.append(rf"{ps}\{WIFI_SCRIPT}")
    if spec_cmds:
        spec += _comp("Microsoft-Windows-Deployment",
                      "<RunSynchronous>" + _commands("RunSynchronousCommand", "Path", spec_cmds) + "</RunSynchronous>")

    # oobeSystem
    shell = ""
    if on and u["skip_oobe"]:
        shell += ("<OOBE><HideEULAPage>true</HideEULAPage><HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>"
                  "<HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>"
                  # Only hide the account screen when we create the user; otherwise nobody gets an account.
                  + ("<HideLocalAccountScreen>true</HideLocalAccountScreen>" if u["user"] else "")
                  + "<ProtectYourPC>3</ProtectYourPC></OOBE>")
    elif "localaccount" in patch_ids:
        # Newer builds ignore BypassNRO; hiding the online screens makes OOBE ask for a local user.
        shell += "<OOBE><HideOnlineAccountScreens>true</HideOnlineAccountScreens></OOBE>"
    if on and u["user"]:
        group = "Administrators" if u["admin"] else "Users"
        pw = (f"<Value>{encode_password(u['password'])}</Value><PlainText>false</PlainText>" if u["password"]
              else "<Value></Value><PlainText>true</PlainText>")
        shell += (f'<UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Name>{escape(u["user"])}</Name>'
                  f"<Group>{group}</Group><Password>{pw}</Password></LocalAccount></LocalAccounts></UserAccounts>")
    if on and u["timezone"]:
        shell += f"<TimeZone>{escape(u['timezone'])}</TimeZone>"
    logon = []
    if wifi:  # again at the first sign-in (the Wi-Fi service may not have been ready earlier); -Final cleans up
        logon.append(rf"{ps}\{WIFI_SCRIPT} -Final")
    if valid_apps(u):
        # Async, so the desktop does not wait for the downloads. Runs once, at the first sign-in.
        logon.append(rf'cmd /c start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File {SCRIPTS_DIR}\{APPS_SCRIPT}')
    if logon:
        shell += "<FirstLogonCommands>" + _commands("SynchronousCommand", "CommandLine", logon) + "</FirstLogonCommands>"

    pe_intl = _comp("Microsoft-Windows-International-Core-WinPE",
                    f"<SetupUILanguage><UILanguage>{lang}</UILanguage></SetupUILanguage>{intl}") if on else ""
    oobe_intl = _comp("Microsoft-Windows-International-Core", intl) if on else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">\n'
            f'<settings pass="windowsPE">{pe_intl}{_comp("Microsoft-Windows-Setup", pe) if pe else ""}</settings>\n'
            f'<settings pass="specialize">{spec}</settings>\n'
            f'<settings pass="oobeSystem">{oobe_intl}{_comp("Microsoft-Windows-Shell-Setup", shell) if shell else ""}</settings>\n'
            "</unattend>\n")


def is_protected(app):
    return any(fnmatch.fnmatch(app.lower(), p.lower()) for p in PROTECTED_APPS)


def ps_quote(s):
    """PowerShell single-quoted string."""
    return "'" + str(s).replace("'", "''") + "'"


def _reg_cmd(entry, user="HKU\\WS_DEFAULT"):
    """One reg.exe call for a catalog entry. DEFAULT goes to `user`: the default profile (loaded at
    HKU\\WS_DEFAULT by the script) or HKCU in the first-logon script."""
    path, name, value = entry.split("|")
    hive, _, rest = path.partition("\\")
    key = (user + "\\" if hive == "DEFAULT" else f"HKLM\\{hive}\\") + rest
    if value == "-":
        return f"Reg delete {ps_quote(key)} /v {ps_quote(name)} /f"
    if name == "@":
        return f"Reg add {ps_quote(key)} /ve /f"
    if value.startswith("sz:"):
        return f"Reg add {ps_quote(key)} /v {ps_quote(name)} /t REG_SZ /d {ps_quote(value[3:])} /f"
    return f"Reg add {ps_quote(key)} /v {ps_quote(name)} /t REG_DWORD /d {hex(int(value))} /f"


def make_patch_script(patch_ids):
    """PowerShell run as SYSTEM in the specialize pass. A failed patch only logs: Setup must never stop."""
    lines = [
        "$ErrorActionPreference = 'Continue'",
        "$ProgressPreference = 'SilentlyContinue'",
        f"$log = '{SCRIPTS_DIR}\\winsmith.log'",
        "function Log($m) { Add-Content $log ('[{0:HH:mm:ss}] {1}' -f (Get-Date), $m) }",
        "function Reg { $o = & reg.exe @args 2>&1; if ($LASTEXITCODE) { Log \"  reg $args failed: $o\" } }",
        "function Run($id, [scriptblock]$b) { Log \"patch $id\"; try { & $b } catch { Log \"  WARN $id failed: $_\" } }",
        "Log 'Winsmith patches started'",
        r"reg.exe load HKU\WS_DEFAULT C:\Users\Default\NTUSER.DAT | Out-Null",
    ]
    apps = [a for i in patch_ids for a in PATCHES[i]["apps"] if not is_protected(a)]
    if apps:
        lines += [
            "Run 'apps' {",
            f"    $remove = @({', '.join(ps_quote(a) for a in apps)})",
            "    Get-AppxProvisionedPackage -Online | Where-Object { $remove -contains $_.DisplayName } | ForEach-Object {",
            "        Log \"  remove $($_.DisplayName)\"; Remove-AppxProvisionedPackage -Online -PackageName $_.PackageName | Out-Null }",
            "}",
        ]
    for i in patch_ids:
        p = PATCHES[i]
        body = [_reg_cmd(e) for e in p["reg"]] + p["script"]
        if body:
            lines.append(f"Run {ps_quote(i)} {{")
            lines += [f"    {b}" for b in body]
            lines.append("}")
    user = [_reg_cmd(e, "HKCU") for i in patch_ids for e in PATCHES[i]["reg"] if e.startswith("DEFAULT\\")]
    if user:
        # Windows resets theme, search box and Spotlight values when it creates the profile, and
        # HKCU\Software\Classes lives in UsrClass.dat, so set them again at each user's first logon.
        lines += [
            "Run 'first logon' {",
            f"    Set-Content -Encoding ASCII -LiteralPath '{SCRIPTS_DIR}\\{USER_SCRIPT}' -Value @'",
            "$log = \"$env:TEMP\\winsmith-user.log\"",
            "function Reg { $o = & reg.exe @args 2>&1; if ($LASTEXITCODE) { Add-Content $log \"reg $args failed: $o\" } }",
            *user,
            "Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue  # restarts by itself with the new settings",
            "'@",
            "    " + _reg_cmd(r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\RunOnce|Winsmith|sz:powershell.exe "
                         rf"-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File {SCRIPTS_DIR}\{USER_SCRIPT}"),
            "}",
        ]
    lines += [
        "[gc]::Collect()",
        r"reg.exe unload HKU\WS_DEFAULT | Out-Null",
        "Log 'done'",
    ]
    return "\r\n".join(lines) + "\r\n"


def make_apps_script(apps):
    """PowerShell run at the first sign-in: waits for winget and the network, then installs each app."""
    lines = [
        "$ProgressPreference = 'SilentlyContinue'",
        rf"$log = '{SCRIPTS_DIR}\winsmith-apps.log'",
        "function Log($m) { Add-Content $log ('[{0:HH:mm:ss}] {1}' -f (Get-Date), $m) }",
        "Log 'Winsmith apps started'",
        "$deadline = (Get-Date).AddMinutes(15)",
        "# App Installer registers winget a little after the first sign-in",
        "$winget = $null",
        "while (-not $winget -and (Get-Date) -lt $deadline) {",
        "    $c = Get-Command winget.exe -ErrorAction SilentlyContinue",
        r'    if ($c) { $winget = $c.Source } elseif (Test-Path "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe") {',
        r'        $winget = "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe" } else { Start-Sleep 10 }',
        "}",
        "if (-not $winget) { Log 'winget not found, giving up'; exit 1 }",
        "while (-not (Test-NetConnection cdn.winget.microsoft.com -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue) -and (Get-Date) -lt $deadline) {",
        "    Log 'waiting for the network'; Start-Sleep 15",
        "}",
        "& $winget source update --disable-interactivity | Out-Null",
        f"foreach ($id in @({', '.join(ps_quote(a) for a in apps)})) {{",
        '    Log "install $id"',
        "    & $winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null",
        '    Log "  exit code $LASTEXITCODE"',
        "}",
        "Log 'done'",
    ]
    return "\r\n".join(lines) + "\r\n"


def make_wifi_script(cfg):
    """PowerShell that adds the Wi-Fi profile for all users. -Final (first sign-in) also deletes the password."""
    u = {**DEFAULTS, **cfg}
    ssid, pw = escape(u["wifi_ssid"].strip()), escape(u["wifi_password"])
    auth = WIFI_SECURITY[u["wifi_security"]][0]
    enc = "none" if auth == "open" else "AES"
    key = "" if auth == "open" else (f"<sharedKey><keyType>passphrase</keyType><protected>false</protected>"
                                     f"<keyMaterial>{pw}</keyMaterial></sharedKey>")
    xml = ('<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
           f"<name>{ssid}</name><SSIDConfig><SSID><name>{ssid}</name></SSID>"
           f"<nonBroadcast>{'true' if u['wifi_hidden'] else 'false'}</nonBroadcast></SSIDConfig>"
           "<connectionType>ESS</connectionType><connectionMode>auto</connectionMode><MSM><security><authEncryption>"
           f"<authentication>{auth}</authentication><encryption>{enc}</encryption><useOneX>false</useOneX>"
           f"</authEncryption>{key}</security></MSM></WLANProfile>")
    b64 = base64.b64encode(xml.encode("utf-8")).decode()  # no quoting problems whatever the name or password holds
    lines = [
        "param([switch]$Final)",
        rf"$log = '{SCRIPTS_DIR}\winsmith.log'",
        "function Log($m) { Add-Content $log ('[{0:HH:mm:ss}] {1}' -f (Get-Date), $m) }",
        "$f = Join-Path $env:TEMP 'winsmith-wifi.xml'",
        "try {",
        "    Start-Service WlanSvc -ErrorAction SilentlyContinue",
        f"    $x = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}'))",
        "    Set-Content -LiteralPath $f -Encoding UTF8 -Value $x",
        "    $o = & netsh.exe wlan add profile filename=$f user=all 2>&1",
        "    Log \"wifi profile: $o\"",
        "} catch { Log \"wifi failed: $_\" }",
        "Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue",
        "if ($Final) {",
        "    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
        "    if (Test-Path -LiteralPath $PSCommandPath) { Log 'could not delete this script; it holds the Wi-Fi password, delete it by hand' }",
        "}",
    ]
    return "\r\n".join(lines) + "\r\n"
