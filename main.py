#!/usr/bin/env python3
"""GHOST DMPM - Development entry point"""
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
if src_path.is_dir(): # Check if it's a directory
    sys.path.insert(0, str(src_path))
else:
    # Fallback for scenarios where src is not found as expected
    # This might happen if the script is run from a different context
    # or if the structure is not as anticipated.
    # For a packaged app, this sys.path manipulation is not needed.
    print(f"Warning: 'src' directory not found at {src_path}. Imports might fail.", file=sys.stderr)


# Now that src is potentially in path, try to import the main function
# from the package and run it.
try:
    from ghost_dmpm.main import main as package_main
except ImportError as e:
    print(f"Error: Could not import the GHOST DMPM application.", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    print(f"Ensure you are running this script from the project root,", file=sys.stderr)
    print(f"or that the 'src' directory is correctly structured and accessible.", file=sys.stderr)
    print(f"Current sys.path: {sys.path}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(package_main()) # Execute and exit with its status
