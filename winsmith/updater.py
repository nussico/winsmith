"""Check GitHub for a newer release and swap the running Winsmith.exe for it. No Qt in here."""
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
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
    name = Path(getattr(compiled, "original_argv0", None) or sys.argv[0]).name
    if os.name == "nt" and not Path(name).suffix:
        name += ".exe"
    folder = getattr(compiled, "containing_dir", None)  # independent of the current directory
    return (Path(folder) / name).resolve() if folder else Path(sys.argv[0]).resolve()


def _version(text):
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(text or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def is_newer(latest, current):
    a, b = _version(latest), _version(current)
    return a is not None and b is not None and a > b


def due(last_check, now=None):
    now = time.time() if now is None else now
    last_check = last_check or 0
    return last_check > now or now - last_check >= CHECK_EVERY  # a clock set in the past must not block checks


def _trusted(url):
    p = urlparse(str(url))
    return p.scheme == "https" and p.netloc == "github.com" and p.path.startswith(f"/{REPO}/releases/download/")


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https":
            raise urllib.error.URLError("Refusing a redirect away from https.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Winsmith-updater"})
    return urllib.request.build_opener(_HttpsOnly).open(req, timeout=TIMEOUT)


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
        size = int(asset.get("size", 0)) if asset else 0
        if not _trusted(url) or size <= 0:  # without a size a truncated download could not be noticed
            url = None
        digest = str(asset.get("digest") or "") if asset and url else ""
        sha256 = digest[7:].lower() if digest.startswith("sha256:") else ""
        return {"version": version, "page": data.get("html_url", ""), "asset_url": url,
                "size": size if url else 0, "sha256": sha256}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def latest_release():
    try:
        return parse_release(_get_json(API))
    except (OSError, ValueError, http.client.HTTPException):  # offline, rate limited, bad JSON: stay silent
        return None


def check(current):
    """The latest release if it is newer than `current`, else None."""
    rel = latest_release()
    return rel if rel and is_newer(rel["version"], current) else None


def download(url, dest, size, progress=None, sha256=""):
    """Download to `dest` and check the size (and the SHA-256, when GitHub gave one). `progress` gets a 0..1 fraction."""
    if not _trusted(url):
        raise RuntimeError("Refusing to download from an unexpected address.")
    dest = Path(dest)
    done = 0
    h = hashlib.sha256()
    try:
        with _open(url) as src, open(dest, "wb") as out:
            while True:
                chunk = src.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and size:
                    progress(min(done / size, 1.0))
        if size and done != size:
            raise RuntimeError(f"Downloaded file has the wrong size ({done} instead of {size} bytes).")
        if sha256 and h.hexdigest() != sha256:
            raise RuntimeError("Downloaded file does not match its checksum.")
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


def cleanup_old(current, wait=0):
    """Delete the exe the last update replaced. The previous process may still hold it for a moment."""
    deadline = time.monotonic() + wait
    while True:
        try:
            _old_path(Path(current)).unlink(missing_ok=True)
            return
        except OSError:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.5)


def cleanup_cache(current_version):
    """Remove the unpacked payloads of older versions (onefile cache: %LOCALAPPDATA%/Winsmith/<version>)."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return
    root = Path(base) / "Winsmith"
    try:
        for d in root.iterdir():
            if d.is_dir() and _version(d.name) is not None and d.name != current_version:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def relaunch(exe):
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    # The Nuitka onefile bootstrap decides parent/child from NUITKA_* variables; the new exe must start fresh.
    env = {k: v for k, v in os.environ.items() if not k.startswith("NUITKA_")}
    subprocess.Popen([str(exe)], creationflags=flags, close_fds=True, env=env)
