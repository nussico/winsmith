# Winsmith UI redesign — spec + plan

## Context
The current PySide6 UI (`winsmith/gui.py`, `winsmith/widgets.py`) carries over design from the old win11-ultimate-iso project. Goal: a fresh, clean, responsive UI that a mixed audience can use — simple by default, every option reachable. Built from scratch; ISO/patch/unattend logic stays untouched except two defaults. Adds saveable/importable profiles.

Decisions (agreed in brainstorming): top stepper, system light/dark theme, native window frame, Basic = default preset, full-profile presets (in-app list + .json import/export, never the password), collapsible patch groups, default username "User".

## Architecture
New package `winsmith/ui/`, old `gui.py` + `widgets.py` deleted. `winsmith/gui.py` becomes a thin shim exporting `main` (keeps `__main__.py` working), or `__main__.py` is updated to import `winsmith.ui.app.main`.

| File | Purpose |
|---|---|
| `winsmith/profiles.py` | Pure logic, no Qt: `PROFILE_KEYS`, `to_profile(name, settings, patches)`, `from_profile(data) -> (settings, patches)` (drops unknown keys/patch IDs, never password), `list_profiles(dir)`, `save_profile(dir, profile)`, `load_profile(path)`, `delete_profile(dir, name)`, safe filename from name. Format: `{"name", "version": 1, "patches": [...], "setup": {unattended, user, admin, computer, skip_oobe, language, keyboard, timezone, edition}}`. Raises `ValueError` with a readable message on bad JSON/shape. |
| `winsmith/ui/theme.py` | `LIGHT`/`DARK` token dicts (bg, surface, surface-2, border, text, muted, accent, accent-hover, success, warn, danger, focus), `current()`, `stylesheet(tokens)`, `apply(app)`; listens to `QGuiApplication.styleHints().colorSchemeChanged` and re-applies + emits a `changed` signal custom-painted widgets repaint on. Font pick (Segoe UI Variable → fallbacks). |
| `winsmith/ui/widgets.py` | `Switch`, `ToggleRow`, `Section` (card with title), `Collapsible` (header "Group · x of y on ›", animated body), `Field` (label, input, inline error, hint, shake), `Combo` (no wheel steal), `ChipGroup` (exclusive, allows none), `ProgressBar`, `DropZone` (click + drag&drop .iso), `ResponsiveGrid` (2 cols ≥640px, else 1), `button()/label()` helpers, `animation()`. All colors from theme tokens. |
| `winsmith/ui/stepper.py` | `Stepper`: numbered steps with label + status line (✓ / "4 patches" / "!" in state colors), click to jump, labels collapse to dots under ~720px except active. |
| `winsmith/ui/pages/{source,patches,setup,build}.py` | One page class each, built on a shared `Page` base (scroll area, centered ≤760px column, gutters 32→16px, sticky footer with Back/Next; footer buttons stretch when narrow). |
| `winsmith/ui/window.py` | `MainWindow` (native frame, 1000×720, min ~480×540): owns state `s`, `patches`, config load/save, step status, shortcuts Ctrl+1…4 / Ctrl+Tab, build thread + `BuildSignals`, closeEvent build-cancel flow. Logic ported from current `gui.py` (`_check`, `_validate`, `_build_thread`, `_tick`, `_finish`, `_open_folder`, `_config_dir`, `CONFIG`/`OLD_CONFIG`, `LOCALES`, `TIMEZONES`). |
| `winsmith/ui/app.py` | `main()` (AppUserModelID, QApplication, theme.apply, show window). |

`pyproject.toml`: `packages = ["winsmith", "winsmith.ui", "winsmith.ui.pages"]`.

## Pages
- **Source**: DropZone ("Drop a Windows 11 ISO here or click to browse"); when set → file row (name, size, ✓, Change). Error "File not found." for bad path. Download-from-Microsoft link when empty. Strips pasted quotes. Picking an ISO pre-fills output if empty.
- **Patches**: ChipGroup Basic / Recommended / Everything / user profiles, one-line explanation under it, shows "Custom" when nothing matches. "⋯" menu: Save as profile… (name dialog, saves patches + Setup answers), Import… (.json → copied into profile dir and applied), Export… (current state to .json), Delete profile (own profiles only). Built-ins change patches only; user profiles also set Setup answers. Below: one Collapsible per group, collapsed by default, "Expand all / Collapse all" link. Count "x of N selected" in header.
- **Setup** (was Unattended): top switch "Answer setup questions automatically"; Sections Account (Username default "User", Password w/ Show + hint "stored base64 on the ISO, never saved", Computer name, Administrator, Skip setup screens), Region (Language, Keyboard, Time zone editable combo), Edition (Ask during setup + GENERIC_KEYS). Hidden when switch off. Inline errors via `account_error` / `region_error`; step shows "!".
- **Build**: Missing-tools warning section (copy buttons, Check again) only if `iso.missing_tools()`; Output field + Browse; Summary rows (Source, Patches, User, Edition, Language) each with "Edit" jumping to its step; Progress (status, sub, bar, expandable Details log). Primary Build ISO; on success "Show in folder". `_check` failure → message, jump to page, shake field (as today).

## Defaults
- Fresh config preset: `PRESETS["Basic"]` (was Recommended).
- Username "User": set in the UI's defaults (`{**DEFAULTS, "user": "User"}` in window.py), **not** in `unattend.DEFAULTS` — keeps `make_unattend({})` meaning "no account" (`tests/test_unattend.py::test_no_user_no_patches` stays valid). Empty field still = asked during setup. Existing configs keep their saved value.

## Steps
1. `profiles.py` + `tests/test_profiles.py` (TDD): round-trip, password excluded, unknown keys/patches dropped, bad JSON → ValueError, delete, filename sanitizing.
2. `ui/theme.py` (tokens, QSS, live scheme switch).
3. `ui/widgets.py` + `ui/stepper.py`.
4. `ui/pages/*` + `ui/window.py` + `ui/app.py`; port logic from `gui.py`; wire `__main__.py`.
5. Delete old `gui.py`/`widgets.py` (or shim); update `pyproject.toml` packages; README mentions profiles + Basic default.
6. Rewrite `tests/test_gui.py` against new UI: step switching, presets + Custom state, step status, Setup validation + switch hides sections, locale combo keeps code, `_check` → Source, config round-trip without password, default user "User" + Basic on fresh config, profile apply sets Setup answers, resize to 480px → no horizontal scrollbar.
7. Save this spec to `docs/superpowers/specs/2026-10-15-ui-redesign-design.md` (no commit unless asked).

## Verification
- `python -m unittest` — all tests pass (offscreen Qt).
- `python main.py`: walk all 4 steps, toggle Windows light/dark while running, resize to ~480px and full screen, save/export/import/delete a profile, pick an ISO via drag&drop, trigger a validation error from Build, run a build if `oscdimg` is present.
