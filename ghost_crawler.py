import time
import random
import json
import os # Added for path joining in example
from urllib.parse import quote_plus
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ghost_config import GhostConfig

# --- Mock Google Search API ---
# This is a placeholder for the actual Google Search API interaction.
# In a real application, you would use the official Google API client library.
MOCK_SEARCH_RESULTS_STORE = {
    "US Mobile no ID prepaid": [
        {"title": "US Mobile - Prepaid Plans, No Contracts, No Credit Checks", "link": "https://www.usmobile.com/", "snippet": "Get US Mobile's affordable, flexible prepaid plans. No contracts, no credit checks. SIM starter kits available."},
        {"title": "Best Anonymous SIM Cards in the US (2024 Guide) - Reddit", "link": "https://www.reddit.com/r/privacy/comments/12345/best_anonymous_sim/", "snippet": "Discussion on MVNOs like US Mobile, Tello, Mint for anonymous SIMs. Some say US Mobile is good for privacy."},
    ],
    "Visible wireless cash sim": [
        {"title": "Visible Wireless - Digital, All-In, Single Line Wireless", "link": "https://www.visible.com/", "snippet": "Visible offers unlimited data, talk, and text for one low price. All digital activation."},
        {"title": "Can I pay for Visible with cash? - Visible Community", "link": "https://community.visible.com/t5/Account/Can-I-pay-for-Visible-with-cash/td-p/12345", "snippet": "Official Visible stance is digital payments only. Some users discuss workarounds like prepaid debit cards."},
    ],
    "Mint Mobile burner sim": [
        {"title": "Mint Mobile - Prepaid Phone Plans Starting at $15/mo", "link": "https://www.mintmobile.com/", "snippet": "Affordable prepaid plans. Bring your own phone or buy one from us. Easy online activation."},
        {"title": "Mint Mobile for Burner Phone? - XDA Developers", "link": "https://forum.xda-developers.com/t/mint-mobile-for-burner-phone.1234567/", "snippet": "Users discussing using Mint Mobile for temporary or burner phones. Mixed opinions on true anonymity."},
    ]
}

def mock_google_search(api_key, query, num_results=10):
    """
    Mocks a Google Search API call.
    In a real implementation, this function would use the `google-api-python-client`.
    """
    print(f"MOCK SEARCH: Using API key '{api_key}' to search for '{query}' (num_results={num_results})")
    # Simulate network delay
    time.sleep(random.uniform(0.5, 1.5))

    # Return results that partially match the query
    results = []
    for key_phrase, items in MOCK_SEARCH_RESULTS_STORE.items():
        if key_phrase.lower() in query.lower():
            results.extend(items)

    # If no specific match, return a generic set or a mix
    if not results and "default" in MOCK_SEARCH_RESULTS_STORE: # pragma: no cover (difficult to ensure this path in simple mock)
        results.extend(MOCK_SEARCH_RESULTS_STORE["default"])

    return random.sample(results, min(len(results), num_results)) if results else [
        {"title": "No relevant mock results", "link": "https://example.com/noresults", "snippet": f"No mock results found for query: {query}"}
    ]
# --- End Mock Google Search API ---


class GhostCrawler:
    """
    Orchestrates web crawling using Google Search (currently mocked) to gather raw data
    about US MVNOs based on a list of MVNOs and anonymity-related keywords.
    It mimics varied user behaviors by introducing temporal offsets between queries.
    """
    def __init__(self, config_manager: GhostConfig):
        """
        Initializes the GhostCrawler.

        Args:
            config_manager (GhostConfig): An instance of GhostConfig for accessing
                                          configuration settings (API keys, file paths, etc.).
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostCrawler")
        self.google_api_key = self.config_manager.get_api_key("google_search")
        self.programmable_search_engine_id = self.config_manager.get("google_programmable_search_engine_id")
        self.google_search_mode = self.config_manager.get("google_search_mode", "auto") # auto|real|mock
        self.search_service = None

        if self.google_search_mode == "real":
            if self.google_api_key and self.programmable_search_engine_id:
                try:
                    self.search_service = build("customsearch", "v1", developerKey=self.google_api_key)
                    self.logger.info("Google Custom Search service initialized for REAL mode.")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Google Custom Search service in REAL mode: {e}. Falling back to MOCK search.")
                    self.search_service = "MOCK_SERVICE" # Fallback identifier
            else:
                self.logger.warning("Google API key or Programmable Search Engine ID missing for REAL mode. Falling back to MOCK search.")
                self.search_service = "MOCK_SERVICE" # Fallback identifier
        elif self.google_search_mode == "mock":
            self.logger.info("Google Search explicitly set to MOCK mode.")
            self.search_service = "MOCK_SERVICE"
        else: # auto mode
            if self.google_api_key and self.programmable_search_engine_id:
                try:
                    self.search_service = build("customsearch", "v1", developerKey=self.google_api_key)
                    self.logger.info("Google Custom Search service initialized for AUTO mode (real search).")
                except Exception as e:
                    self.logger.warning(f"Failed to initialize Google Custom Search service in AUTO mode: {e}. Using MOCK search.")
                    self.search_service = "MOCK_SERVICE"
            else:
                self.logger.info("Google API key or Programmable Search Engine ID not found in AUTO mode. Using MOCK search.")
                self.search_service = "MOCK_SERVICE"

        self.mvno_list_file = self.config_manager.get("mvno_list_file", "mvnos.txt")
        self.keywords_file = self.config_manager.get("keywords_file", "keywords.txt")
        self.output_dir = self.config_manager.get("output_dir", "output")

        self.mvnos = self._load_list_from_file(self.mvno_list_file)
        self.anonymity_keywords = self._load_list_from_file(self.keywords_file)

    def _load_list_from_file(self, filepath: str) -> list[str]:
        """
        Loads a list of strings from a text file, one item per line.
        Empty lines or lines with only whitespace are ignored.

        Args:
            filepath (str): The path to the text file.

        Returns:
            list[str]: A list of strings loaded from the file. Returns an empty
                       list if the file is not found or an error occurs.
        """
        try:
            with open(filepath, "r") as f:
                items = [line.strip() for line in f if line.strip()]
            self.logger.info(f"Loaded {len(items)} items from {filepath}")
            return items
        except FileNotFoundError:
            self.logger.error(f"File not found: {filepath}. Returning empty list.")
            return []
        except Exception as e: # pragma: no cover
            self.logger.error(f"Error loading file {filepath}: {e}")
            return []

    def _generate_queries(self) -> list[str]:
        """
        Generates a list of search query strings by combining each MVNO from the
        MVNO list with each phrase from the anonymity keywords list.
        If keywords are missing, it generates queries with MVNO names and a default suffix.

        Returns:
            list[str]: A list of generated search queries.
        """
        queries = []
        if not self.mvnos:
            self.logger.warning("MVNO list is empty. Cannot generate queries.")
            return queries
        if not self.anonymity_keywords:
            self.logger.warning("Anonymity keywords list is empty. Cannot generate queries effectively.")
            # Fallback to just searching MVNO names if keywords are missing
            for mvno in self.mvnos:
                queries.append(f"{mvno} reviews policies")
            return queries

        for mvno in self.mvnos:
            for keyword_phrase in self.anonymity_keywords:
                queries.append(f"{mvno} {keyword_phrase}")
        self.logger.info(f"Generated {len(queries)} search queries.")
        return queries

    def _perform_search(self, query: str, num_results: int = 10) -> list[dict]:
        """
        Performs a single search query (currently mocked) and returns the results.
        A configurable, pseudo-random temporal offset is introduced before making the "search call"
        to mimic varied user behavior.

        Args:
            query (str): The search query string.
            num_results (int): The desired number of results (passed to the mock search).

        Returns:
            list[dict]: A list of search result items (dictionaries with 'title', 'link', 'snippet').
                        Returns an empty list if the search fails or an error occurs.
        """
        search_delay_base = self.config_manager.get("search_delay_seconds", 5)
        variance_percentage = self.config_manager.get("search_delay_variance_percent", 15)

        delay_offset = (search_delay_base * variance_percentage / 100.0)
        min_delay = search_delay_base - delay_offset
        max_delay = search_delay_base + delay_offset
        actual_delay = random.uniform(min_delay, max_delay)

        self.logger.info(f"Waiting for {actual_delay:.2f} seconds before next search...")
        time.sleep(actual_delay)

        self.logger.info(f"Performing search for: {query}")
        max_retries = 3
        backoff_factor = 2

        # Basic rate limiting: 10 QPS means 0.1s per query.
        # This is a simplified approach. A more robust solution might involve a token bucket algorithm.
        time.sleep(0.1)

        for attempt in range(max_retries):
            try:
                if self.search_service == "MOCK_SERVICE":
                    self.logger.info("Using MOCK Google Search.")
                    return mock_google_search(self.google_api_key or "NO_API_KEY_CONFIGURED", query, num_results)

                if not self.search_service: # Should have been caught by init, but as a safeguard
                    self.logger.error("Google Search service not available (was None). Switching to MOCK search for this query.")
                    self.search_service = "MOCK_SERVICE" # Temporary switch for this call
                    return mock_google_search(self.google_api_key or "NO_API_KEY_CONFIGURED", query, num_results)

                self.logger.info("Using REAL Google Search.")
                result = self.search_service.cse().list(
                    q=query,
                    cx=self.programmable_search_engine_id,
                    num=num_results
                ).execute()
                return result.get('items', [])

            except HttpError as e:
                if e.resp.status in [429, 500, 503]: # Rate limit or server error
                    wait_time = backoff_factor ** attempt + random.uniform(0, 1)
                    self.logger.warning(f"Google Search API error (status {e.resp.status}): {e}. Retrying in {wait_time:.2f}s (attempt {attempt+1}/{max_retries}).")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Unhandled Google Search API HttpError for '{query}': {e}")
                    return [] # Non-retryable HttpError
            except Exception as e: # Catch other potential errors, e.g., network issues
                self.logger.error(f"Generic error during search for '{query}' (attempt {attempt+1}/{max_retries}): {e}")
                wait_time = backoff_factor ** attempt + random.uniform(0, 1)
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {wait_time:.2f}s.")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Max retries reached for query '{query}'. Failing this search.")
                    return []
        return [] # Should be unreachable if loop completes, but as a fallback

    def run_crawling_cycle(self, num_results_per_query: int = 5) -> str | None:
        """
        Runs a full crawling cycle:
        1. Generates search queries.
        2. Performs searches for each query.
        3. Collects all results.
        4. Saves the aggregated raw results to a timestamped JSON file in the output directory.

        Args:
            num_results_per_query (int): The number of results to request for each individual query.

        Returns:
            str | None: The filepath of the saved raw search results JSON file if successful,
                        otherwise None.
        """
        self.logger.info("Starting new crawling cycle.")
        # Initial checks for API key and ID are now handled by __init__ when setting up search_service
        # and by _perform_search for fallback during actual calls.

        queries = self._generate_queries()
        if not queries:
            self.logger.warning("No queries generated. Ending crawling cycle.")
            return None

        all_results = []
        for query in queries:
            results = self._perform_search(query, num_results=num_results_per_query)
            if results:
                # We might want to add the query to the results for context
                for res_item in results:
                    res_item['query_source'] = query
                all_results.extend(results)
            else:
                self.logger.info(f"No results found for query: {query}")

        self.logger.info(f"Crawling cycle completed. Total raw results collected: {len(all_results)}")

        # Save raw results
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.output_dir, f"raw_search_results_{timestamp}.json")
        try:
            with open(filename, "w") as f:
                json.dump(all_results, f, indent=4)
            self.logger.info(f"Raw search results saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save raw search results: {e}")
            return None # Indicate failure if saving fails

        return filename # Return the path to the saved results

    # Placeholder for HTML parsing/content extraction if needed later
    # def extract_content_from_url(self, url):
    #     """
    #     (Future Enhancement) Fetches and parses content from a given URL.
    #     This would require libraries like 'requests' and 'BeautifulSoup'.
    #     """
    #     self.logger.info(f"Attempting to extract content from URL: {url}")
    #     # Implementation would go here:
    #     # - Use requests.get(url)
    #     # - Parse with BeautifulSoup
    #     # - Extract relevant text
    #     # - Handle exceptions
    #     return "Extracted content placeholder"


if __name__ == '__main__':
    # This block demonstrates example usage of the GhostCrawler when the script is run directly.
    print("--- GhostCrawler Example Usage ---")

    # --- Setup for example run ---
    example_output_dir = "crawler_example_output"
    if not os.path.exists(example_output_dir):
        os.makedirs(example_output_dir)
    print(f"Example outputs will be in '{example_output_dir}/'")

    example_config_file = os.path.join(example_output_dir, "crawler_test_config.json")
    example_key_file = os.path.join(example_output_dir, "crawler_test_secret.key")
    example_mvnos_file = os.path.join(example_output_dir, "mvnos_example.txt")
    example_keywords_file = os.path.join(example_output_dir, "keywords_example.txt")
    example_log_file = os.path.join(example_output_dir, "ghost_crawler_example.log")


    config_manager = GhostConfig(config_file=example_config_file, key_file=example_key_file)
    config_manager.set("app_version", "1.0.0-crawler-example")
    config_manager.set("search_delay_seconds", 0.2) # Short delay for testing
    config_manager.set("search_delay_variance_percent", 10)
    config_manager.set_api_key("google_search", "MOCK_API_KEY_FOR_CRAWLER_EXAMPLE")
    config_manager.set("mvno_list_file", example_mvnos_file)
    config_manager.set("keywords_file", example_keywords_file)
    config_manager.set("output_dir", example_output_dir) # Direct crawler output to its example dir
    config_manager.set("log_file", example_log_file)
    config_manager._setup_logging() # Re-initialize logging with new settings


    with open(example_mvnos_file, "w") as f:
        f.write("US Mobile Example\n")
        f.write("Visible Example\n")
        f.write("Mint Mobile Example\n")
        f.write("Google Fi Example\n") # Will likely get "no relevant mock results"
    print(f"Created example MVNOs file: {example_mvnos_file}")

    with open(example_keywords_file, "w") as f:
        f.write("no ID prepaid example\n")
        f.write("cash sim example\n")
        f.write("burner sim example\n")
        f.write("anonymous activation requirements example\n")
    print(f"Created example keywords file: {example_keywords_file}")

    # --- Run the crawler ---
    crawler = GhostCrawler(config_manager)

    # Test loading of MVNOs and Keywords
    print(f"Loaded MVNOs: {crawler.mvnos}")
    print(f"Loaded Keywords: {crawler.anonymity_keywords}")

    # Generate and print queries to see what it would search for
    example_queries = crawler._generate_queries()
    print("\nExample queries to be run:")
    for q in example_queries[:5]: # Print first 5
        print(q)
    if len(example_queries) > 5:
        print(f"...and {len(example_queries) - 5} more.")

    print("\n--- Starting Crawling Cycle (using MOCK search) ---")
    results_filepath = crawler.run_crawling_cycle(num_results_per_query=2)

    if results_filepath:
        print(f"\nCrawling cycle finished. Results saved to: {results_filepath}")
        # You can inspect the JSON file in the 'output' directory.
    else:
        print("\nCrawling cycle failed or produced no results to save.")

    # Clean up dummy files (optional)
    # os.remove("crawler_test_config.json")
    # os.remove("crawler_test_secret.key")
    # os.remove("mvnos_example.txt")
    # os.remove("keywords_example.txt")
    # print("\nCleaned up temporary test files.")
