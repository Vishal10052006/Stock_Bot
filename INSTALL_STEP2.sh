#!/usr/bin/env bash
set -euo pipefail

# Run from the root of the existing Stock_Bot working tree.
# This only copies the new Research Bot domain; it does not modify memory files.
cp -R research .
cp -R tests/research tests/
printf '%s\n' 'Research Bot RB-0..RB-14 files installed.'
