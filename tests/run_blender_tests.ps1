param(
    [Parameter(Mandatory = $true)]
    [string]$Blender,

    [Parameter(Mandatory = $true)]
    [string]$WorkDirectory,

    [string]$PillowRoot = "",

    [string]$TestScript = "tests\blender\verify_public_api.py",

    [string]$ResultName = "public_api.json",

    [switch]$ExcludeWheel,

    [ValidatePattern("^[A-Z]$")]
    [string]$DriveLetter = "Q"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$work = [IO.Path]::GetFullPath($WorkDirectory)

if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}

$profile = Join-Path $work "profile"
$extension = Join-Path $profile "extensions\user_default\shotariyas_material_combiner"
foreach ($directory in @(
    $extension,
    (Join-Path $profile "config"),
    (Join-Path $profile "scripts"),
    (Join-Path $profile "datafiles"),
    (Join-Path $profile "home"),
    (Join-Path $profile "appdata"),
    (Join-Path $profile "localappdata"),
    (Join-Path $profile "cache"),
    (Join-Path $profile "temp"),
    (Join-Path $profile "results")
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$excluded = @(".git", ".ruff_cache", "__pycache__", "build", "dist")
Get-ChildItem -LiteralPath $repo -Force | Where-Object {
    $_.Name -notin $excluded
} | Copy-Item -Destination $extension -Recurse -Force
if ($ExcludeWheel) {
    $wheelDirectory = Join-Path $extension "wheels"
    if (Test-Path -LiteralPath $wheelDirectory) {
        Remove-Item -LiteralPath $wheelDirectory -Recurse -Force
    }
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

$profileRuntime = Join-Path $driveRoot "profile"
$extensionRuntime = Join-Path $profileRuntime "extensions\user_default\shotariyas_material_combiner"
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = (Resolve-Path -LiteralPath $Blender).Path
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
foreach ($argument in @(
    "--factory-startup",
    "--disable-autoexec",
    "--background",
    "--python",
    (Join-Path $extensionRuntime $TestScript)
)) {
    $start.ArgumentList.Add($argument)
}

$environment = @{
    "BLENDER_USER_CONFIG" = Join-Path $profileRuntime "config"
    "BLENDER_USER_SCRIPTS" = Join-Path $profileRuntime "scripts"
    "BLENDER_USER_DATAFILES" = Join-Path $profileRuntime "datafiles"
    "BLENDER_USER_EXTENSIONS" = Join-Path $profileRuntime "extensions"
    "HOME" = Join-Path $profileRuntime "home"
    "USERPROFILE" = Join-Path $profileRuntime "home"
    "APPDATA" = Join-Path $profileRuntime "appdata"
    "LOCALAPPDATA" = Join-Path $profileRuntime "localappdata"
    "XDG_CACHE_HOME" = Join-Path $profileRuntime "cache"
    "TEMP" = Join-Path $profileRuntime "temp"
    "TMP" = Join-Path $profileRuntime "temp"
    "PYTHONNOUSERSITE" = "1"
    "SMC_TEST_CONTRACT" = Join-Path $extensionRuntime "tests\contracts\public_api_contract.json"
    "SMC_TEST_RESULT" = Join-Path $profileRuntime "results\$ResultName"
}
if ($PillowRoot) {
    $environment["SMC_TEST_PILLOW_ROOT"] = [IO.Path]::GetFullPath($PillowRoot)
}
foreach ($key in $environment.Keys) {
    $start.Environment[$key] = $environment[$key]
}
$start.Environment.Remove("PYTHONPATH") | Out-Null

try {
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
}
finally {
    & subst $driveName /d
}
[IO.File]::WriteAllText(
    (Join-Path $profile "results\blender.stdout.log"),
    $stdout,
    [Text.UTF8Encoding]::new($false)
)
[IO.File]::WriteAllText(
    (Join-Path $profile "results\blender.stderr.log"),
    $stderr,
    [Text.UTF8Encoding]::new($false)
)

[PSCustomObject]@{
    ExitCode = $process.ExitCode
    Result = Join-Path $profile "results\$ResultName"
    StandardOutput = Join-Path $profile "results\blender.stdout.log"
    StandardError = Join-Path $profile "results\blender.stderr.log"
}

exit $process.ExitCode
