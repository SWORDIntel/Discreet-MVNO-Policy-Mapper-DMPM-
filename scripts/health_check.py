#!/usr/bin/env python3
"""Quick health check for GHOST DMPM"""
import sys
from pathlib import Path

checks = []

# Check directories
for dir_name in ['data', 'logs', 'config', 'reports']:
    path = Path(dir_name)
    exists = path.exists()
    checks.append(f"{'✓' if exists else '✗'} {dir_name}/ directory")

# Check config
config_exists = Path('config/ghost_config.json').exists()
checks.append(f"{'✓' if config_exists else '✗'} Configuration file")

# Print results
print("=== GHOST DMPM Health Check ===")
for check in checks:
    print(check)

if any('✗' in check for check in checks):
    print("\n⚠️  Some checks failed. Run setup scripts.")
    sys.exit(1)
else:
    print("\n✅ All checks passed!")
