# Build the port on Windows: clang-cl, lld-link, Ninja, the Vulkan backend.
#
#   powershell -ExecutionPolicy Bypass -File tools\windows\build.ps1 [-Reconfigure] [-Check] [-Jobs N]
#
#   -Reconfigure  run CMake again (after a fresh lift, or a new toolkit)
#   -Check        only say how much would be rebuilt
#   -Jobs N       parallel compiles (default: one per 6 GB of RAM, at most the
#                 core count). Each lifted chunk is tens of MB of C++ and clang
#                 takes 3-4 GB on one, so this is what keeps the machine usable.
#
# The build stops itself when free memory falls under 10% (exit code 99).
# Needs: VS 2022 Build Tools (C++), LLVM, CMake, Ninja, Python (the .venv), and
# vcpkg with sdl2[vulkan], glslang and vulkan-headers (tools\windows\install_deps.ps1).
param([switch]$Reconfigure, [switch]$Check, [int]$Jobs = 0, [string]$RecompDir = '')
. "$PSScriptRoot\env.ps1"
Import-BuildEnv

$recomp = if ($RecompDir) { $RecompDir } else { $script:PES_RECOMP }
$bd = $script:PES_BUILD
$tk = $script:PS3RECOMP_DIR
if (-not (Test-Path "$recomp\ppu_recomp.h")) { throw "no lift in $recomp (run tools\windows\rebuild.ps1 first)" }
if (-not (Test-Path "$tk\CMakeLists.txt")) { throw "no toolkit in $tk (run tools\windows\setup_toolkit.ps1)" }
if (-not (Test-Path $script:PY)) { throw "no Python venv at $($script:PES_VENV) (run tools\windows\install_deps.ps1)" }
$vcpkg = Find-Vcpkg
if (-not $vcpkg) { throw 'no vcpkg with sdl2[vulkan], glslang and vulkan-headers for x64-windows (run tools\windows\install_deps.ps1, or set VCPKG_ROOT)' }

if ($Reconfigure -or -not (Test-Path "$bd\build.ninja")) {
    Say "configure -> $bd (toolkit $tk, vcpkg $vcpkg)"
    # /arch:AVX2: SSE4.1 (pshufb for the SPU shuffles), AVX2 and FMA in hardware,
    # any x86 CPU from about 2015 on. -ffp-contract=off everywhere: with FMA
    # available clang would fuse a*b+c, and the PPU/SPU float code is lifted with
    # every rounding where the console has one. /GS- /Gw as the inFAMOUS 2 port.
    Invoke-Checked cmake -S "$($script:PES_ROOT)\port" -B $bd -G Ninja -DCMAKE_BUILD_TYPE=Release `
        -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DCMAKE_LINKER=lld-link `
        '-DCMAKE_C_FLAGS=/arch:AVX2 /clang:-ffp-contract=off /GS- /Gw' `
        '-DCMAKE_CXX_FLAGS=/arch:AVX2 /clang:-ffp-contract=off /GS- /Gw /EHsc' `
        "-DCMAKE_TOOLCHAIN_FILE=$vcpkg\scripts\buildsystems\vcpkg.cmake" `
        '-DVCPKG_TARGET_TRIPLET=x64-windows' '-DVCPKG_MANIFEST_MODE=OFF' `
        '-DPS3RECOMP_RSX_VULKAN=ON' "-DPS3RECOMP_VULKAN_INCLUDE_DIR=$vcpkg\installed\x64-windows\include" `
        "-DPS3RECOMP_DIR=$tk" "-DRECOMP_DIR=$recomp" "-DPython3_EXECUTABLE=$($script:PY)"
}

$exe = 'PES2013Recomp'
Push-Location $bd
try {
    Invoke-Checked ninja build.ninja | Out-Null
    $plan = Invoke-Exe ninja -n $exe
    $steps = @($plan | Where-Object { $_ -match '^\[' }).Count
    $chunks = @($plan | Select-String -Pattern 'ppu_recomp_\d+\.cpp\.obj' -AllMatches |
                ForEach-Object { $_.Matches.Value } | Sort-Object -Unique).Count
    $os = Get-CimInstance Win32_OperatingSystem
    $totalGb = [math]::Round($os.TotalVisibleMemorySize / 1MB)
    if ($Jobs -le 0) {
        $Jobs = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, [math]::Floor($totalGb / 6)))
    }
    Say "build: $steps steps, $chunks lifted chunk(s), $Jobs job(s), $totalGb GB RAM"
    if ($Check) { exit 0 }

    New-Item -ItemType Directory -Force "$($script:PES_ROOT)\cache" | Out-Null
    $log = "$($script:PES_ROOT)\cache\build-last.log"
    $p = Start-Process -FilePath ninja -ArgumentList @("-j$Jobs", $exe) -NoNewWindow -PassThru `
                       -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    $null = $p.Handle   # without a handle taken now, ExitCode reads back empty
    $low = 100
    while (-not $p.HasExited) {
        Start-Sleep -Seconds 3
        $os = Get-CimInstance Win32_OperatingSystem
        $free = [math]::Floor(100 * $os.FreePhysicalMemory / $os.TotalVisibleMemorySize)
        if ($free -lt $low) { $low = $free }
        if ($free -lt 10) {
            Write-Warning "build: only $free% memory free, stopping this build (try -Jobs $([math]::Max(1, $Jobs - 1)))"
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            exit 99
        }
    }
    $p.WaitForExit()
    $rc = $p.ExitCode
    Say "build: ninja exit $rc, lowest free memory $low%, log $log"
    if ($rc) {
        Get-Content $log, "$log.err" -ErrorAction SilentlyContinue |
            Select-String -Pattern 'error|FAILED' | Select-Object -First 25 | ForEach-Object { $_.Line }
        exit 1
    }
} finally { Pop-Location }

# The vcpkg runtime DLLs (SDL2, glslang's) beside the executable.
Copy-Item "$vcpkg\installed\x64-windows\bin\*.dll" $bd -Force
Say "built: $bd\$exe.exe"
Say 'run it:  powershell -ExecutionPolicy Bypass -File tools\windows\run.ps1'
