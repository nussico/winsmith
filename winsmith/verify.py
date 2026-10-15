"""Check script for an installed PC: did every patch take effect?

Run it on the new PC, logged in as the user Setup created (DEFAULT entries are read from that user's HKCU):
  python -m winsmith.verify [patch ids...] > verify_patches.ps1   (no ids = every patch)
  powershell -ExecutionPolicy Bypass -File verify_patches.ps1     (writes verify.txt to the desktop)
"""
import sys

from .patches import PATCHES, resolve
from .unattend import is_protected, ps_quote

_ROOTS = {"SYSTEM": "Registry::HKEY_LOCAL_MACHINE\\SYSTEM\\", "SOFTWARE": "Registry::HKEY_LOCAL_MACHINE\\SOFTWARE\\",
          "DEFAULT": "Registry::HKEY_CURRENT_USER\\"}


def _reg_check(entry):
    """PowerShell test for one catalog reg entry (same format as unattend._reg_cmd)."""
    path, name, value = entry.split("|")
    hive, _, rest = path.partition("\\")
    key = ps_quote(_ROOTS[hive] + rest)
    if value == "-":
        return f"Absent {key} {ps_quote(name)}"
    if name == "@":
        return f"Test-Path -LiteralPath {key}"
    want = ps_quote(value[3:]) if value.startswith("sz:") else int(value)
    return f"(Val {key} {ps_quote(name)}) -eq {want}"


def make_verify_script(patch_ids):
    lines = [
        "$rows = New-Object System.Collections.ArrayList",
        "function Val($k, $n) { (Get-ItemProperty -LiteralPath $k -Name $n -ErrorAction Stop).$n }",
        "function Absent($k, $n) { -not (Get-ItemProperty -LiteralPath $k -Name $n -ErrorAction SilentlyContinue) }",
        "function Check($id, $what, [scriptblock]$test) {",
        "    try { $ok = [bool](& $test) } catch { $ok = $false }",
        "    [void]$rows.Add([pscustomobject]@{ Result = $(if ($ok) { 'PASS' } else { 'FAIL' }); Patch = $id; Check = $what })",
        "}",
    ]
    for i in resolve(patch_ids):
        p = PATCHES[i]
        for e in p["reg"]:
            lines.append(f"Check {ps_quote(i)} {ps_quote(e)} {{ {_reg_check(e)} }}")
        for a in p["apps"]:
            if not is_protected(a):
                lines.append(f"Check {ps_quote(i)} {ps_quote('app ' + a + ' removed')} "
                             f"{{ -not (Get-AppxPackage -Name {ps_quote(a)}) }}")
    lines += [
        "$fail = @($rows | Where-Object { $_.Result -eq 'FAIL' }).Count",
        "$text = ($rows | Format-Table -AutoSize | Out-String -Width 300) + \"$fail of $($rows.Count) checks failed\"",
        "$text",
        "$out = Join-Path ([Environment]::GetFolderPath('Desktop')) 'verify.txt'",
        "Set-Content -LiteralPath $out -Value $text -Encoding UTF8",
        "\"Saved to $out\"",
    ]
    return "\r\n".join(lines) + "\r\n"


if __name__ == "__main__":
    sys.stdout.write(make_verify_script(sys.argv[1:] or list(PATCHES)).replace("\r\n", "\n"))
