# Prepare the ps3recomp toolkit the Windows build uses.
#
#   powershell -ExecutionPolicy Bypass -File tools\windows\setup_toolkit.ps1 [-Dest DIR]
#
# Clones sp00nznet/ps3recomp, checks out the commit in env.ps1 and applies
# patches\ps3recomp-e85647a-pes13-windows.patch. A checkout that already has the
# patch is left alone; one with changes of its own is never touched. Line endings
# are kept as committed (core.autocrlf=false), or the patch would not apply.
param([string]$Dest = '')
. "$PSScriptRoot\env.ps1"
if ($Dest) { $script:PS3RECOMP_DIR = $Dest }
$tk = $script:PS3RECOMP_DIR
$patch = $script:TOOLKIT_PATCH
if (-not (Test-Path $patch)) { throw "patch not found: $patch" }

if (-not (Test-Path (Join-Path $tk '.git'))) {
    Say "cloning $($script:TOOLKIT_URL) -> $tk"
    Invoke-Checked git -c core.autocrlf=false clone --quiet $script:TOOLKIT_URL $tk
}
Invoke-Checked git -C $tk config core.autocrlf false

Invoke-Exe git -C $tk apply --reverse --check $patch | Out-Null
if ($LASTEXITCODE -eq 0) { Say "toolkit already patched: $tk"; exit 0 }

$dirty = Invoke-Exe git -C $tk status --porcelain
if ($dirty) { throw "$tk has local changes and the patch is not applied: not touching it" }

Invoke-Exe git -C $tk cat-file -e "$($script:TOOLKIT_COMMIT)^{commit}" | Out-Null
if ($LASTEXITCODE) { Invoke-Checked git -C $tk fetch --quiet origin }
Invoke-Checked git -C $tk checkout --quiet $script:TOOLKIT_COMMIT
# A checkout made with another core.autocrlf is rewritten as committed.
Invoke-Exe git -C $tk rm --cached -r --quiet . | Out-Null
Invoke-Checked git -C $tk reset --quiet --hard
Invoke-Exe git -C $tk apply --whitespace=nowarn $patch
if ($LASTEXITCODE) { throw "the patch does not apply to $tk -- is it a clean checkout of $($script:TOOLKIT_COMMIT)?" }
Say "toolkit ready: $tk ($($script:TOOLKIT_COMMIT) + $(Split-Path $patch -Leaf))"
