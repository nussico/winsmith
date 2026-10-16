"""Check GitHub for a newer release and swap the running Winsmith.exe for it. No Qt in here."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO = "nussico/winsmith"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "Winsmith.exe"
CHECK_EVERY = 24 * 3600  # seconds
TIMEOUT = 10
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
UPDATE_COMMAND = f"irm {RAW}/install.ps1 | iex" if sys.platform == "win32" else f"curl -fsSL {RAW}/install.sh | sh"


def is_frozen():
    """True in the Nuitka-built Winsmith.exe."""
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def exe_path():
    """The Winsmith.exe the user started (for a onefile build, not the copy it unpacks to)."""
    if not is_frozen():
        return None
    compiled = globals().get("__compiled__")
    return Path(getattr(compiled, "original_argv0", None) or sys.argv[0]).resolve()


def _version(text):
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(text or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def is_newer(latest, current):
    a, b = _version(latest), _version(current)
    return a is not None and b is not None and a > b


def due(last_check, now=None):
    return (time.time() if now is None else now) - (last_check or 0) >= CHECK_EVERY


def _trusted(url):
    p = urlparse(str(url))
    return p.scheme == "https" and p.netloc == "github.com" and p.path.startswith(f"/{REPO}/releases/download/")


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Winsmith-updater"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Winsmith-updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_release(data):
    """{'version', 'page', 'asset_url', 'size'} from the GitHub API answer, or None."""
    try:
        version = str(data["tag_name"]).lstrip("v")
        if _version(version) is None:
            return None
        asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET), None)
        url = asset.get("browser_download_url") if asset else None
        if not _trusted(url):
            url = None
        return {"version": version, "page": data.get("html_url", ""), "asset_url": url,
                "size": int(asset.get("size", 0)) if asset and url else 0}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def latest_release():
    try:
        return parse_release(_get_json(API))
    except (OSError, ValueError):  # offline, rate limited, bad JSON: stay silent
        return None


def check(current):
    """The latest release if it is newer than `current`, else None."""
    rel = latest_release()
    return rel if rel and is_newer(rel["version"], current) else None


def download(url, dest, size, progress=None):
    """Download to `dest` and check the size. `progress` gets a 0..1 fraction."""
    if not _trusted(url):
        raise RuntimeError("Refusing to download from an unexpected address.")
    dest = Path(dest)
    done = 0
    try:
        with _open(url) as src, open(dest, "wb") as out:
            while True:
                chunk = src.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress and size:
                    progress(min(done / size, 1.0))
        if size and done != size:
            raise RuntimeError(f"Downloaded file has the wrong size ({done} instead of {size} bytes).")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest


def _old_path(current):
    return current.with_name(current.stem + ".old" + current.suffix)


def apply(new_exe, current):
    """Swap `new_exe` in for the running exe. Windows lets a running exe be renamed, not overwritten."""
    new_exe, current = Path(new_exe), Path(current)
    old = _old_path(current)
    old.unlink(missing_ok=True)
    current.replace(old)
    try:
        new_exe.replace(current)
    except BaseException:
        old.replace(current)  # put the working exe back
        raise


def cleanup_old(current):
    try:
        _old_path(Path(current)).unlink(missing_ok=True)
    except OSError:  # still locked by the previous process: next start
        pass


def relaunch(exe):
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    subprocess.Popen([str(exe)], creationflags=flags, close_fds=True)
