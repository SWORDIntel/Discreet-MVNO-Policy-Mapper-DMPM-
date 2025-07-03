#!/usr/bin/env python3
"""Quick deployment test"""
import sys
import importlib

modules = ["ghost_config", "ghost_crawler", "ghost_parser", "ghost_db", "ghost_reporter"]

print("=== GHOST DMPM DEPLOYMENT TEST ===")
errors = 0

for module in modules:
    try:
        importlib.import_module(module)
        print(f"✓ {module} loaded successfully")
    except Exception as e:
        print(f"✗ {module} failed: {e}")
        errors += 1

if errors == 0:
    print("\n✓ All modules loaded successfully!")
    print("Run 'python3 main.py' for full test")
else:
    print(f"\n✗ {errors} modules failed to load")
    sys.exit(1)
