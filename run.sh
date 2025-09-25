#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "--- Setting up virtual environment ---"
# Create a new virtual environment using python3
python3 -m venv listen2me-env

echo "--- Activating virtual environment ---"
source listen2me-env/bin/activate

echo "--- Installing dependencies ---"
pip install -r requirements.txt

# Re-install in editable mode to be sure
echo "--- Installing package in editable mode ---"
pip install -e .

echo "--- Running application ---"
# Run the main module, passing all script arguments
python -m listen2me.main "$@"
