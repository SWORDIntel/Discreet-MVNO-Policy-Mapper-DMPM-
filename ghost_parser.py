import json
import os
import re
import time
import difflib # Added for fuzzy matching
from collections import defaultdict
from datetime import datetime, timezone

try:
    import spacy
    from spacy.matcher import Matcher
    # Attempt to import spacytextblob for sentiment analysis
    from spacytextblob.spacytextblob import SpacyTextBlob
except ImportError:
    spacy = None
    Matcher = None
    SpacyTextBlob = None

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

        self.nlp_available = False
        self.nlp_model = None
        self.nlp_matcher = None
        self.nlp_mode = self.config_manager.get("nlp_mode", "auto") # auto | spacy | regex

        if spacy and SpacyTextBlob and Matcher and self.nlp_mode != "regex": # Check if spacy and required components are imported
            self._initialize_nlp()
        else:
            if self.nlp_mode == "spacy":
                self.logger.error("NLP mode set to 'spacy' but spaCy or SpacyTextBlob/Matcher is not available. Falling back to regex.")
            else: # auto mode or regex mode where spacy is not available
                 self.logger.info("spaCy, SpacyTextBlob, or Matcher not available or NLP mode set to 'regex'. Using regex-based analysis.")
            self.nlp_available = False


        self.mvno_list_file = self.config_manager.get("mvno_list_file", "mvnos.txt")
        self.known_mvnos_normalized = {} # Stores {normalized_name: original_name}
        self.mvno_aliases = self.config_manager.get("mvno_aliases", {}) # e.g., {"google fi": "Google Fi Wireless"}
        self._load_known_mvnos()

    def _initialize_nlp(self):
        """
        Initializes the spaCy NLP model and Matcher if spaCy is available.
        Sets self.nlp_available flag.
        """
        if not spacy or not SpacyTextBlob or not Matcher: # Should be caught before calling, but double check
            self.logger.warning("Attempted to initialize NLP when spaCy or its components are unavailable.")
            self.nlp_available = False
            return

        try:
            # Try to load a small English model.
            # Users might need to download this: python -m spacy download en_core_web_sm
            self.nlp_model = spacy.load("en_core_web_sm")

            # Add SpacyTextBlob to the pipeline for sentiment if not already present
            # Some models might include it, others might not.
            # Check if 'spacytextblob' is already in the pipeline
            if 'spacytextblob' not in self.nlp_model.pipe_names:
                self.nlp_model.add_pipe("spacytextblob")
                self.logger.info("Added SpacyTextBlob to NLP pipeline for sentiment analysis.")
            else:
                self.logger.info("SpacyTextBlob component already present in NLP pipeline.")

            self.nlp_matcher = Matcher(self.nlp_model.vocab)
            self._setup_nlp_matchers() # Setup policy requirement patterns

            self.nlp_available = True
            self.logger.info("spaCy NLP model 'en_core_web_sm' loaded successfully with SpacyTextBlob and Matcher.")
        except OSError:
            self.logger.error(
                "spaCy model 'en_core_web_sm' not found. "
                "Please download it: python -m spacy download en_core_web_sm. "
                "Falling back to regex-based analysis."
            )
            self.nlp_model = None
            self.nlp_available = False
        except Exception as e:
            self.logger.error(f"Error initializing spaCy NLP: {e}. Falling back to regex-based analysis.")
            self.nlp_model = None
            self.nlp_available = False

    def _setup_nlp_matchers(self):
        """Sets up the spaCy Matcher with patterns for policy requirements."""
        if not self.nlp_matcher:
            return

        # Define patterns for policy requirements
        # Pattern format: list of dictionaries, each dict describes a token
        # "OP": "?" means optional, "*" zero or more, "+" one or more
        patterns = {
            "REQUIRES_ID": [
                [{"LOWER": "requires"}, {"LOWER": "id"}],
                [{"LOWER": "must"}, {"LOWER": "provide"}, {"LOWER": "id"}],
                [{"LOWER": "id"}, {"LOWER": "is"}, {"LOWER": "required"}],
                [{"LOWER": "identification"}, {"LOWER": "needed"}]
            ],
            "NO_ID_NEEDED": [
                [{"LOWER": "no"}, {"LOWER": "id"}, {"LOWER": "required"}],
                [{"LOWER": "id"}, {"LOWER": "not"}, {"LOWER": "needed"}],
                [{"LOWER": "doesn't"}, {"LOWER": "require"}, {"LOWER": "id"}]
            ],
            "MUST_PROVIDE_INFO": [ # Generic "must provide"
                [{"LOWER": "must"}, {"LOWER": "provide"}, {"ENT_TYPE": "PERSON", "OP": "?"}, {"ENT_TYPE": "ORG", "OP": "?"}],
                [{"LOWER": "requires"}, {"ENT_TYPE": "PERSON", "OP": "?"}, {"ENT_TYPE": "ORG", "OP": "?"}]
            ]
            # Add more patterns as needed
        }

        for pattern_name, pattern_rules in patterns.items():
            self.nlp_matcher.add(pattern_name, pattern_rules)
        self.logger.info(f"Initialized spaCy Matcher with {len(patterns)} pattern types.")


    def _normalize_mvno_name(self, name: str) -> str:
        """
        Normalizes an MVNO name by converting to lowercase and removing common suffixes.
        """
        name_lower = name.lower()
        suffixes_to_remove = [
            " inc", " llc", " wireless", " mobile", " telecom", " communications",
            ".com", ".net", ".org", # also remove common TLDs if they are part of name
            " corporation", " company", " group", " services", " solutions"
        ]
        for suffix in suffixes_to_remove:
            if name_lower.endswith(suffix):
                name_lower = name_lower[:-len(suffix)]

        # Remove extra spaces that might result from suffix removal or be present initially
        name_lower = re.sub(r'\s+', ' ', name_lower).strip()
        return name_lower

    def _load_known_mvnos(self):
        """
        Loads MVNOs from the mvno_list_file and populates the
        self.known_mvnos_normalized dictionary. Applies normalization.
        Also incorporates aliases from config.
        """
        try:
            with open(self.mvno_list_file, "r") as f:
                mvnos = [line.strip() for line in f if line.strip()]
            for mvno_original in mvnos:
                normalized = self._normalize_mvno_name(mvno_original)
                if normalized not in self.known_mvnos_normalized: # Keep first original form if multiple normalize to same
                    self.known_mvnos_normalized[normalized] = mvno_original
                else:
                    self.logger.debug(f"Normalized name collision: '{normalized}' from '{mvno_original}' already mapped to '{self.known_mvnos_normalized[normalized]}'.")

            self.logger.info(f"Loaded {len(self.known_mvnos_normalized)} unique normalized MVNOs from {self.mvno_list_file}.")

            # Process aliases: normalized alias maps to canonical original name from mvnos.txt (if exists) or the alias value
            for alias_key, canonical_name_target in self.mvno_aliases.items():
                normalized_alias_key = self._normalize_mvno_name(alias_key)
                normalized_canonical_target = self._normalize_mvno_name(canonical_name_target)

                # Prefer the version of canonical_name_target that's already in known_mvnos_normalized (if any)
                final_target_name = self.known_mvnos_normalized.get(normalized_canonical_target, canonical_name_target)

                if normalized_alias_key not in self.known_mvnos_normalized:
                    self.known_mvnos_normalized[normalized_alias_key] = final_target_name
                    self.logger.info(f"Added alias: '{normalized_alias_key}' -> '{final_target_name}'")
                else:
                    self.logger.warning(f"Alias key '{normalized_alias_key}' conflicts with an existing MVNO. Original: '{self.known_mvnos_normalized[normalized_alias_key]}', Alias target: '{final_target_name}'. Alias not applied for this key if it's different.")

        except FileNotFoundError:
            self.logger.error(f"MVNO list file not found: {self.mvno_list_file}. MVNO extraction will be limited.")
        except Exception as e:
            self.logger.error(f"Error loading MVNO list file {self.mvno_list_file}: {e}")

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

    def _fuzzy_match_mvno(self, name_to_match: str) -> tuple[str | None, float]:
        """
        Attempts to match an extracted name against the known MVNO list using various strategies.
        Returns the matched canonical MVNO name and a confidence score.
        Scores: exact=1.0, fuzzy=0.8-0.99 (depending on similarity), contains=0.5, None=0.0
        """
        normalized_to_match = self._normalize_mvno_name(name_to_match)

        # 1. Exact match on normalized names
        if normalized_to_match in self.known_mvnos_normalized:
            return self.known_mvnos_normalized[normalized_to_match], 1.0

        # 2. Fuzzy match using difflib
        #    get_close_matches returns a list of matches, we take the best one if any
        #    A higher cutoff means stricter matching. 0.8 is a reasonable starting point.
        #    Adjust n to 1 to get only the best match.
        possible_matches = difflib.get_close_matches(normalized_to_match,
                                                     self.known_mvnos_normalized.keys(),
                                                     n=1, cutoff=0.8)
        if possible_matches:
            best_match_normalized = possible_matches[0]
            # Calculate similarity score more precisely for the "best" fuzzy match.
            # This score will be > cutoff (0.8)
            similarity_score = difflib.SequenceMatcher(None, normalized_to_match, best_match_normalized).ratio()
            # Scale score slightly to be distinct from exact match, e.g., 0.8 to 0.95 range based on actual ratio
            adjusted_score = 0.8 + (similarity_score - 0.8) * 0.75 # Maps 0.8-1.0 ratio to 0.8-0.95 score
            return self.known_mvnos_normalized[best_match_normalized], adjusted_score


        # 3. "Contains" match (e.g., "us mobile" is contained in "us mobile review")
        #    This is tricky because "mobile" could be in many, so we check if a known MVNO name
        #    is *contained within* the name_to_match (normalized).
        for known_norm, known_orig in self.known_mvnos_normalized.items():
            if known_norm in normalized_to_match:
                 # Ensure it's a significant part of the name, not just "us" in "asus"
                if len(known_norm) > 3 or known_norm == normalized_to_match: # very short names must be exact match essentially
                    return known_orig, 0.5 # Lower confidence for "contains"

        self.logger.info(f"MVNO not matched: '{name_to_match}' (normalized: '{normalized_to_match}')")
        return None, 0.0


    def _extract_mvno_name_from_query(self, query_source: str) -> str:
        """
        Extracts a potential MVNO name from the original search query string.
        This version attempts to identify the MVNO part of the query and then
        uses fuzzy matching to find the canonical name.

        Args:
            query_source (str): The original search query string (e.g., "US Mobile no ID prepaid").

        Returns:
            str: The canonical MVNO name if matched, or "Unknown MVNO" if extraction fails.
        """
        # Heuristic: Assume MVNO name is likely at the beginning of the query.
        # Try to extract first few words as potential MVNO name.
        # Example: "US Mobile", "Mint Mobile", "Google Fi"
        # More complex queries like "what is the policy of Tello for cash" are harder.

        # Try matching longer phrases first. Consider up to 3-4 words for MVNO names.
        query_parts = query_source.split()
        potential_mvno_str = ""
        best_match_name = None
        highest_score = 0.0

        # Check phrases of decreasing length (e.g., "Google Fi Wireless", then "Google Fi", then "Google")
        # This gives precedence to longer, more specific matches from the query.
        for num_words in range(min(4, len(query_parts)), 0, -1):
            current_phrase_to_test = " ".join(query_parts[:num_words])

            # Try direct fuzzy match on this extracted phrase
            matched_name, score = self._fuzzy_match_mvno(current_phrase_to_test)

            if matched_name and score > highest_score:
                highest_score = score
                best_match_name = matched_name
                # If we get a very high score (exact or very close fuzzy), we can be confident.
                if score >= 0.95: # Adjusted threshold, exact is 1.0
                    break

        if best_match_name:
            self.logger.debug(f"Extracted MVNO '{best_match_name}' from query '{query_source}' with score {highest_score:.2f}")
            return best_match_name

        # Fallback: Log if no confident match was found from query
        self.logger.info(f"Could not confidently extract known MVNO from query: '{query_source}'. Will be categorized as 'Unknown MVNO' or based on item title/domain if possible later.")
        # The original simple heuristic as a last resort if the above fails, but fuzzy matching should handle most.
        # However, the old logic was very basic. _fuzzy_match_mvno is more robust.
        # If nothing found, return "Unknown MVNO"
        return "Unknown MVNO"

    # --- NLP Enhanced Analysis Methods ---
    def _analyze_sentiment_nlp(self, doc) -> tuple[str, float]:
        """
        Analyzes sentiment using spaCy (SpacyTextBlob).
        Returns (sentiment_label, confidence_score).
        Sentiment labels: "positive", "negative", "neutral".
        Confidence is the polarity score.
        """
        if not self.nlp_available or not doc or not hasattr(doc, '_') or not hasattr(doc._, 'blob'):
            self.logger.debug("NLP not available or doc has no sentiment blob for sentiment analysis.")
            return "neutral", 0.0

        polarity = doc._.blob.polarity
        # SpacyTextBlob polarity is between -1 (negative) and 1 (positive)
        # Thresholds can be adjusted.
        if polarity > 0.1: # Threshold for positive
            sentiment_label = "positive"
        elif polarity < -0.1: # Threshold for negative
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        # Confidence is the absolute polarity score, scaled if needed, or just the raw polarity.
        # For simplicity, let's use raw polarity as confidence.
        return sentiment_label, polarity


    def _extract_entities_nlp(self, doc) -> list[tuple[str, str]]:
        """
        Extracts specified entities (ORG, MONEY, DATE) using spaCy.
        Returns a list of tuples: (entity_text, entity_label).
        """
        if not self.nlp_available or not doc:
            return []

        entities = []
        target_labels = {"ORG", "MONEY", "DATE"}
        for ent in doc.ents:
            if ent.label_ in target_labels:
                entities.append((ent.text, ent.label_))
        return entities

    def _extract_policy_requirements_nlp(self, doc) -> list[tuple[str, str, float]]:
        """
        Extracts policy requirements using spaCy Matcher.
        Returns a list of tuples: (match_id_str, matched_text, confidence_score).
        Confidence score here is basic (1.0 for any match).
        """
        if not self.nlp_available or not self.nlp_matcher or not doc:
            return []

        matches = self.nlp_matcher(doc)
        extracted_requirements = []
        for match_id, start, end in matches:
            match_id_str = self.nlp_model.vocab.strings[match_id] # Get string representation
            span = doc[start:end]
            extracted_requirements.append((match_id_str, span.text, 1.0)) # Basic confidence
        return extracted_requirements

    # --- Regex Fallback Method (remains) ---
    def _analyze_text_sentiment_regex(self, text: str) -> str:
        """
        Performs a very basic keyword-based sentiment analysis on the provided text.
        (This is the original _analyze_text_sentiment method, renamed for clarity)
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
        batch_crawl_timestamp: datetime,
        doc: 'spacy.tokens.Doc | None' = None # Allow passing pre-processed spaCy Doc
    ) -> tuple[float, list[str], dict[str, any]]: # Added nlp_analysis_summary
        """
        Calculates a composite leniency score. Uses NLP if available and `doc` is provided,
        otherwise falls back to regex/keyword-based scoring.

        Returns:
            tuple: (final_score, policy_keywords_matched, nlp_analysis_summary)
                   nlp_analysis_summary contains sentiment, entities, policy_matches from NLP.
        """
        if not text_content:
            return 0.0, [], {}

        base_score = 0
        nlp_score_adjustment = 0
        policy_keywords_matched = [] # For regex-based keywords
        nlp_analysis_summary = {
            "sentiment_label": "neutral", "sentiment_confidence": 0.0,
            "entities": [], "policy_requirements": [], "nlp_used": False
        }

        # --- NLP Processing (if available and doc provided) ---
        if self.nlp_available and self.nlp_model and doc:
            nlp_analysis_summary["nlp_used"] = True

            # 1. NLP Sentiment
            sentiment_label, sentiment_confidence = self._analyze_sentiment_nlp(doc)
            nlp_analysis_summary["sentiment_label"] = sentiment_label
            nlp_analysis_summary["sentiment_confidence"] = sentiment_confidence
            # Adjust score based on NLP sentiment (example adjustment)
            if sentiment_label == "positive": nlp_score_adjustment += 2
            elif sentiment_label == "negative": nlp_score_adjustment -= 2

            # 2. NLP Entity Extraction
            entities = self._extract_entities_nlp(doc)
            nlp_analysis_summary["entities"] = entities
            # Example: Adjust score based on certain entities (e.g., presence of "KYC" as ORG or similar)
            for ent_text, ent_label in entities:
                if "kyc" in ent_text.lower() and ent_label == "ORG": # Simplified check
                    nlp_score_adjustment -= 1


            # 3. NLP Policy Requirements Matching
            policy_requirements = self._extract_policy_requirements_nlp(doc)
            nlp_analysis_summary["policy_requirements"] = policy_requirements
            # Example: Adjust score based on matched policy patterns
            for req_type, req_text, req_confidence in policy_requirements:
                if req_type == "REQUIRES_ID": nlp_score_adjustment -= 3 * req_confidence
                elif req_type == "NO_ID_NEEDED": nlp_score_adjustment += 3 * req_confidence

        # --- Regex/Keyword based scoring (can act as fallback or complement) ---
        text_lower = text_content.lower() # For regex/keyword matching

        # Iterate through ADVANCED_POLICY_PATTERNS for regex scoring
        for pattern_name, pattern_details in ADVANCED_POLICY_PATTERNS.items():
            try:
                if re.search(pattern_details["regex"], text_lower, re.IGNORECASE):
                    base_score += pattern_details["score"]
                    policy_keywords_matched.append(pattern_name) # Log which regex pattern matched
            except Exception as e:
                self.logger.error(f"Error applying regex pattern {pattern_name}: {e}")


        # Combine base keyword score with NLP adjustment
        combined_keyword_nlp_score = base_score + nlp_score_adjustment

        # Source Credibility Weighting
        credibility_weight = self._get_source_credibility(source_url)

        # Temporal Weighting
        temporal_weight = self._calculate_temporal_weight(item_timestamp_str, batch_crawl_timestamp)

        final_score = combined_keyword_nlp_score * credibility_weight * temporal_weight

        self.logger.debug(
            f"Score calc for '{source_url}': BaseRegEx={base_score}, NLPAdjust={nlp_score_adjustment}, "
            f"Credibility={credibility_weight:.2f}, Temporal={temporal_weight:.2f} -> Final Score={final_score:.2f}. NLP Used: {nlp_analysis_summary['nlp_used']}"
        )
        return final_score, policy_keywords_matched, nlp_analysis_summary


    def parse_results(self, raw_data_filepath: str) -> str | None:
        """
        Loads raw search results, processes each item to extract MVNO info,
        calculate leniency scores (using NLP if available), and perform sentiment analysis.
        Saves aggregated data to a new timestamped JSON file.
        """
        raw_results = self._load_raw_data(raw_data_filepath)
        if not raw_results:
            self.logger.error("No raw data to parse.")
            return None

        # NLP mode check is done in __init__. self.nlp_available reflects this.
        if self.nlp_mode == "spacy" and not self.nlp_available:
            self.logger.error("NLP mode is 'spacy' but NLP is not available. Parsing cannot proceed with NLP enhancements as configured.")
            # Depending on strictness, could return None or proceed with regex only.
            # For now, it will proceed and _calculate_leniency_score will use regex.
            # The user is warned at initialization.

        # Use file modification time of raw_data_filepath as batch_crawl_timestamp
        try:
            batch_crawl_timestamp_unix = os.path.getmtime(raw_data_filepath)
            batch_crawl_timestamp = datetime.fromtimestamp(batch_crawl_timestamp_unix, tz=timezone.utc)
        except Exception as e: # pragma: no cover
            self.logger.warning(f"Could not get file modification time for {raw_data_filepath}: {e}. Using current time as batch crawl time.")
            batch_crawl_timestamp = datetime.now(timezone.utc)


        parsed_data = defaultdict(lambda: {
            "sources": [],
            "total_leniency_score": 0.0,
            "mentions": 0,
            "positive_sentiment_mentions": 0, # Based on final sentiment (NLP or regex)
            "negative_sentiment_mentions": 0, # Based on final sentiment
            "neutral_sentiment_mentions": 0,  # Based on final sentiment
            "policy_keywords_matched_counts": defaultdict(int), # For regex patterns
            "aggregated_nlp_entities": defaultdict(int),
            "aggregated_nlp_policy_requirements": defaultdict(int),
            "nlp_sentiment_contributions": {"positive": 0, "negative": 0, "neutral": 0} # Specifically from NLP
        })
        self.logger.info(f"Parser: Starting processing of {len(raw_results)} items. NLP Available: {self.nlp_available}")

        for idx, item in enumerate(raw_results):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            query_source = item.get("query_source", "")
            # Assuming future crawler might provide these:
            # raw_html_content = item.get("raw_html_content")
            # extracted_page_text = item.get("extracted_page_text")
            item_timestamp_str = item.get("published_date")

            mvno_name = self._extract_mvno_name_from_query(query_source)

            text_for_analysis = f"{title} {snippet}".strip() # Primary text for now
            # text_source_type = "snippet_title" # if tracking source of text

            if not text_for_analysis:
                self.logger.warning(f"No text content for item from {link} (query '{query_source}'). Skipping.")
                continue

            doc = None
            if self.nlp_available and self.nlp_model:
                try:
                    doc = self.nlp_model(text_for_analysis)
                except Exception as e:
                    self.logger.error(f"Error processing text with NLP for item {link}: {e}. Will fallback for this item.")

            leniency_score, regex_keywords_matched, nlp_summary = self._calculate_leniency_score(
                text_for_analysis, link, item_timestamp_str, batch_crawl_timestamp, doc
            )

            # Determine final sentiment for this item
            final_sentiment_label = "neutral"
            if nlp_summary.get("nlp_used"):
                final_sentiment_label = nlp_summary["sentiment_label"]
                # Store NLP specific sentiment contribution
                parsed_data[mvno_name]["nlp_sentiment_contributions"][final_sentiment_label] += 1
            else: # Fallback to regex sentiment
                final_sentiment_label = self._analyze_text_sentiment_regex(text_for_analysis.lower())

            # Aggregate data for the MVNO
            parsed_data[mvno_name]["mentions"] += 1
            parsed_data[mvno_name]["total_leniency_score"] += leniency_score

            if final_sentiment_label == "positive":
                parsed_data[mvno_name]["positive_sentiment_mentions"] += 1
            elif final_sentiment_label == "negative":
                parsed_data[mvno_name]["negative_sentiment_mentions"] += 1
            else: # neutral
                parsed_data[mvno_name]["neutral_sentiment_mentions"] +=1


            for keyword in regex_keywords_matched: # These are from ADVANCED_POLICY_PATTERNS
                parsed_data[mvno_name]["policy_keywords_matched_counts"][keyword] += 1

            if nlp_summary.get("nlp_used"):
                for entity_text, entity_label in nlp_summary.get("entities", []):
                    parsed_data[mvno_name]["aggregated_nlp_entities"][f"{entity_label}: {entity_text}"] += 1
                for req_type, req_text, _ in nlp_summary.get("policy_requirements", []):
                    parsed_data[mvno_name]["aggregated_nlp_policy_requirements"][f"{req_type}: {req_text}"] += 1

            source_details = {
                "url": link, "title": title, "snippet": snippet, "query_source": query_source,
                "calculated_score": leniency_score,
                "final_sentiment": final_sentiment_label,
                # "text_source_analysed": text_source_type,
                "item_timestamp_used": item_timestamp_str if item_timestamp_str else batch_crawl_timestamp.isoformat(),
                "nlp_analysis": nlp_summary # Store the whole NLP summary for this source
            }
            parsed_data[mvno_name]["sources"].append(source_details)

        # Calculate average leniency score and finalize structures for JSON
        for mvno, data in parsed_data.items():
            if data["mentions"] > 0:
                data["average_leniency_score"] = data["total_leniency_score"] / data["mentions"]
            else:
                data["average_leniency_score"] = 0.0

            data["policy_keywords_matched_counts"] = dict(data["policy_keywords_matched_counts"])
            data["aggregated_nlp_entities"] = dict(data["aggregated_nlp_entities"])
            data["aggregated_nlp_policy_requirements"] = dict(data["aggregated_nlp_policy_requirements"])
            # nlp_sentiment_contributions is already a dict

        self.logger.info(f"Parsing complete. Processed data for {len(parsed_data)} MVNOs. NLP available: {self.nlp_available}, NLP used in this run (at least once): {any(s['nlp_analysis']['nlp_used'] for mvno_data in parsed_data.values() for s in mvno_data['sources'] if 'nlp_analysis' in s)}")

        # Save processed data
        timestamp_str = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.output_dir, f"parsed_mvno_data_{timestamp_str}.json")
        try:
            # Convert defaultdict to dict for JSON serialization
            serializable_data = {}
            for k, v_defaultdict in parsed_data.items():
                # Convert the main defaultdict for the MVNO to a regular dict
                v_dict = dict(v_defaultdict)
                # Ensure nested defaultdicts are also converted
                v_dict["policy_keywords_matched_counts"] = dict(v_defaultdict.get("policy_keywords_matched_counts", defaultdict(int)))
                v_dict["aggregated_nlp_entities"] = dict(v_defaultdict.get("aggregated_nlp_entities", defaultdict(int)))
                v_dict["aggregated_nlp_policy_requirements"] = dict(v_defaultdict.get("aggregated_nlp_policy_requirements", defaultdict(int)))
                # sources list contains dicts, which are fine.
                # nlp_sentiment_contributions is already a dict.
                serializable_data[k] = v_dict

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
