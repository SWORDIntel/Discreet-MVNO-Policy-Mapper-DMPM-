# ghost_scheduler.py

import schedule
import time
import random
import json
import os
import threading
from datetime import datetime, timedelta

from ghost_config import GhostConfig # For configuration access

class GhostScheduler:
    """
    Manages scheduling of GHOST Protocol DMPM operations.
    """
    DEFAULT_SCHEDULE_STATE_FILE = ".ghost_schedule_state.json"
    DEFAULT_DEAD_MAN_SWITCH_HOURS = 48 # Alert if no successful run in this many hours

    def __init__(self, config_manager: GhostConfig, ghost_task_function, task_args=None, task_kwargs=None):
        """
        Initializes the GhostScheduler.

        Args:
            config_manager (GhostConfig): The application's configuration manager.
            ghost_task_function (callable): The function to be scheduled (e.g., main.run_full_cycle).
            task_args (tuple, optional): Arguments to pass to the ghost_task_function.
            task_kwargs (dict, optional): Keyword arguments to pass to the ghost_task_function.
        """
        self.config_manager = config_manager
        self.logger = self.config_manager.get_logger("GhostScheduler")
        self.ghost_task_function = ghost_task_function
        self.task_args = task_args if task_args is not None else ()
        self.task_kwargs = task_kwargs if task_kwargs is not None else {}

        scheduler_config = self.config_manager.get("scheduler", {})
        self.is_enabled = scheduler_config.get("enabled", False)
        self.interval_hours = scheduler_config.get("interval_hours", 24)
        self.variance_percent = scheduler_config.get("variance_percent", 30) # e.g., 30%

        self.schedule_state_file = os.path.join(
            self.config_manager.get("output_dir", "output"), # Store state in output dir
            scheduler_config.get("state_file", self.DEFAULT_SCHEDULE_STATE_FILE)
        )
        self.dead_man_switch_hours = scheduler_config.get("dead_man_switch_hours", self.DEFAULT_DEAD_MAN_SWITCH_HOURS)

        self._stop_event = threading.Event()
        self._thread = None
        self._load_state() # Load last run state

        if self.is_enabled:
            self.logger.info(f"Scheduler is ENABLED. Interval: {self.interval_hours}hrs, Variance: {self.variance_percent}%.")
            self._schedule_ghost_job()
        else:
            self.logger.info("Scheduler is DISABLED via configuration.")

    def _job_wrapper(self):
        """Wraps the ghost_task_function to include logging and state updates."""
        self.logger.info("Scheduler starting GHOST task execution...")
        try:
            self.ghost_task_function(*self.task_args, **self.task_kwargs)
            self.logger.info("GHOST task execution completed successfully by scheduler.")
            self.last_successful_run = datetime.now().isoformat()
            self._save_state()
        except Exception as e:
            self.logger.error(f"Error during scheduled GHOST task execution: {e}", exc_info=True)

        # Reschedule for the next run with new variance
        # Clear previous schedule first to avoid multiple accumulating schedules if wrapper is called directly
        schedule.clear('ghost-main-task') # Clear by tag
        self._schedule_ghost_job() # Reschedule with new randomization

    def _calculate_varied_interval(self) -> float:
        """Calculates the next run interval in seconds with variance."""
        base_interval_seconds = self.interval_hours * 3600
        variance_amount = base_interval_seconds * (self.variance_percent / 100.0)

        # Calculate random offset: can be +/- variance_amount/2 to center around interval
        # Or, can be 0 to +variance_amount to always delay. Let's do +/-.
        random_offset = random.uniform(-variance_amount / 2, variance_amount / 2)

        varied_interval = base_interval_seconds + random_offset

        # Ensure interval is not excessively short (e.g., minimum 1 hour or 10% of base interval)
        min_practical_interval = max(3600, base_interval_seconds * 0.1)
        final_interval = max(min_practical_interval, varied_interval)

        self.logger.info(f"Base interval: {self.interval_hours}hrs. Calculated next run in: {final_interval / 3600:.2f}hrs.")
        return final_interval # in seconds

    def _schedule_ghost_job(self):
        """Schedules the main GHOST task with randomization."""
        if not self.is_enabled:
            return

        next_run_seconds = self._calculate_varied_interval()
        # Schedule the job to run once after 'next_run_seconds'
        # Then, _job_wrapper will call this method again to set up the *next* randomized run.
        # Using a tag 'ghost-main-task' to manage it.
        schedule.every(next_run_seconds).seconds.do(self._job_wrapper).tag('ghost-main-task')

        # Log the time of the next scheduled job
        if schedule.jobs:
            next_run_time = schedule.next_run()
            if next_run_time:
                 self.logger.info(f"GHOST task scheduled. Next estimated run: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
                 self.next_scheduled_run_time_for_state = next_run_time.isoformat() # For saving state
                 self._save_state() # Save updated next run time

    def _run_scheduler_loop(self):
        """The main loop for the scheduler thread."""
        self.logger.info("GhostScheduler thread started.")
        # Initial check for dead man's switch on startup, then rely on periodic checks
        self._check_dead_mans_switch(startup_check=True)

        # Schedule a periodic check for the dead man's switch
        # e.g. every 6 hours, or configurable
        dms_check_interval_hours = self.config_manager.get("scheduler",{}).get("dms_check_interval_hours", 6)
        schedule.every(dms_check_interval_hours).hours.do(self._check_dead_mans_switch).tag('dms-check')
        self.logger.info(f"Dead man's switch check scheduled every {dms_check_interval_hours} hours.")

        while not self._stop_event.is_set():
            schedule.run_pending()
            time.sleep(1) # Check every second
        self.logger.info("GhostScheduler thread stopped.")

    def start(self):
        """Starts the scheduler in a new thread if enabled."""
        if not self.is_enabled:
            self.logger.info("Scheduler not starting as it is disabled.")
            return

        if self._thread and self._thread.is_alive():
            self.logger.warning("Scheduler thread already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the scheduler thread."""
        if self._thread and self._thread.is_alive():
            self.logger.info("Stopping GhostScheduler thread...")
            self._stop_event.set()
            self._thread.join(timeout=5) # Wait for thread to finish
            if self._thread.is_alive(): # pragma: no cover
                 self.logger.warning("GhostScheduler thread did not stop in time.")
        else:
            self.logger.info("GhostScheduler thread not running or already stopped.")
        schedule.clear() # Clear all scheduled jobs

    def _save_state(self):
        """Saves the last successful run time and next scheduled time to a file."""
        state = {
            "last_successful_run": getattr(self, 'last_successful_run', None),
            "next_scheduled_run_for_persistence": getattr(self, 'next_scheduled_run_time_for_state', None)
        }
        try:
            # Ensure output_dir exists
            os.makedirs(os.path.dirname(self.schedule_state_file), exist_ok=True)
            with open(self.schedule_state_file, "w") as f:
                json.dump(state, f)
            self.logger.debug(f"Scheduler state saved to {self.schedule_state_file}")
        except Exception as e: # pragma: no cover
            self.logger.error(f"Failed to save scheduler state: {e}")

    def _load_state(self):
        """Loads the last run time from a file."""
        self.last_successful_run = None
        self.next_scheduled_run_time_for_state = None # From persistence
        if os.path.exists(self.schedule_state_file):
            try:
                with open(self.schedule_state_file, "r") as f:
                    state = json.load(f)
                    self.last_successful_run = state.get("last_successful_run")
                    self.next_scheduled_run_time_for_state = state.get("next_scheduled_run_for_persistence")
                    if self.last_successful_run:
                        self.logger.info(f"Loaded last successful run time: {self.last_successful_run}")
                    if self.next_scheduled_run_time_for_state:
                         self.logger.info(f"Loaded next scheduled run time (from persistence): {self.next_scheduled_run_time_for_state}")
            except Exception as e: # pragma: no cover
                self.logger.error(f"Failed to load scheduler state: {e}")
        else:
            self.logger.info("No scheduler state file found. Starting fresh.")

    def _check_dead_mans_switch(self, startup_check=False):
        """
        Checks if the last successful run was too long ago.
        Logs a critical error or triggers an alert (placeholder).
        """
        action_prefix = "[Dead Man's Switch]"
        if startup_check:
            action_prefix = "[Dead Man's Switch - Startup Check]"

        if not self.last_successful_run:
            if not startup_check : # Only log if it's not the initial startup and we expected a run
                 self.logger.warning(f"{action_prefix} No last successful run time recorded. Cannot check DMS yet.")
            return

        try:
            last_run_dt = datetime.fromisoformat(self.last_successful_run)
            if (datetime.now() - last_run_dt) > timedelta(hours=self.dead_man_switch_hours):
                alert_message = (
                    f"{action_prefix} CRITICAL: Last successful GHOST task run was at {self.last_successful_run}, "
                    f"which is more than the configured {self.dead_man_switch_hours} hours ago. "
                    "System may not be operating as expected."
                )
                self.logger.critical(alert_message)
                # Placeholder for actual alerting (e.g., email, external system)
                # self.send_alert(alert_message)
            else:
                self.logger.info(f"{action_prefix} Check OK. Last successful run was at {self.last_successful_run}.")
        except Exception as e: # pragma: no cover
            self.logger.error(f"{action_prefix} Error checking dead man's switch: {e}")

    def export_cron_entry(self, python_path="python3", script_path="main.py") -> str:
        """
        Generates an example cron job entry string.
        Assumes the main script can be run directly to perform one cycle.
        The interval for cron is based on self.interval_hours, but cron doesn't support variance easily.
        This provides a fixed-interval cron entry.
        """
        # For cron, we usually use a fixed schedule. Variance is harder.
        # This will generate an entry based on the fixed interval_hours.
        # Example: if interval_hours is 24, it runs once a day at midnight.
        # If interval_hours is < 24, like 6, it runs every 6 hours.

        cron_hour_setting = "*"
        cron_minute_setting = "0" # Default to top of the hour

        if self.interval_hours >= 24: # Daily or more
            cron_day_interval = self.interval_hours // 24
            cron_hour_setting = "0" # Midnight
            if cron_day_interval > 0 :
                 cron_schedule = f"{cron_minute_setting} {cron_hour_setting} */{cron_day_interval} * *"
            else: # Should not happen if interval_hours >= 24
                 cron_schedule = f"{cron_minute_setting} {cron_hour_setting} * * *"
        else: # Hourly, less than 24h
            cron_hour_interval = self.interval_hours
            if 24 % cron_hour_interval == 0: # e.g. every 1, 2, 3, 4, 6, 8, 12 hours
                cron_schedule = f"{cron_minute_setting} */{cron_hour_interval} * * *"
            else: # Irregular hours, cron doesn't handle "every 7 hours" easily. Use closest.
                  # Or just run it hourly and let the script decide if it's time.
                  # For simplicity, let's recommend running it more frequently and letting script's internal logic manage.
                  # This export is just a suggestion.
                self.logger.warning(f"Interval {self.interval_hours}hrs is not a clean divisor of 24 for cron. Generating hourly cron and suggesting script manages frequency.")
                cron_schedule = f"{cron_minute_setting} * * * *"


        # Ensure script_path is absolute or relative to a known location for cron
        abs_script_path = os.path.abspath(script_path)
        log_dir = os.path.abspath(self.config_manager.get("output_dir", "output"))
        cron_log_file = os.path.join(log_dir, "ghost_cron.log")

        # Change to script's directory before running, then execute
        script_dir = os.path.dirname(abs_script_path)
        script_basename = os.path.basename(abs_script_path)

        cron_command = f"cd {script_dir} && {python_path} {script_basename} --run-once >> {cron_log_file} 2>&1"
        full_cron_entry = f"{cron_schedule} {cron_command}"

        self.logger.info(f"Example cron entry generated: {full_cron_entry}")
        return full_cron_entry

if __name__ == '__main__':
    # Example Usage (conceptual, needs a dummy task and config)

    class MockMainTaskRunner:
        def __init__(self):
            self.run_count = 0
        def run_full_cycle(self, *args, **kwargs):
            logger = logging.getLogger("MockGhostTask")
            logger.info(f"Mock GHOST Full Cycle Run CALLED with args: {args}, kwargs: {kwargs}")
            self.run_count +=1
            # Simulate work
            time.sleep(2)
            if self.run_count % 3 == 0: # Simulate an error occasionally
                # raise ValueError("Simulated error in GHOST task!")
                pass
            logger.info("Mock GHOST Full Cycle Run COMPLETED.")

    # Setup basic logging for the example
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    example_logger = logging.getLogger("SchedulerExample")

    example_output_dir = "scheduler_example_output"
    if not os.path.exists(example_output_dir):
        os.makedirs(example_output_dir)

    # Create a dummy GhostConfig for the scheduler
    # In a real app, this would be the main config instance
    dummy_config_file = os.path.join(example_output_dir, "dummy_scheduler_config.json")
    dummy_key_file = os.path.join(example_output_dir, "dummy_scheduler_key.key") # Not strictly needed if crypto is off

    try:
        # This will create default config if not exists.
        config = GhostConfig(config_file=dummy_config_file, key_file=dummy_key_file)
        config.set("output_dir", example_output_dir)
        config.set("log_file", os.path.join(example_output_dir, "scheduler_example.log"))
        # Configure scheduler settings for the example
        config.set("scheduler", {
            "enabled": True,
            "interval_hours": 0.002, # Run every ~7 seconds for testing (0.002 hours)
            "variance_percent": 20,   # 20% variance
            "state_file": ".example_schedule_state.json",
            "dead_man_switch_hours": 0.01 # ~36 seconds for testing DMS
        })
        config._setup_logging() # Re-init with example log path
        example_logger = config.get_logger("SchedulerExample") # Use config's logger
    except Exception as e:
        example_logger.error(f"Failed to init GhostConfig for scheduler example: {e}. Some features might not work.")
        # Fallback config if GhostConfig fails completely
        class DummyCfg:
            def __init__(self): self.config = {"scheduler": {"enabled": True, "interval_hours": 0.002, "variance_percent": 10}}
            def get(self, k, d=None): return self.config.get(k, d) if k != "output_dir" else example_output_dir
            def get_logger(self, name): return logging.getLogger(name)
        config = DummyCfg()


    task_runner = MockMainTaskRunner()

    # Instantiate scheduler
    # Pass arguments to the task if needed: task_args=("arg1",), task_kwargs={"key": "value"}
    scheduler = GhostScheduler(config, task_runner.run_full_cycle)

    if config.get("scheduler", {}).get("enabled"):
        example_logger.info("Starting scheduler for example run...")
        scheduler.start()

        # Export example cron entry
        cron_entry = scheduler.export_cron_entry(script_path="/opt/ghost/main.py")
        example_logger.info(f"Suggested cron entry: {cron_entry}")

        try:
            example_logger.info("Scheduler running in background. Press Ctrl+C to stop example.")
            # Keep the main thread alive for a while to see scheduler work
            for i in range(150): # Run for ~150 seconds to see a few cycles
                if scheduler._stop_event.is_set(): break
                time.sleep(1)
        except KeyboardInterrupt:
            example_logger.info("Ctrl+C received. Stopping scheduler example.")
        finally:
            scheduler.stop()
            example_logger.info("Scheduler example finished.")
    else:
        example_logger.info("Scheduler is disabled in config. Example will not run scheduling loop.")

    example_logger.info(f"Total mock GHOST task runs: {task_runner.run_count}")
    example_logger.info(f"Scheduler example files (log, state) are in '{example_output_dir}'")
