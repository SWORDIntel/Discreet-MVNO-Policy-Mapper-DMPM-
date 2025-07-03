#!/usr/bin/env python3
from ghost_config import GhostConfig
from ghost_reporter import GhostReporter
from ghost_reporter_pdf import GhostPDFGenerator, REPORTLAB_AVAILABLE # Import REPORTLAB_AVAILABLE
import glob
import os
import json # For loading data

# --- Configuration ---
# Use the root config.json for consistency, as it contains API keys and other settings
# that might influence reporter behavior (though less critical for reporter than crawler).
# GhostReporter itself will create its output in its configured output_dir/reports.
# We need to ensure GhostConfig loads the root config, and then we can potentially
# override the output_dir for this specific script's reporting output if needed,
# or let GhostReporter use the output_dir from the loaded root config.json.

# Let's use the root config, but then explicitly tell the reporter
# to save reports into a specific subdirectory for this command's output.
# The prompt's example output for reports:
# "- Encrypted JSON: {json_report}"
# "- PDF Report: {pdf_report}"
# These don't specify a full path, but GhostReporter defaults to output_dir/reports.
# The main.py run created files in "test_output_main_integration/".
# The "latest parsed data" should come from there.

config = GhostConfig() # Loads root config.json by default

# Define where this script's reports should go.
# Let's use a dedicated folder for this command's output to keep things clean.
COMMAND_4_OUTPUT_DIR = "command_4_intel_reports"
if not os.path.exists(COMMAND_4_OUTPUT_DIR):
    os.makedirs(COMMAND_4_OUTPUT_DIR)
    print(f"Created directory for command 4 reports: {COMMAND_4_OUTPUT_DIR}")

# The GhostReporter will use the output_dir from the *loaded config* to create its 'reports' subdir.
# If we want reports in COMMAND_4_OUTPUT_DIR/reports, we should set "output_dir" in the config
# *for the scope of this script*.
# The config loaded is the root config.json. Let's set its output_dir for this run.
# This will make GhostReporter create COMMAND_4_OUTPUT_DIR/reports/.
original_output_dir = config.get("output_dir") # Save original if needed, though not strictly for this script
config.set("output_dir", COMMAND_4_OUTPUT_DIR)
print(f"Reporter will use output directory: {os.path.abspath(COMMAND_4_OUTPUT_DIR)}")
# GhostReporter will internally create a "reports" subdirectory in COMMAND_4_OUTPUT_DIR.

# --- Find latest parsed data ---
# Parsed data comes from COMMAND 3's output directory: test_output_main_integration/
parsed_data_source_dir = "test_output_main_integration"
parsed_files = glob.glob(os.path.join(parsed_data_source_dir, "parsed_mvno_data_*.json"))

if not parsed_files:
    print(f"No parsed data found in {parsed_data_source_dir}. Run main.py (COMMAND 3) first.")
    # Attempt to restore original output_dir in config if it was changed
    if original_output_dir:
        config.set("output_dir", original_output_dir)
    exit(1)

try:
    latest_parsed_file = max(parsed_files, key=os.path.getctime)
    print(f"Using latest parsed data: {latest_parsed_file}")
except Exception as e:
    print(f"Error finding latest parsed file: {e}")
    if original_output_dir:
        config.set("output_dir", original_output_dir)
    exit(1)


# --- Generate reports ---
# GhostReporter's __init__ will use the modified config (with output_dir = COMMAND_4_OUTPUT_DIR)
reporter_logger = config.get_logger("IntelReportGeneratorReporter") # Get a logger for the reporter part
reporter = GhostReporter(config) # This will create COMMAND_4_OUTPUT_DIR/reports/

# Get a logger for GhostPDFGenerator as well
pdf_gen_logger = config.get_logger("IntelReportPDFGenerator")
pdf_gen = GhostPDFGenerator(config, pdf_gen_logger) # Pass the logger

# Load and analyze data
# The reporter._load_parsed_data is a helper, direct load here is also fine.
try:
    with open(latest_parsed_file, 'r') as f:
        data_to_report = json.load(f)
    if not data_to_report:
        print(f"Loaded data from {latest_parsed_file} is empty. Cannot generate report.")
        if original_output_dir:
             config.set("output_dir", original_output_dir)
        exit(1)
except Exception as e:
    print(f"Error loading data from {latest_parsed_file}: {e}")
    if original_output_dir:
        config.set("output_dir", original_output_dir)
    exit(1)

top_n_data = reporter.generate_top_n_leniency_report(data_to_report, top_n=15)

if not top_n_data:
    print("No data available to generate Top N report (parsed data might have been empty or invalid).")
    if original_output_dir:
        config.set("output_dir", original_output_dir)
    exit(1)


# Generate outputs using GhostReporter and GhostPDFGenerator methods
# These methods will save into COMMAND_4_OUTPUT_DIR/reports/
json_report_path = reporter.save_report_as_encrypted_json(top_n_data, "mvno_intel_report")

# For PDF, use the combined method from GhostReporter that calls GhostPDFGenerator
# This handles ReportLab availability and fallback to .txt.
# It returns (plain_pdf_path, encrypted_pdf_path)
# The prompt implies a single PDF report path. Let's assume plaintext for this output.
plain_pdf_report_path, encrypted_pdf_report_path = reporter.save_report_as_pdf_versions(
    top_n_data, "mvno_intel_report"
)

# Determine which PDF path to report based on availability
final_pdf_report_path_to_display = None
if plain_pdf_report_path:
    final_pdf_report_path_to_display = plain_pdf_report_path
    print(f"Plaintext PDF/TXT report generated by GhostReporter: {os.path.abspath(plain_pdf_report_path)}")
    if encrypted_pdf_report_path: # If Fernet encryption was also possible for PDF
        print(f"Encrypted PDF report also generated: {os.path.abspath(encrypted_pdf_report_path)}")
elif encrypted_pdf_report_path: # Should not happen if plain failed, unless logic changes
    final_pdf_report_path_to_display = encrypted_pdf_report_path
    print(f"Only Encrypted PDF report was generated: {os.path.abspath(encrypted_pdf_report_path)}")


print(f"\nReports generated (look in {os.path.abspath(os.path.join(COMMAND_4_OUTPUT_DIR, 'reports'))}/):")
if json_report_path:
    print(f"- Encrypted JSON: {os.path.abspath(json_report_path)}")
else:
    print("- Encrypted JSON: Failed or skipped (check logs, crypto_provider mode may not be 'fernet')")

if final_pdf_report_path_to_display:
    suffix = ".pdf" if REPORTLAB_AVAILABLE else ".txt"
    print(f"- PDF Report (or .txt fallback): {os.path.abspath(final_pdf_report_path_to_display)}")
else:
    print("- PDF Report: Failed or skipped (check logs, ReportLab might be missing and fallback failed)")


print("\nTop 5 Most Lenient MVNOs:")
if top_n_data:
    for mvno_entry in top_n_data[:5]:
        score = mvno_entry.get('average_leniency_score', 0.0)
        print(f"- {mvno_entry.get('mvno_name', 'N/A')}: Score {score:.2f}")
else:
    print("  No data to display for Top 5.")

# Restore original output_dir in config if it was changed.
# This is important if GhostConfig object is reused or if other parts of a larger app rely on it.
if original_output_dir:
    config.set("output_dir", original_output_dir)
    print(f"\nRestored original output_dir in config: {original_output_dir}")

print("\ngenerate_intel_report.py finished.")
