#!/usr/bin/env python3
from ghost_dmpm.core.config import GhostConfig
from ghost_dmpm.core.crawler import GhostCrawler
import json
import os
from pathlib import Path # For creating test_api_output_dir more robustly

# Initialize config. This will use the new GhostConfig logic:
# - Auto-detect project_root.
# - Load config from project_root/config/ghost_config.json (or example).
# - Logging and other paths will be relative to project_root.
config = GhostConfig()

# Explicitly set output_dir for this test script's specific outputs,
# if this test is meant to write to a unique location different from config's defaults.
test_api_output_dir_name = "test_api_output_google_api"
test_api_output_abs_path = config.project_root / test_api_output_dir_name
test_api_output_abs_path.mkdir(parents=True, exist_ok=True)

# Set the specific 'crawler.output_dir' key the crawler now expects.
config.set("crawler.output_dir", test_api_output_dir_name) # Path relative to project_root

# Initialize crawler - this will use the API key from config.json
# and the crawler.output_dir we just set.
crawler = GhostCrawler(config)

# Test single search
print("Testing Google Search API...")
# The API key and CX ID from config should be used by GhostCrawler.
# GhostCrawler will attempt to use the real Google API if configured,
# otherwise it will use mock data.

# Changed _perform_search to _google_search and removed num_results.
# _google_search is an internal method; for a true integration test,
# search_mvno_policies might be more appropriate if the test aims to check the full search flow.
# For now, aligning with the apparent original intent of testing a single API-like call.
results_container = crawler._google_search(query="US Mobile prepaid no ID")
results = results_container.get("items", []) if results_container and isinstance(results_container, dict) else []


if results:
    print(f"✓ API Working! Found {len(results)} results")
    print("\nFirst result:")
    # Ensure results are serializable before printing, handle potential complex objects if any
    try:
        print(json.dumps(results[0], indent=2))
    except TypeError:
        print("Could not serialize the first result to JSON. Printing as string:")
        print(str(results[0]))
    # Log all results for inspection if needed, especially if the first one is minimal
    print("\nFull results (first 3 or fewer):")
    for res_item in results[:3]: # Print only up to 3 results
        try:
            print(json.dumps(res_item, indent=2))
        except TypeError:
            print(str(res_item))

else:
    print("✗ API Call to _google_search did not return items or failed.")
    print("  This could be due to an invalid/restricted API key (if not in mock mode),")
    print("  incorrect CX ID, billing issues, or the API not being enabled.")
    if results_container is None:
        print("  (Call to _google_search returned None)")
    elif not isinstance(results_container, dict):
        print(f"  (Call to _google_search returned unexpected type: {type(results_container)})")


# Print the search mode the crawler decided on, for clarity
# The attribute 'search_service' is not in GhostCrawler. It's 'search_mode'.
print(f"\nGhostCrawler effective search mode: {crawler.search_mode}")
