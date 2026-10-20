// Winsmith automatic install ("Best SSD"). Runs inside Windows Setup, started by autounattend.xml:
//   cscript //nologo <media>\sources\autoinstall.js "<edition>"
// JScript + WMI because Setup's boot.wim has no PowerShell; cscript, WMI, diskpart, dism and bcdboot are all there.
// Picks the one clear best internal disk (NVMe > SSD > HDD). Picked: 10 s to cancel, then wipe it, apply the
// image, make it bootable and reboot. Not picked or cancelled: exit, and the normal Setup UI continues.
// Switches set by a line before this file: PREVIEW (print the pick, change nothing), TESTING (load functions only).

var GB = 1073741824;
var MIN_SIZE = 64 * GB;
var RANK = { 'NVMe': 3, 'SSD': 2, 'HDD/other': 1 };   // 'USB/removable' has no rank: never picked
var TITLE = 'Winsmith - automatic install';
var LOG = 'X:\\autoinstall.log';
var EFI = 'S:', WIN = 'W:';

// dism exit code -> what to tell the user.
var DISM_ERRORS = {
    8: 'not enough memory. Give the PC/VM at least 4 GB RAM (turn off dynamic memory).',
    14: 'not enough memory. Give the PC/VM at least 4 GB RAM (turn off dynamic memory).',
    1450: 'not enough memory. Give the PC/VM at least 4 GB RAM (turn off dynamic memory).',
    2: '{edition} is not in this image. Pick another edition.',
    87: '{edition} is not in this image. Pick another edition.'
};

var sh = new ActiveXObject('WScript.Shell');
var fso = new ActiveXObject('Scripting.FileSystemObject');

// ---- Disks ----

function contains(list, x) {
    for (var i = 0; i < list.length; i++) { if (list[i] == x) return true; }
    return false;
}

// One Win32_DiskDrive row -> { number, name, size, kind }. Win32_DiskDrive because the storage classes
// (MSFT_PhysicalDisk) return nothing inside Setup. NVMe disks have VEN_NVME in their device ID; SATA SSD vs HDD
// is guessed from the model name, and a wrong guess at worst causes a tie, which opens normal Setup.
function toDisk(index, model, iface, pnp, mediaType, size) {
    var id = String(pnp).toUpperCase(), name = String(model), kind;
    if (iface == 'USB' || /^(USBSTOR|SD|SDBUS)\\/.test(id) || /Removable|External/i.test(mediaType)) kind = 'USB/removable';
    else if (/VEN_NVME/.test(id) || /NVME/i.test(name)) kind = 'NVMe';
    else if (/SSD/i.test(name)) kind = 'SSD';
    else kind = 'HDD/other';
    return { number: index, name: name, size: parseFloat(size) || 0, kind: kind };
}

function describe(d) {
    return 'Disk ' + d.number + ': ' + d.name + ', ' + Math.round(d.size / GB) + ' GB, ' + d.kind;
}

function wmi() { return GetObject('winmgmts:\\\\.\\root\\cimv2'); }

function readDisks() {
    var disks = [];
    var rows = wmi().ExecQuery('SELECT Index, Model, InterfaceType, PNPDeviceID, MediaType, Size FROM Win32_DiskDrive');
    for (var e = new Enumerator(rows); !e.atEnd(); e.moveNext()) {
        var r = e.item();
        disks.push(toDisk(r.Index, r.Model, r.InterfaceType, r.PNPDeviceID, r.MediaType, r.Size));
    }
    return disks;
}

// Disk numbers holding the install media (a DVD has none). Never wiped.
function mediaDisks(media) {
    var found = [];
    try {
        var q = 'ASSOCIATORS OF {Win32_LogicalDisk.DeviceID="' + media + '"} WHERE AssocClass=Win32_LogicalDiskToPartition';
        for (var e = new Enumerator(wmi().ExecQuery(q)); !e.atEnd(); e.moveNext()) found.push(e.item().DiskIndex);
    } catch (err) { }
    return found;
}

// The single best disk, or null when none qualifies or the best kind is a tie.
function pickDisk(disks, exclude) {
    var top = [], best = 0;
    for (var i = 0; i < disks.length; i++) {
        var d = disks[i], r = RANK[d.kind];
        if (!r || d.size < MIN_SIZE || contains(exclude, d.number)) continue;
        if (r > best) { best = r; top = [d]; } else if (r == best) { top.push(d); }
    }
    return top.length == 1 ? top[0] : null;
}

// ---- Output and commands ----

function log(s) {
    WScript.Echo(s);
    try { var f = fso.OpenTextFile(LOG, 8, true); f.WriteLine(s); f.Close(); } catch (err) { }
}

// Popups show even when Setup hides this console. Returns the button clicked (-1 = timed out).
function say(s, secs, buttons) { log(s); return sh.Popup(s, secs, TITLE, buttons || 48); }

function run(cmd) { log('> ' + cmd); return sh.Run(cmd, 1, true); }

function mustRun(cmd, what) {
    var rc = run(cmd);
    if (rc) throw new Error(what + ' failed (' + rc + ')');
}

// ---- Install steps ----

function isUefi() { return sh.RegRead('HKLM\\SYSTEM\\CurrentControlSet\\Control\\PEFirmwareType') == 2; }

// True unless the user clicks Cancel within 10 s.
function confirm(disk) {
    return say('Installing Windows to ' + describe(disk) + '.\n\nALL DATA ON THIS DISK WILL BE ERASED.\n\n' +
        'Starts by itself in 10 seconds. Click Cancel to stop and choose the disk in setup.', 10, 1 + 48) != 2;
}

// GPT: EFI (300 MB, FAT32), MSR (16 MB), Windows (rest, NTFS).
function partition(disk) {
    var script = 'X:\\diskpart.txt', f = fso.CreateTextFile(script, true);
    f.Write(['select disk ' + disk.number, 'clean', 'convert gpt',
        'create partition efi size=300', 'format quick fs=fat32 label=System', 'assign letter=' + EFI.charAt(0),
        'create partition msr size=16',
        'create partition primary', 'format quick fs=ntfs label=Windows', 'assign letter=' + WIN.charAt(0)].join('\r\n'));
    f.Close();
    mustRun('diskpart /s ' + script, 'diskpart');
}

// dism arguments for the image: install.wim, else install.esd (small ISO), else split install*.swm.
function findImage(media) {
    var src = media + '\\sources\\';
    if (fso.FileExists(src + 'install.wim')) return '/ImageFile:' + src + 'install.wim';
    if (fso.FileExists(src + 'install.esd')) return '/ImageFile:' + src + 'install.esd';
    return '/ImageFile:' + src + 'install.swm /SWMFile:' + src + 'install*.swm';
}

function applyImage(image, edition) {
    log('Applying ' + edition + '...');
    // Scratch on the new disk: Setup's X: RAM disk is too small for dism on low-memory PCs (error 1450).
    var scratch = WIN + '\\$winsmith.scratch';
    fso.CreateFolder(scratch);
    var rc = run('dism /Apply-Image ' + image + ' /Name:"' + edition + '" /ApplyDir:' + WIN + '\\ /ScratchDir:' + scratch);
    try { fso.DeleteFolder(scratch, true); } catch (err) { }
    var why = DISM_ERRORS[rc] || 'see X:\\windows\\logs\\dism\\dism.log';
    if (rc) throw new Error('dism failed (' + rc + '): ' + why.replace('{edition}', '"' + edition + '"'));
}

// .inf files under a folder (recursive).
function findInfs(folder, found) {
    found = found || [];
    if (!fso.FolderExists(folder)) return found;
    for (var e = new Enumerator(fso.GetFolder(folder).Files); !e.atEnd(); e.moveNext()) {
        if (/\.inf$/i.test(e.item().Name)) found.push(e.item().Path);
    }
    for (var d = new Enumerator(fso.GetFolder(folder).SubFolders); !d.atEnd(); d.moveNext()) findInfs(d.item().Path, found);
    return found;
}

// Drivers from the "Drivers" folder on the media, so Setup sees disks that need them (Intel RST/VMD). Never fatal.
function loadDrivers(media) {
    var infs = findInfs(media + '\\$WinpeDriver$');
    for (var i = 0; i < infs.length; i++) run('drvload "' + infs[i] + '"');
    return infs.length;
}

// The same drivers inside the installed Windows. Never fatal.
function addDrivers(media) {
    var dir = media + '\\$WinpeDriver$';
    if (fso.FolderExists(dir)) run('dism /Image:' + WIN + '\\ /Add-Driver /Driver:"' + dir + '" /Recurse');
}

function makeBootable() { mustRun('bcdboot ' + WIN + '\\Windows /s ' + EFI + ' /f UEFI', 'bcdboot'); }

// Setup normally carries these over itself; here we skipped it, so copy the answer file and $OEM$ files.
function copyAnswers(media) {
    var panther = WIN + '\\Windows\\Panther';
    if (!fso.FolderExists(panther)) fso.CreateFolder(panther);
    fso.CopyFile(media + '\\autounattend.xml', panther + '\\unattend.xml', true);
    var oem = media + '\\sources\\$OEM$\\$$';
    if (fso.FolderExists(oem)) run('robocopy "' + oem + '" ' + WIN + '\\Windows /E /NFL /NDL /NJH /NJS');
}

function reboot() {
    log('Done, rebooting...');
    sh.Run('wpeutil reboot', 0, true);
}

function main() {
    var edition = WScript.Arguments(0);
    var media = WScript.ScriptFullName.substr(0, 2);   // e.g. "D:"
    if (!isUefi()) { say('Legacy BIOS: automatic install skipped, choose the disk in setup.', 30); return; }

    loadDrivers(media);
    var skip = mediaDisks(media), disks = readDisks(), disk = pickDisk(disks, skip);
    if (!disk) {
        var seen = [];
        for (var i = 0; i < disks.length; i++) seen.push(describe(disks[i]) + (contains(skip, disks[i].number) ? ', install media' : ''));
        say('No single best disk found, choose the disk in setup.\n\n' + (seen.join('\n') || 'No disks found.'), 60);
        return;
    }
    if (!confirm(disk)) { log('Cancelled by user.'); return; }

    log('Installing to ' + describe(disk));
    partition(disk);
    applyImage(findImage(media), edition);
    addDrivers(media);
    makeBootable();
    copyAnswers(media);
    reboot();
}

if (this.PREVIEW) {
    var all = readDisks(), pick = pickDisk(all, []);
    WScript.Echo(pick ? 'PICK ' + describe(pick) : 'NOPICK');
    for (var k = 0; k < all.length; k++) WScript.Echo(describe(all[k]));
} else if (!this.TESTING) {
    try { main(); } catch (err) {
        say('Automatic install failed: ' + (err.message || err) + '\n\nChoose the disk in setup instead.', 120, 16);
        WScript.Quit(1);
    }
}
