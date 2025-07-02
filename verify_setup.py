import importlib
import os
import sys
import json
import shutil
import time
import base64 # For checking mock fernet direct output

# --- Configuration for the verification script ---
VERIFY_OUTPUT_DIR = "verify_setup_output"
TEST_CONFIG_FILE = os.path.join(VERIFY_OUTPUT_DIR, "verify_config.json")
TEST_KEY_FILE = os.path.join(VERIFY_OUTPUT_DIR, "verify_secret.key")
TEST_DB_DIR = os.path.join(VERIFY_OUTPUT_DIR, "verify_db_files")
TEST_MVNOS_FILE = os.path.join(VERIFY_OUTPUT_DIR, "verify_mvnos.txt")
TEST_KEYWORDS_FILE = os.path.join(VERIFY_OUTPUT_DIR, "verify_keywords.txt")

# --- Helper Functions ---
def print_section(title):
    print(f"\n--- {title} ---")

def print_status(item, success, message=""):
    status_icon = "✓" if success else "✗"
    print(f"  [{status_icon}] {item}{': ' + message if message else ''}")
    return success

def setup_test_environment():
    """Creates a clean output directory for test files."""
    if os.path.exists(VERIFY_OUTPUT_DIR):
        shutil.rmtree(VERIFY_OUTPUT_DIR)
    os.makedirs(VERIFY_OUTPUT_DIR)
    os.makedirs(TEST_DB_DIR)

    with open(TEST_MVNOS_FILE, "w") as f:
        f.write("VerifyMVNO1\n")
    with open(TEST_KEYWORDS_FILE, "w") as f:
        f.write("verify keyword\n")

# --- Main Verification Logic ---
def main():
    setup_test_environment()
    print_section("GHOST DMPM System Verification")

    all_tests_passed = True
    feature_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "overall_status": "PENDING",
        "module_imports": {},
        "cryptography_library_available": False,
        "mock_encryption_functional": False,
        "database_creation_functional": False,
        "mini_cycle_functional": False,
        "notes": []
    }

    # 1. Test All Module Imports
    print_section("Module Import Tests")
    modules_to_test = [
        "ghost_config", "ghost_crypto", "ghost_crawler",
        "ghost_parser", "ghost_reporter", "ghost_db"
    ]
    for module_name in modules_to_test:
        try:
            importlib.import_module(module_name)
            status = print_status(f"Import {module_name}", True, "Successful")
            feature_report["module_imports"][module_name] = {"status": "OK"}
        except ImportError as e:
            status = print_status(f"Import {module_name}", False, f"Failed: {e}")
            feature_report["module_imports"][module_name] = {"status": "FAIL", "error": str(e)}
            all_tests_passed = False

    # Attempt to import cryptography to check its availability for the report
    try:
        importlib.import_module("cryptography.fernet")
        feature_report["cryptography_library_available"] = True
        print_status("Cryptography library (cryptography.fernet)", True, "Available")
    except ImportError:
        feature_report["cryptography_library_available"] = False
        print_status("Cryptography library (cryptography.fernet)", False, "Not available")
        feature_report["notes"].append("Cryptography library not found. System will operate in mock encryption mode.")


    # If core modules failed to import, we might not be able to proceed with other tests.
    if not all_tests_passed: # Check after initial imports
        print("\nCore module import failed. Some subsequent tests might be unreliable or skipped.")
        # Potentially exit or conditionally run other tests

    # Import necessary classes after checking module availability
    try:
        from ghost_config import GhostConfig
        from ghost_crypto import CryptoProvider, MockFernet
        from ghost_db import GhostDatabase
        from ghost_crawler import GhostCrawler
        from ghost_parser import GhostParser
        # Reporter not used in mini-cycle directly to avoid TUI if npyscreen is problematic in some envs
    except ImportError:
        print_status("Importing main classes for tests", False, "One or more core classes could not be imported. Halting detailed tests.")
        feature_report["overall_status"] = "FAIL (Core Class Import)"
        all_tests_passed = False
        # Write report and exit if core classes can't be loaded
        with open(os.path.join(VERIFY_OUTPUT_DIR, "feature_compatibility_report.json"), "w") as f:
            json.dump(feature_report, f, indent=2)
        print(f"\nVerification incomplete due to import failures. Report saved to {VERIFY_OUTPUT_DIR}/feature_compatibility_report.json")
        return not all_tests_passed


    # 2. Verify Mock Encryption Works
    print_section("Mock Encryption Verification")
    try:
        # Test CryptoProvider in forced mock mode
        crypto_prov_mock = CryptoProvider(mode="mock")
        test_data = b"This is a secret message for mock encryption!"
        encrypted = crypto_prov_mock.encrypt(test_data)
        decrypted = crypto_prov_mock.decrypt(encrypted)
        mock_encrypt_ok = test_data == decrypted
        print_status("CryptoProvider (mock mode) encrypt/decrypt", mock_encrypt_ok)
        if not mock_encrypt_ok: all_tests_passed = False
        feature_report["mock_encryption_functional"] = mock_encrypt_ok

        # Additionally check if the encrypted data is valid base64
        try:
            base64.urlsafe_b64decode(encrypted)
            print_status("CryptoProvider (mock mode) output is valid base64", True)
        except Exception:
            print_status("CryptoProvider (mock mode) output is NOT valid base64", False)
            all_tests_passed = False
            feature_report["mock_encryption_functional"] = False


        # Test MockFernet directly (as used by CryptoProvider in mock mode)
        mock_key = MockFernet.generate_key()
        mock_f = MockFernet(mock_key)
        encrypted_direct = mock_f.encrypt(test_data)
        decrypted_direct = mock_f.decrypt(encrypted_direct)
        mock_fernet_direct_ok = test_data == decrypted_direct
        print_status("MockFernet (direct use) encrypt/decrypt", mock_fernet_direct_ok)
        if not mock_fernet_direct_ok: all_tests_passed = False
        # This part of the test also contributes to mock_encryption_functional overall
        feature_report["mock_encryption_functional"] = feature_report["mock_encryption_functional"] and mock_fernet_direct_ok

    except Exception as e:
        print_status("Mock Encryption Verification", False, f"Error during test: {e}")
        all_tests_passed = False
        feature_report["mock_encryption_functional"] = False


    # 3. Check Database Creation & Basic Operations
    print_section("Database Creation and Basic Operations Verification")
    db_test_config = None
    db_instance = None
    try:
        db_test_config = GhostConfig(config_file=TEST_CONFIG_FILE, key_file=TEST_KEY_FILE)
        db_test_config.set("output_dir", VERIFY_OUTPUT_DIR) # Ensure config uses test dir
        db_test_config.set("log_file", os.path.join(VERIFY_OUTPUT_DIR, "verify_db_test.log"))
        # Force mock mode for DB crypto operations in this test for consistency
        db_test_config.set("ENCRYPTION_MODE", "mock")
        db_test_config._setup_logging() # Initialize logging for this config

        # Re-initialize crypto_provider with the new ENCRYPTION_MODE setting
        current_key = db_test_config.crypto_provider.key
        db_test_config.crypto_provider = CryptoProvider(mode=db_test_config.get("ENCRYPTION_MODE"), key=current_key)


        db_instance = GhostDatabase(config_manager=db_test_config, db_dir=TEST_DB_DIR)
        print_status("GhostDatabase initialization", True)

        sample_mvno_name = "TestDB_MVNO"
        sample_data = {
            "average_leniency_score": 7.7,
            "policy_keywords": {"test_db_keyword": 1},
            "sources": [{"url": "dbtest.com", "snippet": "This is a DB test snippet."}]
        }
        db_instance.update_mvno_data(sample_mvno_name, sample_data)
        print_status("GhostDatabase update_mvno_data", True)

        retrieved_data = db_instance.get_mvno_data(sample_mvno_name)
        db_ops_ok = (retrieved_data is not None and
                     retrieved_data.get("average_leniency_score") == 7.7 and
                     "snippet_blob" in retrieved_data.get("sources_summary", [{}])[0])
        print_status("GhostDatabase get_mvno_data & data integrity", db_ops_ok)
        if not db_ops_ok: all_tests_passed = False
        feature_report["database_creation_functional"] = db_ops_ok

        # Verify snippet_blob is "decryptable" (base64 decode) by the provider
        if db_ops_ok and db_test_config.crypto_provider:
            try:
                blob = retrieved_data["sources_summary"][0]["snippet_blob"]
                dec_snippet = db_test_config.crypto_provider.decrypt(blob.encode('utf-8'))
                print_status("Snippet blob decryption (base64 decode)", dec_snippet.decode('utf-8') == "This is a DB test snippet.")
            except Exception as e_dec:
                print_status("Snippet blob decryption", False, f"Failed: {e_dec}")
                all_tests_passed = False
                feature_report["database_creation_functional"] = False

    except Exception as e:
        print_status("Database Verification", False, f"Error during test: {e}")
        all_tests_passed = False
        feature_report["database_creation_functional"] = False


    # 4. Run Mini Crawl->Parse->Store Cycle
    print_section("Mini End-to-End Cycle Verification")
    mini_cycle_ok = False
    try:
        # Use the db_test_config and db_instance from the previous step
        if not db_test_config or not db_instance:
            raise RuntimeError("Config or DB not initialized from previous step, cannot run mini-cycle.")

        # Override MVNO and Keywords files for the mini-cycle
        db_test_config.set("mvno_list_file", TEST_MVNOS_FILE)
        db_test_config.set("keywords_file", TEST_KEYWORDS_FILE)

        # Mini Crawler (relies on mock search)
        mini_crawler = GhostCrawler(config_manager=db_test_config)
        raw_results_file = mini_crawler.run_crawling_cycle(num_results_per_query=1)
        if not raw_results_file or not os.path.exists(raw_results_file):
            raise RuntimeError(f"Mini-crawler failed to produce output. Expected: {raw_results_file}")
        print_status("Mini-Cycle: Crawler output generated", True, raw_results_file)

        # Mini Parser
        mini_parser = GhostParser(config_manager=db_test_config)
        parsed_results_file = mini_parser.parse_results(raw_results_file)
        if not parsed_results_file or not os.path.exists(parsed_results_file):
            raise RuntimeError(f"Mini-parser failed to produce output. Expected: {parsed_results_file}")
        print_status("Mini-Cycle: Parser output generated", True, parsed_results_file)

        # Load parsed data and store in DB
        with open(parsed_results_file, 'r') as f:
            parsed_content = json.load(f)

        stored_in_db = False
        for mvno_name, mvno_data in parsed_content.items():
            db_instance.update_mvno_data(mvno_name, mvno_data) # Uses the existing db_instance
            # Check if data for "VerifyMVNO1" (from TEST_MVNOS_FILE) is in DB
            if db_instance.get_mvno_data("VerifyMVNO1"):
                stored_in_db = True
                break

        if stored_in_db:
            print_status("Mini-Cycle: Data stored in DB", True)
            mini_cycle_ok = True
        else:
            print_status("Mini-Cycle: Data NOT found in DB after store attempt", False)
            all_tests_passed = False

        feature_report["mini_cycle_functional"] = mini_cycle_ok

    except Exception as e:
        print_status("Mini End-to-End Cycle", False, f"Error during test: {e}")
        all_tests_passed = False
        feature_report["mini_cycle_functional"] = False


    # 5. Output Feature Compatibility Report (Summary)
    print_section("Feature Compatibility Report Summary")
    print(f"  Cryptography Library Available: {feature_report['cryptography_library_available']}")
    # Determine expected encryption mode based on report
    expected_encryption = "Fernet (real)" if feature_report["cryptography_library_available"] else "MockFernet (base64)"
    print(f"  Expected System Encryption Mode: {expected_encryption}")
    print(f"  Mock Encryption Functional: {feature_report['mock_encryption_functional']}")
    print(f"  Database Creation & Ops Functional: {feature_report['database_creation_functional']}")
    print(f"  Mini End-to-End Cycle Functional: {feature_report['mini_cycle_functional']}")

    if all_tests_passed:
        feature_report["overall_status"] = "PASS"
        print("\n✓✓✓ All verification checks passed successfully! ✓✓✓")
    else:
        feature_report["overall_status"] = "FAIL"
        print("\n✗✗✗ Some verification checks failed. Please review the output. ✗✗✗")

    # Save the report
    report_path = os.path.join(VERIFY_OUTPUT_DIR, "feature_compatibility_report.json")
    try:
        with open(report_path, "w") as f:
            json.dump(feature_report, f, indent=2)
        print(f"\nDetailed feature compatibility report saved to: {report_path}")
    except Exception as e:
        print(f"\nError saving feature compatibility report: {e}")

    return not all_tests_passed # Return 0 if all passed (success), 1 if any failed


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
