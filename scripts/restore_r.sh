#!/usr/bin/env bash
# Explicit R bootstrap + lock restore + library selection.
#
# Usage:
#   scripts/restore_r.sh                 # restore into the renv project library
#   scripts/restore_r.sh /abs/path/lib   # restore into an explicit isolated library
#
# Set RSCRIPT to override the Rscript executable. Every Rscript call is checked;
# a failure exits non-zero before any success instructions are printed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RSCRIPT="${RSCRIPT:-Rscript}"

if ! command -v "$RSCRIPT" >/dev/null 2>&1; then
  echo "error: Rscript not found; install R 4.5.x or set RSCRIPT" >&2
  exit 2
fi

# 1. Bootstrap renv; `set -e` makes a non-zero status fatal.
"$RSCRIPT" -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'

# 2. Resolve the target. Explicit paths are absolutized; the default target is
#    resolved by renv after restore (never guessed here).
unset RENV_LIBRARY || true
if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
  mkdir -p "$1"
  RENV_LIBRARY="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
  export RENV_LIBRARY
fi

# 3. Restore and print the actual absolute library path.
RESTORE_OUTPUT="$("$RSCRIPT" -e '
lib <- Sys.getenv("RENV_LIBRARY")
args <- list(lockfile = "renv.lock", prompt = FALSE)
if (nzchar(lib)) args$library <- lib
do.call(renv::restore, args)
resolved <- if (nzchar(lib)) normalizePath(lib) else normalizePath(renv::paths$library(project = getwd()))
cat("R_LIBRARY=", resolved, "\n", sep = "")
')" || {
  echo "error: renv restore failed; no library was selected" >&2
  exit 1
}

LIBRARY="$(printf '%s\n' "$RESTORE_OUTPUT" | sed -n 's/^R_LIBRARY=//p' | tail -n 1)"
if [ -z "$LIBRARY" ]; then
  echo "error: restore did not report an R_LIBRARY path" >&2
  exit 1
fi
case "$LIBRARY" in
  /*) ;;
  *)
    echo "error: restore reported a non-absolute R library path: '$LIBRARY'" >&2
    exit 1
    ;;
esac

echo
echo "Use this exact library for Python R subprocesses:"
echo "  export R_LIBS=\"$LIBRARY\""
echo "  export RNP_RSCRIPT=\"$(command -v "$RSCRIPT")\""
echo "R_LIBS=$LIBRARY"
