#!/usr/bin/env python3
# setup_monitoring.py
from ghost_config import GhostConfig
from ghost_scheduler import GhostScheduler
import os

# This script configures scheduler settings in the main config.json
# and exports a cron entry.

config = GhostConfig() # Loads root config.json

# Define a dummy task for GhostScheduler instantiation, as it's required.
# This task won't actually be run by this script.
def dummy_scheduled_task():
    print("Dummy scheduled task for GhostScheduler configuration.")

# Initialize GhostScheduler to allow accessing its methods like export_cron_entry
# It will also apply scheduler settings from the config if they exist, or use defaults.
# The act of instantiating it doesn't start the scheduling loop here.
# We pass the dummy task.
scheduler = GhostScheduler(config, dummy_scheduled_task)

# Configure scheduler settings in config.json
# These values will be set and saved to the root config.json
config.set("scheduler", {
    "enabled": True, # Note: This enables it in config, but scheduler.start() is needed to run it.
    "interval_hours": 24,
    "variance_percent": 30,
    "start_time": "02:00",  # 2 AM UTC - This is a conceptual setting, GhostScheduler itself doesn't use 'start_time' currently
                            # It uses interval + variance from the moment it's started or last ran.
                            # For cron, this start_time is more relevant.
    "state_file": ".ghost_schedule_state.json", # Default, but good to be explicit
    "dead_man_switch_hours": 48, # Default
    "dms_check_interval_hours": 6 # Default
})

print("Scheduler settings configured in config.json:")
print(f"  Enabled: {config.get('scheduler', {}).get('enabled')}")
print(f"  Interval: {config.get('scheduler', {}).get('interval_hours')} hours")
print(f"  Variance: {config.get('scheduler', {}).get('variance_percent')}%")
print(f"  Conceptual Start Time (for cron): {config.get('scheduler', {}).get('start_time')}")


# Re-initialize scheduler with the new config to make export_cron_entry use updated interval
# (though export_cron_entry primarily uses interval_hours which was already default or set)
# This isn't strictly necessary if export_cron_entry only reads from config directly,
# but good practice if scheduler instance variables matter for the export.
# GhostScheduler's export_cron_entry reads interval_hours directly from self.interval_hours
# which is set during __init__ from the config at that time.
# So, we should re-init or update its internal variables if config changed *after* its init.
scheduler.interval_hours = config.get('scheduler', {}).get('interval_hours', 24) # Update instance var

# Export cron entry for system integration
# The export_cron_entry method needs to know the path to the main script to run.
# Let's assume main.py in the current directory is the target.
main_script_path = os.path.abspath("main.py")
python_executable = "python3" # Or determine dynamically: import sys; sys.executable

cron_entry = scheduler.export_cron_entry(python_path=python_executable, script_path=main_script_path)
print("\nAdd this to crontab to run the main GHOST cycle:")
print(cron_entry)

# The prompt mentions "Start scheduler (for testing - normally run as service)"
# but the python code provided for setup_monitoring.py does not start it.
# It only prints "Run 'python -m ghost_scheduler' to start monitoring."
# The ghost_scheduler.py itself, when run as a module, would start the loop.
print("\nScheduler configured in config.json.")
print("To start the actual scheduler daemon (if this machine were to run it):")
print(f"Execute: {python_executable} -m ghost_scheduler")

print("\nsetup_monitoring.py finished.")
