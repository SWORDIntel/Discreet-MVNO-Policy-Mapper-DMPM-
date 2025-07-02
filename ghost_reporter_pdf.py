# ghost_reporter_pdf.py

import os
from datetime import datetime

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from ghost_config import GhostConfig # For accessing crypto_provider if passed

class GhostPDFGenerator:
    def __init__(self, config_manager: GhostConfig, logger):
        self.config_manager = config_manager
        self.logger = logger
        self.crypto_provider = config_manager.crypto_provider if hasattr(config_manager, 'crypto_provider') else None

        if not REPORTLAB_AVAILABLE:
            self.logger.warning("ReportLab library not found. PDF generation will be skipped.")

        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else {}

    def _add_header_footer(self, canvas, doc):
        """Adds headers and footers to each page."""
        if not REPORTLAB_AVAILABLE:
            return

        canvas.saveState()
        # Header
        header_text = "GHOST Protocol - MVNO Leniency Report"
        canvas.setFont('Helvetica', 9)
        canvas.drawString(inch, letter[1] - 0.5 * inch, header_text)

        # Footer
        footer_text = f"Page {doc.page} - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(letter[0] - inch, 0.5 * inch, footer_text)
        canvas.restoreState()

    def generate_leniency_report_pdf(self, report_data: list[dict], output_filepath_plain: str) -> bool:
        """
        Generates a PDF leniency report.

        Args:
            report_data (list[dict]): Data from GhostReporter.generate_top_n_leniency_report.
            output_filepath_plain (str): Path to save the plaintext PDF report.

        Returns:
            bool: True if PDF generation was successful (or skipped due to missing library but no error),
                  False if an error occurred during generation.
        """
        if not REPORTLAB_AVAILABLE:
            self.logger.info("Skipping PDF generation as ReportLab is not available.")
            # Optionally, create a simple text file as fallback
            try:
                with open(output_filepath_plain.replace(".pdf", ".txt"), "w") as f:
                    f.write("PDF Generation Skipped - ReportLab Missing\n\n")
                    for item in report_data:
                        f.write(f"MVNO: {item.get('mvno_name', 'N/A')}, Score: {item.get('average_leniency_score', 'N/A')}\n")
                self.logger.info(f"Fallback text report saved to {output_filepath_plain.replace('.pdf', '.txt')}")
            except Exception as e_txt:
                self.logger.error(f"Failed to write fallback text report: {e_txt}")
            return True # Still true because we handled the "generation" part

        doc = SimpleDocTemplate(output_filepath_plain, pagesize=letter)
        story = []

        # Title
        story.append(Paragraph("MVNO Leniency Analysis Report", self.styles['h1']))
        story.append(Spacer(1, 0.2 * inch))

        # Executive Summary (Placeholder)
        story.append(Paragraph("Executive Summary", self.styles['h2']))
        summary_text = """
        This report provides an analysis of Mobile Virtual Network Operators (MVNOs) based on their
        perceived leniency in customer identification and payment requirements. The scores are derived
        from public web data and reflect a snapshot in time. Lower scores indicate stricter policies,
        while higher scores suggest more lenient or privacy-respecting practices.
        """
        story.append(Paragraph(summary_text, self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Top MVNOs Table
        story.append(Paragraph("Top MVNOs by Leniency Score", self.styles['h2']))
        if report_data:
            table_data = [["Rank", "MVNO Name", "Avg. Score", "Mentions"]]
            for i, item in enumerate(report_data):
                table_data.append([
                    str(i + 1),
                    item.get('mvno_name', 'N/A'),
                    f"{item.get('average_leniency_score', 0.0):.2f}",
                    str(item.get('total_mentions', 0))
                ])

            mvno_table = Table(table_data, colWidths=[0.5*inch, 3*inch, 1.5*inch, 1*inch])
            mvno_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(mvno_table)
        else:
            story.append(Paragraph("No MVNO data available for the report.", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Trend Charts (Placeholder)
        story.append(Paragraph("Trend Analysis (Placeholder)", self.styles['h2']))
        story.append(Paragraph("Trend charts would be displayed here, showing score changes over time for key MVNOs.", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.styles['Normal']))

        try:
            doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
            self.logger.info(f"Plaintext PDF report generated successfully at {output_filepath_plain}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to generate PDF report: {e}")
            return False

    def generate_and_encrypt_pdf_report(self, report_data: list[dict], base_filename_prefix: str, reports_subdir: str) -> tuple[str | None, str | None]:
        """
        Generates a PDF report and an encrypted version if crypto is available.

        Args:
            report_data: Data for the report.
            base_filename_prefix: Base for naming output files (e.g., "leniency_report").
            reports_subdir: The subdirectory to save reports in.

        Returns:
            A tuple (path_to_plain_pdf, path_to_encrypted_pdf). Paths can be None if generation/encryption fails.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        plain_pdf_filename = f"{base_filename_prefix}_{timestamp}.pdf"
        encrypted_pdf_filename = f"{base_filename_prefix}_{timestamp}.pdf.enc"

        plain_pdf_filepath = os.path.join(reports_subdir, plain_pdf_filename)
        encrypted_pdf_filepath = os.path.join(reports_subdir, encrypted_pdf_filename)

        # Generate plaintext PDF
        success_plain = self.generate_leniency_report_pdf(report_data, plain_pdf_filepath)

        path_to_plain_pdf = plain_pdf_filepath if success_plain and REPORTLAB_AVAILABLE else None
        path_to_encrypted_pdf = None

        if success_plain and REPORTLAB_AVAILABLE and self.crypto_provider and self.crypto_provider.is_encryption_active():
            try:
                with open(plain_pdf_filepath, "rb") as f_plain:
                    pdf_bytes = f_plain.read()

                encrypted_bytes = self.crypto_provider.encrypt(pdf_bytes)

                with open(encrypted_pdf_filepath, "wb") as f_enc:
                    f_enc.write(encrypted_bytes)
                self.logger.info(f"Encrypted PDF report saved to {encrypted_pdf_filepath} using {self.crypto_provider.effective_mode} mode.")
                path_to_encrypted_pdf = encrypted_pdf_filepath
            except Exception as e:
                self.logger.error(f"Failed to encrypt PDF report {plain_pdf_filepath}: {e}")
                # Keep plain_pdf_filepath as it was generated, but encrypted one is None
        elif success_plain and REPORTLAB_AVAILABLE and (not self.crypto_provider or not self.crypto_provider.is_encryption_active()):
            self.logger.info("Encryption is not active or crypto_provider is unavailable. Skipping PDF encryption.")

        # If ReportLab is not available, path_to_plain_pdf will be None (or path to .txt fallback if that's how we define success)
        # For simplicity, if ReportLab is missing, we consider the "PDF" generation step for the plain file as "done" via fallback.
        # The actual .pdf file won't exist, but a .txt might.
        if not REPORTLAB_AVAILABLE and success_plain: # Fallback text file was created
             path_to_plain_pdf = plain_pdf_filepath.replace(".pdf", ".txt")


        return path_to_plain_pdf, path_to_encrypted_pdf

if __name__ == '__main__':
    # Example Usage (requires ReportLab installed)
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")

    # Create a mock GhostConfig, assuming crypto might not be fully set up for this isolated example
    # In a real run, GhostConfig would be properly initialized by main.py
    mock_conf_dir = "pdf_generator_example_output"
    if not os.path.exists(mock_conf_dir):
        os.makedirs(mock_conf_dir)

    mock_config_file = os.path.join(mock_conf_dir, "dummy_config.json")
    mock_key_file = os.path.join(mock_conf_dir, "dummy_key.key")

    # Create a minimal GhostConfig for the PDF generator
    # For real encryption testing, ensure ghost_crypto.py and a valid key are available
    # Here, we might not have a fully functional crypto_provider if cryptography lib is missing
    # or key file is not pre-existing.
    try:
        # This might create a new key if dummy_key.key doesn't exist.
        # For the PDF example, we primarily care about ReportLab's functionality.
        config = GhostConfig(config_file=mock_config_file, key_file=mock_key_file)
        config.set("output_dir", mock_conf_dir) # Set output_dir for the config instance
        config.set("log_file", os.path.join(mock_conf_dir, "pdf_gen_example.log"))
        config._setup_logging() # Re-init with new log file path
        logger = config.get_logger("GhostPDFGeneratorExample")
    except Exception as e:
        logger = MockLogger()
        logger.error(f"Failed to initialize GhostConfig for example: {e}. Using mock logger.")
        # Create a dummy config object if GhostConfig init fails, so PDF generator can be instantiated
        class DummyConfig:
            def __init__(self):
                self.crypto_provider = None # No encryption
                self.config = {"output_dir": mock_conf_dir}
            def get(self, key, default=None): return self.config.get(key, default)
        config = DummyConfig()


    pdf_gen = GhostPDFGenerator(config_manager=config, logger=logger)

    sample_report_data = [
        {"mvno_name": "US Mobile Example", "average_leniency_score": 5.0, "total_mentions": 15},
        {"mvno_name": "Visible Example", "average_leniency_score": -2.5, "total_mentions": 10},
        {"mvno_name": "Mint Mobile Example", "average_leniency_score": 3.0, "total_mentions": 20},
    ]

    reports_output_subdir = os.path.join(mock_conf_dir, "reports") # Mimic GhostReporter's subdir
    if not os.path.exists(reports_output_subdir):
        os.makedirs(reports_output_subdir)

    logger.info(f"Attempting to generate PDF report in {reports_output_subdir}...")
    plain_path, enc_path = pdf_gen.generate_and_encrypt_pdf_report(sample_report_data, "example_leniency_report", reports_output_subdir)

    if plain_path:
        logger.info(f"Plaintext report generated/handled: {plain_path}")
    else:
        logger.warning("Plaintext PDF (or fallback) was not generated.")

    if enc_path:
        logger.info(f"Encrypted PDF report generated: {enc_path}")
    else:
        logger.warning("Encrypted PDF was not generated (may be due to ReportLab missing, crypto issues, or other errors).")

    logger.info(f"Example PDF generator output (if any) is in '{mock_conf_dir}'.")
