param(
    [Parameter(Mandatory = $true)]
    [string]$Blender,

    [Parameter(Mandatory = $true)]
    [string]$MaterialCombinerPackage,

    [Parameter(Mandatory = $true)]
    [string]$CatsPackage,

    [Parameter(Mandatory = $true)]
    [string]$WorkDirectory,

    [ValidatePattern("^[A-Z]$")]
    [string]$DriveLetter = "N"
)

$ErrorActionPreference = "Stop"
$expectedCatsHash = (
    "14EBB5945AE803B32F40CD9E35CC3313C7ED914AB2A02BE407B2DAE35474403C"
)
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$mcPackage = (Resolve-Path -LiteralPath $MaterialCombinerPackage).Path
$catsPackagePath = (Resolve-Path -LiteralPath $CatsPackage).Path
$actualCatsHash = (Get-FileHash $catsPackagePath -Algorithm SHA256).Hash
if ($actualCatsHash -ne $expectedCatsHash) {
    throw "CATS reference hash mismatch: $actualCatsHash"
}

$work = [IO.Path]::GetFullPath($WorkDirectory)
if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}
$profile = Join-Path $work "profile"
foreach ($directory in @(
    "config",
    "scripts",
    "datafiles",
    "extensions",
    "home",
    "appdata",
    "localappdata",
    "cache",
    "temp",
    "results"
)) {
    New-Item -ItemType Directory -Path (Join-Path $profile $directory) -Force |
        Out-Null
}

$driveName = "$DriveLetter`:"
$driveRoot = "$driveName\"
if ((& subst) -match "(?m)^$([regex]::Escape($driveName))\:") {
    throw "Temporary drive alias already exists: $driveName"
}
& subst $driveName $work
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create temporary drive alias $driveName for $work"
}

$runtimeProfile = Join-Path $driveRoot "profile"
$environment = @{
    "BLENDER_USER_CONFIG" = Join-Path $runtimeProfile "config"
    "BLENDER_USER_SCRIPTS" = Join-Path $runtimeProfile "scripts"
    "BLENDER_USER_DATAFILES" = Join-Path $runtimeProfile "datafiles"
    "BLENDER_USER_EXTENSIONS" = Join-Path $runtimeProfile "extensions"
    "HOME" = Join-Path $runtimeProfile "home"
    "USERPROFILE" = Join-Path $runtimeProfile "home"
    "APPDATA" = Join-Path $runtimeProfile "appdata"
    "LOCALAPPDATA" = Join-Path $runtimeProfile "localappdata"
    "XDG_CACHE_HOME" = Join-Path $runtimeProfile "cache"
    "TEMP" = Join-Path $runtimeProfile "temp"
    "TMP" = Join-Path $runtimeProfile "temp"
    "PYTHONNOUSERSITE" = "1"
    "SMC_TEST_CONTRACT" = Join-Path $repo (
        "tests\contracts\public_api_contract.json"
    )
}

function Invoke-BlenderProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$ResultName = ""
    )

    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = (Resolve-Path -LiteralPath $Blender).Path
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        $start.ArgumentList.Add($argument)
    }
    foreach ($key in $environment.Keys) {
        $start.Environment[$key] = $environment[$key]
    }
    $start.Environment.Remove("PYTHONPATH") | Out-Null
    if ($ResultName) {
        $start.Environment["SMC_TEST_RESULT"] = Join-Path $runtimeProfile (
            "results\$ResultName"
        )
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    [IO.File]::WriteAllText(
        (Join-Path $profile "results\$Name.stdout.log"),
        $stdoutTask.Result,
        [Text.UTF8Encoding]::new($false)
    )
    [IO.File]::WriteAllText(
        (Join-Path $profile "results\$Name.stderr.log"),
        $stderrTask.Result,
        [Text.UTF8Encoding]::new($false)
    )
    if ($process.ExitCode -ne 0) {
        throw "Blender process failed: $Name ($($process.ExitCode))"
    }
    if ($ResultName) {
        $resultPath = Join-Path $profile "results\$ResultName"
        if (-not (Test-Path -LiteralPath $resultPath)) {
            throw "Blender process did not create $resultPath"
        }
    }
}

try {
    Invoke-BlenderProcess -Name "install-mc" -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--command",
        "extension",
        "install-file",
        "-r",
        "user_default",
        $mcPackage
    )
    Invoke-BlenderProcess -Name "install-cats" -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--command",
        "extension",
        "install-file",
        "-r",
        "user_default",
        $catsPackagePath
    )
    Invoke-BlenderProcess -Name "integration" -ResultName (
        "cats_checkpoint.json"
    ) -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--background",
        "--python",
        (Join-Path $repo "tests\blender\verify_cats_checkpoint.py")
    )
    Invoke-BlenderProcess -Name "restart" -ResultName (
        "checkpoint_restart.json"
    ) -Arguments @(
        "--disable-autoexec",
        "--background",
        "--python",
        (Join-Path $repo "tests\blender\verify_checkpoint_restart.py")
    )
    Invoke-BlenderProcess -Name "uninstall" -Arguments @(
        "--disable-autoexec",
        "--command",
        "extension",
        "remove",
        "cats_blender_plugin,shotariyas_material_combiner"
    )
    Invoke-BlenderProcess -Name "uninstall-check" -ResultName (
        "checkpoint_uninstall.json"
    ) -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--background",
        "--python",
        (Join-Path $repo "tests\blender\verify_checkpoint_uninstall.py")
    )
}
finally {
    & subst $driveName /d
}

[PSCustomObject]@{
    CatsHash = $actualCatsHash
    Integration = Join-Path $profile "results\cats_checkpoint.json"
    Restart = Join-Path $profile "results\checkpoint_restart.json"
    Uninstall = Join-Path $profile "results\checkpoint_uninstall.json"
    ResultsDirectory = Join-Path $profile "results"
}
