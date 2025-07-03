"""Unit tests for scheduler functionality"""
import pytest
from unittest.mock import Mock, patch
import schedule # To check scheduled jobs
from ghost_dmpm.enhancements.scheduler import GhostScheduler
from ghost_dmpm.core.config import GhostConfig

@pytest.fixture
def mock_config_for_scheduler():
    config = Mock(spec=GhostConfig)
    config.get_logger.return_value = Mock()
    config.get.side_effect = lambda key, default=None: {
        "scheduler.enabled": True,
        "scheduler.jobs": [
            {
                "name": "test_job_1",
                "function": "test_module:test_function", # Mocked, won't be called
                "interval": {"every": 1, "unit": "minutes"}
            }
        ],
        "logging.level": "DEBUG" # For logger inside scheduler
    }.get(key, default)
    config.get_absolute_path.side_effect = lambda x: x
    return config

def test_scheduler_initialization_loads_jobs(mock_config_for_scheduler):
    """Test scheduler initialization and job loading from config"""
    with patch('ghost_dmpm.enhancements.scheduler.importlib.import_module') as mock_import_module:
        # Mock the function resolution to avoid actual import errors
        mock_module = Mock()
        mock_module.test_function = Mock()
        mock_import_module.return_value = mock_module

        scheduler_instance = GhostScheduler(mock_config_for_scheduler)
        assert scheduler_instance.config == mock_config_for_scheduler

        # Check if schedule library has jobs
        jobs = schedule.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_func is not None # Check if .do() was called
        assert "test_job_1" in jobs[0].tags
    schedule.clear() # Clean up global schedule state

def test_scheduler_disabled_no_jobs_loaded(mock_config_for_scheduler):
    """Test that no jobs are loaded if scheduler is disabled"""
    mock_config_for_scheduler.get.side_effect = lambda key, default=None: {
        "scheduler.enabled": False, # Disabled
        "scheduler.jobs": [{"name": "test_job_1", "function": "tm:tf", "interval": {"every": 1, "unit": "minutes"}}],
        "logging.level": "DEBUG"
    }.get(key, default)

    with patch('ghost_dmpm.enhancements.scheduler.importlib.import_module'):
        GhostScheduler(mock_config_for_scheduler)
        assert len(schedule.get_jobs()) == 0
    schedule.clear()

def test_resolve_task_function_success():
    """Test resolving a valid function string"""
    config = Mock(spec=GhostConfig)
    config.get_logger.return_value = Mock()
    scheduler = GhostScheduler(config) # Config jobs not loaded as get() not fully mocked here for jobs

    with patch('importlib.import_module') as mock_import:
        mock_module = Mock()
        mock_function = Mock()
        mock_module.my_task_func = mock_function
        mock_import.return_value = mock_module

        func = scheduler._resolve_task_function("my_module:my_task_func")
        assert func == mock_function
        mock_import.assert_called_once_with("my_module")

def test_resolve_task_function_failure(mock_config_for_scheduler):
    """Test resolving an invalid function string"""
    # Use mock_config_for_scheduler to get a logger
    scheduler = GhostScheduler(mock_config_for_scheduler) # Jobs will be loaded but we test _resolve_task_function

    with patch('importlib.import_module', side_effect=ImportError("Test Import Error")):
        func = scheduler._resolve_task_function("non_existent_module:non_existent_func")
        assert func is None
        scheduler.logger.error.assert_called()
    schedule.clear()


# Add more test stubs for:
# - Different job types (cron, specific days, 'at' times)
# - Correct parsing of interval units
# - Error handling for malformed job definitions
# - PID file creation/removal in run() (might need integration-like setup or heavy mocking)
# - Scheduler main loop (run()) behavior (likely needs threading and event for testing stop)
