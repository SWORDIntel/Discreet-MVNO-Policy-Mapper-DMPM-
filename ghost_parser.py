#!/usr/bin/env python3
"""GHOST Protocol Intelligence Parser - Per Document #2, Section 4.3"""
import json
import re
from datetime import datetime
from pathlib import Path
import time

class GhostParser:
    def __init__(self, config):
        self.config = config
        self.logger = config.get_logger("GhostParser")
        self.output_dir = Path("test_output")
        self.output_dir.mkdir(exist_ok=True)

        # Scoring weights
        self.scoring_rules = {
            # Positive indicators (lenient)
            "no id required": 5,
            "no identification": 5,
            "anonymous activation": 4,
            "anonymous": 3,
            "cash payment accepted": 3,
            "cash payment": 3,
            "no ssn": 4,
            "no social security": 4,
            "prepaid": 2,
            "no credit check": 3,
            "instant activation": 2,
            "no personal information": 4,

            # Negative indicators (stringent)
            "id required": -5,
            "identification required": -5,
            "id verification mandatory": -5,
            "ssn required": -5,
            "social security required": -5,
            "credit check required": -4,
            "background check": -4,
            "government id": -4,
            "photo id": -3,
            "proof of address": -3,
            "bank account required": -3
        }

    def parse_results(self, search_results):
        """Parse search results and extract intelligence"""
        parsed_data = {}

        self.logger.info("Beginning intelligence extraction")

        for mvno, results in search_results.items():
            mvno_intelligence = {
                "mvno_name": mvno,
                "policies": [],
                "leniency_score": 0,
                "evidence_count": 0,
                "sources": [],
                "timestamp": datetime.now().isoformat()
            }

            # Extract policies from each search result
            for result in results:
                if not result or 'items' not in result:
                    continue

                for item in result['items']:
                    policy_data = self._extract_policy_indicators(
                        item.get('snippet', ''),
                        item.get('title', '')
                    )

                    if policy_data['indicators_found']:
                        mvno_intelligence['policies'].append(policy_data)
                        mvno_intelligence['sources'].append({
                            "url": item.get('link', ''),
                            "title": item.get('title', '')
                        })

            # Calculate aggregate leniency score
            mvno_intelligence['leniency_score'] = self._calculate_leniency_score(
                mvno_intelligence['policies']
            )
            mvno_intelligence['evidence_count'] = len(mvno_intelligence['policies'])

            parsed_data[mvno] = mvno_intelligence

        # Save parsed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"parsed_mvno_data_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(parsed_data, f, indent=2)

        self.logger.info(f"Parsing complete. Intelligence saved to {output_file}")
        return parsed_data

    def _extract_policy_indicators(self, text, title=""):
        """Extract policy indicators from text using regex patterns"""
        combined_text = f"{title} {text}".lower()
        found_indicators = []
        score_contributions = []

        for indicator, score in self.scoring_rules.items():
            # Use word boundaries for more accurate matching
            pattern = r'\b' + re.escape(indicator) + r'\b'
            if re.search(pattern, combined_text, re.IGNORECASE):
                found_indicators.append(indicator)
                score_contributions.append(score)
                self.logger.debug(f"Found indicator: '{indicator}' (score: {score})")

        return {
            "text_snippet": text[:200],  # First 200 chars
            "indicators_found": found_indicators,
            "score_contributions": score_contributions,
            "total_score": sum(score_contributions)
        }

    def _calculate_leniency_score(self, policies):
        """Calculate aggregate leniency score with normalization"""
        if not policies:
            return 0.0

        total_score = sum(p['total_score'] for p in policies)
        evidence_weight = min(len(policies) / 5.0, 2.0)  # Cap evidence multiplier at 2x

        # Normalize to 0-5 scale
        raw_score = (total_score / len(policies)) * evidence_weight
        normalized_score = max(0, min(5, (raw_score + 10) / 4))  # Map [-10,10] -> [0,5]

        return round(normalized_score, 2)
