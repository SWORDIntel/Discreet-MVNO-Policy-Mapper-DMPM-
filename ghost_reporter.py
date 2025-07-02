import json
import os
import time
import npyscreen
# from cryptography.fernet import Fernet # Replaced by CryptoProvider via GhostConfig
from ghost_config import GhostConfig
from datetime import datetime, timedelta # Added for trend analysis
from ghost_reporter_pdf import GhostPDFGenerator, REPORTLAB_AVAILABLE # Import new PDF generator

# ghost_crypto is not directly imported here, accessed via config_manager.crypto_provider

# Header for mock-encrypted files
MOCK_ENCRYPTION_HEADER = b"--GHOST_MOCK_ENCRYPTED_CONTENT_BASE64--\n"

class GhostReporter:
    """
    Generates reports from parsed MVNO data.
    This includes creating a Top N leniency report, saving reports as "encrypted" JSON
    (using CryptoProvider from GhostConfig), and displaying reports in a TUI.
    """
    def __init__(self, config_manager: GhostConfig):
        """
        Initializes the GhostReporter.

        Args:
            config_manager (GhostConfig): An instance of GhostConfig for accessing
                                          configuration settings and the CryptoProvider.
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostReporter")
        self.output_dir = self.config_manager.get("output_dir", "output")

        # Use the CryptoProvider from GhostConfig directly
        if not hasattr(config_manager, 'crypto_provider') or not config_manager.crypto_provider:
            self.logger.error("CryptoProvider not found in GhostConfig. Reporting encryption will fail.")
            # Fallback or error handling could be more robust, e.g. creating a dummy provider
            self.crypto_provider = None
        else:
            self.crypto_provider = config_manager.crypto_provider
            self.logger.info(f"GhostReporter initialized with CryptoProvider in '{self.crypto_provider.effective_mode}' mode.")

        # The _load_report_key method is no longer needed as we use the config_manager's crypto_provider
        # self.report_key_file = os.path.join(self.output_dir, "reporter_secret.key") # No longer needed
        # self._load_report_key() # No longer needed

        self.reports_subdir = os.path.join(self.output_dir, "reports")
        if not os.path.exists(self.reports_subdir): # pragma: no cover
            os.makedirs(self.reports_subdir)
            self.logger.info(f"Created reports subdirectory: {self.reports_subdir}")

        # Alert log file path (directly in output_dir, not reports_subdir)
        self.alerts_log_file = os.path.join(self.output_dir, "alerts_log.json")


    def _get_previous_parsed_data_files(self, current_parsed_file: str, days_limit: int = 90) -> list[str]:
        """
        Finds previous 'parsed_mvno_data_*.json' files in the output directory,
        sorted by modification time (newest first), excluding the current one.
        Limited by days_limit to avoid loading excessively old data.
        """
        parsed_data_dir = self.config_manager.get("output_dir", "output") # Parsed data is in main output dir
        if not os.path.exists(parsed_data_dir):
            return []

        files = []
        cutoff_time = datetime.now() - timedelta(days=days_limit)

        for f_name in os.listdir(parsed_data_dir):
            if f_name.startswith("parsed_mvno_data_") and f_name.endswith(".json") and \
               os.path.join(parsed_data_dir, f_name) != current_parsed_file:
                f_path = os.path.join(parsed_data_dir, f_name)
                try:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(f_path))
                    if mod_time >= cutoff_time:
                        files.append(f_path)
                except OSError: # pragma: no cover
                    self.logger.warning(f"Could not get modification time for {f_path}")
                    continue

        # Sort files by modification time, newest first
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return files

    # def _load_report_key(self): # This method is removed
    #     """
    #     DEPRECATED: Loads an existing Fernet encryption key from `self.report_key_file` or
    #     generates a new one if the file doesn't exist. This key is used for
    #     encrypting reports if the main `GhostConfig` cipher is not used/available.
    #     This method is primarily a fallback if `GhostConfig` doesn't directly expose its cipher.
    #     """
    #     pass # Logic moved to GhostConfig and CryptoProvider

    def _load_parsed_data(self, parsed_data_filepath: str) -> dict | None:
        """
        Loads parsed MVNO data from a JSON file (typically output from GhostParser).

        Args:
            parsed_data_filepath (str): The path to the JSON file containing parsed data.

        Returns:
            dict | None: A dictionary containing the parsed MVNO data, or None if
                         loading fails (file not found, JSON decode error, etc.).
        """
        try:
            with open(parsed_data_filepath, "r") as f:
                data = json.load(f)
            self.logger.info(f"Successfully loaded parsed data from {parsed_data_filepath}")
            return data
        except FileNotFoundError:
            self.logger.error(f"Parsed data file not found: {parsed_data_filepath}")
            return None
        except json.JSONDecodeError: # pragma: no cover
            self.logger.error(f"Error decoding JSON from parsed data file: {parsed_data_filepath}")
            return None
        except Exception as e: # pragma: no cover
            self.logger.error(f"Error loading parsed data: {e}")
            return None

    def generate_top_n_leniency_report(self, parsed_data: dict, top_n: int = 10) -> list[dict]:
        """
        Generates a structured report of the top N MVNOs based on their
        average leniency score.

        Args:
            parsed_data (dict): The parsed MVNO data (output from GhostParser).
            top_n (int): The number of top MVNOs to include in the report.

        Returns:
            list[dict]: A list of dictionaries, where each dictionary represents an MVNO
                        and contains its name, score, mention counts, and top keywords.
                        Returns an empty list if input data is empty.
        """
        if not parsed_data:
            self.logger.warning("No parsed data available to generate report.")
            return []

        # Sort MVNOs by average_leniency_score in descending order
        # Handle cases where 'average_leniency_score' might be missing gracefully
        sorted_mvnos = sorted(
            parsed_data.items(),
            key=lambda item: item[1].get("average_leniency_score", float('-inf')),
            reverse=True
        )

        report_data = []
        for mvno_name, data in sorted_mvnos[:top_n]:
            report_data.append({
                "mvno_name": mvno_name,
                "average_leniency_score": data.get("average_leniency_score", "N/A"),
                "total_mentions": data.get("mentions", 0),
                "positive_mentions": data.get("positive_sentiment_mentions", 0),
                "negative_mentions": data.get("negative_sentiment_mentions", 0),
                "top_keywords": sorted(data.get("policy_keywords", {}).items(), key=lambda x: x[1], reverse=True)[:3] # Top 3 contributing keywords
            })

        return report_data

    def save_report_as_encrypted_json(self, report_data: list[dict], report_name_prefix: str = "leniency_report") -> str | None:
        """
        Saves the provided report data as an encrypted JSON file.
        The filename is timestamped and includes the given prefix.
        Uses the `self.cipher_suite` for encryption.

        Args:
            report_data (list[dict]): The report data to save (typically output from
                                      `generate_top_n_leniency_report`).
            report_name_prefix (str): A prefix for the report filename.

        Returns:
            str | None: The filepath of the saved encrypted JSON file if successful,
                        otherwise None.
        """
        if not self.cipher_suite: # pragma: no cover (should be set by __init__)
            self.logger.error("Encryption cipher not available. Cannot save encrypted report.")
            return None
        if not report_data:
            self.logger.warning("No report data to save.")
            return None

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.reports_subdir, f"{report_name_prefix}_{timestamp}.json.enc")

        try:
            json_data = json.dumps(report_data, indent=4).encode('utf-8')
            encrypted_data = self.cipher_suite.encrypt(json_data)

            with open(filename, "wb") as f:
                f.write(encrypted_data)
            self.logger.info(f"Encrypted report saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to save encrypted JSON report: {e}")
            return None

    def _generate_pdf_report(self, report_data: list[dict], filename: str) -> str | None:
        """
        (Placeholder) Generates a PDF report from the report data.
        This method is not implemented and requires a dedicated PDF generation library
        (e.g., ReportLab, FPDF).

        Args:
            report_data (list[dict]): The data to include in the PDF report.
            filename (str): The path where the PDF file should be saved.

        Returns:
            str | None: Path to the generated PDF if successful, else None.
        """
        self.logger.warning(f"PDF generation for {filename} is a placeholder and not implemented.")
        # Example with ReportLab (if installed):
        # from reportlab.lib.pagesizes import letter
        # from reportlab.platypus import SimpleDocTemplate, Paragraph
        # from reportlab.lib.styles import getSampleStyleSheet
        #
        # doc = SimpleDocTemplate(filename, pagesize=letter)
        # styles = getSampleStyleSheet()
        # story = []
        # story.append(Paragraph("Top N Leniency Report", styles['h1']))
        # for item in report_data:
        #     story.append(Paragraph(f"MVNO: {item['mvno_name']}", styles['h2']))
        #     story.append(Paragraph(f"Score: {item['average_leniency_score']}", styles['normal']))
        #     # ... add more details
        # doc.build(story)
        # self.logger.info(f"PDF report placeholder generated: {filename}")
        return None # As it's not implemented

    def save_report_as_pdf_versions(self, report_data: list[dict], report_name_prefix: str = "leniency_report") -> tuple[str | None, str | None]:
        """
        Generates and saves plaintext and (if applicable) encrypted PDF versions of the report.

        Args:
            report_data (list[dict]): The report data to save.
            report_name_prefix (str): A prefix for the report filename.

        Returns:
            tuple[str | None, str | None]: Paths to (plaintext_pdf, encrypted_pdf).
                                           Paths can be None if generation/encryption fails or is skipped.
        """
        if not REPORTLAB_AVAILABLE:
            self.logger.warning("ReportLab library not available, PDF report generation will be skipped by GhostReporter.")
            # Attempt to create a fallback text file via GhostPDFGenerator's internal fallback
            pdf_generator = GhostPDFGenerator(self.config_manager, self.logger)
            # The generate_and_encrypt_pdf_report method in GhostPDFGenerator handles the txt fallback creation
            # when REPORTLAB_AVAILABLE is false.
            # We still call it to trigger that fallback.
            # The reports_subdir is where GhostPDFGenerator expects to save.
            plain_fallback_path, _ = pdf_generator.generate_and_encrypt_pdf_report(
                report_data, report_name_prefix, self.reports_subdir
            )
            # plain_fallback_path will be path to .txt if successful, or None
            return plain_fallback_path, None


        pdf_generator = GhostPDFGenerator(self.config_manager, self.logger)

        plain_pdf_path, encrypted_pdf_path = pdf_generator.generate_and_encrypt_pdf_report(
            report_data,
            report_name_prefix,
            self.reports_subdir
        )

        if plain_pdf_path:
            self.logger.info(f"Plaintext PDF report processing handled by GhostPDFGenerator: {plain_pdf_path}")
        else:
            self.logger.warning("Plaintext PDF report was not generated by GhostPDFGenerator.")

        if encrypted_pdf_path:
            self.logger.info(f"Encrypted PDF report generated by GhostPDFGenerator: {encrypted_pdf_path}")
        # else: (GhostPDFGenerator already logs if encryption fails or is skipped)

        return plain_pdf_path, encrypted_pdf_path


    def _append_alerts_to_log(self, alerts: list[dict]):
        """Appends a list of alert dictionaries to the alerts_log.json file."""
        if not alerts:
            return

        try:
            # Ensure output_dir exists (it should, but good practice)
            if not os.path.exists(self.output_dir): # pragma: no cover
                os.makedirs(self.output_dir)

            # Read existing alerts if file exists, otherwise start fresh
            existing_alerts = []
            if os.path.exists(self.alerts_log_file):
                with open(self.alerts_log_file, "r") as f:
                    try:
                        existing_alerts = json.load(f)
                        if not isinstance(existing_alerts, list): # Ensure it's a list
                            self.logger.warning(f"Alerts log {self.alerts_log_file} was not a list. Resetting.")
                            existing_alerts = []
                    except json.JSONDecodeError: # pragma: no cover
                        self.logger.warning(f"Could not decode existing alerts log {self.alerts_log_file}. It will be overwritten.")
                        existing_alerts = []

            existing_alerts.extend(alerts) # Add new alerts

            with open(self.alerts_log_file, "w") as f:
                json.dump(existing_alerts, f, indent=4)
            self.logger.info(f"Appended {len(alerts)} alerts to {self.alerts_log_file}")

        except Exception as e: # pragma: no cover
            self.logger.error(f"Failed to append alerts to log {self.alerts_log_file}: {e}")


    def generate_policy_change_alerts(self, current_parsed_data_filepath: str) -> list[dict]:
        """
        Generates alerts for significant policy changes by comparing current parsed data
        with the most recent previous parsed data.
        """
        current_data = self._load_parsed_data(current_parsed_data_filepath)
        if not current_data:
            self.logger.error("Cannot generate alerts: current parsed data is missing.")
            return []

        previous_data_files = self._get_previous_parsed_data_files(current_parsed_data_filepath, days_limit=90)
        if not previous_data_files:
            self.logger.info("No previous parsed data found. Cannot generate change alerts (first run?).")
            # Check for NEW_MVNO alerts even if no previous data
            alerts = []
            alert_thresholds = self.config_manager.get("alert_thresholds", {})
            new_mvno_min_score = alert_thresholds.get("new_mvno_score", 3.0) # Default from prompt

            for mvno_name, data in current_data.items():
                current_score = data.get("average_leniency_score", 0)
                if current_score >= new_mvno_min_score:
                    alerts.append({
                        "timestamp": datetime.now().isoformat(),
                        "mvno_name": mvno_name,
                        "alert_type": "NEW_MVNO_HIGH_SCORE",
                        "description": f"New MVNO '{mvno_name}' detected with initial score {current_score:.2f} (>= {new_mvno_min_score}).",
                        "current_score": current_score,
                        "previous_score": None,
                        "score_change": None,
                        "current_data_file": os.path.basename(current_parsed_data_filepath),
                        "previous_data_file": None
                    })
            if alerts:
                self._append_alerts_to_log(alerts)
            return alerts


        previous_data = self._load_parsed_data(previous_data_files[0]) # Load the most recent one
        if not previous_data:
            self.logger.error(f"Cannot generate alerts: failed to load previous parsed data from {previous_data_files[0]}.")
            return []

        alerts = []
        alert_thresholds = self.config_manager.get("alert_thresholds", {})
        score_change_threshold = alert_thresholds.get("score_change", 0.2) # 20%
        new_mvno_min_score = alert_thresholds.get("new_mvno_score", 3.0)

        # Check for changes and new MVNOs
        for mvno_name, data in current_data.items():
            current_score = data.get("average_leniency_score", 0)
            prev_mvno_data = previous_data.get(mvno_name)

            if prev_mvno_data:
                prev_score = prev_mvno_data.get("average_leniency_score", 0)
                # Avoid division by zero if prev_score is 0
                if prev_score == 0 and current_score != 0:
                    relative_change = float('inf') if current_score > 0 else float('-inf') # Treat as significant
                elif prev_score == 0 and current_score == 0:
                    relative_change = 0.0
                else:
                    relative_change = (current_score - prev_score) / abs(prev_score)

                alert_type = None
                description = ""
                if relative_change > score_change_threshold:
                    alert_type = "POLICY_RELAXED"
                    description = f"Policy for '{mvno_name}' significantly relaxed. Score changed from {prev_score:.2f} to {current_score:.2f} (change: {relative_change:+.2%})."
                elif relative_change < -score_change_threshold:
                    alert_type = "POLICY_TIGHTENED"
                    description = f"Policy for '{mvno_name}' significantly tightened. Score changed from {prev_score:.2f} to {current_score:.2f} (change: {relative_change:+.2%})."

                if alert_type:
                    alerts.append({
                        "timestamp": datetime.now().isoformat(),
                        "mvno_name": mvno_name,
                        "alert_type": alert_type,
                        "description": description,
                        "current_score": current_score,
                        "previous_score": prev_score,
                        "score_change_percentage": relative_change if abs(relative_change) != float('inf') else None,
                        "current_data_file": os.path.basename(current_parsed_data_filepath),
                        "previous_data_file": os.path.basename(previous_data_files[0])
                    })
            else: # New MVNO
                if current_score >= new_mvno_min_score:
                    alert_type = "NEW_MVNO_HIGH_SCORE"
                    description = f"New MVNO '{mvno_name}' detected with initial score {current_score:.2f} (>= {new_mvno_min_score})."
                else:
                    alert_type = "NEW_MVNO_DETECTED" # Lower priority, just noting it
                    description = f"New MVNO '{mvno_name}' detected with initial score {current_score:.2f}."

                alerts.append({
                    "timestamp": datetime.now().isoformat(),
                    "mvno_name": mvno_name,
                    "alert_type": alert_type,
                    "description": description,
                    "current_score": current_score,
                    "previous_score": None,
                    "score_change_percentage": None,
                    "current_data_file": os.path.basename(current_parsed_data_filepath),
                    "previous_data_file": None
                })

        # Check for MVNOs that disappeared (optional, could be noisy if data sources vary)
        # for mvno_name in previous_data:
        #     if mvno_name not in current_data:
        #         alerts.append(...)

        if alerts:
            self._append_alerts_to_log(alerts)

        self.logger.info(f"Generated {len(alerts)} policy change alerts.")
        return alerts

    def generate_trend_analysis(self, current_parsed_data_filepath: str, mvno_name: str | None = None, windows_days: list[int] = [7, 30, 90]) -> dict:
        """
        Generates trend analysis for MVNO scores over specified day windows.
        If mvno_name is None, attempts to do for all top N MVNOs or a summary.
        For simplicity, this initial version will focus on a single MVNO if provided,
        or a few top MVNOs, and will look back at a few recent files.
        """
        trend_results = {}
        # Load current data to identify MVNOs of interest if not specified
        current_data = self._load_parsed_data(current_parsed_data_filepath)
        if not current_data:
            self.logger.error("Cannot generate trend analysis: current parsed data is missing.")
            return {}

        # Determine target MVNOs
        target_mvnos = []
        if mvno_name:
            if mvno_name in current_data:
                target_mvnos = [mvno_name]
            else:
                self.logger.warning(f"MVNO '{mvno_name}' not found in current data for trend analysis.")
                return {}
        else: # Get top 5 MVNOs from current data if no specific one is requested
            sorted_mvnos = sorted(current_data.items(), key=lambda item: item[1].get("average_leniency_score", float('-inf')), reverse=True)
            target_mvnos = [name for name, _ in sorted_mvnos[:5]]


        # Get all relevant previous files up to the max window
        max_window = max(windows_days) if windows_days else 90
        historical_files = self._get_previous_parsed_data_files(current_parsed_data_filepath, days_limit=max_window + 5) # Add buffer

        if not historical_files:
            self.logger.info("No historical data files found for trend analysis.")
            return {}

        # Structure to hold scores over time for each target MVNO
        # { "MVNO_Name": [{"date": "YYYY-MM-DD", "score": X.X}, ...], ... }
        mvno_score_history = {name: [] for name in target_mvnos}

        # Add current data point
        current_file_date_str = self._extract_date_from_filename(os.path.basename(current_parsed_data_filepath))
        if current_file_date_str:
            for name in target_mvnos:
                if name in current_data:
                    mvno_score_history[name].append({
                        "date": current_file_date_str,
                        "score": current_data[name].get("average_leniency_score", 0)
                    })

        # Load historical data and populate score history
        for file_path in historical_files: # Already sorted newest to oldest
            data = self._load_parsed_data(file_path)
            file_date_str = self._extract_date_from_filename(os.path.basename(file_path))
            if data and file_date_str:
                for name in target_mvnos:
                    if name in data:
                        mvno_score_history[name].append({
                            "date": file_date_str,
                            "score": data[name].get("average_leniency_score", 0)
                        })

        # Calculate trends for each window
        now = datetime.now()
        for name in target_mvnos:
            trend_results[name] = {}
            # Sort history by date ascending for trend calculation
            history = sorted(mvno_score_history.get(name, []), key=lambda x: x["date"])

            for window in windows_days:
                window_start_date = now - timedelta(days=window)
                relevant_scores = [dp["score"] for dp in history if datetime.fromisoformat(dp["date"].split('T')[0]) >= window_start_date.date()] # Compare date part

                if len(relevant_scores) >= 2:
                    # Simple trend: change between first and last score in window
                    trend = relevant_scores[-1] - relevant_scores[0]
                    trend_results[name][f"{window}d_trend"] = {"change": trend, "start_score": relevant_scores[0], "end_score": relevant_scores[-1], "points": len(relevant_scores)}
                elif len(relevant_scores) == 1:
                    trend_results[name][f"{window}d_trend"] = {"change": 0, "start_score": relevant_scores[0], "end_score": relevant_scores[0], "points": 1}
                else:
                    trend_results[name][f"{window}d_trend"] = {"change": None, "points": 0}

        self.logger.info(f"Generated trend analysis for {len(target_mvnos)} MVNOs.")
        # Optionally, save this trend_results to a file or log it.
        # For now, it's returned.
        return trend_results

    def _extract_date_from_filename(self, filename: str) -> str | None:
        """
        Extracts date from filenames like 'parsed_mvno_data_YYYYMMDD-HHMMSS.json'.
        Returns date as 'YYYY-MM-DDTHH:MM:SS' ISO-like string.
        """
        # Example: parsed_mvno_data_20231026-153000.json
        parts = filename.replace("parsed_mvno_data_", "").replace(".json", "")
        try:
            dt_obj = datetime.strptime(parts, "%Y%m%d-%H%M%S")
            return dt_obj.isoformat()
        except ValueError:
            self.logger.warning(f"Could not parse date from filename: {filename}")
            return None


    def save_report_as_encrypted_pdf(self, report_data: list[dict], report_name_prefix: str = "leniency_report_pdf") -> str | None:
        """
        (Placeholder) Saves the report data as an encrypted PDF file.
        This would first involve generating a PDF (using `_generate_pdf_report`),
        then encrypting the bytes of the generated PDF file.

        Args:
            report_data (list[dict]): The report data.
            report_name_prefix (str): Prefix for the output filename.

        Returns:
            str | None: Path to the encrypted PDF if successful, else None.
        """
        if not self.cipher_suite: # pragma: no cover
            self.logger.error("Encryption cipher not available. Cannot save encrypted PDF.")
            return None

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        temp_pdf_filename = os.path.join(self.reports_subdir, f"temp_{timestamp}.pdf")
        encrypted_filename = os.path.join(self.reports_subdir, f"{report_name_prefix}_{timestamp}.pdf.enc")

        pdf_generated_path = self._generate_pdf_report(report_data, temp_pdf_filename)

        if pdf_generated_path: # pragma: no cover (depends on _generate_pdf_report)
            try:
                with open(pdf_generated_path, "rb") as f:
                    pdf_bytes = f.read()
                encrypted_data = self.cipher_suite.encrypt(pdf_bytes)
                with open(encrypted_filename, "wb") as f:
                    f.write(encrypted_data)
                os.remove(pdf_generated_path) # Clean up temp unencrypted PDF
                self.logger.info(f"Encrypted PDF report saved to {encrypted_filename}")
                return encrypted_filename
            except Exception as e:
                self.logger.error(f"Failed to encrypt and save PDF report: {e}")
                if os.path.exists(pdf_generated_path):
                    os.remove(pdf_generated_path) # Clean up if encryption failed
                return None
        else:
            self.logger.warning("PDF generation failed or not implemented, so no encrypted PDF saved.")
            return None

    # --- npyscreen TUI for displaying reports ---
    def display_report_tui(self, report_data: list[dict]):
        """
        Displays the provided report data in a terminal user interface (TUI)
        using the npyscreen library.

        Args:
            report_data (list[dict]): The report data to display (typically the output
                                      of `generate_top_n_leniency_report`).
        """
        if not report_data:
            self.logger.warning("No report data to display in TUI.")
            print("No report data to display.")
            return

        app = LeniencyReportApp(report_data)
        app.run()


class LeniencyReportForm(npyscreen.FormBaseNew):
    """
    An npyscreen Form for displaying the MVNO leniency report in a grid.
    """
    def create(self):
        """Called by npyscreen to build the form's widgets."""
        self.name = "Top Lenient MVNOs Report"
        self.report_data = self.parentApp.get_report_data()

        y_offset = 2
        self.add(npyscreen.FixedText, value="MVNO Leniency Report:", editable=False, rely=y_offset, relx=5)
        y_offset += 2

        if not self.report_data: # pragma: no cover (covered by display_report_tui check)
            self.add(npyscreen.FixedText, value="No data available.", editable=False, rely=y_offset, relx=5)
            return

        col_titles = ["MVNO Name", "Avg. Score", "Mentions", "Positive", "Negative", "Top Keywords"]
        self.grid = self.add(npyscreen.GridColTitles, col_titles=col_titles, rely=y_offset, relx=2, max_height=20, col_width=20)

        grid_values = []
        for item in self.report_data:
            keywords_str = ", ".join([f"{kw}({count})" for kw, count in item.get('top_keywords', [])])
            grid_values.append([
                item.get('mvno_name', 'N/A'),
                f"{item.get('average_leniency_score', 0):.2f}",
                str(item.get('total_mentions', 0)),
                str(item.get('positive_mentions', 0)),
                str(item.get('negative_mentions', 0)),
                keywords_str
            ])
        self.grid.values = grid_values

    def afterEditing(self):
        """Called by npyscreen after the form is edited (e.g., user quits)."""
        self.parentApp.setNextForm(None)


class LeniencyReportApp(npyscreen.NPSAppManaged):
    """
    The main npyscreen application class for the leniency report TUI.
    """
    def __init__(self, report_data: list[dict], *args, **kwargs):
        """
        Initializes the npyscreen app.

        Args:
            report_data (list[dict]): The report data to be displayed.
        """
        super().__init__(*args, **kwargs)
        self._report_data = report_data

    def onStart(self):
        """Called by npyscreen when the application starts."""
        self.addForm("MAIN", LeniencyReportForm, name="MVNO Leniency Report")

    def get_report_data(self) -> list[dict]:
        """
        Allows forms within the app to access the report data.

        Returns:
            list[dict]: The report data.
        """
        return self._report_data


if __name__ == '__main__':
    # This block demonstrates example usage of the GhostReporter when the script is run directly.
    print("--- GhostReporter Example Usage ---")

    # --- Setup for example run ---
    example_output_dir = "reporter_example_output"
    if not os.path.exists(example_output_dir):
        os.makedirs(example_output_dir)
    print(f"Example outputs will be in '{example_output_dir}/'")

    example_config_file = os.path.join(example_output_dir, "reporter_test_config.json")
    example_key_file = os.path.join(example_output_dir, "reporter_test_secret.key")
    example_log_file = os.path.join(example_output_dir, "ghost_reporter_example.log")
    dummy_parsed_data_filepath = os.path.join(example_output_dir, "dummy_parsed_data_for_reporter.json")

    config_manager = GhostConfig(config_file=example_config_file, key_file=example_key_file)
    config_manager.set("output_dir", example_output_dir) # Direct reporter's knowledge of output dir
    config_manager.set("log_file", example_log_file)
    config_manager._setup_logging()

    # Create a dummy parsed_mvno_data.json file for the reporter to process
    sample_parsed_data = {
        "US Mobile Example": {
            "sources": [], "total_leniency_score": 15, "mentions": 3,
            "positive_sentiment_mentions": 2, "negative_sentiment_mentions": 0,
            "average_leniency_score": 5.0,
            "policy_keywords": {"no id required": 2, "anonymous activation": 1}
        },
        "Visible Example": {
            "sources": [], "total_leniency_score": -8, "mentions": 2,
            "positive_sentiment_mentions": 0, "negative_sentiment_mentions": 1,
            "average_leniency_score": -4.0,
            "policy_keywords": {"id verification mandatory": 1, "ssn required": 1}
        },
        "Mint Mobile Example": {
            "sources": [], "total_leniency_score": 6, "mentions": 4,
            "positive_sentiment_mentions": 3, "negative_sentiment_mentions": 1,
            "average_leniency_score": 1.5,
            "policy_keywords": {"easy setup": 2, "prepaid no contract": 1}
        },
         "Google Fi Example": { # Corrected name for consistency
            "sources": [], "total_leniency_score": -2, "mentions": 1,
            "positive_sentiment_mentions": 0, "negative_sentiment_mentions": 1,
            "average_leniency_score": -2.0,
            "policy_keywords": {"must provide address": 1}
        }
    }
    # Ensure the main output directory for GhostConfig (where reports_subdir will be created) exists
    # This is usually handled by GhostConfig itself, but good to be explicit for the example.
    gc_output_dir = config_manager.get("output_dir") # This is 'reporter_example_output'
    if not os.path.exists(gc_output_dir): # pragma: no cover
        os.makedirs(gc_output_dir)

    with open(dummy_parsed_data_filepath, "w") as f:
        json.dump(sample_parsed_data, f, indent=4)
    print(f"Dummy parsed data for reporter created at: {dummy_parsed_data_filepath}")

    # --- Run the reporter ---
    reporter = GhostReporter(config_manager)

    loaded_data = reporter._load_parsed_data(dummy_parsed_data_filepath)

    if loaded_data:
        top_n_report = reporter.generate_top_n_leniency_report(loaded_data, top_n=5)
        print("\n--- Generated Top N Leniency Report Data (Example) ---")
        for item in top_n_report:
            print(f"  {item.get('mvno_name')}: Score {item.get('average_leniency_score', 0):.2f}")

        encrypted_json_path = reporter.save_report_as_encrypted_json(top_n_report, "example_top_mvnos")
        if encrypted_json_path:
            print(f"\nEncrypted JSON report saved to: {encrypted_json_path}")
            # Example: How to decrypt (requires the key and cipher_suite from reporter)
            # try:
            #     with open(encrypted_json_path, "rb") as f_enc:
            #         encrypted_content = f_enc.read()
            #     decrypted_bytes = reporter.cipher_suite.decrypt(encrypted_content)
            #     decrypted_json = json.loads(decrypted_bytes.decode())
            #     print(f"Successfully decrypted report. First item: {decrypted_json[0]['mvno_name']}")
            # except Exception as decrypt_e:
            #     print(f"Could not verify decryption for example: {decrypt_e}")


        encrypted_pdf_path = reporter.save_report_as_encrypted_pdf(top_n_report, "example_top_mvnos_pdf")
        if encrypted_pdf_path: # pragma: no cover
             print(f"Encrypted PDF report placeholder saved to: {encrypted_pdf_path}")


        print("\n--- Launching TUI to display report (Press Q to quit TUI) ---")
        try:
            if top_n_report:
                 reporter.display_report_tui(top_n_report)
            else: # pragma: no cover
                print("No report data generated, TUI will not be shown.")
        except Exception as e: # pragma: no cover
            reporter.logger.error(f"Could not run npyscreen TUI for example: {e}")
            print(f"Could not run npyscreen TUI for example: {e}. This might be due to the execution environment.")

    else: # pragma: no cover
        print("\nFailed to load parsed data for reporter example.")

    print(f"\nAll GhostReporter example outputs are in '{example_output_dir}/'")
    print(f"Specifically, reports are in: '{reporter.reports_subdir}/'")
