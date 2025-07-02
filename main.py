# Marker: Script started
with open('script_started.marker', 'w') as f_marker:
    f_marker.write('Script initialization begun')

import os
import shutil # For cleaning up output directory during tests
import sys # For directory creation diagnostic
import traceback # For exception capture

# Marker: Imports complete (basic os, shutil, sys, traceback)
with open('imports_base_complete.marker', 'w') as f_marker:
    f_marker.write('Base imports successful')

print("DEBUG: main.py script started loading imports...")

from ghost_config import GhostConfig
from ghost_crawler import GhostCrawler
from ghost_parser import GhostParser
from ghost_reporter import GhostReporter

# Marker: All application imports complete
with open('imports_app_complete.marker', 'w') as f_marker:
    f_marker.write('All application imports successful')

if __name__ == '__main__':
    # Marker: Entered __main__ block
    with open('main_block_entered.marker', 'w') as f_marker:
        f_marker.write('__main__ block entered.')

    print("--- GHOST Protocol DMPM - Full Cycle Test (with Mocks) ---")
    # print("DEBUG: __main__ block execution started.") # Less verbose now

    try:
        import time # Add time import for the success marker

        # Create dummy mvnos_example.txt and keywords_example.txt if the main ones don't exist
        if not os.path.exists("mvnos.txt") and not os.path.exists("mvnos_example.txt"):
            with open("mvnos_example.txt", "w") as f:
                f.write("US Mobile Example\n")
                f.write("Visible Example\n")
        if not os.path.exists("keywords.txt") and not os.path.exists("keywords_example.txt"):
            with open("keywords_example.txt", "w") as f:
                f.write("example keyword one\n")
                f.write("example keyword two\n")

        output_dir_name = "test_output"

        if os.path.exists(output_dir_name):
            try:
                shutil.rmtree(output_dir_name)
            except Exception as e:
                # Log to a marker file if shutil.rmtree fails, as logging might not be set up
                with open('rmtree_error_early.marker', 'w') as f_marker:
                    f_marker.write(f"Error removing directory '{output_dir_name}' before logging: {e}")

        try:
            os.makedirs(output_dir_name, exist_ok=True)
            if not os.path.exists(output_dir_name) or not os.path.isdir(output_dir_name):
                # Log to marker if directory creation fails
                with open('mkdir_failed_early.marker', 'w') as f_marker:
                    f_marker.write(f"os.makedirs for '{output_dir_name}' did not result in a directory.")
                raise SystemExit(f"Halting: Output directory {output_dir_name} not created.")

        except Exception as e:
            with open('mkdir_exception_early.marker', 'w') as f_marker:
                 f_marker.write(f"Exception during os.makedirs for '{output_dir_name}' before logging: {type(e).__name__}: {e}")
            raise

        main_config_file = os.path.join(output_dir_name, "main_app_config.json")
        main_secret_key = os.path.join(output_dir_name, "main_app_secret.key")

        # Restore original file usage
        mvnos_file = "mvnos.txt" if os.path.exists("mvnos.txt") else "mvnos_example.txt"
        keywords_file = "keywords.txt" if os.path.exists("keywords.txt") else "keywords_example.txt"

        # Minimal checks for file existence, actual handling is within modules
        if not os.path.exists(mvnos_file):
             print(f"Warning: MVNO file '{mvnos_file}' not found by main.py.") # Use print as logger not yet up
        if not os.path.exists(keywords_file):
             print(f"Warning: Keywords file '{keywords_file}' not found by main.py.")

        config_manager = GhostConfig(config_file=main_config_file, key_file=main_secret_key)
        config_manager.set("app_name", "GhostDMPM_IntegrationTest")
        config_manager.set("output_dir", output_dir_name)
        config_manager.set("log_file", os.path.join(output_dir_name, "ghost_main_test.log"))
        config_manager.set("search_delay_seconds", 0.1) # Keep test delays low
        config_manager.set("search_delay_variance_percent", 5) # Keep test delays low
        config_manager.set_api_key("google_search", "INTEGRATION_TEST_MOCK_API_KEY")
        config_manager.set("mvno_list_file", mvnos_file)
        config_manager.set("keywords_file", keywords_file)

        config_manager._setup_logging()
        logger = config_manager.get_logger("MainIntegrationTest")
        logger.info("Main integration test started. Configuration initialized.")

        crawler = GhostCrawler(config_manager)
        raw_results_filepath = crawler.run_crawling_cycle(num_results_per_query=1) # Keep num_results_per_query low for tests

        if not raw_results_filepath:
            logger.error("Crawler did not produce an output file. Halting test.")
            raise SystemExit("Crawler failed.")
        logger.info(f"Crawler finished. Raw results at: {raw_results_filepath}")

        parser = GhostParser(config_manager)
        parsed_data_filepath = parser.parse_results(raw_results_filepath)

        if not parsed_data_filepath:
            logger.error("Parser did not produce an output file. Halting test.")
            raise SystemExit("Parser failed.")
        logger.info(f"Parser finished. Parsed data at: {parsed_data_filepath}")

        reporter = GhostReporter(config_manager)
        loaded_parsed_data = reporter._load_parsed_data(parsed_data_filepath)
        if not loaded_parsed_data:
            logger.error("Reporter could not load parsed data. Halting test.")
            raise SystemExit("Reporter data load failed.")

        top_n_report_data = reporter.generate_top_n_leniency_report(loaded_parsed_data, top_n=5)
        if not top_n_report_data:
            logger.warning("Reporter generated an empty Top N report, but proceeding.")
        else:
            logger.info(f"Reporter generated Top N report data for {len(top_n_report_data)} MVNOs.")

        encrypted_report_path = reporter.save_report_as_encrypted_json(top_n_report_data, "integration_test_report")
        if not encrypted_report_path:
            logger.error("Reporter failed to save the encrypted JSON report.")
        else:
            logger.info(f"Reporter saved encrypted JSON report to: {encrypted_report_path}")

        logger.info("--- GHOST Protocol DMPM - Full Cycle Test Complete ---")

        success_marker_path = os.path.join(output_dir_name, "SUCCESS_MARKER.txt")
        try:
            with open(success_marker_path, "w") as f:
                f.write(f"Main.py completed successfully at {time.strftime('%Y%m%d-%H%M%S')}\n")
                f.write(f"Raw results: {raw_results_filepath}\n")
                f.write(f"Parsed results: {parsed_data_filepath}\n")
                if encrypted_report_path:
                    f.write(f"Encrypted report: {encrypted_report_path}\n")
            logger.info(f"Successfully created success marker: {success_marker_path}")
        except Exception as e:
            logger.error(f"Failed to create success marker: {e}")
            # No marker file here as logging should be working


    except SystemExit as se:
        # Log SystemExit to a specific marker for clarity
        with open('system_exit_log.txt', 'w') as f:
            f.write(f"SystemExit: {str(se)}\n")
            f.write(traceback.format_exc())
        raise # Re-raise to ensure it's treated as an error if possible
    except Exception as e:
        with open('error_log.txt', 'w') as f:
            f.write(f"FATAL ERROR in __main__: {type(e).__name__}: {str(e)}\n")
            f.write(traceback.format_exc())
        raise
