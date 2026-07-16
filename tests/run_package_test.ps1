param(
    [Parameter(Mandatory = $true)]
    [string]$Blender,

    [Parameter(Mandatory = $true)]
    [string]$Package,

    [Parameter(Mandatory = $true)]
    [string]$WorkDirectory,

    [ValidatePattern("^[A-Z]$")]
    [string]$DriveLetter = "O"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$packagePath = (Resolve-Path -LiteralPath $Package).Path
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
if ((& subst) -match "(?m)^$([regex]::Escape($driveName))\\:") {
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
}

function New-BlenderProcess {
    param([string[]]$Arguments)

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
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    return $process
}

function Invoke-BlenderProcess {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    $process = New-BlenderProcess -Arguments $Arguments
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
    [IO.File]::WriteAllText(
        (Join-Path $profile "results\$Name.stdout.log"),
        $stdout,
        [Text.UTF8Encoding]::new($false)
    )
    [IO.File]::WriteAllText(
        (Join-Path $profile "results\$Name.stderr.log"),
        $stderr,
        [Text.UTF8Encoding]::new($false)
    )
    if ($process.ExitCode -ne 0) {
        throw "Blender process failed: $Name ($($process.ExitCode))"
    }
}

try {
    Invoke-BlenderProcess -Name "install" -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--command",
        "extension",
        "install-file",
        "-r",
        "user_default",
        $packagePath
    )

    $environment["SMC_TEST_RESULT"] = Join-Path $runtimeProfile (
        "results\packaged_dependency.json"
    )
    Invoke-BlenderProcess -Name "dependency" -Arguments @(
        "--factory-startup",
        "--disable-autoexec",
        "--background",
        "--python",
        (Join-Path $repo "tests\blender\verify_packaged_dependency.py")
    )
}
finally {
    & subst $driveName /d
}

[PSCustomObject]@{
    Result = Join-Path $profile "results\packaged_dependency.json"
    InstallLog = Join-Path $profile "results\install.stdout.log"
    DependencyLog = Join-Path $profile "results\dependency.stdout.log"
}
