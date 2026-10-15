"""Patch catalog and presets.

Reg entries: 'HIVE\\Key|Name|Value'
  HIVE = SYSTEM, SOFTWARE or DEFAULT (the default user profile, i.e. every new user)
  Value: DWORD number, 'sz:text' for a string, '-' deletes the value.
  Name '@' with no value = empty default value.
Patches with 'script' run extra PowerShell lines during Windows setup.
"""

REMOVE_APPS = [
    "Clipchamp.Clipchamp", "Microsoft.BingNews", "Microsoft.BingSearch", "Microsoft.BingWeather",
    "Microsoft.Getstarted", "Microsoft.MicrosoftOfficeHub", "Microsoft.MicrosoftSolitaireCollection",
    "Microsoft.People", "Microsoft.PowerAutomateDesktop", "Microsoft.Todos", "Microsoft.WindowsFeedbackHub",
    "Microsoft.WindowsMaps", "MSTeams", "Microsoft.OutlookForWindows",
    "Microsoft.Windows.DevHome", "MicrosoftCorporationII.MicrosoftFamily",
]

# Never removed, even if a removal list names them. Wildcards allowed.
PROTECTED_APPS = [
    "Microsoft.WindowsStore", "Microsoft.DesktopAppInstaller", "Microsoft.VCLibs.*", "Microsoft.UI.Xaml.*",
    "Microsoft.NET.Native.*", "Microsoft.WebView2*", "Microsoft.EdgeWebView*", "Microsoft.SecHealthUI",
    "Microsoft.StorePurchaseApp", "Microsoft.HEIFImageExtension", "Microsoft.VP9VideoExtensions",
    "Microsoft.WebpImageExtension", "Microsoft.AV1VideoExtension", "Microsoft.LanguageExperiencePack*",
    "Microsoft.WindowsCalculator", "Microsoft.Windows.Photos", "Microsoft.WindowsNotepad",
    "Microsoft.WindowsTerminal", "Microsoft.Paint", "Microsoft.ScreenSketch", "Microsoft.WindowsCamera",
    "Microsoft.WindowsSoundRecorder", "Microsoft.XboxIdentityProvider", "Microsoft.Xbox.TCUI",
    "Microsoft.XboxGamingOverlay", "Microsoft.GetHelp",
]

_ADV = r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_CDM = r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
_CDM_OFF = [f"{_CDM}|{n}|0" for n in (
    "ContentDeliveryAllowed", "SilentInstalledAppsEnabled", "SystemPaneSuggestionsEnabled", "SoftLandingEnabled",
    "PreInstalledAppsEnabled", "OemPreInstalledAppsEnabled", "RotatingLockScreenOverlayEnabled",
    "SubscribedContent-338387Enabled", "SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled",
    "SubscribedContent-338393Enabled", "SubscribedContent-353694Enabled", "SubscribedContent-353696Enabled")]
_AI = r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
_EDGE = r"SOFTWARE\Policies\Microsoft\Edge"


def _p(group, label, desc, reg=(), apps=(), script=()):
    return {"group": group, "label": label, "desc": desc, "reg": list(reg), "apps": list(apps), "script": list(script)}


PATCHES = {
    # 'hwchecks' is special: it also goes into the windowsPE pass (see unattend.py).
    "hwchecks": _p("Install", "Skip TPM/CPU/RAM checks",
        "Installs on PCs without TPM 2.0, Secure Boot, 4 GB RAM or a supported CPU.",
        [r"SYSTEM\Setup\LabConfig|BypassTPMCheck|1", r"SYSTEM\Setup\LabConfig|BypassSecureBootCheck|1",
         r"SYSTEM\Setup\LabConfig|BypassRAMCheck|1", r"SYSTEM\Setup\LabConfig|BypassCPUCheck|1",
         r"SYSTEM\Setup\LabConfig|BypassStorageCheck|1", r"SYSTEM\Setup\MoSetup|AllowUpgradesWithUnsupportedTPMOrCPU|1"]),
    # Newer builds ignore BypassNRO; unattend.py also hides the online account screens, which still works.
    "localaccount": _p("Install", "Local account",
        "Setup lets you create a local account, without a Microsoft account and without internet.",
        [r"SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE|BypassNRO|1"]),
    "skipprivacy": _p("Install", "Skip privacy screens",
        "Skips the privacy settings questions (location, ads ID, diagnostics) during setup.",
        [r"SOFTWARE\Policies\Microsoft\Windows\OOBE|DisablePrivacyExperience|1"]),
    "nobitlocker": _p("Install", "No automatic BitLocker",
        "Windows does not encrypt the drive on its own. You can still turn BitLocker on later.",
        [r"SYSTEM\ControlSet001\Control\BitLocker|PreventDeviceEncryption|1"]),

    "bloatapps": _p("Apps", "Remove bloat apps",
        "Removes: " + ", ".join(a.split(".")[-1] for a in REMOVE_APPS) +
        ". Store, Calculator, Photos, Xbox login and Game Bar are always kept.", apps=REMOVE_APPS),
    "xboxapp": _p("Apps", "Remove Xbox app",
        "Removes only the Xbox app. Xbox login and Game Bar stay, so games keep working.", apps=["Microsoft.GamingApp"]),
    "onedrive": _p("Apps", "Remove OneDrive",
        "OneDrive is not installed for new users. You can still get it from the Store later.",
        [r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\Run|OneDriveSetup|-"],
        script=[r"Remove-Item -Force -ErrorAction SilentlyContinue C:\Windows\System32\OneDriveSetup.exe"]),
    "nowidgets": _p("Apps", "Remove widgets",
        "Removes the news and weather widgets board. The Store can bring it back.",
        apps=["MicrosoftWindows.Client.WebExperience"]),

    "ai": _p("AI", "Turn off Copilot and Recall",
        "Removes the Copilot app and turns off Recall snapshots and Click to Do.",
        [r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot|TurnOffWindowsCopilot|1",
         r"DEFAULT\Software\Policies\Microsoft\Windows\WindowsCopilot|TurnOffWindowsCopilot|1",
         r"DEFAULT\Software\Policies\Microsoft\Windows\WindowsAI|RemoveMicrosoftCopilotApp|1",
         _AI + "|DisableAIDataAnalysis|1", _AI + "|AllowRecallEnablement|0", _AI + "|DisableClickToDo|1"],
        apps=["Microsoft.Copilot"]),

    "tracking": _p("Privacy", "Less tracking",
        "Turns off diagnostic data, activity history and the advertising ID.",
        [r"SOFTWARE\Policies\Microsoft\Windows\DataCollection|AllowTelemetry|0",
         r"SYSTEM\ControlSet001\Services\DiagTrack|Start|4", r"SYSTEM\ControlSet001\Services\dmwappushservice|Start|4",
         r"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo|DisabledByGroupPolicy|1"] +
        [rf"SOFTWARE\Policies\Microsoft\Windows\System|{n}|0"
         for n in ("EnableActivityFeed", "PublishUserActivities", "UploadUserActivities")]),
    "ads": _p("Privacy", "No ads, tips and suggestions",
        "Turns off Start menu recommendations, suggested apps, lock screen ads and tips in Settings.",
        [r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement|ScoobeSystemSettingEnabled|0",
         r"SOFTWARE\Policies\Microsoft\Windows\CloudContent|DisableWindowsConsumerFeatures|1",
         _ADV + "|Start_IrisRecommendations|0", _ADV + "|Start_AccountNotifications|0"] + _CDM_OFF),
    "nobing": _p("Privacy", "No Bing in Start search",
        "Start menu search only finds things on your PC: no web results, no search highlights.",
        [r"DEFAULT\Software\Policies\Microsoft\Windows\Explorer|DisableSearchBoxSuggestions|1",
         r"SOFTWARE\Policies\Microsoft\Windows\Windows Search|EnableDynamicContentInWSB|0"]),
    "edge": _p("Privacy", "Quiet Edge",
        "Edge skips its first-run setup, imports nothing and stops asking to be the default browser. "
        'Edge then shows "managed by your organization".',
        [_EDGE + "|HideFirstRunExperience|1", _EDGE + "|AutoImportAtFirstRun|4",
         _EDGE + "|DefaultBrowserSettingEnabled|0", _EDGE + "|ShowRecommendationsEnabled|0"]),

    "taskbarleft": _p("Taskbar & Start", "Taskbar icons on the left",
        "Start button and taskbar icons on the left like Windows 10.", [_ADV + "|TaskbarAl|0"]),
    "endtask": _p("Taskbar & Start", '"End task" in taskbar menu',
        "Right-click a frozen app on the taskbar and choose End task.",
        [_ADV + r"\TaskbarDeveloperSettings|TaskbarEndTask|1"]),
    "tidytaskbar": _p("Taskbar & Start", "Tidy taskbar",
        "Hides the search box and the Task View button. Press Start and type to search; Win+Tab still works.",
        [r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\Search|SearchboxTaskbarMode|0",
         _ADV + "|ShowTaskViewButton|0"]),

    "classicmenu": _p("Explorer", "Classic right-click menu",
        'The full Windows 10 style context menu, without "Show more options".',
        [r"DEFAULT\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32|@|"]),
    "fileext": _p("Explorer", "Show file extensions",
        'Shows .exe, .pdf, .jpg in Explorer. Makes fake files like "photo.jpg.exe" easy to spot.',
        [_ADV + "|HideFileExt|0"]),
    "hiddenfiles": _p("Explorer", "Show hidden files", "Explorer shows hidden files and folders like AppData.",
        [_ADV + "|Hidden|1"]),
    "thispc": _p("Explorer", 'Explorer opens "This PC"', "Explorer starts on your drives instead of Home.",
        [_ADV + "|LaunchTo|1"]),

    "darkmode": _p("System & Updates", "Dark mode", "Windows and apps use the dark theme from the first login.",
        [r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize|AppsUseLightTheme|0",
         r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize|SystemUsesLightTheme|0"]),
    "nofaststart": _p("System & Updates", "Disable Fast Startup",
        "Shut down really shuts down. Fixes driver glitches and dual-boot problems.",
        [r"SYSTEM\ControlSet001\Control\Session Manager\Power|HiberbootEnabled|0"]),
    "longpaths": _p("System & Updates", "Allow long file paths", "Removes the old 260 character limit for file paths.",
        [r"SYSTEM\ControlSet001\Control\FileSystem|LongPathsEnabled|1"]),
    "nop2p": _p("System & Updates", "No update sharing (P2P)",
        "Windows Update downloads only from Microsoft and does not upload to other PCs.",
        [r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization|DODownloadMode|0"]),
    "noautoreboot": _p("System & Updates", "No automatic restart",
        "Windows does not restart by itself for updates while you are logged in.",
        [r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU|NoAutoRebootWithLoggedOnUsers|1"]),

    "gamedvr": _p("Gaming", "Disable background recording",
        "Stops Game DVR from recording gameplay in the background. Game Bar itself stays.",
        [r"DEFAULT\System\GameConfigStore|GameDVR_Enabled|0",
         r"DEFAULT\Software\Microsoft\Windows\CurrentVersion\GameDVR|AppCaptureEnabled|0"]),
    "mouseaccel": _p("Gaming", "Disable mouse acceleration",
        'Turns off "Enhance pointer precision".',
        [rf"DEFAULT\Control Panel\Mouse|{n}|sz:0" for n in ("MouseSpeed", "MouseThreshold1", "MouseThreshold2")]),
    "stickykeys": _p("Gaming", "No Sticky Keys popup",
        "Pressing Shift five times no longer opens the Sticky Keys question.",
        [r"DEFAULT\Control Panel\Accessibility\StickyKeys|Flags|sz:506"]),
}

# Old patch IDs (merged or renamed) -> new ones, so saved configs and profiles keep their meaning.
ALIASES = {"telemetry": ["tracking"], "activity": ["tracking"], "adid": ["tracking"],
           "adscopilot": ["ads", "ai"], "nosearchbox": ["tidytaskbar"], "notaskview": ["tidytaskbar"]}


def resolve(ids):
    """Known patch IDs, old ones mapped to the new ones; unknown dropped, order kept, no duplicates."""
    out = []
    for i in ids:
        for n in ALIASES.get(i, [i]) if isinstance(i, str) else []:
            if n in PATCHES and n not in out:
                out.append(n)
    return out


_BASIC = ["hwchecks", "localaccount", "skipprivacy", "nobitlocker"]
PRESETS = {
    "Basic": _BASIC,
    "Recommended": _BASIC + ["bloatapps", "onedrive", "ai", "tracking", "ads", "nobing", "edge",
                             "fileext", "endtask", "nop2p", "noautoreboot", "gamedvr"],
    "Everything": list(PATCHES),
}
