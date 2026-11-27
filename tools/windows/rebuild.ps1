# Rebuild the PES 2013 port on Windows: decrypt, analyse, lift, build.
#
#   powershell -ExecutionPolicy Bypass -File tools\windows\rebuild.ps1 [step ...]
#
# Steps, in order (default: all of them): decrypt analyse lift spu build
#
#   decrypt  game\EBOOT.BIN (the 1.04 update from the PKG: NPDRM SELF, key_rev
#            0x0019, free licence, no .rap) -> game\EBOOT.elf with
#            tools\decrypt_self.py and the key file in PES_KEYS. Skipped when
#            EBOOT.elf is already there.
#   analyse  toolkit tools\ppu_loader.py -> analysis\BLUS31029
#   lift     toolkit tools\ppu_lifter.py -> recompiled\BLUS31029, then
#            tools\weaken_lifted.py for the functions the port replaces
#   spu      the SPU images and SPURS jobs in the EBOOT -> port\spu
#   build    tools\windows\build.ps1 (configures the first time)
#
# The same steps as tools/rebuild.sh on macOS; see tools\windows\env.ps1 for
# the paths. LIFT_JOBS sets the lifter's parallelism (default: the core count).
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Steps)
. "$PSScriptRoot\env.ps1"
if (-not $Steps) { $Steps = @('decrypt', 'analyse', 'lift', 'spu', 'build') }
$py = $script:PY
$tk = $script:PS3RECOMP_DIR
$E = $script:PES_EBOOT
if (-not (Test-Path $py)) { throw "no Python venv at $($script:PES_VENV) (run tools\windows\install_deps.ps1)" }
function Assert-Toolkit {
    if (-not (Test-Path "$tk\tools\ppu_lifter.py")) { throw "no toolkit in $tk (run tools\windows\setup_toolkit.ps1)" }
}
$jobs = if ($env:LIFT_JOBS) { $env:LIFT_JOBS } else { [Environment]::ProcessorCount }

foreach ($s in $Steps) {
    switch ($s) {
        'decrypt' {
            Say 'decrypt'
            if (-not (Test-Path $E)) {
                if (-not (Test-Path $script:PES_EBOOT_BIN)) {
                    throw "EBOOT.BIN not found: $($script:PES_EBOOT_BIN) (copy EBOOT.BIN, PARAM.SFO, ICON0.PNG and PS3LOGO.DAT from the 01.04 update into game\)"
                }
                if (-not (Test-Path $script:PES_KEYS)) {
                    throw "no key file: $($script:PES_KEYS) (see tools\decrypt_self.py for its format; set PES_KEYS to use another path)"
                }
                # Written beside it first, so a failed run leaves no EBOOT.elf behind.
                Invoke-Exe $py "$($script:PES_ROOT)\tools\decrypt_self.py" $script:PES_EBOOT_BIN -o "$E.partial" --keys $script:PES_KEYS
                if ($LASTEXITCODE) { Remove-Item "$E.partial" -ErrorAction SilentlyContinue; throw 'decrypt_self.py failed' }
                Move-Item -Force "$E.partial" $E
            }
            $fs = [System.IO.File]::OpenRead($E)
            $magic = New-Object byte[] 4
            [void]$fs.Read($magic, 0, 4)
            $fs.Close()
            if (-not ($magic[0] -eq 0x7F -and $magic[1] -eq 0x45 -and $magic[2] -eq 0x4C -and $magic[3] -eq 0x46)) { throw "$E is not an ELF" }
            Write-Host "  $E`: $((Get-FileHash $E -Algorithm SHA256).Hash.ToLower())"
        }
        'analyse' {
            Say 'analyse'
            Assert-Toolkit
            Invoke-Checked $py "$tk\tools\ppu_loader.py" $E --output $script:PES_ANALYSIS
        }
        'lift' {
            Say 'lift'
            Assert-Toolkit
            Invoke-Checked $py "$tk\tools\ppu_lifter.py" $E --jobs $jobs --chunks 12 `
                --functions "$($script:PES_ANALYSIS)\EBOOT.functions.json" `
                --hle-stubs "$($script:PES_ANALYSIS)\EBOOT.imports.json" `
                --output $script:PES_RECOMP
            # The functions port\pes_leagues.cpp and port\pes_ml.cpp replace (port\lifted_overrides.txt).
            Invoke-Checked $py "$($script:PES_ROOT)\tools\weaken_lifted.py" $script:PES_RECOMP
        }
        'spu' {
            Say 'spu'
            Assert-Toolkit
            Invoke-Checked $py "$tk\tools\extract_spu_images.py" $E --output "$($script:PES_ANALYSIS)\spu"
            Invoke-Checked $py "$($script:PES_ROOT)\tools\lift_spu.py" --toolkit $tk --images "$($script:PES_ANALYSIS)\spu"
            Invoke-Checked $py "$($script:PES_ROOT)\tools\lift_jobs.py" --toolkit $tk --eboot $E
        }
        'build' {
            Say 'build'
            $reconf = -not (Test-Path "$($script:PES_BUILD)\build.ninja")
            if ($reconf) { & "$PSScriptRoot\build.ps1" -Reconfigure } else { & "$PSScriptRoot\build.ps1" }
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
        }
        default { throw "unknown step '$s' (decrypt analyse lift spu build)" }
    }
}
Say 'done'
