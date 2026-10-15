# Winsmith installer for Windows:  irm https://raw.githubusercontent.com/nussico/winsmith/main/install.ps1 | iex
$src = 'https://github.com/nussico/winsmith/archive/refs/heads/main.zip'

function Find-Python {
    foreach ($c in @(@{ exe = 'py'; args = @('-3') }, @{ exe = 'python'; args = @() }, @{ exe = 'python3'; args = @() })) {
        if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
        $a = $c.args
        $ok = & $c.exe @a -c 'import sys; print(sys.version_info >= (3, 9))' 2>$null
        if ($ok -eq 'True') { return $c }
    }
}

function Run($what) {
    $a = $py.args
    & $py.exe @a @args
    if ($LASTEXITCODE) { throw "$what failed (exit code $LASTEXITCODE)." }
}

$py = Find-Python
if (-not $py) {
    Write-Host 'Python 3.9+ not found. Installing it with winget...'
    winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $py = Find-Python
    if (-not $py) { throw 'Python is installed but not on PATH yet. Open a new terminal and run this again.' }
}

Write-Host 'Installing Winsmith...'
Run 'Installing pipx' -m pip install --user --upgrade --quiet --disable-pip-version-check pipx
Run 'Installing Winsmith' -m pipx install --force $src
Run 'Adding winsmith to PATH' -m pipx ensurepath --quiet

Write-Host ''
Write-Host 'Done. Start it with:  winsmith   (open a new terminal first)'
Write-Host 'Writing the ISO also needs oscdimg:  winget install Microsoft.WindowsADK  (pick "Deployment Tools")'
