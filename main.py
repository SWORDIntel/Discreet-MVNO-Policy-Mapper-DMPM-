#!/usr/bin/env python3
"""GHOST Protocol DMPM - Main Integration Test - Per Document #2"""
import sys
import time
from datetime import datetime
from pathlib import Path

# Import core modules
from ghost_config import GhostConfig
from ghost_crawler import GhostCrawler
from ghost_parser import GhostParser
from ghost_db import GhostDatabase
from ghost_reporter import GhostReporter

def main():
    """Execute full GHOST DMPM intelligence cycle"""
    print("=" * 70)
    print("GHOST PROTOCOL - DISCREET MVNO POLICY MAPPER")
    print("=" * 70)

    start_time = time.time()

    # Initialize configuration
    print("\n[*] Initializing configuration...")
    config = GhostConfig()
    logger = config.get_logger("Main")

    # Display feature status
    print(f"[*] Feature Status:")
    print(f"    - Encryption: {'ENABLED' if config.features['encryption'] else 'FALLBACK MODE'}")
    print(f"    - NLP: {'ENABLED' if config.features['nlp'] else 'REGEX MODE'}")
    print(f"    - API Mode: {config.get('google_search_mode', 'mock').upper()}")

    try:
        # Phase 1: Web Crawling
        print("\n[*] Phase 1: Initiating web crawl...")
        crawler = GhostCrawler(config)
        search_results = crawler.search_mvno_policies()
        print(f"    - Crawled {len(search_results)} MVNOs")

        # Phase 2: Intelligence Parsing
        print("\n[*] Phase 2: Parsing intelligence...")
        parser = GhostParser(config)
        parsed_data = parser.parse_results(search_results)
        print(f"    - Extracted policies from {len(parsed_data)} MVNOs")

        # Phase 3: Database Storage
        print("\n[*] Phase 3: Storing intelligence...")
        db = GhostDatabase(config)

        new_policies = 0
        for mvno_name, intel in parsed_data.items():
            if db.store_policy(
                mvno_name,
                intel['policies'],
                intel['leniency_score'],
                intel['sources'][0]['url'] if intel['sources'] else None
            ):
                new_policies += 1

        print(f"    - Stored {new_policies} new/updated policies")

        # Phase 4: Report Generation
        print("\n[*] Phase 4: Generating intelligence report...")
        reporter = GhostReporter(config)
        report = reporter.generate_intelligence_brief()

        # Log crawl statistics
        duration = time.time() - start_time
        db.log_crawl_stats({
            'mvnos_found': len(parsed_data),
            'new_policies': new_policies,
            'changes_detected': len(report['recent_changes']),
            'errors': 0, # Assuming no errors for this script version
            'duration': duration
        })

        # Display summary
        print("\n[*] OPERATION COMPLETE")
        print(f"    - Duration: {duration:.2f} seconds")
        print(f"    - Top MVNO: {report['top_lenient_mvnos'][0]['name'] if report['top_lenient_mvnos'] else 'None'}")
        print(f"    - Reports saved to: reports/")
        print(f"    - Raw data saved to: test_output/")

    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        print(f"\n[!] ERROR: {e}")
        return 1 # Modified to return 1 on error

    print("\n" + "=" * 70)
    return 0

if __name__ == "__main__":
    # Ensure sys.exit is called with the result of main()
    sys.exit(main())
