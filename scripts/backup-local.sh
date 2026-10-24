#!/usr/bin/env bash
set -euo pipefail
exec "${QH_PYTHON:-python3}" "$(dirname "$0")/local_backup.py" backup "$@"
