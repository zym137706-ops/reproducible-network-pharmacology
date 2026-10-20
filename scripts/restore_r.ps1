# Restore the R lock explicitly (Windows).
# Usage: .\scripts\restore_r.ps1 [-Library C:\path\to\lib]
#
# Every Rscript call is checked. Any non-zero exit stops the script with a
# non-zero status; no "success" hint is printed after a failure.
param(
    [string]$Library = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Rscript = if ($env:RNP_RSCRIPT) { $env:RNP_RSCRIPT } else { "Rscript" }
if (-not (Get-Command $Rscript -ErrorAction SilentlyContinue)) {
    throw "Rscript not found; install R 4.5.x or set RNP_RSCRIPT"
}

# 1. Bootstrap renv. Check the exit status explicitly.
& $Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'
if ($LASTEXITCODE -ne 0) {
    throw "renv bootstrap failed with exit code $LASTEXITCODE"
}

# 2. Resolve the target. Explicit paths are absolutized here; the default path
#    is resolved by renv itself after restore, so no platform/version suffix is
#    guessed by this script.
$explicitLibrary = $null
if ($Library) {
    $explicitLibrary = [System.IO.Path]::GetFullPath($Library)
    New-Item -ItemType Directory -Force $explicitLibrary | Out-Null
    $env:RENV_LIBRARY = $explicitLibrary
} else {
    Remove-Item Env:RENV_LIBRARY -ErrorAction SilentlyContinue
}

# 3. Restore, print the actual absolute library path, and check the status.
$restoreOutput = & $Rscript -e @'
lib <- Sys.getenv("RENV_LIBRARY")
args <- list(lockfile = "renv.lock", prompt = FALSE)
if (nzchar(lib)) args$library <- lib
do.call(renv::restore, args)
resolved <- if (nzchar(lib)) normalizePath(lib) else normalizePath(renv::paths$library(project = getwd()))
cat("R_LIBRARY=", resolved, "\n", sep = "")
'@
if ($LASTEXITCODE -ne 0) {
    throw "renv restore failed with exit code $LASTEXITCODE"
}

$marker = $restoreOutput | Where-Object { $_ -like "R_LIBRARY=*" } | Select-Object -Last 1
if (-not $marker) {
    throw "restore did not report an R_LIBRARY path"
}
$resolvedLibrary = ($marker -replace "^R_LIBRARY=", "").Trim()
if (-not $resolvedLibrary -or -not [System.IO.Path]::IsPathRooted($resolvedLibrary)) {
    throw "restore reported a non-absolute R library path: '$resolvedLibrary'"
}

Write-Host ""
Write-Host "Use this exact library for Python R subprocesses:"
Write-Host "  `$env:R_LIBS = `"$resolvedLibrary`""
Write-Host "  `$env:RNP_RSCRIPT = `"$Rscript`""
Write-Host "R_LIBS=$resolvedLibrary"
