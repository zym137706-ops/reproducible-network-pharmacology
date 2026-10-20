#!/usr/bin/env bash
# Explicit R bootstrap + lock restore + library selection.
#
# Usage:
#   scripts/restore_r.sh                 # restore into the renv project library
#   scripts/restore_r.sh /abs/path/lib   # restore into an isolated library
#
# Set RSCRIPT to override the Rscript executable. The selected library is printed
# and must be exported as R_LIBS for Python subprocesses that call Rscript.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RSCRIPT="${RSCRIPT:-Rscript}"

if ! command -v "$RSCRIPT" >/dev/null 2>&1; then
  echo "error: Rscript not found; install R 4.5.x or set RSCRIPT" >&2
  exit 2
fi

"$RSCRIPT" -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'

LIB="${1:-}"
if [ -n "$LIB" ]; then
  mkdir -p "$LIB"
fi

RENV_LIBRARY="$LIB" "$RSCRIPT" -e '
lib <- Sys.getenv("RENV_LIBRARY")
args <- list(lockfile = "renv.lock", prompt = FALSE)
if (nzchar(lib)) args$library <- lib
do.call(renv::restore, args)
cat("R library:", if (nzchar(lib)) lib else renv::paths$library(), "\n")
'

echo
echo "Use this library for Python R subprocesses, e.g.:"
echo "  export R_LIBS=\"${LIB:-$ROOT/renv/library}\""
echo "  export RNP_RSCRIPT=\"$(command -v "$RSCRIPT")\""
