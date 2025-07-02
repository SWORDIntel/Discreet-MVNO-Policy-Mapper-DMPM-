# Marker: Script started
with open('script_started.marker', 'w') as f_marker:
    f_marker.write('Script initialization begun')

import os
import shutil # For cleaning up output directory during tests
import sys # For directory creation diagnostic
import traceback # For exception capture
import time # For timestamps and success marker
import json # For loading parsed data for DB

# Marker: Imports complete (basic os, shutil, sys, traceback, time, json)
with open('imports_base_complete.marker', 'w') as f_marker:
    f_marker.write('Base imports successful')

print("DEBUG: main.py script started loading imports...")

from ghost_config import GhostConfig
from ghost_crawler import GhostCrawler
from ghost_parser import GhostParser
from ghost_reporter import GhostReporter
from ghost_db import GhostDatabase # Import GhostDatabase

# Marker: All application imports complete
with open('imports_app_complete.marker', 'w') as f_marker:
    f_marker.write('All application imports successful')

# --- Helper function for running a cycle ---
def run_ghost_cycle(config_manager: GhostConfig, cycle_name: str, db_instance: GhostDatabase):
    logger = config_manager.get_logger(f"MainIntegrationTest:{cycle_name}")
    logger.info(f"Starting GHOST cycle: {cycle_name}")

    crawler = GhostCrawler(config_manager)
    # For the second run, we might want to use slightly different keywords or MVNOs
    # to ensure change detection works. For now, assume crawler behavior is consistent
    # or we modify the input files (mvnos.txt, keywords.txt) between runs.
    # As a simple simulation, we'll rely on re-parsing potentially updated mock data
    # if the crawler's mock store was modified by an external factor (not done here yet).
    # Or, more simply, the act of re-processing identical data should show "no change".

    # If cycle_name is "second_run_change_test", we could modify a dummy source file
    # that ghost_crawler.MOCK_SEARCH_RESULTS_STORE might (hypothetically) load.
    # For this test, we'll assume the crawler might pick up subtle differences if any.
    # The main test for change detection will be to feed slightly altered *parsed data* to the DB.

    raw_results_filepath = crawler.run_crawling_cycle(num_results_per_query=1)
    if not raw_results_filepath:
        logger.error(f"Crawler did not produce an output file during {cycle_name}. Halting cycle.")
        return None, None # Return None for both parsed_path and loaded_parsed_data

    logger.info(f"Crawler finished for {cycle_name}. Raw results at: {raw_results_filepath}")

    parser = GhostParser(config_manager)
    parsed_data_filepath = parser.parse_results(raw_results_filepath)
    if not parsed_data_filepath:
        logger.error(f"Parser did not produce an output file during {cycle_name}. Halting cycle.")
        return None, None

    logger.info(f"Parser finished for {cycle_name}. Parsed data at: {parsed_data_filepath}")

    # Load parsed data for database update
    try:
        with open(parsed_data_filepath, 'r') as f:
            loaded_parsed_data_for_db = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load parsed data from {parsed_data_filepath} for DB update: {e}")
        return parsed_data_filepath, None # Return parsed_path but None for loaded_data

    # Update database with parsed results
    if loaded_parsed_data_for_db and db_instance:
        logger.info(f"Updating database with results from {cycle_name}...")
        for mvno_name, mvno_data in loaded_parsed_data_for_db.items():
            db_instance.update_mvno_data(mvno_name, mvno_data)
        logger.info(f"Database update complete for {cycle_name}.")
    elif not db_instance:
        logger.warning("DB instance not available, skipping database update.")

    return parsed_data_filepath, loaded_parsed_data_for_db


if __name__ == '__main__':
    # Marker: Entered __main__ block
    with open('main_block_entered.marker', 'w') as f_marker:
        f_marker.write('__main__ block entered.')

    print("--- GHOST Protocol DMPM - Full Cycle Test (with Mocks & DB Integration) ---")

    encryption_mode_final = "unknown" # For success marker
    db_active_final = False
    change_detection_tested_final = False
    run1_parsed_path, run2_parsed_path = None, None
    run1_encrypted_report_path, run2_encrypted_report_path = None, None


    try:
        # --- Initial Setup ---
        output_dir_name = "test_output_main_integration" # More specific name
        if os.path.exists(output_dir_name):
            shutil.rmtree(output_dir_name)
        os.makedirs(output_dir_name, exist_ok=True)

        main_config_file = os.path.join(output_dir_name, "main_app_config.json")
        main_secret_key = os.path.join(output_dir_name, "main_app_secret.key")

        # Create dummy mvnos.txt and keywords.txt for the test if real ones don't exist
        # These will be used by the crawler.
        mvnos_file_main = os.path.join(output_dir_name, "mvnos_for_main_test.txt")
        keywords_file_main = os.path.join(output_dir_name, "keywords_for_main_test.txt")

        with open(mvnos_file_main, "w") as f:
            f.write("US Mobile Example\n") # Keep it simple for testing
            f.write("Visible Example\n")
        with open(keywords_file_main, "w") as f:
            f.write("no ID prepaid\n") # For US Mobile mock
            f.write("cash sim\n")      # For Visible mock
            f.write("privacy policy\n") # Generic


        config_manager = GhostConfig(config_file=main_config_file, key_file=main_secret_key)
        config_manager.set("app_name", "GhostDMPM_MainFullTest")
        config_manager.set("output_dir", output_dir_name) # Set the main output dir
        config_manager.set("log_file", os.path.join(output_dir_name, "ghost_main_full_test.log"))
        config_manager.set("search_delay_seconds", 0.05) # Faster for tests
        config_manager.set_api_key("google_search", "MAIN_FULL_TEST_MOCK_API_KEY")
        config_manager.set("mvno_list_file", mvnos_file_main) # Use the test-specific mvnos file
        config_manager.set("keywords_file", keywords_file_main) # Use the test-specific keywords
        # config_manager.set("ENCRYPTION_MODE", "mock") # Optionally force mock for testing

        config_manager._setup_logging() # Initialize logging
        logger = config_manager.get_logger("MainIntegrationFullTest")
        logger.info("Main integration full test started. Configuration and logging initialized.")
        encryption_mode_final = config_manager.crypto_provider.effective_mode if config_manager.crypto_provider else "provider_error"
        logger.info(f"Effective encryption mode for this run: {encryption_mode_final}")

        # Initialize Database
        db = GhostDatabase(config_manager=config_manager, db_dir=os.path.join(output_dir_name, "database_files"))
        db_active_final = True
        logger.info("GhostDatabase initialized.")

        # --- First Run ---
        logger.info("--- Starting First Run ---")
        run1_parsed_path, run1_loaded_data = run_ghost_cycle(config_manager, "first_run", db)

        if run1_loaded_data:
            reporter1 = GhostReporter(config_manager)
            run1_top_n_report = reporter1.generate_top_n_leniency_report(run1_loaded_data, top_n=3)
            run1_encrypted_report_path = reporter1.save_report_as_encrypted_json(run1_top_n_report, "main_test_report_run1")
            if run1_encrypted_report_path:
                logger.info(f"Run 1: Encrypted JSON report saved to: {run1_encrypted_report_path}")
            else:
                logger.error("Run 1: Reporter failed to save the encrypted JSON report.")
        else:
            logger.error("First run did not produce data for reporting. Skipping report generation for run 1.")
        logger.info("--- First Run Complete ---")


        # --- Second Run (for Change Detection Test) ---
        logger.info("--- Starting Second Run (for Change Detection) ---")
        # To effectively test change detection, we need to ensure some data *might* change.
        # Option 1: Modify the input files (mvnos.txt, keywords.txt) - Complex for this script.
        # Option 2: Modify the crawler's mock data source if it's file-based - Also complex here.
        # Option 3: Directly modify the *parsed data* before feeding it to the DB for the second time.
        # For simplicity, let's assume the crawler/parser might produce slightly different results
        # on a second pass, or we could manually tweak the `run1_loaded_data` before a hypothetical
        # second call to `db.update_mvno_data`.

        # For a more direct test of DB change detection:
        # We'll take the data from run1, slightly modify it, and update the DB again.
        if run1_loaded_data and "US Mobile Example" in run1_loaded_data:
            logger.info("Simulating data modification for 'US Mobile Example' for change detection test.")
            modified_usm_data = json.loads(json.dumps(run1_loaded_data["US Mobile Example"])) # Deep copy

            # Change score and a policy keyword to trigger hash difference
            modified_usm_data["average_leniency_score"] = (modified_usm_data.get("average_leniency_score", 0) or 0) - 0.5 # Decrease score
            if "policy_keywords" not in modified_usm_data : modified_usm_data["policy_keywords"] = {}
            modified_usm_data["policy_keywords"]["no_id_strong"] = modified_usm_data["policy_keywords"].get("no_id_strong", 0) + 1 # Increment a keyword count
            modified_usm_data["sources"] = modified_usm_data.get("sources", []) + [{"url": "internal_change_test.com", "snippet": "This data was internally modified for testing change detection."}]


            logger.info("Updating 'US Mobile Example' with modified data to test change detection.")
            db.update_mvno_data("US Mobile Example", modified_usm_data)

            # Verify change was detected
            usm_db_data = db.get_mvno_data("US Mobile Example")
            if usm_db_data and usm_db_data.get("change_detected_on_last_update"):
                logger.info("SUCCESS: Change detection correctly identified a policy change for 'US Mobile Example'.")
                change_detection_tested_final = True
            else:
                logger.error("FAILURE: Change detection did NOT identify a policy change for 'US Mobile Example' after modification.")
                if usm_db_data: logger.error(f"  Change detected flag was: {usm_db_data.get('change_detected_on_last_update')}")

            # Now run the full GHOST cycle again to see if it picks up any other changes or behaves as expected
            # This second full cycle might overwrite the manual change above if crawler/parser output is stable.
            # The purpose here is more about ensuring the system runs end-to-end twice.
            run2_parsed_path, run2_loaded_data = run_ghost_cycle(config_manager, "second_run_full_cycle", db)
            if run2_loaded_data:
                reporter2 = GhostReporter(config_manager) # New reporter instance for potentially different data context
                run2_top_n_report = reporter2.generate_top_n_leniency_report(run2_loaded_data, top_n=3)
                run2_encrypted_report_path = reporter2.save_report_as_encrypted_json(run2_top_n_report, "main_test_report_run2")
                if run2_encrypted_report_path:
                    logger.info(f"Run 2: Encrypted JSON report saved to: {run2_encrypted_report_path}")
            else:
                 logger.warning("Second run (full cycle) did not produce data for reporting.")

        else:
            logger.warning("Skipping direct change detection test as 'US Mobile Example' data from run 1 is missing.")
            # Still attempt a second full cycle run
            run2_parsed_path, run2_loaded_data = run_ghost_cycle(config_manager, "second_run_no_direct_change_test", db)
            if run2_loaded_data and run2_encrypted_report_path: # Check if path was set
                logger.info(f"Run 2 (no direct change test): Encrypted JSON report saved to: {run2_encrypted_report_path}")


        logger.info("--- Second Run Complete ---")

        # --- Feature Detection Output ---
        logger.info("--- GHOST Protocol DMPM - Feature Detection Summary ---")
        logger.info(f"  Encryption Mode: {encryption_mode_final}")
        logger.info(f"  Database Active: {db_active_final}")
        logger.info(f"  Change Detection Tested: {change_detection_tested_final}")
        logger.info("--- Full Test Cycle(s) Complete ---")

        # --- Success Marker ---
        success_marker_path = os.path.join(output_dir_name, "SUCCESS_MARKER_MAIN_FULL_TEST.txt")
        with open(success_marker_path, "w") as f:
            f.write(f"Main.py full integration test completed successfully at {time.strftime('%Y%m%d-%H%M%S')}\n")
            f.write(f"Effective Encryption Mode: {encryption_mode_final}\n")
            f.write(f"Database Active: {db_active_final}\n")
            f.write(f"Change Detection Tested: {change_detection_tested_final}\n")
            if run1_parsed_path: f.write(f"Run 1 Parsed Results: {run1_parsed_path}\n")
            if run1_encrypted_report_path: f.write(f"Run 1 Encrypted Report: {run1_encrypted_report_path}\n")
            if run2_parsed_path: f.write(f"Run 2 Parsed Results: {run2_parsed_path}\n")
            if run2_encrypted_report_path: f.write(f"Run 2 Encrypted Report: {run2_encrypted_report_path}\n")
            if db.db_filepath: f.write(f"Database file: {db.db_filepath}\n")
            if db.history_filepath: f.write(f"History file: {db.history_filepath}\n")
        logger.info(f"Successfully created success marker: {success_marker_path}")

    except SystemExit as se:
        logger_name = "MainIntegrationFullTest" if 'logger' in locals() else "MainEarlyExit"
        early_logger = logging.getLogger(logger_name)
        if not early_logger.handlers: logging.basicConfig(level=logging.INFO) # Ensure some logging
        early_logger.critical(f"SystemExit: {str(se)}", exc_info=True)
        with open(os.path.join(output_dir_name if 'output_dir_name' in locals() else '.', 'system_exit_log_main.txt'), 'w') as f:
            f.write(f"SystemExit: {str(se)}\n{traceback.format_exc()}")
        raise
    except Exception as e:
        logger_name = "MainIntegrationFullTest" if 'logger' in locals() else "MainEarlyError"
        early_logger = logging.getLogger(logger_name)
        if not early_logger.handlers: logging.basicConfig(level=logging.INFO)
        early_logger.critical(f"FATAL ERROR in __main__: {type(e).__name__}: {str(e)}", exc_info=True)
        with open(os.path.join(output_dir_name if 'output_dir_name' in locals() else '.', 'error_log_main.txt'), 'w') as f:
            f.write(f"FATAL ERROR in __main__: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        # This block executes regardless of exceptions, good for final status logging
        print(f"--- Final Status Report ---")
        print(f"  Output Directory: {output_dir_name if 'output_dir_name' in locals() else 'N/A'}")
        print(f"  Encryption Mode Reported: {encryption_mode_final}")
        print(f"  Database Active Reported: {db_active_final}")
        print(f"  Change Detection Tested Reported: {change_detection_tested_final}")
        print(f"  Log file: {config_manager.get('log_file') if 'config_manager' in locals() and config_manager else 'N/A'}")
        print(f"--- End of GHOST Protocol DMPM Test ---")
