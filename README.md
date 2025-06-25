Software Development Query: GHOST Protocol Module - Discreet MVNO Policy Mapper (DMPM) Objective: Develop a modular, extensible "GHOST Protocol" component, the Discreet MVNO Policy Mapper (DMPM), to autonomously and continuously map the US Mobile Virtual Network Operator (MVNO) landscape, specifically identifying and ranking MVNOs based on their perceived leniency regarding prepaid SIM card identity verification and ease of anonymous acquisition. This system must operate with minimal digital footprint and optimize for data freshness and relevance.

Architectural Overview (GHOST Protocol Principles Applied):

The DMPM will adhere to "GHOST Protocol" by employing principles of decentralized data acquisition, temporal obfuscation, data anonymization, and adaptive query generation. It will be designed as a series of Python modules, each with specific roles, outputting structured data.

Module Breakdown:

ghost_crawler.py (Data Acquisition Module):

Purpose: This core module will orchestrate the Google Search queries to gather raw data from the open web concerning US MVNOs, their policies, and public discussions. It will mimic varied user behaviors to avoid detection. Key Functionality: Dynamic Query Generation: Based on an initial seed list of MVNOs and a dictionary of "anonymity keywords" (e.g., "no ID prepaid," "cash sim," "burner sim"), it will construct intelligent Google Search queries. Temporal Offset: Introduce calculated, pseudorandom delays (±15% variance) between search queries and result processing to avoid predictable patterns. Result Filtering: Implement logic to filter Google Search results for relevance, prioritizing official MVNO sites, reputable news articles, and high-signal forum discussions (e.g., Reddit, XDA Developers, dedicated telecom forums). Data Extraction (HTML Parsing): Post-search, if URLs lead to public web pages, it will extract relevant text snippets containing keywords related to activation processes, payment methods, and identity requirements. (Note: This would require a web-scraping sub-module, which is beyond direct Google Search capability but a necessary component for the overall software system). Input: Seed MVNO list, anonymity keywords, Google Search API access. Output: Raw, categorized search results (snippets, URLs) and extracted text data. Integration Point: Directly leverages the Google Search tool API for all external data retrieval. ghost_parser.py (Information Extraction & Scoring Module):

Purpose: Process the raw data from ghost_crawler.py to extract actionable intelligence and assign a "leniency score" to each MVNO. Key Functionality: Keyword & Phrase Recognition: Identify patterns and specific phrases indicating lenient (e.g., "no SSN required," "anonymous activation," "purchase with cash") or stringent (e.g., "ID verification," "credit check") policies. Sentiment Analysis (Basic): Analyze forum discussions for sentiment regarding ease of activation or perceived privacy. Leniency Scoring Algorithm: Develop a weighted algorithm to assign a numerical score to each MVNO based on identified keywords, anecdotal evidence, and official policy statements. Higher scores indicate greater leniency. Data Structuring: Convert unstructured text into a normalized, structured format (e.g., JSON or CSV). Input: Raw data from ghost_crawler.py. Output: Structured MVNO data with assigned leniency scores. ghost_reporter.py (Reporting & Alerting Module):

Purpose: Generate concise, actionable reports and trigger alerts for significant policy shifts or new MVNO discoveries. Key Functionality: Top N Leniency Report: Present the top-ranked MVNOs based on their leniency score. Policy Change Alerts: Detect and highlight significant changes in activation requirements for tracked MVNOs. Trend Analysis: Provide a high-level overview of the evolving regulatory landscape. Secure Output: Outputs reports in encrypted formats (e.g., AES-256-GCM encrypted JSON/PDF), viewable via a npyscreen interface. Input: Processed data from ghost_parser.py. Output: Encrypted intelligence reports and real-time alerts. ghost_config.py (Configuration & Orchestration Module):

Purpose: Manage the operational parameters of the entire DMPM system. Key Functionality: Scheduled Task Management: Configure cron jobs (or similar) to automate the execution of ghost_crawler.py at defined intervals (e.g., bi-weekly, triggered by specific events). API Key Management: Securely manage API keys for Google Search and any potential future integrations. Logging: Implement robust, deniable logging of operations. Error Handling & Resiliency: Design for graceful failure and resumable tasks. Technology Stack:

Primary Language: Python (3.x) Libraries: requests (for web content fetching beyond snippets), BeautifulSoup or lxml (for HTML parsing), cryptography (for AES-256-GCM), npyscreen (for terminal UI for reports), sqlite3 (for local, encrypted data persistence). Execution Environment: Debian-based Linux environment, ideally within a containerized (e.g., Docker) and isolated setup for operational security. This "GHOST Protocol" DMPM would serve as a critical intelligence component, providing a continuous, discreet mapping of the US MVNO landscape tailored to our operational requirements for deniable SIM card acquisition.

## Project Structure

- `ghost_config.py`: Manages configuration, encryption keys, and logging.
- `ghost_crawler.py`: Handles data acquisition from Google Search (currently mocked). Generates queries, applies temporal offsets, and saves raw results.
- `ghost_parser.py`: Processes raw data from the crawler. Extracts MVNO info, calculates leniency scores, and performs basic sentiment analysis. Saves parsed data.
- `ghost_reporter.py`: Generates reports from parsed data. Creates encrypted JSON reports and provides a TUI for viewing. (PDF generation is a placeholder).
- `main.py`: Orchestrates the full cycle (config -> crawl -> parse -> report) for integration testing or running the application.
- `requirements.txt`: Lists Python dependencies.
- `mvnos.txt`: Seed list of MVNOs for the crawler.
- `keywords.txt`: Seed list of keywords for query generation by the crawler.
- `output/`: Default directory for logs, raw data, parsed data, and reports. (Not in Git, as specified in `.gitignore`).
- `test_output/`: Directory created by `main.py` for its outputs. (Not in Git).
- `*_example_output/`: Directories created by `if __name__ == '__main__'` blocks in individual modules, containing example outputs for that specific module. (Not in Git).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory_name>
    ```
    (Replace `<repository_url>` and `<repository_directory_name>` accordingly)

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Prepare input files:**
    *   Review and update `mvnos.txt` with the target MVNOs. One MVNO per line.
    *   Review and update `keywords.txt` with relevant search keywords. One keyword/phrase per line.

5.  **API Key Configuration (Optional - for real Google Search):**
    *   The system currently uses a **mock Google Search** by default.
    *   To use the real Google Search API (which is more effective):
        *   You will need a Google API Key and a Google Programmable Search Engine ID (cx) configured to search the entire web.
        *   The first time you run any module that instantiates `GhostConfig` (e.g., `python ghost_config.py` or `python main.py`), it will create `config.json` (encrypted) and `secret.key` in the root directory (or in the respective example/test output directory).
        *   To add your API key and CX ID:
            You can programmatically set them once. Create a temporary Python script in the project root (e.g., `set_api_key.py`):
            ```python
            from ghost_config import GhostConfig
            # This uses default "config.json" and "secret.key" in the project root
            cfg = GhostConfig()
            cfg.set_api_key("google_search", "YOUR_ACTUAL_GOOGLE_API_KEY")
            cfg.set("google_programmable_search_engine_id", "YOUR_CX_ID_HERE")
            print("API key and CX ID have been set in the encrypted 'config.json'.")
            ```
            Replace `"YOUR_ACTUAL_GOOGLE_API_KEY"` and `"YOUR_CX_ID_HERE"` with your actual credentials. Run this script *once* (`python set_api_key.py`). This `config.json` will then be used if no other specific config is loaded by the scripts.
        *   **Important**: If you run `main.py`, it creates its own configuration in `test_output/`. To use a central `config.json` with `main.py`, you would need to modify `main.py` to point to the root `config.json` or manually copy the root `config.json` and `secret.key` into `test_output/` before running `main.py` (and rename them to `main_app_config.json` and `main_app_secret.key`).
        *   You would also need to modify `ghost_crawler.py` to uncomment and use the real Google Search API client code instead of the mock service.

## Usage

The primary way to run the full data processing cycle is using `main.py`. Each module can also be run individually to test its specific functionality, which will generate outputs in its own `*_example_output/` directory.

1.  **Run the full cycle (Config -> Crawl -> Parse -> Report using Mocks):**
    ```bash
    python main.py
    ```
    *   This script is configured for testing and uses mock search.
    *   It creates a `test_output/` directory for all its files.
    *   Inside `test_output/`:
        *   `main_app_config.json` and `main_app_secret.key`: Configuration for this specific run.
        *   `ghost_main_test.log`: Log file for the run.
        *   A `raw_search_results_YYYYMMDD-HHMMSS.json` file: Output from the crawler.
        *   A `parsed_mvno_data_YYYYMMDD-HHMMSS.json` file: Output from the parser.
        *   `reports/`: Subdirectory containing encrypted reports from the reporter (e.g., `integration_test_report_YYYYMMDD-HHMMSS.json.enc`).

2.  **Run individual modules (for testing or specific tasks, uses example files & outputs):**
    *   **GhostConfig example:**
        ```bash
        python ghost_config.py
        ```
        (Creates `example_output/` with `example_app_config.json`, etc. and demonstrates config operations.)
    *   **GhostCrawler example:**
        ```bash
        python ghost_crawler.py
        ```
        (Creates `crawler_example_output/` with raw results from mock search, logs, etc., using example MVNO/keyword files it also creates in that directory.)
    *   **GhostParser example:**
        (This example run creates its own dummy raw results file based on crawler's mock data.)
        ```bash
        python ghost_parser.py
        ```
        (Creates `parser_example_output/` with parsed data from its self-generated dummy raw results, logs, etc.)
    *   **GhostReporter example:**
        (This example run creates its own dummy parsed data file.)
        ```bash
        python ghost_reporter.py
        ```
        (Creates `reporter_example_output/` and `reporter_example_output/reports/`. Will also attempt to launch the TUI to display the report from its self-generated dummy parsed data.)

### Viewing Encrypted Reports

Encrypted reports (`*.json.enc`) are not directly human-readable.
-   The `GhostReporter`'s TUI (launched when running `python ghost_reporter.py` or if enabled in `main.py`) is the primary way to view the Top N Leniency report.
-   To decrypt a report file manually (e.g., for other uses), you would need to use the `Fernet` cipher from `GhostConfig` (using the correct `secret.key` that was used during report generation for that specific report file) and decrypt the file content.

Example snippet to decrypt a file (you'll need to adapt paths):
```python
from cryptography.fernet import Fernet
import json

# Path to the key used for encrypting the specific report
# (e.g., "reporter_example_output/reporter_test_secret.key" if from ghost_reporter.py example)
key_filepath = "path/to/your/secret.key"
report_filepath = "path/to/your/report.json.enc"

try:
    with open(key_filepath, "rb") as f:
        key = f.read()
    cipher = Fernet(key)
    with open(report_filepath, "rb") as f:
        encrypted_data = f.read()

    decrypted_data_bytes = cipher.decrypt(encrypted_data)
    decrypted_json_str = decrypted_data_bytes.decode()
    report_content = json.loads(decrypted_json_str)

    print("Decrypted Report Content:")
    print(json.dumps(report_content, indent=4))
except Exception as e:
    print(f"An error occurred during decryption: {e}")
```

## Output Structure (General for `main.py` in `test_output/`)

-   **Logs:** Detailed logs are generated (e.g., `ghost_main_test.log`).
-   **Raw Search Results (`raw_search_results_*.json`):** JSON file from `GhostCrawler` containing a list of search result items. Each item is a dictionary with:
    -   `title` (str): Title of the search result.
    -   `link` (str): URL of the search result.
    -   `snippet` (str): Snippet of text from the search result.
    -   `query_source` (str): The original query that produced this result.
-   **Parsed MVNO Data (`parsed_mvno_data_*.json`):** JSON file from `GhostParser`. A dictionary where keys are MVNO names. Each MVNO entry is a dictionary with fields like:
    -   `sources` (list): List of source snippets (dictionaries with url, title, snippet, score, sentiment) that contributed to this MVNO's data.
    -   `total_leniency_score` (int): Sum of leniency scores from all its mentions.
    -   `mentions` (int): Number of times the MVNO was mentioned/processed.
    -   `positive_sentiment_mentions` (int): Count of associated snippets with positive sentiment.
    -   `negative_sentiment_mentions` (int): Count of associated snippets with negative sentiment.
    -   `average_leniency_score` (float): The key metric for ranking (total_leniency_score / mentions).
    -   `policy_keywords` (dict): Dictionary of specific policy keywords found for this MVNO and their counts.
-   **Encrypted Reports (`reports/*.json.enc`):** Encrypted JSON files from `GhostReporter`, typically containing the Top N leniency report data (list of MVNOs with their scores and key details).

## Future Enhancements (Derived from original README objectives)
-   **Activate Real Google Search:** Fully integrate and enable the real Google Search API calls in `ghost_crawler.py` (currently uses a mock).
-   **HTML Content Parsing:** Implement functionality in `ghost_crawler.py` or `ghost_parser.py` to fetch and parse full HTML content from promising URLs found in search results for deeper data extraction (using libraries like `requests` and `BeautifulSoup`/`lxml`).
-   **Advanced Sentiment Analysis:** Enhance sentiment analysis in `ghost_parser.py` using more sophisticated NLP techniques or libraries for better accuracy.
-   **PDF Report Generation:** Implement PDF report generation in `ghost_reporter.py` (currently a placeholder) using a library like `ReportLab` or `FPDF`.
-   **Policy Change Alerts & Trend Analysis:** Develop features in `ghost_reporter.py` to detect significant changes in MVNO policies over time and provide trend analysis (would require data persistence and comparison across runs).
-   **Scheduled Task Management:** Implement robust cron job/task scheduling capabilities, potentially managed via `ghost_config.py` or a dedicated scheduling module, to automate periodic crawling and analysis.
-   **Data Persistence:** For trend analysis and historical data, implement a database solution (e.g., SQLite as mentioned in original tech stack) for storing processed data from `ghost_parser.py` across multiple runs.
-   **Refined MVNO Extraction:** Improve the heuristic in `ghost_parser.py` for `_extract_mvno_name_from_query` to more accurately map search results to MVNOs, possibly by using the definitive list of MVNOs from `mvnos.txt`.
