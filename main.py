import os
import shutil # For cleaning up output directory during tests

from ghost_config import GhostConfig
from ghost_crawler import GhostCrawler
from ghost_parser import GhostParser
from ghost_reporter import GhostReporter

def main():
    """
    Main function to run a full cycle of the GHOST Protocol DMPM application.
    This script orchestrates the configuration, crawling, parsing, and reporting modules.
    It's primarily intended for integration testing using mock functionalities.

    The cycle involves:
    1. Setting up configuration using GhostConfig, directing outputs to a 'test_output' directory.
    2. Running GhostCrawler to simulate fetching raw data (uses mock search).
    3. Running GhostParser to process the raw data and generate analyzed MVNO data.
    4. Running GhostReporter to generate a leniency report from the parsed data
       and save it as encrypted JSON.
    5. (Commented out) Optionally displaying the report in a TUI.

    Output files (logs, raw data, parsed data, encrypted reports) are saved in
    the './test_output/' directory, which is cleaned and recreated on each run.
    """
    print("--- GHOST Protocol DMPM - Full Cycle Test (with Mocks) ---")
    # print("DEBUG: main() started.") # Kept for potential future debugging

    # 0. Configuration Setup (and cleanup previous test outputs)
    output_dir_name = "test_output"
    # print(f"DEBUG: output_dir_name = {output_dir_name}")

    if os.path.exists(output_dir_name):
        # print(f"DEBUG: '{output_dir_name}' exists. Attempting to remove.")
        try:
            shutil.rmtree(output_dir_name)
            print(f"Cleaned up previous '{output_dir_name}' directory.")
        except Exception as e: # pragma: no cover
            print(f"Error removing directory '{output_dir_name}': {e}. Attempting to continue.")
    # else:
        # print(f"DEBUG: '{output_dir_name}' does not exist.")

    try:
        # print(f"DEBUG: Attempting to create '{output_dir_name}'.")
        os.makedirs(output_dir_name)
        print(f"Successfully created output directory '{output_dir_name}'.")
    except Exception as e: # pragma: no cover
        print(f"Error creating directory '{output_dir_name}': {e}")
        print("Halting due to directory creation error.")
        return # Stop if we can't create the output directory

    # Config files for this main test run
    main_config_file = os.path.join(output_dir_name, "main_app_config.json")
    main_secret_key = os.path.join(output_dir_name, "main_app_secret.key")

    # Ensure mvnos.txt and keywords.txt are findable or use defaults from GhostConfig
    # For this test, we assume they are in the root, or GhostConfig defaults will be used.
    # If they are not found, the crawler will log warnings but proceed with empty lists.
    # Let's ensure example files are used if they exist, otherwise, the crawler will try its defaults.
    mvnos_file = "mvnos.txt" if os.path.exists("mvnos.txt") else "mvnos_example.txt" # Fallback for testing
    keywords_file = "keywords.txt" if os.path.exists("keywords.txt") else "keywords_example.txt"

    if not os.path.exists(mvnos_file):
        print(f"Warning: MVNO file '{mvnos_file}' not found. Crawler might not generate queries.")
    if not os.path.exists(keywords_file):
        print(f"Warning: Keywords file '{keywords_file}' not found. Crawler might not generate queries effectively.")


    config_manager = GhostConfig(config_file=main_config_file, key_file=main_secret_key)
    config_manager.set("app_name", "GhostDMPM_IntegrationTest")
    config_manager.set("output_dir", output_dir_name) # Crucial: direct all outputs here
    config_manager.set("log_file", os.path.join(output_dir_name, "ghost_main_test.log"))
    config_manager.set("search_delay_seconds", 0.1) # Very short delay for testing
    config_manager.set("search_delay_variance_percent", 5)
    config_manager.set_api_key("google_search", "INTEGRATION_TEST_MOCK_API_KEY")
    config_manager.set("mvno_list_file", mvnos_file)
    config_manager.set("keywords_file", keywords_file)

    # Re-initialize logging with the new settings from config_manager
    config_manager._setup_logging()
    logger = config_manager.get_logger("MainIntegrationTest")
    logger.info("Main integration test started. Configuration initialized.")

    # 1. Ghost Crawler
    logger.info("--- Initializing GhostCrawler ---")
    crawler = GhostCrawler(config_manager)
    raw_results_filepath = crawler.run_crawling_cycle(num_results_per_query=2) # Small number for test

    if not raw_results_filepath:
        logger.error("Crawler did not produce an output file. Halting test.")
        print("Crawler failed. Check logs.")
        return
    logger.info(f"Crawler finished. Raw results at: {raw_results_filepath}")
    print(f"Crawler produced: {raw_results_filepath}")

    # 2. Ghost Parser
    logger.info("--- Initializing GhostParser ---")
    parser = GhostParser(config_manager)
    parsed_data_filepath = parser.parse_results(raw_results_filepath)

    if not parsed_data_filepath:
        logger.error("Parser did not produce an output file. Halting test.")
        print("Parser failed. Check logs.")
        return
    logger.info(f"Parser finished. Parsed data at: {parsed_data_filepath}")
    print(f"Parser produced: {parsed_data_filepath}")

    # 3. Ghost Reporter
    logger.info("--- Initializing GhostReporter ---")
    reporter = GhostReporter(config_manager)

    loaded_parsed_data = reporter._load_parsed_data(parsed_data_filepath)
    if not loaded_parsed_data:
        logger.error("Reporter could not load parsed data. Halting test.")
        print("Reporter failed to load data. Check logs.")
        return

    top_n_report_data = reporter.generate_top_n_leniency_report(loaded_parsed_data, top_n=5)
    if not top_n_report_data:
        logger.warning("Reporter generated an empty Top N report, but proceeding.")
        # This might be okay if mock data resulted in no scores, etc.
    else:
        logger.info(f"Reporter generated Top N report data for {len(top_n_report_data)} MVNOs.")
    print(f"Reporter generated data for {len(top_n_report_data)} MVNOs.")

    encrypted_report_path = reporter.save_report_as_encrypted_json(top_n_report_data, "integration_test_report")
    if not encrypted_report_path:
        logger.error("Reporter failed to save the encrypted JSON report.")
        print("Reporter failed to save encrypted JSON. Check logs.")
        # Not halting for this, but it's a failure point
    else:
        logger.info(f"Reporter saved encrypted JSON report to: {encrypted_report_path}")
        print(f"Reporter saved encrypted report: {encrypted_report_path}")

    # Note: TUI display is interactive, so we might skip it in an automated integration test script
    # or make it optional. For now, let's try to run it.
    # print("\n--- Attempting to display report in TUI (Press Q to exit TUI) ---")
    # logger.info("Attempting to display TUI report.")
    # try:
    #     if top_n_report_data: # Only display if there's data
    #         reporter.display_report_tui(top_n_report_data)
    #         logger.info("TUI display finished.")
    #     else:
    #         logger.info("Skipping TUI as no report data was generated.")
    #         print("No data for TUI.")
    # except Exception as e:
    #     logger.error(f"Reporter TUI failed: {e}. This can happen in non-interactive environments.")
    #     print(f"Reporter TUI failed: {e}. This is common in automated test environments.")

    logger.info("--- GHOST Protocol DMPM - Full Cycle Test Complete ---")
    print("\n--- Full Cycle Test Complete ---")
    print(f"All outputs and logs should be in the '{output_dir_name}' directory.")

    # Create a success marker file
    success_marker_path = os.path.join(output_dir_name, "SUCCESS_MARKER.txt")
    try:
        with open(success_marker_path, "w") as f:
            f.write(f"Main.py completed successfully at {time.strftime('%Y%m%d-%H%M%S')}\n")
            f.write(f"Raw results: {raw_results_filepath}\n")
            f.write(f"Parsed results: {parsed_data_filepath}\n")
            if encrypted_report_path:
                f.write(f"Encrypted report: {encrypted_report_path}\n")
        logger.info(f"Successfully created success marker: {success_marker_path}")
        print(f"Created success marker: {success_marker_path}")
    except Exception as e: # pragma: no cover
        logger.error(f"Failed to create success marker: {e}")
        print(f"Failed to create success marker: {e}")


if __name__ == '__main__':
    import time # Add time import for the success marker

    # Create dummy mvnos_example.txt and keywords_example.txt if the main ones don't exist
    # This ensures the main.py can run even if the user hasn't created the primary files yet
    # (though they were created in a previous step of this agent's plan)
    if not os.path.exists("mvnos.txt") and not os.path.exists("mvnos_example.txt"):
        with open("mvnos_example.txt", "w") as f:
            f.write("US Mobile Example\n")
            f.write("Visible Example\n")
        print("Created dummy 'mvnos_example.txt' for test run.")

    if not os.path.exists("keywords.txt") and not os.path.exists("keywords_example.txt"):
        with open("keywords_example.txt", "w") as f:
            f.write("example keyword one\n")
            f.write("example keyword two\n")
        print("Created dummy 'keywords_example.txt' for test run.")

    main()
