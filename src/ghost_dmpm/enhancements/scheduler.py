"""
Scheduled task system for GHOST DMPM
Supports: Cron syntax, interval-based, one-time tasks.
Uses the 'schedule' library for underlying job management.
"""

import schedule
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from functools import partial # For calling methods with arguments
import os # For PID file management

# Assuming GhostConfig is accessible
from ghost_dmpm.core.config import GhostConfig
# To dynamically call functions by name (e.g., for main.py cycle, reporter)
import importlib

class GhostScheduler:
    """
    Manages scheduled tasks for GHOST DMPM operations like crawls and report generation.
    """
    def __init__(self, config: GhostConfig):
        """
        Initializes the GhostScheduler.

        Args:
            config (GhostConfig): The system's configuration object.
        """
        self.config = config
        self.logger = config.get_logger("GhostScheduler")
        # state_file is for future use if we persist dynamically added jobs.
        # self.jobs_file_path = config.get_absolute_path(config.get("scheduler.state_file", "data/.scheduler_state.json"))

        self._load_jobs_from_config()
        self.logger.info(f"Scheduler initialized. {len(schedule.get_jobs())} job(s) currently scheduled.")

    def _resolve_task_function(self, function_string: str) -> Optional[Callable]:
        """
        Resolves a function string (e.g., 'module.submodule:function_name') to a callable.
        """
        try:
            module_path, function_name = function_string.split(':')
            module = importlib.import_module(module_path)
            return getattr(module, function_name)
        except (ValueError, ImportError, AttributeError) as e:
            self.logger.error(f"Could not resolve task function '{function_string}': {e}")
            return None
        except Exception as e: # Catch any other unexpected import error
            self.logger.error(f"Unexpected error resolving task function '{function_string}': {e}", exc_info=True)
            return None


    def _load_jobs_from_config(self):
        """
        Loads job definitions from the main application configuration (e.g., ghost_config.json)
        and schedules them.
        """
        if not self.config.get("scheduler.enabled", False):
            self.logger.info("Scheduler is disabled in configuration. No jobs will be loaded or run.")
            schedule.clear() # Clear any existing jobs if scheduler is disabled
            return

        configured_jobs = self.config.get("scheduler.jobs", [])
        if not configured_jobs:
            self.logger.info("No jobs found in 'scheduler.jobs' configuration.")
            return

        schedule.clear() # Clear any previously loaded jobs before loading new ones

        for job_def in configured_jobs:
            name = job_def.get("name")
            function_str = job_def.get("function")
            cron_schedule_str = job_def.get("cron_schedule")
            interval_def = job_def.get("interval")
            job_args = job_def.get("args", [])
            job_kwargs = job_def.get("kwargs", {})
            job_tags = [name, 'ghost_dmpm_task'] # Default tags
            if job_def.get("tags") and isinstance(job_def.get("tags"), list):
                job_tags.extend(job_def.get("tags"))

            if not name or not function_str:
                self.logger.warning(f"Skipping job with missing name or function: {job_def}")
                continue

            task_func = self._resolve_task_function(function_str)
            if not task_func:
                self.logger.warning(f"Skipping job '{name}' due to unresolvable function '{function_str}'.")
                continue

            job_instance_setup = None # This will be like `schedule.every().monday`

            # Cron-based scheduling (Simplified)
            if cron_schedule_str:
                parts = cron_schedule_str.split()
                if len(parts) == 5:
                    minute, hour, day_of_month, month, day_of_week_cron = parts
                    time_str = f"{hour.zfill(2)}:{minute.zfill(2)}" if hour != '*' and minute != '*' else None

                    if time_str:
                        if day_of_week_cron != '*' and day_of_month == '*' and month == '*': # Specific day of week
                            days_map = {"1": "monday", "2": "tuesday", "3": "wednesday", "4": "thursday", "5": "friday", "6": "saturday", "0": "sunday", "7": "sunday",
                                        "mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday", "fri": "friday", "sat": "saturday", "sun": "sunday"}
                            day_method_name = days_map.get(day_of_week_cron.lower())
                            if day_method_name:
                                job_instance_setup = getattr(schedule.every(), day_method_name).at(time_str)
                            else:
                                self.logger.warning(f"Unsupported day_of_week '{day_of_week_cron}' for cron job '{name}'.")
                        elif day_of_week_cron == '*' and day_of_month == '*' and month == '*': # Daily
                            job_instance_setup = schedule.every().day.at(time_str)
                        # TODO: Add support for specific day_of_month if needed, schedule lib doesn't directly support it like cron.
                        else:
                            self.logger.warning(f"Cron string '{cron_schedule_str}' for job '{name}' has unsupported day/month specifics for simple mapping.")
                    else:
                        self.logger.warning(f"Cron string '{cron_schedule_str}' for job '{name}' must specify hour and minute for simple mapping.")
                else:
                    self.logger.warning(f"Invalid cron_schedule format for job '{name}': {cron_schedule_str}. Expected 5 parts.")

            # Interval-based scheduling
            elif interval_def and isinstance(interval_def, dict):
                unit = interval_def.get("unit", "minutes").lower()
                every_val = interval_def.get("every", 1)
                at_time = interval_def.get("at") # Optional specific time for daily/hourly intervals e.g. "HH:MM" or ":MM" for hourly

                if not isinstance(every_val, int) or every_val <= 0:
                    self.logger.warning(f"Invalid 'every' value '{every_val}' for interval job '{name}'.")
                    continue

                current_job = schedule.every(every_val)

                if unit in ["second", "seconds"]: job_instance_setup = current_job.seconds
                elif unit in ["minute", "minutes"]: job_instance_setup = current_job.minutes
                elif unit in ["hour", "hours"]: job_instance_setup = current_job.hours
                elif unit in ["day", "days"]: job_instance_setup = current_job.days
                elif unit in ["week", "weeks"]: job_instance_setup = current_job.weeks
                # For specific days like "monday", "tuesday"
                elif hasattr(schedule.every(), unit): # e.g. unit is "monday"
                    job_instance_setup = getattr(schedule.every(), unit) # schedule.every().monday
                else:
                    self.logger.warning(f"Unsupported interval unit '{unit}' for job '{name}'.")

                if job_instance_setup and at_time and isinstance(at_time, str):
                    if hasattr(job_instance_setup, 'at'):
                         try:
                            job_instance_setup = job_instance_setup.at(at_time)
                         except schedule.ScheduleValueError as e:
                            self.logger.warning(f"Invalid 'at' time '{at_time}' for job '{name}': {e}")
                            job_instance_setup = None # Invalidate job if 'at' is bad
                    else:
                        self.logger.warning(f"'at' time specification not supported for unit '{unit}' in job '{name}'.")


            if job_instance_setup:
                # Use partial to include arguments correctly with schedule's .do()
                task_with_args = partial(task_func, *job_args, **job_kwargs)
                final_job = job_instance_setup.do(task_with_args).tag(*job_tags)
                self.logger.info(f"Scheduled job '{name}' (Function: {function_str}). Next run: {final_job.next_run}")
            else:
                self.logger.warning(f"Could not schedule job '{name}' due to invalid or unsupported schedule definition.")

    def schedule_crawl(self, cron_expression: str, crawl_args: Optional[Dict] = None):
        """Schedules a periodic web crawl. Illustrative - prefer config."""
        self.logger.warning("Programmatic schedule_crawl is illustrative. Define jobs in config.")
        # For a real implementation, this would construct a job_def and call a method like _add_job_dynamically
        # or directly use `schedule` library if dynamic additions are simple enough.

    def schedule_report(self, frequency: str, recipients: List[str], report_args: Optional[Dict] = None):
        """Schedules report generation. Illustrative - prefer config."""
        self.logger.warning("Programmatic schedule_report is illustrative. Define jobs in config.")

    def run(self):
        """
        Starts the scheduler's main loop. This is a blocking call.
        """
        if not self.config.get("scheduler.enabled", False):
            # Logged during _load_jobs_from_config if disabled
            return

        self.logger.info("Starting scheduler main loop...")
        pid_file_path_str = self.config.get("scheduler.pid_file", "data/scheduler.pid")
        pid_file = self.config.get_absolute_path(pid_file_path_str)

        try:
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            self.logger.info(f"Scheduler PID {os.getpid()} written to {pid_file}")
        except IOError as e:
            self.logger.error(f"Could not write PID file to {pid_file}: {e}")
            # Depending on policy, might choose to exit if PID file is critical
            # For now, log and continue.

        try:
            while True:
                runnable_jobs = schedule.get_jobs()
                if not runnable_jobs:
                    self.logger.info("No jobs scheduled. Scheduler idling for 60s. Will re-check config if dynamic reloading is implemented.")
                    time.sleep(60) # Sleep longer if no jobs
                    # TODO: Optionally implement dynamic config reloading here if state_file changes
                    continue

                schedule.run_pending()

                idle_seconds = schedule.idle_seconds()
                if idle_seconds is None: # Should not happen if runnable_jobs is not empty
                    sleep_duration = 60
                elif idle_seconds <= 0:
                     sleep_duration = 0.1 # Minimal sleep if jobs are due, to yield CPU
                else:
                    sleep_duration = min(idle_seconds, 60) # Sleep at most 60s, or until next job

                time.sleep(sleep_duration)
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user (KeyboardInterrupt).")
        except Exception as e:
            self.logger.error(f"Scheduler encountered an unhandled error in main loop: {e}", exc_info=True)
        finally:
            self.logger.info("Scheduler shutdown initiated.")
            if pid_file.exists():
                try:
                    os.remove(pid_file)
                    self.logger.info(f"PID file {pid_file} removed.")
                except OSError as e:
                    self.logger.error(f"Error removing PID file {pid_file}: {e}")
            schedule.clear()
            self.logger.info("All scheduled jobs cleared.")

# Example task function for testing the scheduler itself
def example_task_func(message: str, extra_param: str = "default_extra"):
    """A simple task function for demonstration."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] EXECUTE_TASK: '{message}' with extra_param: '{extra_param}'"
    print(log_msg)
    logging.getLogger("ExampleScheduledTask").info(log_msg)


if __name__ == '__main__':
    # This __main__ is for direct testing of the scheduler.
    # It uses a MockConfigForScheduler.

    # Setup basic logging for the example run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("SchedulerExampleMain")

    main_logger.info("Starting GhostScheduler example...")

    class MockConfigForScheduler:
        def __init__(self):
            self.project_root = Path(__file__).resolve().parent.parent.parent
            self.data = {
                "scheduler": {
                    "enabled": True,
                    "pid_file": "data/scheduler_test.pid",
                    "jobs": [
                        {
                            "name": "echo_seconds",
                            "function": "ghost_dmpm.enhancements.scheduler:example_task_func",
                            "interval": {"every": 15, "unit": "seconds"},
                            "args": ["15 Second Echo"],
                            "kwargs": {"extra_param": "from_config_15s"}
                        },
                        {
                            "name": "echo_minute_at_10s",
                            "function": "ghost_dmpm.enhancements.scheduler:example_task_func",
                            "interval": {"every": 1, "unit": "minutes", "at": ":10"}, # Every minute at 10 seconds past
                            "args": ["Minute Echo at :10"],
                        },
                        {
                             "name": "daily_echo_at_specific_time", # Replace with a future time for testing
                             "function": "ghost_dmpm.enhancements.scheduler:example_task_func",
                             # For testing, set this to a time a few minutes in the future
                             # "cron_schedule": "YOUR_MINUTE YOUR_HOUR * * *", # e.g. "30 14 * * *" for 2:30 PM
                             # Using interval for easier testing:
                             "interval": {"every": 5, "unit": "minutes", "at": ":00"}, # Every 5 mins on the minute
                             "args": ["5 Minute Interval Echo (on the minute)"],
                        }
                    ]
                },
                "logging": {"level": "DEBUG"} # Use DEBUG for more verbose output from scheduler
            }
            (self.project_root / "data").mkdir(exist_ok=True) # Ensure data dir for PID

        def get(self, key, default=None):
            keys = key.split('.')
            val = self.data
            try:
                for k_part in keys: val = val[k_part]
                return val
            except KeyError: return default

        def get_absolute_path(self, relative_path_str: str) -> Path:
            return self.project_root / relative_path_str

        def get_logger(self, name):
            logger = logging.getLogger(name)
            # Example __main__ already configures basicConfig, so just ensure level
            logger.setLevel(self.get("logging.level", "INFO").upper())
            return logger

    mock_config_instance = MockConfigForScheduler()
    scheduler_instance = GhostScheduler(config=mock_config_instance)

    try:
        scheduler_instance.run()
    except KeyboardInterrupt:
        main_logger.info("Example scheduler run interrupted by user.")
    finally:
        main_logger.info("Example scheduler run finished.")

# Add to src/ghost_dmpm/enhancements/__init__.py:
# from .scheduler import GhostScheduler
# __all__ = [..., 'GhostScheduler']
#
# Config structure for ghost_config.json (Refer to comments at the end of the original example)
# ... (cron_schedule parsing notes, job persistence notes, error recovery notes)
