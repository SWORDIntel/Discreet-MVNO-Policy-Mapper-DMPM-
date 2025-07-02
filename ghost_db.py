import json
import os
import time
import hashlib
from datetime import datetime, timezone
from ghost_config import GhostConfig # To access CryptoProvider if needed, or pass provider directly

# Define a path for the database file within the output directory
DB_FILENAME = "ghost_dmpm_database.json"
# Define a path for the historical data file
HISTORY_FILENAME = "ghost_dmpm_history.json"

# Migration path comment
# TODO: When real encryption is enforced, a migration script will be needed to:
#   1. Read all base64 encoded "blobs" from the database.
#   2. Decrypt them using MockFernet (i.e., base64 decode).
#   3. Re-encrypt them using the real Fernet cipher.
#   4. Update the database with the new, truly encrypted blobs.
#   This process should be idempotent if possible.

class GhostDatabase:
    """
    Manages persistence for GHOST DMPM, including MVNO data, policy change detection,
    and historical trend analysis. "Encryption" is handled via CryptoProvider.
    """
    def __init__(self, config_manager: GhostConfig, db_dir: str = None):
        """
        Initializes the GhostDatabase.

        Args:
            config_manager (GhostConfig): The application's configuration manager,
                                          providing access to CryptoProvider and output_dir.
            db_dir (str, optional): Directory to store database files. Defaults to
                                    config_manager's output_dir.
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostDatabase")

        if not hasattr(config_manager, 'crypto_provider') or not config_manager.crypto_provider:
            self.logger.error("CryptoProvider not found in GhostConfig. Database encryption will fail/be mocked without proper setup.")
            # In a real scenario, might raise an error or have a more robust fallback.
            # For now, operations requiring crypto_provider will likely fail if it's None.
            self.crypto_provider = None
        else:
            self.crypto_provider = config_manager.crypto_provider
            self.logger.info(f"GhostDatabase initialized with CryptoProvider in '{self.crypto_provider.effective_mode}' mode.")

        self.db_dir = db_dir if db_dir else self.config_manager.get("output_dir", "output")
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
            self.logger.info(f"Database directory created: {self.db_dir}")

        self.db_filepath = os.path.join(self.db_dir, DB_FILENAME)
        self.history_filepath = os.path.join(self.db_dir, HISTORY_FILENAME)

        self.data = self._load_db()
        self.history = self._load_history()

    def _load_db(self) -> dict:
        """Loads the main database from a JSON file."""
        if os.path.exists(self.db_filepath):
            try:
                with open(self.db_filepath, "r") as f:
                    db_content = json.load(f)
                self.logger.info(f"Database loaded from {self.db_filepath}")
                return db_content
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON from {self.db_filepath}. Starting with an empty DB.")
            except Exception as e:
                self.logger.error(f"Error loading database from {self.db_filepath}: {e}. Starting fresh.")
        return {}

    def _save_db(self):
        """Saves the main database to a JSON file."""
        try:
            with open(self.db_filepath, "w") as f:
                json.dump(self.data, f, indent=4)
            self.logger.info(f"Database saved to {self.db_filepath}")
        except Exception as e:
            self.logger.error(f"Error saving database to {self.db_filepath}: {e}")

    def _load_history(self) -> dict:
        """Loads historical data from a JSON file."""
        if os.path.exists(self.history_filepath):
            try:
                with open(self.history_filepath, "r") as f:
                    hist_content = json.load(f)
                self.logger.info(f"Historical data loaded from {self.history_filepath}")
                return hist_content
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON from {self.history_filepath}. Starting with empty history.")
            except Exception as e:
                self.logger.error(f"Error loading history from {self.history_filepath}: {e}. Starting fresh.")
        return {} # { "mvno_name": [ {timestamp, score, policy_flags_hash}, ... ] }

    def _save_history(self):
        """Saves historical data to a JSON file."""
        try:
            with open(self.history_filepath, "w") as f:
                json.dump(self.history, f, indent=4)
            self.logger.info(f"Historical data saved to {self.history_filepath}")
        except Exception as e:
            self.logger.error(f"Error saving history to {self.history_filepath}: {e}")

    def _hash_policy_data(self, policy_data: dict) -> str:
        """
        Creates a SHA256 hash of relevant policy data to detect changes.
        Args:
            policy_data (dict): A dictionary representing key policy aspects.
                                Example: {"id_required": true, "payment_types": ["cash", "card"]}
        Returns:
            str: A SHA256 hash string.
        """
        # Sort the dictionary by keys to ensure consistent hash for the same data
        # Convert all values to string to handle various data types consistently
        # Using json.dumps with sort_keys ensures a canonical representation
        canonical_string = json.dumps(policy_data, sort_keys=True)
        return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

    def update_mvno_data(self, mvno_name: str, parsed_mvno_info: dict):
        """
        Updates or adds data for a given MVNO. Handles "encryption" of sensitive blobs,
        policy change detection, and logs historical data.

        Args:
            mvno_name (str): The name of the MVNO.
            parsed_mvno_info (dict): Parsed data for the MVNO from GhostParser.
                                     Expected to contain fields like 'average_leniency_score',
                                     'policy_keywords', and potentially raw text snippets
                                     or source URLs that might be stored as "encrypted" blobs.
        """
        if not self.crypto_provider:
            self.logger.error(f"Cannot update MVNO {mvno_name}: CryptoProvider is not available.")
            return

        timestamp_iso = datetime.now(timezone.utc).isoformat()

        # --- "Encrypt" sensitive parts of parsed_mvno_info if any ---
        # Example: Let's assume 'sources' contains snippets that should be "encrypted"
        encrypted_sources = []
        if "sources" in parsed_mvno_info and isinstance(parsed_mvno_info["sources"], list):
            for source_item in parsed_mvno_info["sources"]:
                item_copy = source_item.copy()
                if "snippet" in item_copy and item_copy["snippet"]:
                    try:
                        snippet_bytes = item_copy["snippet"].encode('utf-8')
                        encrypted_snippet = self.crypto_provider.encrypt(snippet_bytes)
                        # Store as base64 string (CryptoProvider returns bytes, base64 encoding is URL-safe)
                        item_copy["snippet_blob"] = encrypted_snippet.decode('utf-8')
                        del item_copy["snippet"] # Remove plaintext snippet
                    except Exception as e:
                        self.logger.error(f"Error 'encrypting' snippet for {mvno_name}: {e}")
                        item_copy["snippet_blob"] = "Error during encryption" # Placeholder
                encrypted_sources.append(item_copy)

        # Construct current policy data for hashing and storage
        # This should include key aspects that define its leniency profile
        current_policy_details = {
            "keywords": parsed_mvno_info.get("policy_keywords", {}),
            "score": parsed_mvno_info.get("average_leniency_score", 0)
            # Add other relevant fields that define the policy state, e.g.,
            # "id_requirement_level": parsed_mvno_info.get("id_level"),
            # "payment_options_summary": parsed_mvno_info.get("payment_summary")
        }
        current_policy_hash = self._hash_policy_data(current_policy_details)

        # --- Policy Change Detection ---
        previous_record = self.data.get(mvno_name)
        change_detected = False
        if previous_record:
            previous_policy_hash = previous_record.get("policy_hash")
            if previous_policy_hash != current_policy_hash:
                change_detected = True
                self.logger.info(f"Policy change detected for MVNO: {mvno_name}. Old hash: {previous_policy_hash}, New hash: {current_policy_hash}")
            else:
                self.logger.info(f"No policy change detected for MVNO: {mvno_name} (hash: {current_policy_hash}).")
        else:
            self.logger.info(f"New MVNO detected: {mvno_name}. Storing initial policy state.")
            change_detected = True # Treat new entry as a change for historical logging

        # --- Update Main Database Record ---
        db_record = {
            "mvno_name": mvno_name,
            "last_updated": timestamp_iso,
            "average_leniency_score": parsed_mvno_info.get("average_leniency_score"),
            "mentions": parsed_mvno_info.get("mentions"),
            "positive_sentiment_mentions": parsed_mvno_info.get("positive_sentiment_mentions"),
            "negative_sentiment_mentions": parsed_mvno_info.get("negative_sentiment_mentions"),
            "policy_keywords_summary": parsed_mvno_info.get("policy_keywords", {}), # Store summary
            "aggregated_nlp_entities": parsed_mvno_info.get("aggregated_nlp_entities",{}),
            "sources_summary": encrypted_sources, # Store "encrypted" sources
            "policy_hash": current_policy_hash,
            "change_detected_on_last_update": change_detected
        }
        self.data[mvno_name] = db_record
        self._save_db()

        # --- Historical Trend Analysis Logging ---
        if change_detected or not previous_record : # Log if change or new
            if mvno_name not in self.history:
                self.history[mvno_name] = []

            historical_entry = {
                "timestamp": timestamp_iso,
                "average_leniency_score": db_record["average_leniency_score"],
                "policy_hash": current_policy_hash,
                # You could add more specific policy flags here if needed for trends
                # e.g., "id_required_flag": True/False based on keywords
            }
            self.history[mvno_name].append(historical_entry)
            # Optional: Limit history size per MVNO
            max_history_entries = self.config_manager.get("db_max_history_per_mvno", 100)
            if len(self.history[mvno_name]) > max_history_entries:
                self.history[mvno_name] = self.history[mvno_name][-max_history_entries:]

            self._save_history()

        self.logger.info(f"Data for MVNO '{mvno_name}' updated. Change detected: {change_detected}")

    def get_mvno_data(self, mvno_name: str) -> dict | None:
        """
        Retrieves data for a specific MVNO, "decrypting" blobs if necessary.

        Args:
            mvno_name (str): The name of the MVNO.

        Returns:
            dict | None: The MVNO's data, or None if not found.
                         "Encrypted" blobs will be returned as base64 strings.
                         For actual use, they would need to be decoded by the consumer.
        """
        record = self.data.get(mvno_name)
        if record and self.crypto_provider:
            # Example: "Decrypt" snippets if they were stored in 'sources_summary'
            # Note: This returns the base64 string. The caller would decode if needed.
            # For true decryption, the decrypt method would be used.
            # Here, we are just showing how to access the potentially "encrypted" (base64'd) blob.
            if "sources_summary" in record:
                for source_item in record["sources_summary"]:
                    if "snippet_blob" in source_item:
                        # To actually "decrypt" (base64 decode):
                        # try:
                        #    decoded_snippet_bytes = self.crypto_provider.decrypt(source_item["snippet_blob"].encode('utf-8'))
                        #    source_item["snippet_decrypted"] = decoded_snippet_bytes.decode('utf-8')
                        # except Exception as e:
                        #    self.logger.error(f"Error 'decrypting' snippet_blob for {mvno_name}: {e}")
                        #    source_item["snippet_decrypted"] = "Error during decryption"
                        pass # Blobs are kept as base64 strings in this example get method
            return record
        elif not self.crypto_provider:
             self.logger.warning(f"CryptoProvider not available, cannot properly process MVNO data for {mvno_name}")
             return record # Return raw record, blobs might not be handled correctly
        return None

    def get_historical_trends(self, mvno_name: str) -> list[dict] | None:
        """
        Retrieves historical trend data for a specific MVNO.

        Args:
            mvno_name (str): The name of the MVNO.

        Returns:
            list[dict] | None: A list of historical data points (timestamp, score, hash),
                               or None if no history for the MVNO.
        """
        return self.history.get(mvno_name)

    def detect_policy_change(self, mvno_name: str, new_policy_data_summary: dict) -> bool:
        """
        Compares a new policy data summary with the stored one for an MVNO.

        Args:
            mvno_name (str): The name of the MVNO.
            new_policy_data_summary (dict): A dictionary representing the new policy state
                                            (e.g., as created by _hash_policy_data).
        Returns:
            bool: True if a change is detected or if the MVNO is new, False otherwise.
        """
        current_record = self.data.get(mvno_name)
        if not current_record:
            return True # New MVNO is considered a change

        new_hash = self._hash_policy_data(new_policy_data_summary)
        old_hash = current_record.get("policy_hash")

        return new_hash != old_hash

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Setup a mock GhostConfig and CryptoProvider for testing
    # In a real app, GhostConfig would be instantiated and passed.
    class MockCryptoProvider:
        def __init__(self, mode="mock", key=None):
            self.effective_mode = mode
            self.key = key if key else b"mock_key_for_db_test"
            self.logger = logging.getLogger("MockCryptoProviderForDB") # Use standard logging

        def encrypt(self, data: bytes) -> bytes:
            self.logger.info(f"MockEncrypt: {data[:30]}...")
            return base64.urlsafe_b64encode(data)

        def decrypt(self, token: bytes) -> bytes:
            self.logger.info(f"MockDecrypt: {token[:30]}...")
            return base64.urlsafe_b64decode(token)

    class MockGhostConfig:
        def __init__(self, output_dir_name="test_db_output"):
            self.output_dir = output_dir_name
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            self.crypto_provider = MockCryptoProvider() # Use the mock crypto for DB tests
            self.config = {"output_dir": self.output_dir, "db_max_history_per_mvno": 5}

        def get_logger(self, name):
            logger = logging.getLogger(name)
            if not logger.handlers: # Setup basic logging if not configured
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            return logger

        def get(self, key, default=None):
            return self.config.get(key, default)

    print("--- GhostDatabase Example Usage ---")
    # Ensure the test output directory exists and is clean for the test
    test_output_dir = "db_example_output"
    if os.path.exists(test_output_dir):
        # Clean up old DB files for a fresh test run
        for f_name in [DB_FILENAME, HISTORY_FILENAME]:
            f_path = os.path.join(test_output_dir, f_name)
            if os.path.exists(f_path):
                os.remove(f_path)
    else:
        os.makedirs(test_output_dir)

    mock_config = MockGhostConfig(output_dir_name=test_output_dir)
    db = GhostDatabase(config_manager=mock_config)

    # Sample MVNO data (as if from GhostParser)
    mvno1_data_v1 = {
        "average_leniency_score": 4.5,
        "mentions": 10,
        "positive_sentiment_mentions": 7,
        "negative_sentiment_mentions": 1,
        "policy_keywords": {"no id required": 2, "cash payment": 1},
        "sources": [{"url": "example.com/page1", "snippet": "US Mobile is great, no ID needed sometimes."}]
    }
    mvno1_data_v2 = { # Simulating a policy change
        "average_leniency_score": 3.0, # Score changed
        "mentions": 12,
        "positive_sentiment_mentions": 6,
        "negative_sentiment_mentions": 3,
        "policy_keywords": {"id required for all plans": 1, "cash payment": 0}, # Keywords changed
        "sources": [{"url": "example.com/page2", "snippet": "US Mobile now requires ID for all plans."}]
    }
    mvno2_data_v1 = {
        "average_leniency_score": -2.0,
        "mentions": 5,
        "positive_sentiment_mentions": 1,
        "negative_sentiment_mentions": 4,
        "policy_keywords": {"ssn mandatory": 3},
        "sources": [{"url": "example.org/review", "snippet": "Visible needs SSN, not good for privacy."}]
    }

    # Update MVNO data (first time)
    print("\nUpdating MVNO1 (v1) and MVNO2 (v1)...")
    db.update_mvno_data("US Mobile Example", mvno1_data_v1)
    db.update_mvno_data("Visible Example", mvno2_data_v1)

    # Retrieve and print data
    print("\nRetrieving MVNO1 data...")
    retrieved_mvno1 = db.get_mvno_data("US Mobile Example")
    if retrieved_mvno1:
        print(f"MVNO: {retrieved_mvno1['mvno_name']}, Score: {retrieved_mvno1['average_leniency_score']}")
        print(f"  Policy Hash: {retrieved_mvno1['policy_hash']}")
        if retrieved_mvno1.get("sources_summary"):
             print(f"  First source snippet blob: {retrieved_mvno1['sources_summary'][0].get('snippet_blob', 'N/A')[:50]}...")


    # Simulate a policy change for MVNO1 and update
    print("\nUpdating MVNO1 (v2) - simulating policy change...")
    db.update_mvno_data("US Mobile Example", mvno1_data_v2)
    retrieved_mvno1_v2 = db.get_mvno_data("US Mobile Example")
    if retrieved_mvno1_v2:
        print(f"MVNO: {retrieved_mvno1_v2['mvno_name']}, New Score: {retrieved_mvno1_v2['average_leniency_score']}")
        print(f"  New Policy Hash: {retrieved_mvno1_v2['policy_hash']}")
        print(f"  Change detected on last update: {retrieved_mvno1_v2['change_detected_on_last_update']}")


    # Get historical trends for MVNO1
    print("\nRetrieving historical trends for MVNO1...")
    trends_mvno1 = db.get_historical_trends("US Mobile Example")
    if trends_mvno1:
        print(f"Found {len(trends_mvno1)} historical entries for US Mobile Example:")
        for entry in trends_mvno1:
            print(f"  - Timestamp: {entry['timestamp']}, Score: {entry['average_leniency_score']}, Hash: {entry['policy_hash'][:10]}...")

    # Test policy change detection method directly
    policy_summary_v1_direct = {
        "keywords": mvno1_data_v1.get("policy_keywords", {}),
        "score": mvno1_data_v1.get("average_leniency_score", 0)
    }
    policy_summary_v2_direct = {
         "keywords": mvno1_data_v2.get("policy_keywords", {}),
        "score": mvno1_data_v2.get("average_leniency_score", 0)
    }
    print(f"\nDirect change detection for MVNO1 (v1 vs v1): {db.detect_policy_change('US Mobile Example', policy_summary_v1_direct)}") # Should be False
    print(f"Direct change detection for MVNO1 (v1 vs v2): {db.detect_policy_change('US Mobile Example', policy_summary_v2_direct)}") # Should be True
    print(f"Direct change detection for NewMVNO: {db.detect_policy_change('NewMVNO Example', policy_summary_v1_direct)}") # Should be True


    print(f"\n--- GhostDatabase Example Complete ---")
    print(f"Database files are in: {db.db_dir}")
    print(f"Main DB: {db.db_filepath}")
    print(f"History DB: {db.history_filepath}")

    # Test a non-existent MVNO
    print("\nRetrieving non-existent MVNO data...")
    retrieved_non_existent = db.get_mvno_data("NonExistent MVNO")
    if not retrieved_non_existent:
        print("Correctly returned None for non-existent MVNO.")

    # Test history for non-existent MVNO
    print("\nRetrieving history for non-existent MVNO...")
    history_non_existent = db.get_historical_trends("NonExistent MVNO")
    if not history_non_existent:
        print("Correctly returned None for history of non-existent MVNO.")

    import base64 # For the snippet blob check in main example
    print("--- Done with GhostDatabase main example ---")
