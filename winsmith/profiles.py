"""Saved profiles: a named set of patches plus the Setup answers (never the password).

File format: {"name": str, "version": 1, "patches": [ids], "setup": {key: value}}
"""
import json
import re
from pathlib import Path

from .patches import PATCHES, resolve
from .unattend import DEFAULTS

VERSION = 1
SETUP_KEYS = [k for k in DEFAULTS if k != "password"]


def filename(name):
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip()).strip(" .")
    return f"{stem or 'profile'}.json"


def to_profile(name, settings, patch_ids):
    name = name.strip()
    if not name:
        raise ValueError("A profile needs a name.")
    return {"name": name, "version": VERSION,
            "patches": [p for p in patch_ids if p in PATCHES],
            "setup": {k: settings[k] for k in SETUP_KEYS if k in settings}}


def from_profile(data):
    """Returns (setup answers, patch ids); unknown keys, wrong types and unknown patches are dropped."""
    setup = {k: v for k, v in data.get("setup", {}).items()
             if k in SETUP_KEYS and type(v) is type(DEFAULTS[k])}
    return setup, resolve(data.get("patches", []))


def _check(data):
    if not isinstance(data, dict):
        raise ValueError("Not a Winsmith profile.")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError("The profile has no name.")
    if not isinstance(data.get("patches", []), list) or not isinstance(data.get("setup", {}), dict):
        raise ValueError("Not a Winsmith profile.")
    return data


def load_profile(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"Could not read the file: {e.strerror or e}") from e
    except ValueError as e:
        raise ValueError("The file is not valid JSON.") from e
    return _check(data)


def save_profile(folder, profile, path=None):
    """Writes the profile to `path`, or to `folder` under a name derived from the profile name."""
    path = Path(path) if path else Path(folder) / filename(profile["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_check(profile), indent=2), encoding="utf-8")
    return path


def list_profiles(folder):
    out = []
    for path in sorted(Path(folder).glob("*.json")) if Path(folder).is_dir() else []:
        try:
            out.append(load_profile(path))
        except ValueError:
            pass  # skip broken files instead of hiding all profiles
    return sorted(out, key=lambda p: p["name"].lower())


def delete_profile(folder, name):
    (Path(folder) / filename(name)).unlink(missing_ok=True)
