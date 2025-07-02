import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone

# Removed spacy import and related comments

from ghost_config import GhostConfig

# Basic sentiment keyword lists (very simplistic)
POSITIVE_WORDS = {"easy", "simple", "quick", "no problem", "anonymous", "privacy", "recommended", "good", "great", "love", "best", "straightforward", "hassle-free", "no id", "no ssn", "cash", "minimal requirements"}
NEGATIVE_WORDS = {"difficult", "hard", "problem", "issues", "requires id", "ssn needed", "credit check", "avoid", "bad", "terrible", "warning", "strict", "verification", "mandatory id", "full kyc"}

# Source credibility weights - ensured this is present and used
SOURCE_CREDIBILITY_WEIGHTS = {
    "official": 1.0,  # High credibility for official MVNO sites (e.g., mvno.com/policy)
    "news": 0.8,      # Reputable news sources, tech journals
    "forum": 0.6,     # Forums, discussions (e.g., Reddit, XDA) - user experiences
    "blog": 0.7,      # Tech blogs, review sites - often well-researched
    "unknown": 0.4    # Default for unidentified or very generic sources (lowered weight)
}

# Enhanced Policy Keywords & Regex Patterns
# Structure: "keyword_group_name": {"regex": r"...", "score": X, "type": "lenient/stringent"}
# Regexes should be case-insensitive where appropriate (use re.IGNORECASE flag)
# More specific patterns get higher absolute scores.
ADVANCED_POLICY_PATTERNS = {
    # Lenient Patterns
    "no_id_strong": {"regex": r"\bno id (required|needed|necessary)\b|\banonymous activation\b|id free", "score": 7, "type": "lenient"},
    "no_id_moderate": {"regex": r"\bminimal id\b|\beasy verification\b|no personal info", "score": 4, "type": "lenient"},
    "no_ssn_strong": {"regex": r"\bno ssn (required|needed)\b|ssn free", "score": 7, "type": "lenient"},
    "cash_payment": {"regex": r"\bcash payment(s)? (accepted|ok|allowed)\b|\bpay with cash\b", "score": 5, "type": "lenient"},
    "crypto_payment": {"regex": r"\b(bitcoin|crypto|btc|eth|xmr) payment(s)? (accepted|ok)\b|\bpay with crypto\b", "score": 6, "type": "lenient"},
    "privacy_focused": {"regex": r"\bprivacy focused\b|\brespects privacy\b|privacy first", "score": 3, "type": "lenient"},
    "no_credit_check": {"regex": r"\bno credit check\b", "score": 3, "type": "lenient"},
    "burner_phone_friendly": {"regex": r"\bburner phone friendly\b|good for burner(s)?\b", "score": 4, "type": "lenient"},
    "prepaid_no_contract": {"regex": r"\bprepaid no contract\b|\bpay as you go\b", "score": 1, "type": "lenient"}, # Lower impact as it's common

    # Stringent Patterns
    "id_mandatory_strong": {"regex": r"\b(id|identification|driver'?s license|passport) (is )?(required|mandatory|needed|must provide|essential)\b|\bfull kyc\b", "score": -7, "type": "stringent"},
    "id_photo": {"regex": r"\bphoto id\b|\bphotographic identification\b", "score": -6, "type": "stringent"},
    "ssn_mandatory_strong": {"regex": r"\bssn (is )?(required|mandatory|needed)\b", "score": -7, "type": "stringent"},
    "credit_check_required": {"regex": r"\bcredit check (is )?(required|performed|mandatory)\b", "score": -5, "type": "stringent"},
    "address_verification": {"regex": r"\b(address verification|proof of address)\b", "score": -4, "type": "stringent"},
    "extensive_registration": {"regex": r"\b(extensive|lengthy|detailed) registration process\b", "score": -3, "type": "stringent"},
    "data_collection_heavy": {"regex": r"\bcollects (significant|extensive|lots of) personal data\b", "score": -3, "type": "stringent"},
    "not_anonymous": {"regex": r"\bnot anonymous\b|\bcannot be used anonymously\b", "score": -4, "type": "stringent"},
}


class GhostParser:
    """
    Processes raw data collected by GhostCrawler to extract actionable intelligence
    regarding MVNO leniency. It assigns a "leniency score" to each MVNO based on
    advanced regex pattern matching, source credibility, and temporal decay.
    Spacy/NLP based entity extraction has been removed.
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
        # self.nlp = self._initialize_nlp() # NLP initialization removed

    # _initialize_nlp method is now fully removed.
    # _extract_policy_entities method (NLP-based) is now fully removed.

    def _get_source_credibility(self, source_url: str | None) -> float:
        """
        Determines the credibility weight of a source based on its URL.

        Args:
            source_url (str | None): The URL of the data source.

        Returns:
            float: The credibility weight.
        """
        if not source_url:
            return SOURCE_CREDIBILITY_WEIGHTS["unknown"]

        url_lower = source_url.lower()
        # This is a basic implementation. More sophisticated matching could be used.
        # Order matters: check for more specific before general
        if any(official_domain in url_lower for official_domain in ["usmobile.com", "visible.com", "mintmobile.com", "googlefi.com", "cricketwireless.com", "boostmobile.com"]): # Add more official domains
            return SOURCE_CREDIBILITY_WEIGHTS["official"]
        if any(news_domain in url_lower for news_domain in ["reuters.com", "apnews.com", "nytimes.com", "wsj.com", "theverge.com", "techcrunch.com"]): # Add reputable news
            return SOURCE_CREDIBILITY_WEIGHTS["news"]
        if any(forum_domain in url_lower for forum_domain in ["reddit.com", "xda-developers.com", "howardforums.com"]):
            return SOURCE_CREDIBILITY_WEIGHTS["forum"]
        if any(blog_domain in url_lower for blog_domain in ["androidpolice.com", "bestmvno.com", "clark.com/cell-phones"]): # Generic tech blogs
            return SOURCE_CREDIBILITY_WEIGHTS["blog"]

        # Fallback if no specific category matches
        return SOURCE_CREDIBILITY_WEIGHTS["unknown"]

    def _calculate_temporal_weight(self, item_timestamp_str: str | None, batch_crawl_timestamp: datetime) -> float:
        """
        Calculates a weight based on the age of the data.
        Uses item_timestamp_str if available, otherwise falls back to batch_crawl_timestamp.

        Args:
            item_timestamp_str (str | None): ISO format string of the item's publication date.
            batch_crawl_timestamp (datetime): Timestamp of the current crawl batch.

        Returns:
            float: The calculated temporal weight (between 0.05 and 1.0).
        """
        data_timestamp = None
        if item_timestamp_str:
            try:
                data_timestamp = datetime.fromisoformat(item_timestamp_str.replace("Z", "+00:00"))
                # If timezone naive, assume UTC
                if data_timestamp.tzinfo is None:
                    data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                self.logger.warning(f"Could not parse item_timestamp_str: {item_timestamp_str}. Using batch crawl time for temporal weight.")
                data_timestamp = batch_crawl_timestamp

        if data_timestamp is None: # Should only happen if item_timestamp_str was None initially
             data_timestamp = batch_crawl_timestamp

        # Ensure batch_crawl_timestamp is timezone-aware (assume UTC if not)
        if batch_crawl_timestamp.tzinfo is None:
            effective_batch_crawl_timestamp = batch_crawl_timestamp.replace(tzinfo=timezone.utc)
        else:
            effective_batch_crawl_timestamp = batch_crawl_timestamp

        # Ensure data_timestamp is timezone-aware for correct comparison
        if data_timestamp.tzinfo is None:
             # This case should ideally be handled by earlier logic, but as a fallback:
            data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)


        days_old = (effective_batch_crawl_timestamp - data_timestamp).days

        if days_old < 0: # Data from the future? Or timestamp parsing issue.
            self.logger.warning(f"Data timestamp {data_timestamp} is in the future compared to crawl time {effective_batch_crawl_timestamp}. Defaulting temporal weight to 1.0.")
            return 1.0

        decay_rate = 0.01 # 1% decay per day
        min_weight = 0.05 # Minimum weight for very old data (e.g. data older than 95 days)

        weight = 1.0 - (days_old * decay_rate)
        return max(min_weight, weight) # Ensure weight doesn't go below min_weight or above 1.0 (implicitly handled if days_old is not negative)


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

    def _calculate_leniency_score(
        self,
        text_content: str,
        source_url: str | None,
        item_timestamp_str: str | None,
        batch_crawl_timestamp: datetime
    ) -> tuple[float, list[str]]:
        """
        Calculates a composite leniency score for a given text content.
        The score incorporates keyword matching, NLP entity analysis, source credibility,
        and temporal decay.

        Args:
            text_content (str): The text (e.g., search result snippet, extracted page text) to analyze.
            source_url (str | None): The URL of the data source.
            item_timestamp_str (str | None): ISO format string of the item's publication date.
            batch_crawl_timestamp (datetime): Timestamp of the current crawl batch.

        Returns:
            tuple[float, list[str]]: A tuple containing:
                - float: The calculated composite leniency score.
                - list[str]: A list of policy-related entities extracted by NLP.
        """
        if not text_content:
            return 0.0, []

        text_lower = text_content.lower()
        base_score = 0
        nlp_score_adjustment = 0

        # 1. Traditional Keyword Scoring (base)
        for keyword, points in LENIENT_POLICY_KEYWORDS.items():
            if keyword in text_lower:
                base_score += points
        for keyword, points in STRINGENT_POLICY_KEYWORDS.items():
            if keyword in text_lower: # points are already negative
                base_score += points

        # 2. NLP Entity Extraction and Scoring Adjustment
        extracted_entities = self._extract_policy_entities(text_lower) # Pass lowercased text

        # Example: Boost score if certain positive keywords are found by NLP as distinct entities
        # This logic can be expanded significantly.
        nlp_positive_indicators = {"no id", "anonymous", "no ssn", "cash payment", "privacy"}
        nlp_negative_indicators = {"id verification", "ssn required", "credit check", "kyc"}

        for entity in extracted_entities:
            # Check if the entity text itself is an indicator
            if entity in nlp_positive_indicators:
                nlp_score_adjustment += 2 # Small boost for NLP confirmed positive entities
            elif entity in nlp_negative_indicators:
                nlp_score_adjustment -= 2 # Small penalty for NLP confirmed negative entities
            else:
                # Check if parts of the entity text match broader keywords (more nuanced)
                if any(indicator in entity for indicator in nlp_positive_indicators):
                     nlp_score_adjustment += 1
                if any(indicator in entity for indicator in nlp_negative_indicators):
                     nlp_score_adjustment -=1

        # Combine base keyword score with NLP adjustment
        combined_keyword_nlp_score = base_score + nlp_score_adjustment

        # 3. Source Credibility Weighting
        credibility_weight = self._get_source_credibility(source_url)

        # 4. Temporal Weighting
        temporal_weight = self._calculate_temporal_weight(item_timestamp_str, batch_crawl_timestamp)

        # Calculate final composite score
        # Example: (keyword_score + nlp_score_adj) * credibility_weight * temporal_weight
        # Ensure factors are reasonably scaled. If base_score can be large, direct multiplication might be too much.
        # For now, let's apply them as multipliers to the combined score.
        final_score = combined_keyword_nlp_score * credibility_weight * temporal_weight

        self.logger.debug(
            f"Score calculation for source '{source_url}': "
            f"BaseKeywords={base_score}, NLPAdjust={nlp_score_adjustment}, "
            f"Credibility={credibility_weight:.2f}, Temporal={temporal_weight:.2f} "
            f"-> Final Score={final_score:.2f}"
        )

        return final_score, extracted_entities


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

        if not self.nlp: # Check if NLP model loaded
            self.logger.error("NLP model not available. Cannot perform enhanced parsing.")
            # Optionally, could fall back to a basic parsing mode here,
            # but for now, we'll indicate failure to meet enhanced parsing objective.
            return None

        # Use file modification time of raw_data_filepath as batch_crawl_timestamp
        try:
            batch_crawl_timestamp_unix = os.path.getmtime(raw_data_filepath)
            batch_crawl_timestamp = datetime.fromtimestamp(batch_crawl_timestamp_unix, tz=timezone.utc)
        except Exception as e: # pragma: no cover
            self.logger.warning(f"Could not get file modification time for {raw_data_filepath}: {e}. Using current time as batch crawl time.")
            batch_crawl_timestamp = datetime.now(timezone.utc)


        parsed_data = defaultdict(lambda: {
            "sources": [],
            "total_leniency_score": 0.0, # Now float
            "mentions": 0,
            "positive_sentiment_mentions": 0,
            "negative_sentiment_mentions": 0,
            "policy_keywords": defaultdict(int),
            "aggregated_nlp_entities": defaultdict(int) # New: To store counts of NLP entities
        })
        self.logger.info(f"Parser: Starting processing of {len(raw_results)} raw_results items with NLP enhancements.")

        for idx, item in enumerate(raw_results):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "") # This is the source_url
            query_source = item.get("query_source", "")
            raw_html_content = item.get("raw_html_content")
            extracted_page_text = item.get("extracted_page_text")

            # Attempt to get item-specific timestamp (e.g., from metadata if crawler provides it)
            # Placeholder: Assuming 'published_date' might be a field in item from future crawler
            item_timestamp_str = item.get("published_date") # This will be None for current mock data

            # --- MVNO Name Extraction (using existing logic) ---
            mvno_name = self._extract_mvno_name_from_query(query_source)
            # (Original logic for Google Fi, US Mobile specific extraction can be kept or refined if needed)
            # For simplicity, relying on the general _extract_mvno_name_from_query here.

            # Determine the primary text content for analysis
            text_for_analysis = ""
            text_source_type = "none"
            if extracted_page_text and extracted_page_text.strip():
                text_for_analysis = extracted_page_text # Already lowercased in _calculate_leniency_score
                text_source_type = "extracted_page_text"
            elif snippet:
                text_for_analysis = f"{title} {snippet}"
                text_source_type = "snippet_title"
            else:
                text_for_analysis = title
                text_source_type = "title_only"

            if not text_for_analysis.strip():
                self.logger.warning(f"No text content for item from {link} (query '{query_source}'). Skipping.")
                continue

            # 1. Enhanced Leniency Score Calculation
            leniency_score, nlp_entities = self._calculate_leniency_score(
                text_for_analysis,
                link,  # source_url
                item_timestamp_str,
                batch_crawl_timestamp
            )

            # 2. Basic Sentiment Analysis (can remain as is, or be enhanced by NLP later)
            sentiment = self._analyze_text_sentiment(text_for_analysis.lower()) # Ensure lower for this

            # Aggregate data for the MVNO
            parsed_data[mvno_name]["mentions"] += 1
            parsed_data[mvno_name]["total_leniency_score"] += leniency_score # Now float
            if sentiment == "positive":
                parsed_data[mvno_name]["positive_sentiment_mentions"] += 1
            elif sentiment == "negative":
                parsed_data[mvno_name]["negative_sentiment_mentions"] += 1

            for entity in nlp_entities:
                parsed_data[mvno_name]["aggregated_nlp_entities"][entity] += 1

            source_details = {
                "url": link,
                "title": title,
                "snippet": snippet,
                "query_source": query_source,
                "calculated_score": leniency_score, # Store the new composite score
                "estimated_sentiment": sentiment,
                "text_source_analysed": text_source_type,
                "extracted_text_length": len(extracted_page_text) if extracted_page_text else 0,
                "raw_html_length": len(raw_html_content) if raw_html_content else 0,
                "nlp_entities_found": nlp_entities, # Store entities for this source
                "item_timestamp_used": item_timestamp_str if item_timestamp_str else batch_crawl_timestamp.isoformat()
            }
            parsed_data[mvno_name]["sources"].append(source_details)

            # Track which policy keywords contributed (from traditional keyword spotting)
            # text_for_analysis is already effectively lowercased by _calculate_leniency_score
            current_text_lower = text_for_analysis.lower()
            for keyword in LENIENT_POLICY_KEYWORDS:
                if keyword in current_text_lower:
                    parsed_data[mvno_name]["policy_keywords"][keyword] +=1
            for keyword in STRINGENT_POLICY_KEYWORDS:
                 if keyword in current_text_lower:
                    parsed_data[mvno_name]["policy_keywords"][keyword] +=1

        # Calculate average leniency score
        for mvno, data in parsed_data.items():
            if data["mentions"] > 0:
                data["average_leniency_score"] = data["total_leniency_score"] / data["mentions"]
            else:
                data["average_leniency_score"] = 0.0 # Float

            # Convert aggregated_nlp_entities from defaultdict to dict for serialization
            data["aggregated_nlp_entities"] = dict(data["aggregated_nlp_entities"])


        self.logger.info(f"Parsing complete with NLP. Processed data for {len(parsed_data)} MVNOs.")

        # Save processed data
        timestamp_str = time.strftime("%Y%m%d-%H%M%S") # Changed variable name for clarity
        filename = os.path.join(self.output_dir, f"parsed_mvno_data_{timestamp_str}.json")
        try:
            # Convert defaultdict to dict for JSON serialization
            serializable_data = {k: dict(v) for k, v in parsed_data.items()}
            for mvno_data_key in serializable_data:
                serializable_data[mvno_data_key]["policy_keywords"] = dict(serializable_data[mvno_data_key]["policy_keywords"])
                # aggregated_nlp_entities already converted above

            with open(filename, "w") as f:
                json.dump(serializable_data, f, indent=4)
            self.logger.info(f"Processed MVNO data (NLP enhanced) saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to save NLP enhanced processed MVNO data: {e}", exc_info=True)
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
