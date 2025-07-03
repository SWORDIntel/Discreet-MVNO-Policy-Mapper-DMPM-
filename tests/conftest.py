import sys
import os
import pytest
from pathlib import Path

# Add src to path for tests to find the ghost_dmpm package
# This assumes conftest.py is in the 'tests' directory, and 'src' is a sibling of 'tests'
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / 'src'
if src_path.is_dir():
    sys.path.insert(0, str(src_path))
else:
    # Fallback if structure is different or tests are run from an unexpected CWD
    # This might happen if tests are copied elsewhere or if project_root isn't what we think.
    # In a typical `pip install -e .` and `pytest` from root, this shouldn't be an issue.
    print(f"Warning: Could not find 'src' directory at {src_path} from conftest.py. Imports may fail.", file=sys.stderr)


@pytest.fixture(scope="session")
def project_test_root():
    """Provides the root directory of the project for test purposes."""
    return project_root

@pytest.fixture
def test_config(project_test_root):
    """Provide a basic, initialized GhostConfig instance for testing."""
    from ghost_dmpm.core.config import GhostConfig

    # Create a temporary config directory for this test session if it doesn't exist
    # to avoid interfering with actual user config or requiring it.
    # We'll use a config file name that's unlikely to clash.
    test_config_dir = project_test_root / "config_for_pytest"
    test_config_dir.mkdir(parents=True, exist_ok=True)

    test_config_file_name = "pytest_ghost_config.json"
    test_config_path = test_config_dir / test_config_file_name

    # Minimal config content for the test fixture
    # Tests can override specific values as needed.
    # Note: GhostConfig will try to load `project_root/config/pytest_ghost_config.json`
    # if project_root is auto-detected to be the actual project root.
    # By passing `project_root=project_test_root` and `config_file_name` that implies
    # it should look for `project_test_root / "config_for_pytest" / "pytest_ghost_config.json"`
    # if GhostConfig's init is `self.config_dir = self.project_root / "config"`
    # We need to ensure GhostConfig either uses the passed project_root for its config subdirectory
    # or we pass a full path to the config file.
    # The current GhostConfig init is:
    # self.config_dir = self.project_root / "config"
    # self.config_file = self.config_dir / config_file_name
    # So, we should use config_file_name="pytest_ghost_config.json" and ensure
    # project_test_root / "config" / "pytest_ghost_config.json" is what we write to.

    # Let's make the test config live under the actual project_root/config directory
    # but with a specific name for tests.
    actual_config_dir = project_test_root / "config"
    actual_config_dir.mkdir(parents=True, exist_ok=True)
    test_cfg_in_actual_dir_path = actual_config_dir / test_config_file_name

    if not test_cfg_in_actual_dir_path.exists():
        with open(test_cfg_in_actual_dir_path, "w") as f:
            json.dump({
                "google_search_mode": "mock",
                "database": {"path": "data/pytest_test.db"}, # Relative to project_root
                "logging": {"level": "DEBUG", "directory": "logs", "file_name": "pytest_ghost.log"}
            }, f)

    # Instantiate GhostConfig. It will auto-detect project_root.
    # We pass config_file_name so it loads our test-specific config.
    config = GhostConfig(config_file_name=test_config_file_name)
    # Ensure a known mode for tests if not already set by the file
    config.set("google_search_mode", "mock")
    return config

@pytest.fixture
def mock_database(test_config, tmp_path):
    """Provide a test database using a temporary path."""
    from ghost_dmpm.core.database import GhostDatabase

    # Override the database path in the test_config fixture to use tmp_path
    # The original db path in test_config might be "data/pytest_test.db"
    # We want each test using mock_database to have a fresh, isolated DB.
    temp_db_path = tmp_path / "test_temp.db"

    # Create a copy of test_config to modify for this fixture instance
    # Or, if test_config is function-scoped, we can modify it directly.
    # Pytest fixtures are usually recreated if their scope allows.
    # test_config is function-scoped by default.

    original_db_path = test_config.get("database.path")
    test_config.set("database.path", str(temp_db_path)) # Path relative to project_root
                                                        # GhostDatabase will resolve it.
                                                        # Since GhostDatabase uses project_root/config.get("database.path"),
                                                        # and temp_db_path is absolute, this needs care.
                                                        # GhostDatabase: self.db_path = config.project_root / db_relative_path
                                                        # So, database.path in config MUST be relative.
                                                        # We need to make temp_db_path relative to project_root for storage in config.
                                                        # Or, GhostDatabase needs to handle absolute paths in config.

    # Forcing an absolute path into a config key that's expected to be relative:
    # Option A: Make GhostDatabase smarter to detect absolute paths.
    # Option B: (Simpler for now) Store a relative path that points outside,
    #           but this is hacky. e.g. "../../../tmp/pytest-of-user/pytest-0/mock_database0/test_temp.db"
    # Option C: The fixture creates the DB and passes the GhostDatabase instance,
    #           GhostConfig's database.path is not used by THIS GhostDatabase instance.
    #           This means GhostDatabase init needs to accept a direct db_path.

    # Let's assume GhostConfig.set("database.path", "some_name_in_tmp_dir.db")
    # and then GhostDatabase resolves project_root / "some_name_in_tmp_dir.db"
    # This means tmp_path needs to be *under* project_root for this to work easily, or
    # GhostConfig needs to be able to handle absolute paths for certain keys if they are explicitly set.

    # The easiest is to have GhostDatabase accept an absolute path directly for testing.
    # Let's modify GhostDatabase to accept an optional absolute_db_path.
    # For now, let's go with the provided structure, assuming database.path from config is used.
    # We will set database.path to be a path relative to tmp_path, and then make GhostDatabase
    # use tmp_path as its "root" for this specific database. This means GhostDatabase needs
    # to be more flexible or the config needs to be structured differently for this.

    # The prompt's version of this fixture:
    # config = GhostConfig() # This creates a new config instance
    # config.set("database.path", str(tmp_path / "test.db")) # This is an absolute path
    # return GhostDatabase(config)
    # This works if GhostDatabase can take an absolute path from config if it's absolute.
    # The current GhostDatabase: self.db_path = config.project_root / db_relative_path
    # This will fail if db_relative_path is absolute.

    # Let's make GhostDatabase accept an absolute path if provided in config:
    # In GhostDatabase.__init__:
    #   db_path_str = config.get("database.path", "data/ghost_data.db")
    #   db_path_obj = Path(db_path_str)
    #   if db_path_obj.is_absolute():
    #       self.db_path = db_path_obj
    #   else:
    #       self.db_path = config.project_root / db_path_obj
    # This change will be made to database.py separately.
    # For now, assuming that change is made:

    # We use the 'test_config' fixture instance, not a new GhostConfig()
    test_config.set("database.path", str(tmp_path / "test_fixture.db"))

    # Ensure the directory for the temp db exists (tmp_path itself)
    # tmp_path.mkdir(parents=True, exist_ok=True) # tmp_path is a directory fixture, already exists

    db_instance = GhostDatabase(test_config)

    # Restore original db path in test_config if it was changed, to not affect other tests using test_config
    # (This is good practice if test_config were session/module scoped)
    # if original_db_path:
    #    test_config.set("database.path", original_db_path)

    return db_instance

# Placeholder for importing json, will be used by test_config fixture.
# This is just to ensure the linter/static analysis doesn't complain if json is used
# without being imported directly in this file, as it's used inside a string for a file write.
import json
