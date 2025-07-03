#!/bin/bash
# Verification script for GHOST DMPM installation

echo "=== GHOST DMPM Installation Verification ==="

# Check Python version
echo -n "Python version: "
python --version

# Check package installation
echo -n "Package installed: "
python -c "import ghost_dmpm; print('YES')" 2>/dev/null || echo "NO"

# Check dependencies
echo "Checking dependencies..."
python -c "
import sys
deps = ['requests', 'beautifulsoup4', 'flask', 'websockets']
for dep in deps:
    try:
        __import__(dep)
        print(f'  ✓ {dep}')
    except ImportError:
        print(f'  ✗ {dep}')
        sys.exit(1)
"

echo "=== Basic installation verified ==="
