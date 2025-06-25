import json
import os
import time
import npyscreen
from cryptography.fernet import Fernet # For encryption
from ghost_config import GhostConfig

class GhostReporter:
    """
    Generates reports from parsed MVNO data.
    This includes creating a Top N leniency report, saving reports as encrypted JSON,
    (placeholder for PDF reports), and displaying reports in a terminal UI (TUI)
    using npyscreen.
    """
    def __init__(self, config_manager: GhostConfig):
        """
        Initializes the GhostReporter.

        Args:
            config_manager (GhostConfig): An instance of GhostConfig for accessing
                                          configuration settings and the encryption cipher.
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostReporter")
        self.output_dir = self.config_manager.get("output_dir", "output")

        # For encryption of reports - use a dedicated key or the main app key
        # For simplicity, let's try to use the main app's key logic from GhostConfig
        # If GhostConfig's cipher_suite is directly accessible and suitable:
        if hasattr(config_manager, 'cipher_suite') and config_manager.cipher_suite:
            self.cipher_suite = config_manager.cipher_suite
        else:
            # Fallback: generate/load a dedicated report key if GhostConfig doesn't expose its cipher
            # This part would mirror GhostConfig's key handling if needed separately
            self.report_key_file = os.path.join(self.output_dir, "reporter_secret.key")
            self._load_report_key()

        self.reports_subdir = os.path.join(self.output_dir, "reports")
        if not os.path.exists(self.reports_subdir):
            os.makedirs(self.reports_subdir)
            self.logger.info(f"Created reports subdirectory: {self.reports_subdir}")

    def _load_report_key(self):
        """
        Loads an existing Fernet encryption key from `self.report_key_file` or
        generates a new one if the file doesn't exist. This key is used for
        encrypting reports if the main `GhostConfig` cipher is not used/available.
        This method is primarily a fallback if `GhostConfig` doesn't directly expose its cipher.
        """
        try:
            if os.path.exists(self.report_key_file):
                with open(self.report_key_file, "rb") as f:
                    key = f.read()
            else: # pragma: no cover (usually covered by GhostConfig providing a cipher)
                key = Fernet.generate_key()
                with open(self.report_key_file, "wb") as f:
                    f.write(key)
                self.logger.info(f"Generated new report encryption key: {self.report_key_file}")
            self.cipher_suite = Fernet(key)
        except Exception as e: # pragma: no cover
            self.logger.error(f"Error managing report encryption key: {e}")
            self.cipher_suite = None # Encryption will fail

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
