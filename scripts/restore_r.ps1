# Restore the R lock explicitly (Windows).
# Usage: .\scripts\restore_r.ps1 [-Library C:\path\to\lib]
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

& $Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'

if ($Library) {
    New-Item -ItemType Directory -Force $Library | Out-Null
}

$env:RENV_LIBRARY = $Library
& $Rscript -e @'
lib <- Sys.getenv("RENV_LIBRARY")
args <- list(lockfile = "renv.lock", prompt = FALSE)
if (nzchar(lib)) args$library <- lib
do.call(renv::restore, args)
cat("R library:", if (nzchar(lib)) lib else renv::paths$library(), "\n")
'@

Write-Host ""
Write-Host "Use this library for Python R subprocesses:"
Write-Host "  `$env:R_LIBS = `"$Library`""
Write-Host "  `$env:RNP_RSCRIPT = `"$Rscript`""
