import json
import os
import re
from collections import defaultdict
from ghost_config import GhostConfig # Assuming ghost_config.py is in the same directory or PYTHONPATH

# Basic sentiment keyword lists (very simplistic)
POSITIVE_WORDS = {"easy", "simple", "quick", "no problem", "anonymous", "privacy", "recommended", "good", "great", "love", "best", "straightforward", "hassle-free", "no id", "no ssn", "cash"}
NEGATIVE_WORDS = {"difficult", "hard", "problem", "issues", "requires id", "ssn needed", "credit check", "avoid", "bad", "terrible", "warning", "strict", "verification"}

# More specific policy keywords
LENIENT_POLICY_KEYWORDS = {
    "no id required": 5, "no ssn": 5, "anonymous activation": 4, "cash payment accepted": 3,
    "minimal personal information": 3, "privacy focused": 2, "prepaid no contract": 1,
    "no credit check": 2, "easy setup": 1, "pay with crypto": 5, "burner phone friendly": 3
}
STRINGENT_POLICY_KEYWORDS = {
    "id verification mandatory": -5, "ssn required": -5, "credit check needed": -4,
    "account registration extensive": -3, "must provide address": -2, "strict kyc": -4,
    "photo id": -3, "not anonymous": -2
}

class GhostParser:
    """
    Processes raw data collected by GhostCrawler to extract actionable intelligence
    regarding MVNO leniency. It assigns a "leniency score" to each MVNO based on
    keyword analysis and performs basic sentiment analysis on text snippets.
    """
    def __init__(self, config_manager: GhostConfig):
        """
        Initializes the GhostParser.

        Args:
            config_manager (GhostConfig): An instance of GhostConfig for accessing
                                          configuration settings (e.g., output directory).
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostParser")
        self.output_dir = self.config_manager.get("output_dir", "output")

    def _load_raw_data(self, filepath: str) -> list[dict] | None:
        """
        Loads raw search result data from a JSON file.

        Args:
            filepath (str): The path to the JSON file containing raw search results
                            (typically output from GhostCrawler).

        Returns:
            list[dict] | None: A list of dictionaries, where each dictionary is a
                               raw search item. Returns None if the file is not found,
                               cannot be decoded, or another error occurs.
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.logger.info(f"Successfully loaded {len(data)} raw search items from {filepath}")
            return data
        except FileNotFoundError:
            self.logger.error(f"Raw data file not found: {filepath}")
            return None
        except json.JSONDecodeError: # pragma: no cover
            self.logger.error(f"Error decoding JSON from file: {filepath}")
            return None
        except Exception as e: # pragma: no cover
            self.logger.error(f"Error loading raw data from {filepath}: {e}")
            return None

    def _extract_mvno_name_from_query(self, query_source: str) -> str:
        """
        Extracts a potential MVNO name from the original search query string.
        This method uses heuristics (e.g., taking the first one or two words) and
        may require refinement for higher accuracy. It includes specific hacks for
        known two-word names like "Google Fi" and "US Mobile".

        Args:
            query_source (str): The original search query string (e.g., "US Mobile no ID prepaid").

        Returns:
            str: The extracted MVNO name, or "Unknown MVNO" if extraction fails.
        """
        # Specific two-word name checks first for better accuracy
        if "google fi" in query_source.lower():
            return "Google Fi"
        if "us mobile" in query_source.lower():
            return "US Mobile"

        # General heuristic: if the first part is short (e.g. "US"), take two parts. Otherwise one.
        parts = query_source.split()
        if not parts:
            return "Unknown MVNO" # pragma: no cover
        if len(parts) > 1 and len(parts[0]) <= 3 and parts[0].upper() == parts[0]: # e.g. US Mobile
            return f"{parts[0]} {parts[1]}"
        return parts[0]


    def _analyze_text_sentiment(self, text: str) -> str:
        """
        Performs a very basic keyword-based sentiment analysis on the provided text.
        Compares words in the text against predefined lists of positive and negative words.

        Args:
            text (str): The text content to analyze.

        Returns:
            str: "positive", "negative", or "neutral" based on the simplistic analysis.
        """
        score = 0
        text_lower = text.lower()
        for word in POSITIVE_WORDS:
            if word in text_lower:
                score += 1
        for word in NEGATIVE_WORDS:
            if word in text_lower:
                score -= 1

        if score > 0: return "positive"
        if score < 0: return "negative"
        return "neutral"

    def _calculate_leniency_score(self, text_content: str) -> int:
        """
        Calculates a leniency score for a given text content based on predefined
        lenient and stringent policy keywords. Each keyword has an associated point value.

        Args:
            text_content (str): The text (e.g., search result snippet) to analyze.

        Returns:
            int: The calculated leniency score. Positive scores indicate leniency,
                 negative scores indicate stringency.
        """
        score = 0
        text_lower = text_content.lower()

        for keyword, points in LENIENT_POLICY_KEYWORDS.items():
            if keyword in text_lower:
                score += points

        for keyword, points in STRINGENT_POLICY_KEYWORDS.items():
            if keyword in text_lower: # points are already negative
                score += points

        return score

    def parse_results(self, raw_data_filepath: str) -> str | None:
        """
        Loads raw search results from the given filepath, processes each item to
        extract MVNO information, calculate leniency scores, and perform sentiment analysis.
        The aggregated and processed data is then saved to a new timestamped JSON file
        in the output directory.

        Args:
            raw_data_filepath (str): Path to the JSON file containing raw search results
                                     from GhostCrawler.

        Returns:
            str | None: The filepath of the saved parsed data JSON file if successful,
                        otherwise None.
        """
        raw_results = self._load_raw_data(raw_data_filepath)
        if not raw_results:
            self.logger.error("No raw data to parse.")
            return None

        parsed_data = defaultdict(lambda: {"sources": [], "total_leniency_score": 0, "mentions": 0, "positive_sentiment_mentions": 0, "negative_sentiment_mentions": 0, "policy_keywords": defaultdict(int)})

        for item in raw_results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            query_source = item.get("query_source", "") # Added by crawler

            # Attempt to identify the MVNO from the query source
            # This is a simplification. A better way might involve passing the original MVNO list used by the crawler.
            mvno_name_match = re.match(r"([^ ]+(\s[^ ]+)?)", query_source) # Try to get first 1 or 2 words as MVNO
            mvno_name = mvno_name_match.group(0).strip() if mvno_name_match else "Unknown MVNO"

            # For now, let's assume the first part of the query is the MVNO name.
            # This needs to be more robust, perhaps by using the original MVNO list.
            # query_parts = query_source.split(' ', 1)
            # mvno_name = query_parts[0] if query_parts else "Unknown MVNO"
            if "google fi" in query_source.lower(): # hack for two word name
                mvno_name = "Google Fi"
            elif "us mobile" in query_source.lower():
                 mvno_name = "US Mobile"


            text_content = f"{title} {snippet}".lower() # Combine title and snippet for analysis

            # 1. Keyword & Phrase Recognition for Leniency Score
            leniency_score = self._calculate_leniency_score(text_content)

            # 2. Basic Sentiment Analysis
            sentiment = self._analyze_text_sentiment(text_content)

            # Aggregate data for the MVNO
            parsed_data[mvno_name]["mentions"] += 1
            parsed_data[mvno_name]["total_leniency_score"] += leniency_score
            if sentiment == "positive":
                parsed_data[mvno_name]["positive_sentiment_mentions"] += 1
            elif sentiment == "negative":
                parsed_data[mvno_name]["negative_sentiment_mentions"] += 1

            # Store source and individual score for traceability
            parsed_data[mvno_name]["sources"].append({
                "url": link,
                "title": title,
                "snippet": snippet,
                "query_source": query_source,
                "calculated_score_for_snippet": leniency_score,
                "estimated_sentiment": sentiment
            })

            # Track which policy keywords contributed
            for keyword in LENIENT_POLICY_KEYWORDS:
                if keyword in text_content:
                    parsed_data[mvno_name]["policy_keywords"][keyword] +=1
            for keyword in STRINGENT_POLICY_KEYWORDS:
                 if keyword in text_content:
                    parsed_data[mvno_name]["policy_keywords"][keyword] +=1


        # Calculate average leniency score
        for mvno, data in parsed_data.items():
            if data["mentions"] > 0:
                data["average_leniency_score"] = data["total_leniency_score"] / data["mentions"]
            else:
                data["average_leniency_score"] = 0

        self.logger.info(f"Parsing complete. Processed data for {len(parsed_data)} MVNOs.")

        # Save processed data
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.output_dir, f"parsed_mvno_data_{timestamp}.json")
        try:
            # Convert defaultdict to dict for JSON serialization
            serializable_data = {k: dict(v) for k, v in parsed_data.items()}
            for mvno in serializable_data: # ensure policy_keywords is also dict
                serializable_data[mvno]["policy_keywords"] = dict(serializable_data[mvno]["policy_keywords"])

            with open(filename, "w") as f:
                json.dump(serializable_data, f, indent=4)
            self.logger.info(f"Processed MVNO data saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to save processed MVNO data: {e}")
            return None

if __name__ == '__main__':
    import time # Make sure time is imported for the filename timestamp

    # This block demonstrates example usage of the GhostParser when the script is run directly.
    print("--- GhostParser Example Usage ---")

    # --- Setup for example run ---
    example_output_dir = "parser_example_output"
    if not os.path.exists(example_output_dir):
        os.makedirs(example_output_dir)
    print(f"Example outputs will be in '{example_output_dir}/'")

    example_config_file = os.path.join(example_output_dir, "parser_test_config.json")
    example_key_file = os.path.join(example_output_dir, "parser_test_secret.key")
    example_log_file = os.path.join(example_output_dir, "ghost_parser_example.log")
    dummy_raw_results_filepath = os.path.join(example_output_dir, "dummy_raw_results_for_parser.json")

    config_manager = GhostConfig(config_file=example_config_file, key_file=example_key_file)
    config_manager.set("output_dir", example_output_dir) # Direct parser's knowledge of output dir
    config_manager.set("log_file", example_log_file)
    config_manager._setup_logging()


    # Create a dummy raw_search_results.json file for the parser to process
    # Re-importing MOCK_SEARCH_RESULTS_STORE from ghost_crawler for realistic dummy data
    try:
        from ghost_crawler import MOCK_SEARCH_RESULTS_STORE
        sample_raw_data = []
        query1 = "US Mobile no ID prepaid" # Example query
        for res_item in MOCK_SEARCH_RESULTS_STORE.get(query1, []):
            res_copy = res_item.copy()
            res_copy["query_source"] = query1
            sample_raw_data.append(res_copy)
        sample_raw_data.append({ # Custom entry for testing specific scoring
            "title": "US Mobile Privacy Policy", "link": "https://www.usmobile.com/privacy_example",
            "snippet": "US Mobile is privacy focused and offers anonymous activation. No ID required for some plans. No SSN needed.",
            "query_source": "US Mobile anonymous activation requirements"
        })
        query2 = "Visible wireless cash sim" # Another example query
        for res_item in MOCK_SEARCH_RESULTS_STORE.get(query2, []):
            res_copy = res_item.copy()
            res_copy["query_source"] = query2
            sample_raw_data.append(res_copy)
        sample_raw_data.append({ # Custom entry for testing stringent scoring
            "title": "Visible ID Check Example", "link": "https://www.visible.com/help/id-check_example",
            "snippet": "Visible requires ID verification mandatory for all new accounts. SSN required for financing.",
            "query_source": "Visible strict kyc requirements"
        })
        with open(dummy_raw_results_filepath, "w") as f:
            json.dump(sample_raw_data, f, indent=4)
        print(f"Dummy raw results for parser created at: {dummy_raw_results_filepath}")
    except ImportError: # pragma: no cover
        print("Could not import MOCK_SEARCH_RESULTS_STORE from ghost_crawler. Skipping dummy data generation.")
        dummy_raw_results_filepath = None # Ensure parser doesn't run if data isn't there
    except Exception as e: # pragma: no cover
        print(f"Error creating dummy raw results: {e}")
        dummy_raw_results_filepath = None


    if dummy_raw_results_filepath and os.path.exists(dummy_raw_results_filepath):
        # --- Run the parser ---
        parser = GhostParser(config_manager)
        print(f"\n--- Starting Parsing (using dummy data: {dummy_raw_results_filepath}) ---")
        parsed_data_filepath = parser.parse_results(dummy_raw_results_filepath)

        if parsed_data_filepath:
            print(f"\nParsing complete. Processed data saved to: {parsed_data_filepath}")
            # You can inspect the JSON file in the 'parser_example_output' directory.
            with open(parsed_data_filepath, "r") as f:
                final_data = json.load(f)
                print("\n--- Parsed Data Sample (from example run) ---")
                for mvno, data in list(final_data.items())[:2]: # Print sample for first 2 MVNOs
                    print(f"\nMVNO: {mvno}")
                    print(f"  Average Leniency Score: {data.get('average_leniency_score', 0):.2f}")
                    print(f"  Total Mentions: {data.get('mentions', 0)}")
                    print(f"  Policy Keywords: {data.get('policy_keywords', {})}")
        else:
            print("\nParsing failed or produced no results to save for the example.")
    else:
        print("\nSkipping GhostParser example run as dummy raw data file was not created.")

    print(f"\nAll GhostParser example outputs are in '{example_output_dir}/'")
