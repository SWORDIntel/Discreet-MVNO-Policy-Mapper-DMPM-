#!/usr/bin/env python3
"""GHOST DMPM package entry point"""
from .app_logic import main

if __name__ == "__main__":
    # This allows running the package module directly via `python -m ghost_dmpm.main`
    # The actual console script `ghost-dmpm` will call the main() function.
    main()
