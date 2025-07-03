#!/bin/bash
# GHOST DMPM Environment Setup

echo "=== GHOST DMPM SETUP ==="
echo "[*] Checking Python..."
python3 --version || { echo "Python 3 required"; exit 1; }

echo "[*] Creating virtual environment..."
python3 -m venv venv || echo "Virtual environment creation failed, continuing..."

echo "[*] Installing base dependencies..."
pip3 install requests beautifulsoup4 Flask Flask-HTTPAuth python-dateutil

echo "[*] Attempting optional dependencies..."
pip3 install cryptography || echo "Cryptography unavailable - using fallback"
pip3 install spacy || echo "spaCy unavailable - using regex mode"

echo "[*] Creating directory structure..."
mkdir -p data logs reports test_output config templates

echo "[*] Setup complete!"
echo "Run 'python3 main.py' to test or 'docker compose up -d' to deploy"
