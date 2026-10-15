# Rethink the patch catalog — spec + plan

## Context
`winsmith/patches.py` holds 29 patches in 8 groups. Some of them no longer do what they claim on current Windows 11 (24H2/25H2):
- BypassNRO is unreliable on 25H2.
- Copilot is now an app with its own removal policy.
- Recall and other new nags are not covered.
- Several patches overlap.

Goal: a verified, clearer catalog with rebuilt groups and presets.

Agreed in brainstorming:
- All four goals: verify and fix existing patches, add missing ones, fewer and clearer patches, rebuilt groups and presets.
- **Safe only:** nothing that lowers security or stops updates.
- Old IDs are **mapped to the new ones** so configs and profiles are not lost silently.
- Verification is a **VM test install** with a check script.

## Catalog (28 patches, 8 groups)
| Group | Patches |
|---|---|
| Install | `hwchecks`, `localaccount` (description fixed: works by hiding the online screens; BypassNRO kept as a fallback), `skipprivacy`, `nobitlocker` |
| Apps | `bloatapps` (list re-checked against 25H2 package names; `Microsoft.Copilot` moves to `ai`), `xboxapp`, `onedrive`, `nowidgets` |
| AI | **new** `ai`: removes the Copilot app; sets `TurnOffWindowsCopilot` (HKLM + DEFAULT) and `WindowsAI\RemoveMicrosoftCopilotApp`; turns off Recall (`WindowsAI\DisableAIDataAnalysis=1`, `AllowRecallEnablement=0`); turns off Click to Do (`DisableClickToDo`) |
| Privacy | `tracking` (merges telemetry + activity + adid), `ads` (adscopilot without the Copilot parts, plus lock-screen ads/Spotlight tips `RotatingLockScreenOverlayEnabled`/`SubscribedContent-338387Enabled` and Settings suggestions), `nobing` (plus search highlights `EnableDynamicContentInWSB=0`), **new** `edge` (Edge policy `HideFirstRunExperience=1` plus the import and default-browser nags) |
| Taskbar & Start | `taskbarleft`, `endtask`, `tidytaskbar` (merges nosearchbox + notaskview) |
| Explorer | `classicmenu`, `fileext`, `hiddenfiles`, `thispc` |
| System & Updates | `darkmode`, `nofaststart`, `longpaths`, `nop2p`, `noautoreboot` |
| Gaming | `gamedvr`, `mouseaccel`, `stickykeys` |

The registry names above come from research. The VM run decides what ships: an entry that does not take effect is fixed or dropped.

**Presets**
- Basic: the 4 Install patches (unchanged).
- Recommended: Basic + bloatapps, onedrive, ai, tracking, ads, nobing, edge, fileext, endtask, nop2p, noautoreboot, gamedvr.
- Everything: all patches.
- Update `ABOUT` texts in `winsmith/ui/pages/patches.py` to match.

## Old IDs → new
New in `winsmith/patches.py`:
```python
ALIASES = {"telemetry": ["tracking"], "activity": ["tracking"], "adid": ["tracking"],
           "adscopilot": ["ads", "ai"], "nosearchbox": ["tidytaskbar"], "notaskview": ["tidytaskbar"]}
def resolve(ids): ...  # expands aliases, drops unknown IDs, de-duplicates, keeps order
```
Use it in:
- `profiles.from_profile` (replaces the `p in PATCHES` filter)
- `winsmith/ui/window.py:56` (config load)

## Files
- `winsmith/patches.py`: new catalog, groups, presets, `ALIASES`, `resolve`. Keep the `_p` helper and the reg-entry format. `hwchecks` stays the PE special case.
- `winsmith/profiles.py`, `winsmith/ui/window.py`: call `resolve`.
- `winsmith/ui/pages/patches.py`: `ABOUT` texts only. Groups render from the catalog automatically.
- `README.md`: the "What it does → Patches" line.
- `tests/test_unattend.py`, `tests/test_profiles.py`, `tests/test_gui.py`: update for the new IDs. Add tests for:
  - `resolve`, including one-to-many aliases and duplicates
  - a profile with old IDs loads as the new ones
  - every patch has a group/label/desc
  - every reg entry parses through `_reg_cmd`
- **New** `tools/verify_patches.ps1`: generated from the catalog by a small `python -m winsmith.verify` or a helper in `unattend.py`. It runs on the installed VM and checks:
  - each reg value (HKLM, plus HKCU of the logged-in user for DEFAULT entries)
  - each removed app is absent
  
  It writes a PASS/FAIL table to the console and to `verify.txt`.

## Steps
1. Save this as `docs/superpowers/specs/2026-10-15-patch-catalog-design.md` (no commit unless asked).
2. TDD: tests for `ALIASES`/`resolve` and the profile migration, then implement them.
3. Rewrite the catalog and presets. Update tests, `ABOUT`, README.
4. Write the verify-script generator and its unit test (the script contains one check per reg entry and app).
5. VM run (user): build an ISO with Everything from a current 25H2 ISO, install, log in, run the verify script, share `verify.txt` and `C:\Windows\Setup\Scripts\winsmith.log`.
6. Fix or drop every FAIL, then repeat step 5 until everything is clean.

## Verification
- `python -m unittest` passes.
- `python main.py`:
  - Patches page shows 8 groups and 28 patches.
  - Presets match.
  - Importing an old profile containing `telemetry` and `adscopilot` selects `tracking`, `ads` and `ai`.
- VM install on 25H2:
  - The local-account flow works offline.
  - `verify.txt` is all PASS.
  - `winsmith.log` has no WARN.
