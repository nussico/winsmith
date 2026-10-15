"""Unpack a Windows ISO, add the answer file + patch script, pack it again.

Windows: built-in Mount-DiskImage to read, oscdimg (Windows ADK) to write.
Linux:   7z to read (it understands the UDF part Windows ISOs keep their files in), xorriso to write.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .unattend import AUTO_SCRIPT, SCRIPT_NAME, auto_mode, make_patch_script, make_unattend, ps_quote

IS_WINDOWS = sys.platform == "win32"
LABEL = "WINSMITH"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
AUTO_JS = Path(__file__).with_name(AUTO_SCRIPT)


class Cancelled(Exception):
    pass


def _find_oscdimg():
    found = shutil.which("oscdimg")
    if found:
        return found
    base = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    p = base / r"Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe"
    return str(p) if p.exists() else None


def _find_7z():
    found = shutil.which("7z") or shutil.which("7zz")
    if not found and IS_WINDOWS:
        p = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe"
        found = str(p) if p.exists() else None
    return found


# Only the Deployment Tools feature (oscdimg), not the whole ADK. The ADK installer asks for admin rights itself.
ADK_INSTALL = ["winget", "install", "-e", "--id", "Microsoft.WindowsADK", "--accept-source-agreements",
               "--accept-package-agreements", "--override", "/quiet /norestart /features OptionId.DeploymentTools"]


def can_install_oscdimg():
    return IS_WINDOWS and shutil.which("winget") is not None


def install_oscdimg(log, cancel=None):
    """Installs oscdimg with winget. Raises with a readable message if it is still missing afterwards."""
    try:
        _run(ADK_INSTALL, log, cancel)
    except RuntimeError as e:  # winget also exits non-zero for "already installed"; the check below decides
        log(str(e))
    if not _find_oscdimg():
        raise RuntimeError("oscdimg is still missing. If the Windows ADK is already installed, add the "
                           "'Deployment Tools' feature in Settings > Apps > Windows Assessment and Deployment Kit > Modify.")
    log("oscdimg installed.")


def missing_tools():
    """List of (tool, install hint) that are missing on this OS."""
    if IS_WINDOWS:
        if not _find_oscdimg():
            return [("oscdimg", "winget install Microsoft.WindowsADK  (only the 'Deployment Tools' feature is needed)")]
        return []
    missing = []
    if not _find_7z():
        missing.append(("7z", "sudo apt install 7zip   /   sudo dnf install p7zip-plugins   /   sudo pacman -S 7zip"))
    if not shutil.which("xorriso"):
        missing.append(("xorriso", "sudo apt install xorriso   /   sudo dnf install xorriso   /   sudo pacman -S libisoburn"))
    return missing


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled("Build cancelled.")


def _run(cmd, log, cancel=None):
    log("> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    with tempfile.TemporaryFile("w+", errors="replace") as out:
        p = subprocess.Popen([str(c) for c in cmd], stdout=out, stderr=subprocess.STDOUT, text=True,
                             creationflags=_NO_WINDOW)
        while True:
            try:
                p.wait(0.3)
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    p.kill()
                    p.wait()
                    raise Cancelled("Build cancelled.")
        out.seek(0)
        text = out.read()
    if p.returncode:
        tail = [l for l in text.splitlines() if l.strip() and "% complete" not in l][-8:]
        raise RuntimeError(f"{Path(cmd[0]).name} failed ({p.returncode}):\n" + "\n".join(tail))
    return text


def _ps(script, log):
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], log).strip()


def extract(iso, dest, log, cancel=None):
    iso = Path(iso).resolve()
    if not IS_WINDOWS:
        _run([_find_7z(), "x", "-y", f"-o{dest}", iso], log, cancel)
        return
    q = ps_quote(iso)
    try:
        letter = _ps(f"$i = Mount-DiskImage -ImagePath {q} -PassThru; ($i | Get-Volume).DriveLetter", log)
        if len(letter) != 1 or not letter.isalpha():
            raise RuntimeError("Windows mounted the ISO but gave it no drive letter. Try again, "
                               "or check that automatic drive letters are turned on.")
        log(f"Copying files from {letter}: (a few minutes)")

        def copy(src, dst):
            _check(cancel)
            return shutil.copy2(src, dst)
        shutil.copytree(f"{letter}:\\", dest, dirs_exist_ok=True, copy_function=copy)
    finally:
        _ps(f"Dismount-DiskImage -ImagePath {q} | Out-Null", log)
    make_writable(dest)


def make_writable(dest):
    """Files copied from a CD image are read-only, and copytree gives `dest` itself the CD root's read-only flag."""
    os.chmod(dest, stat.S_IWRITE | stat.S_IREAD)
    for root, dirs, files in os.walk(dest):
        for n in dirs + files:
            os.chmod(os.path.join(root, n), stat.S_IWRITE | stat.S_IREAD)


def _find(root, rel):
    """Case-insensitive path lookup (Linux extracts keep the ISO's mixed case)."""
    cur = Path(root)
    for part in Path(rel).parts:
        match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        if match is None:
            raise FileNotFoundError(f"{rel} not found in the ISO - is this a Windows 11 ISO?")
        cur = match
    return cur


def pack(src, out, log, cancel=None):
    bios = _find(src, "boot/etfsboot.com")
    uefi = _find(src, "efi/microsoft/boot/efisys.bin")
    if Path(out).exists():
        Path(out).unlink()
    if IS_WINDOWS:
        _run([_find_oscdimg(), "-m", "-o", "-u2", "-udfver102", f"-l{LABEL}",
              f"-bootdata:2#p0,e,b{bios}#pEF,e,b{uefi}", src, out], log, cancel)
    else:
        _run(["xorriso", "-as", "mkisofs", "-iso-level", "3", "-J", "-joliet-long", "-V", LABEL,
              "-b", bios.relative_to(src).as_posix(), "-no-emul-boot", "-boot-load-size", "8", "-hide", "boot.catalog",
              "-eltorito-alt-boot", "-e", uefi.relative_to(src).as_posix(), "-no-emul-boot",
              "-o", out, src], log, cancel)


def build(iso, out, settings, patch_ids, log, step=None, cancel=None):
    """Whole build. `log` gets progress lines, `step(i, total, label)` the current step. Raises on failure.
    Setting the `cancel` event stops it with Cancelled; the work folder is still cleaned up."""
    step = step or (lambda i, total, label: None)
    missing = missing_tools()
    if missing:
        raise RuntimeError("Missing tools:\n" + "\n".join(f"  {t}: {h}" for t, h in missing))
    if not Path(iso).is_file():
        raise RuntimeError("Pick a Windows 11 ISO first.")
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="winsmith-", dir=out.parent))
    try:
        step(1, 3, "Extracting the ISO")
        log(f"Extracting {Path(iso).name}")
        extract(iso, work, log, cancel)
        _check(cancel)
        sources = _find(work, "sources")
        if not any(f.name.lower() in ("install.wim", "install.esd") for f in sources.iterdir()):
            raise RuntimeError("No install.wim/install.esd in this ISO - is it a Windows 11 ISO?")

        step(2, 3, "Adding your settings")
        log("Adding autounattend.xml")
        (work / "autounattend.xml").write_text(make_unattend(settings, patch_ids), encoding="utf-8")
        if patch_ids:
            # Windows Setup copies sources\$OEM$\$$ to C:\Windows.
            scripts = sources / "$OEM$" / "$$" / "Setup" / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / SCRIPT_NAME).write_text(make_patch_script(patch_ids), encoding="utf-8-sig")
            log(f"Added {len(patch_ids)} patches (log on the installed PC: C:\\Windows\\Setup\\Scripts\\winsmith.log)")
        if auto_mode(settings) == "best_ssd":
            shutil.copyfile(AUTO_JS, sources / AUTO_SCRIPT)
            log("Added the Best SSD automatic install")

        step(3, 3, "Writing the new ISO")
        log(f"Writing {out} (1-3 minutes)")
        pack(work, out, log, cancel)
        log(f"Done: {out} ({out.stat().st_size / 2**30:.1f} GB)")
    except Cancelled:
        Path(out).unlink(missing_ok=True)  # a half-written ISO is useless
        raise
    finally:
        log("Cleaning up")
        shutil.rmtree(work, ignore_errors=True)


def wipe_preview(mode):
    """What the automatic install would erase if THIS PC booted the ISO. Runs autoinstall.js itself, read-only."""
    if not IS_WINDOWS:
        return "Preview only works on Windows."
    fd, f = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="ascii", errors="replace") as fh:
            fh.write("var PREVIEW = true;\r\n" + AUTO_JS.read_text(encoding="utf-8"))
        out = subprocess.run(["cscript", "//nologo", "//E:jscript", f], capture_output=True, text=True,
                             timeout=60, creationflags=_NO_WINDOW).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as e:
        return f"On THIS PC: could not read the disks ({e})."
    finally:
        Path(f).unlink(missing_ok=True)
    out = [line.strip() for line in out if line.strip()]
    if not out:
        return "On THIS PC: could not read the disks."
    disks = sorted(out[1:])
    if mode == "disk0":
        pick = next((d for d in disks if d.startswith("Disk 0:")), None)
    else:
        pick = out[0][5:] if out[0].startswith("PICK ") else None
    head = (f"On THIS PC it would erase:\n  {pick}" if pick
            else "On THIS PC: no single best disk, normal setup would open (nothing erased).")
    return (head + "\n\nDisks in this PC:\n  " + "\n  ".join(disks)
            + "\n(Disk numbers can differ when booted from a USB stick.)")

