#!/usr/bin/env python3
"""GHOST Protocol Web Crawler - Per Document #2, Section 4.2"""
import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
import hashlib

class GhostCrawler:
    def __init__(self, config):
        self.config = config
        self.logger = config.get_logger("GhostCrawler")

        # Use project_root from config to resolve the output directory path
        # Allow overriding via config file, e.g., crawler.output_dir
        output_dir_str = config.get("crawler.output_dir", "test_output") # Default relative path
        self.output_dir = config.get_absolute_path(output_dir_str)

        if not self.output_dir:
            self.logger.error(f"Crawler output directory '{output_dir_str}' could not be resolved. Crawler outputs will likely fail.")
            # Allow to proceed, operations might fail if self.output_dir is None
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # API configuration
        self.api_key = config.get_api_key("google_search")
        self.cx_id = config.get("google_programmable_search_engine_id")
        self.search_mode = config.get("google_search_mode", "mock")

    def _apply_temporal_variance(self, base_delay):
        """Apply ±15% variance to delays"""
        variance = self.config.get("crawler.delay_variance", 0.15)
        min_delay = base_delay * (1 - variance)
        max_delay = base_delay * (1 + variance)
        return random.uniform(min_delay, max_delay)

    def search_mvno_policies(self):
        """Execute search for MVNO policies"""
        mvno_list = self.config.get("mvno_list", [])
        keywords = self.config.get("keywords", [])
        results = {}

        self.logger.info(f"Starting crawl in {self.search_mode} mode")
        start_time = time.time()

        for mvno in mvno_list:
            mvno_results = []

            for keyword in keywords:
                query = f"{mvno} {keyword}"
                self.logger.info(f"Searching: {query}")

                if self.search_mode == "mock":
                    # Generate mock data
                    result = self._generate_mock_result(mvno, keyword)
                else:
                    # Real Google Search API call
                    result = self._google_search(query)

                if result:
                    mvno_results.append(result)

                # Apply delay with variance
                delay = self._apply_temporal_variance(
                    self.config.get("crawler.delay_base", 2.0)
                )
                time.sleep(delay)

            results[mvno] = mvno_results

        # Save raw results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"raw_search_results_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "search_mode": self.search_mode,
                "duration": time.time() - start_time,
                "results": results
            }, f, indent=2)

        self.logger.info(f"Crawl complete. Results saved to {output_file}")
        return results

    def _google_search(self, query):
        """Execute real Google Search API call"""
        if not self.api_key or not self.cx_id:
            self.logger.error("API credentials not configured")
            return None

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx_id,
            "q": query,
            "num": 10
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.get("crawler.timeout", 30)
            )
            response.raise_for_status()

            data = response.json()
            return {
                "query": query,
                "items": data.get("items", []),
                "total_results": data.get("searchInformation", {}).get("totalResults", 0)
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Search failed for '{query}': {e}")
            return None

    def _generate_mock_result(self, mvno, keyword):
        """Generate realistic mock search result"""
        # Create deterministic but varied mock data
        seed = hashlib.md5(f"{mvno}{keyword}".encode()).hexdigest()
        random.seed(seed)

        snippets = {
            "no id required": f"{mvno} offers prepaid plans with no ID verification required for activation. Simply purchase a SIM card with cash at any retail location.",
            "anonymous": f"Get anonymous prepaid service with {mvno}. No personal information needed for basic plans under $50/month.",
            "prepaid": f"{mvno} prepaid plans start at $15/month. Activation can be done online or in-store with minimal information.",
            "cash payment": f"Pay with cash at thousands of {mvno} retail locations. No credit check or bank account required."
        }

        return {
            "query": f"{mvno} {keyword}",
            "items": [{
                "title": f"{mvno} - {keyword.title()} Options",
                "link": f"https://example.com/{mvno.lower().replace(' ', '-')}/{keyword.replace(' ', '-')}",
                "snippet": snippets.get(keyword, f"Information about {mvno} and {keyword}"),
                "htmlSnippet": f"<b>{mvno}</b> {keyword}"
            }],
            "total_results": random.randint(100, 10000)
        }
