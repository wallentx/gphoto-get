#!/bin/bash
set -e

FIX=false

while getopts "f" opt; do
  case $opt in
    f)
      FIX=true
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

echo "Syncing dependencies..."
uv sync --extra dev

if [ "$FIX" = true ]; then
    echo "Linting and formatting (fixing errors)..."
    uv run ruff check --fix .
    uv run ruff format .
else
    echo "Linting and formatting (check only)..."
    uv run ruff check .
    uv run ruff format --check .
fi

echo "Building binary..."
uv run --with pyinstaller pyinstaller --onefile gphoto_get.py --name gphoto-get

echo "Build complete! Binary is at dist/gphoto-get"
