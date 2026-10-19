"""Find winget packages on this PC. No Qt in here."""
import re
import shutil
import subprocess
import sys

from .unattend import app_id_ok

IS_WINDOWS = sys.platform == "win32"
TIMEOUT = 60  # seconds


def available():
    return IS_WINDOWS and shutil.which("winget") is not None


def parse_search(text):
    """[{'name', 'id', 'version'}] from the table `winget search` prints; anything unreadable is skipped."""
    lines = [re.sub(r".*\r", "", line) for line in text.splitlines()]  # drop spinner redraws
    head = next((i for i, line in enumerate(lines)
                 if re.match(r"Name\s+Id\s+Version", line) and i + 1 < len(lines) and lines[i + 1].startswith("--")), None)
    if head is None:
        return []
    h = lines[head]
    id_at, ver_at = h.index("Id"), h.index("Version")
    nxt = re.search(r"\s(Match|Source)\b", h[ver_at:])
    end = ver_at + nxt.start() + 1 if nxt else None
    found = []
    for line in lines[head + 2:]:
        name, app, version = line[:id_at].strip(), line[id_at:ver_at].strip(), line[ver_at:end].strip()
        if app_id_ok(app):
            found.append({"name": name or app, "id": app, "version": version})
    return found


def search(query):
    """Runs `winget search`. Raises RuntimeError with a readable message when it cannot."""
    if not available():
        raise RuntimeError("winget was not found on this PC.")
    cmd = ["winget", "search", query.strip(), "--accept-source-agreements", "--disable-interactivity"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"winget search failed: {e}") from e
    return parse_search(out.stdout.decode("utf-8", "replace"))
