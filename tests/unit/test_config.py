import pytest
from pathlib import Path
import json

# Ensure ghost_dmpm package is importable (handled by conftest.py sys.path modification)
from ghost_dmpm.core.config import GhostConfig

def test_config_initialization_default(tmp_path):
    """Test GhostConfig initialization with default config file name, letting it auto-detect project_root."""
    # For this test, we want GhostConfig to behave as it would in the package,
    # finding its own project_root. We'll create a dummy structure.

    # Simulate a project structure within tmp_path
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch() # Marker for project root detection
    config_dir = project_dir / "config"
    config_dir.mkdir()

    default_config_content = {
        "mvno_list": ["Test MVNO 1", "Test MVNO 2"],
        "keywords": ["test keyword"],
        "database": {"path": "data/test_default.db"}
    }
    with open(config_dir / "ghost_config.json", "w") as f:
        json.dump(default_config_content, f)

    # Instantiate GhostConfig, telling it where the "project" is for this test
    # It should then find project_dir/config/ghost_config.json
    config = GhostConfig(project_root=project_dir) # Pass our simulated project_root

    assert config is not None
    assert config.project_root == project_dir
    assert config.config_file == config_dir / "ghost_config.json"
    assert config.get("mvno_list") == ["Test MVNO 1", "Test MVNO 2"]
    assert config.get("keywords") == ["test keyword"]
    # Check that database path from config is stored as is (relative)
    assert config.get("database.path") == "data/test_default.db"


def test_config_initialization_with_specific_file_and_root(tmp_path):
    """Test GhostConfig with a specific config file name and project_root."""
    project_dir = tmp_path / "another_project"
    project_dir.mkdir()
    config_dir = project_dir / "config" # GhostConfig expects config file in <project_root>/config/
    config_dir.mkdir()

    specific_config_content = {"custom_key": "custom_value"}
    specific_file_name = "my_specific_config.json"
    with open(config_dir / specific_file_name, "w") as f:
        json.dump(specific_config_content, f)

    config = GhostConfig(config_file_name=specific_file_name, project_root=project_dir)

    assert config is not None
    assert config.project_root == project_dir
    assert config.config_file == config_dir / specific_file_name
    assert config.get("custom_key") == "custom_value"


def test_config_fallback_to_defaults_if_file_missing(tmp_path):
    """Test GhostConfig falls back to internal defaults if config file doesn't exist."""
    # project_root where no config file will be found
    project_dir = tmp_path / "no_config_project"
    project_dir.mkdir()
    # (project_dir / "pyproject.toml").touch() # Marker for root, but no config/ghost_config.json

    # GhostConfig will try to load <project_dir>/config/ghost_config.json
    # Since it won't exist, it should use its internal defaults.
    config = GhostConfig(project_root=project_dir)

    assert config is not None
    # Check some default values (assuming these are in GhostConfig's internal defaults)
    assert isinstance(config.get("mvno_list"), list)
    assert len(config.get("mvno_list")) > 0
    assert config.get("crawler.delay_base") is not None


def test_config_get_set(tmp_path):
    """Test getting and setting config values."""
    project_dir = tmp_path / "get_set_project"
    project_dir.mkdir()
    config_dir = project_dir / "config"
    config_dir.mkdir()

    config_file_name = "get_set_test.json"
    initial_content = {"original_key": "original_value"}
    config_file_path = config_dir / config_file_name
    with open(config_file_path, "w") as f:
        json.dump(initial_content, f)

    config = GhostConfig(config_file_name=config_file_name, project_root=project_dir)

    # Test get
    assert config.get("original_key") == "original_value"
    assert config.get("non_existent_key") is None
    assert config.get("non_existent_key", "default_val") == "default_val"

    # Test set new key
    config.set("new.nested.key", "new_value")
    assert config.get("new.nested.key") == "new_value"

    # Test overwrite existing key
    config.set("original_key", "updated_value")
    assert config.get("original_key") == "updated_value"

    # Verify that changes were saved to the file
    with open(config_file_path, "r") as f:
        saved_config = json.load(f)
    assert saved_config["new"]["nested"]["key"] == "new_value"
    assert saved_config["original_key"] == "updated_value"


def test_config_get_api_key(tmp_path):
    """Test API key retrieval."""
    project_dir = tmp_path / "api_key_project"
    project_dir.mkdir()
    config_dir = project_dir / "config"
    config_dir.mkdir()

    config_file_name = "api_test_config.json"
    initial_content = {
        "api_keys": {
            "google_search": "test_google_key",
            "another_service": "test_another_key"
        }
    }
    with open(config_dir / config_file_name, "w") as f:
        json.dump(initial_content, f)

    config = GhostConfig(config_file_name=config_file_name, project_root=project_dir)

    assert config.get_api_key("google_search") == "test_google_key"
    assert config.get_api_key("another_service") == "test_another_key"
    assert config.get_api_key("non_existent_service") is None


def test_config_set_api_key(tmp_path):
    """Test setting API keys."""
    project_dir = tmp_path / "set_api_key_project"
    project_dir.mkdir()
    config_dir = project_dir / "config"
    config_dir.mkdir()

    config_file_name = "set_api_config.json"
    config_file_path = config_dir / config_file_name
    # Start with an empty config file for this test
    with open(config_file_path, "w") as f:
        json.dump({}, f)

    config = GhostConfig(config_file_name=config_file_name, project_root=project_dir)

    config.set_api_key("service1", "key1")
    assert config.get_api_key("service1") == "key1"

    config.set_api_key("service2", "key2")
    assert config.get_api_key("service2") == "key2"

    # Check if saved to file
    with open(config_file_path, "r") as f:
        saved_config = json.load(f)
    assert saved_config["api_keys"]["service1"] == "key1"
    assert saved_config["api_keys"]["service2"] == "key2"


def test_config_logging_initialization(tmp_path):
    """Test that logging is initialized and paths are correct."""
    project_dir = tmp_path / "logging_test_project"
    project_dir.mkdir()
    # (project_dir / "pyproject.toml").touch() # Root marker

    log_dir_name = "test_logs_custom"
    log_file_name_custom = "my_app_test.log"

    config_dir = project_dir / "config"
    config_dir.mkdir()
    config_file_path = config_dir / "logging_config.json"

    with open(config_file_path, "w") as f:
        json.dump({
            "logging": {
                "level": "DEBUG",
                "directory": log_dir_name, # Relative to project_root
                "file_name": log_file_name_custom
            }
        }, f)

    # GhostConfig will use project_dir as root, and load logging_config.json
    config = GhostConfig(config_file_name="logging_config.json", project_root=project_dir)

    # Check that the log directory and file would be created correctly
    # GhostConfig._init_logging creates these.
    expected_log_dir = project_dir / log_dir_name
    expected_log_file = expected_log_dir / log_file_name_custom

    assert expected_log_dir.exists()
    # We can't easily check if logging.FileHandler is pointing to expected_log_file
    # without inspecting internal state of logging module or FileHandler instance.
    # But we can check if the directory was created.
    # A more thorough test would capture log output or mock logging.FileHandler.

    # For now, primarily testing that config values are read for logging path construction.
    # The actual log file creation test is implicit via GhostConfig running _init_logging.
    # If a file exists at expected_log_file after init, that's a good sign.
    # This depends on GhostConfig actually writing a log line during init or soon after.
    # A simple check is if the directory was made.

    # Check that a logger can be obtained
    logger = config.get_logger("TestLogger")
    assert logger is not None
    # Check if the logger's level is set (might be tricky as it could be inherited)
    # This depends on how _init_logging sets levels (e.g., root logger vs specific).
    # For this test, it's enough that it runs without error and paths seem right.
    assert logger.level == pytest.approx(0) or logger.level == logging.DEBUG # Effective level for DEBUG might be 0 for root

    # After config init, the log file should exist if logging was set up and something was logged.
    # GhostConfig logs messages during init, so the file should be there.
    # Adjust for the date prepended by _init_logging
    from datetime import datetime
    dated_log_file_name = f"{datetime.now():%Y%m%d}_{log_file_name_custom}"
    expected_dated_log_file = expected_log_dir / dated_log_file_name

    assert expected_dated_log_file.exists(), f"Log file {expected_dated_log_file} was not created."
    assert expected_dated_log_file.is_file()

# Example of how to use the test_config fixture from conftest.py
def test_with_conftest_fixture(test_config):
    """Test using the test_config fixture from conftest.py."""
    assert test_config is not None
    assert test_config.get("google_search_mode") == "mock" # Set by fixture
    # The database path in the fixture's config file is "data/pytest_test.db"
    assert test_config.get("database.path") == "data/pytest_test.db"
    # Fixture also sets logging level to DEBUG
    assert test_config.get("logging.level") == "DEBUG"

    logger = test_config.get_logger("FixtureTest")
    assert logger.level == pytest.approx(0) or logger.level == logging.DEBUG

    # Check if the log file specified in pytest_ghost_config.json was created
    # (relative to project_root detected by GhostConfig when fixture ran)
    log_dir_name = test_config.get("logging.directory")
    log_base_file_name = test_config.get("logging.file_name") # e.g., "pytest_ghost.log"

    log_dir_abs = test_config.project_root / log_dir_name

    from datetime import datetime
    dated_log_file_name = f"{datetime.now():%Y%m%d}_{log_base_file_name}"
    expected_dated_log_file = log_dir_abs / dated_log_file_name

    assert expected_dated_log_file.exists(), f"Log file {expected_dated_log_file} from fixture was not created."
    assert expected_dated_log_file.is_file()

# TODO: Add tests for feature detection (encryption, nlp) if GhostConfig exposes them more directly
# or if their effects can be easily tested via config values.
# Current features are attributes like config.features['encryption'], which could be checked.
# def test_config_feature_detection(test_config_with_crypto_and_spacy, test_config_without_crypto_or_spacy):
# pass
