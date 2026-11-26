#!/usr/bin/env bash
# Dev helper: ./dev.sh <args> runs Python from your venv.
# Set WFMT_PY to your venv's python, e.g. WFMT_PY=C:/wfmt-venv/Scripts/python.exe
exec "${WFMT_PY:-python}" "$@"
