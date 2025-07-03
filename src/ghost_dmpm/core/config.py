#!/usr/bin/env python3
"""GHOST Protocol Configuration Management"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

class GhostConfig:
    def __init__(self, config_file_name="ghost_config.json", project_root=None):
        self.project_root = self._determine_project_root(project_root)

        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / config_file_name

        self.config = self._load_config() # Load first
        self._init_logging() # Then init logging, as it might use values from config

        # Feature detection
        self.features = {
            "encryption": self._check_encryption(), # cryptography might not be installed
            "nlp": self._check_nlp(), # spacy might not be installed
        }
        # api_mode is typically set from the config file itself.
        # Defaulting it here might override a loaded value if not handled carefully.
        # It's better to rely on get('google_search_mode', 'mock') when needed.

    def _determine_project_root(self, provided_root=None):
        """Determines the project root directory."""
        if provided_root:
            return Path(provided_root).resolve()

        current_path = Path(__file__).resolve().parent
        for _ in range(5): # Search up to 5 levels for a known marker
            if (current_path / "pyproject.toml").exists() or \
               (current_path / ".git").exists() or \
               (current_path / "src").is_dir() and (current_path / "tests").is_dir() : # Common project markers
                return current_path
            if current_path.parent == current_path: # Reached filesystem root
                break
            current_path = current_path.parent

        # Fallback for safety, though ideally a marker should be found.
        # This might happen if package is installed and __file__ is deep in site-packages.
        # For an installed package, user-specific writable locations (appdirs) are better for logs/data.
        # For now, this focuses on running from a repository clone.
        return Path.cwd()


    def _load_config(self):
        """Load configuration with fallback to defaults."""
        loaded_config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
            except json.JSONDecodeError as e:
                # Log error, but proceed to load defaults. An empty/corrupt config is like no config.
                logging.getLogger("GhostConfigInit").error(f"Error decoding JSON from {self.config_file}: {e}. Using defaults.")
            except Exception as e:
                logging.getLogger("GhostConfigInit").error(f"Could not load config file {self.config_file}: {e}. Using defaults.")
        else:
            logging.getLogger("GhostConfigInit").info(f"Config file {self.config_file} not found. Using defaults and attempting to create.")

        # Merge defaults with loaded config, loaded_config takes precedence
        default_cfg = self._get_default_config_values()
        merged_config = {**default_cfg, **loaded_config} # Loaded overrides defaults

        # If the config file didn't exist and we're using defaults, try to save it.
        if not self.config_file.exists() and merged_config:
             try:
                with open(self.config_file, 'w') as f:
                    json.dump(merged_config, f, indent=2)
                logging.getLogger("GhostConfigInit").info(f"Created default config file at {self.config_file}")
             except Exception as e:
                logging.getLogger("GhostConfigInit").error(f"Could not write default config file to {self.config_file}: {e}")

        return merged_config

    def _get_default_config_values(self):
        """Returns the hardcoded default configuration values."""
        return {
            "mvno_list": ["Mint Mobile", "US Mobile", "Visible", "Cricket", "Metro PCS"],
            "keywords": ["no id required", "anonymous", "prepaid", "cash payment"],
            "crawler": {
                "delay_base": 2.0,
                "delay_variance": 0.15,
                "timeout": 30,
                "output_dir": "test_output" # Relative to project_root
            },
            "parser": {
                "output_dir": "test_output" # Relative to project_root
            },
            "database": {
                "path": "data/ghost_data.db", # Relative to project_root
                "encryption_enabled": True # This might be overridden by feature detection
            },
            "dashboard": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "username": "admin", # Example, should be changed
                "password": "ghost2024" # Example, should be changed
            },
            "mcp_server": {
                "host": "0.0.0.0",
                "port": 8765,
                "auth_token": "ghost-mcp-secret-token" # Example, should be changed
            },
            "logging": {
                "level": "INFO",
                "directory": "logs", # Relative to project_root
                "file_name": "ghost_dmpm.log" # Will be prepended with date by _init_logging
            },
            "reports": { # Added section for reporter related paths
                "output_dir": "reports", # Relative to project_root
                "alerts_log_filename": "alerts_log.json"
            },
            "google_search_mode": "mock", # Default mode
        }

    def _check_encryption(self):
        try:
            from cryptography.fernet import Fernet
            Fernet.generate_key() # Test if it can actually be used
            return True
        except Exception: # Broad exception as various issues can occur
            return False

    def _check_nlp(self):
        try:
            import spacy
            # Optional: Try loading a small model to be sure
            # spacy.load("en_core_web_sm")
            return True
        except Exception:
            return False

    def _init_logging(self):
        """Initialize logging configuration using values from self.config."""
        log_conf = self.get("logging", {}) # Get the whole logging dict

        log_dir_name = log_conf.get("directory", "logs") # Default if not in config
        log_base_file_name = log_conf.get("file_name", "ghost_app.log")

        # Ensure log file name includes date, as in original behavior
        dated_log_file_name = f"{datetime.now():%Y%m%d}_{log_base_file_name}"

        log_dir_abs = self.project_root / log_dir_name
        log_dir_abs.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir_abs / dated_log_file_name

        log_level_str = log_conf.get("level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Use a specific logger for the application rather than basicConfig on root
        # This allows other libraries to have their own logging levels.
        app_logger = logging.getLogger("ghost_dmpm_app") # Main app logger
        app_logger.setLevel(log_level)

        # Remove existing handlers to avoid duplication if re-initialized
        for handler in app_logger.handlers[:]:
            app_logger.removeHandler(handler)
            handler.close() # Close handler before removing

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        app_logger.addHandler(stream_handler)

        # If this is the first logger being setup, also configure the root logger minimally
        # to catch any logs from libraries not under "ghost_dmpm_app" namespace if desired.
        # However, it's often better to let libraries manage their own logging.
        # For now, we primarily configure our application's logger.
        # If basicConfig was called by another part of the app already, this might conflict.
        # The approach of getting a named logger and configuring it is generally safer.
        logging.getLogger("GhostConfig").info(f"Logging initialized. Level: {log_level_str}. File: {log_file_path}")


    def get(self, key, default=None):
        """Get configuration value with dot notation support (e.g., 'database.path')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        """Set configuration value with dot notation support and save to file."""
        keys = key.split('.')
        target_dict = self.config
        for k in keys[:-1]:
            if k not in target_dict or not isinstance(target_dict[k], dict):
                target_dict[k] = {} # Create intermediate dicts if they don't exist
            target_dict = target_dict[k]
        target_dict[keys[-1]] = value
        self._save_config()

    def _save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.get_logger("GhostConfig").error(f"Failed to save config to {self.config_file}: {e}")


    def get_api_key(self, service):
        """Get API key for a specific service (e.g., 'google_search')."""
        return self.get(f'api_keys.{service}')

    def set_api_key(self, service, key):
        """Set API key for a service and save configuration."""
        self.set(f'api_keys.{service}', key) # 'set' already calls _save_config

    def get_logger(self, name):
        """Get a logger instance, namespaced under the main app logger."""
        # Ensures loggers are children of "ghost_dmpm_app" so they inherit its settings
        if not name.startswith("ghost_dmpm_app.") and name != "ghost_dmpm_app":
             logger_name = f"ghost_dmpm_app.{name}"
        else:
             logger_name = name
        return logging.getLogger(logger_name)

    def get_absolute_path(self, relative_or_absolute_path_str):
        """
        Resolves a path string. If absolute, returns it as Path.
        If relative, resolves it against project_root.
        """
        if not relative_or_absolute_path_str:
            return None
        path_obj = Path(relative_or_absolute_path_str)
        if path_obj.is_absolute():
            return path_obj
        return self.project_root / path_obj

    # Example of how other modules should get resolved paths:
    # db_path_str = config.get("database.path")
    # actual_db_path = config.get_absolute_path(db_path_str)
    # if actual_db_path:
    #     actual_db_path.parent.mkdir(parents=True, exist_ok=True)
    # else:
    #     # handle error, path not configured
    #
    # This means modules like GhostDatabase should use config.get_absolute_path("database.path")
    # instead of config.project_root / config.get("database.path") directly.
    # I will update GhostDatabase and other modules to use this helper.
