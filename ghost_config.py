#!/usr/bin/env python3
"""GHOST Protocol Configuration Management - Per Document #2, Section 4.1"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

class GhostConfig:
    def __init__(self, config_file="config/ghost_config.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config()
        self._init_logging()

        # Feature detection
        self.features = {
            "encryption": self._check_encryption(),
            "nlp": self._check_nlp(),
            "api_mode": "mock"  # Default to mock
        }

    def _load_config(self):
        """Load configuration with fallback to defaults"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass

        # Default configuration
        return {
            "mvno_list": ["Mint Mobile", "US Mobile", "Visible", "Cricket", "Metro PCS"],
            "keywords": ["no id required", "anonymous", "prepaid", "cash payment"],
            "crawler": {
                "delay_base": 2.0,
                "delay_variance": 0.15,
                "timeout": 30
            },
            "database": {
                "path": "data/ghost_data.db",
                "encryption_enabled": True
            },
            "dashboard": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "username": "admin",
                "password": "ghost2024"
            }
        }

    def _check_encryption(self):
        """Check if cryptography is available"""
        try:
            from cryptography.fernet import Fernet
            return True
        except:
            return False

    def _check_nlp(self):
        """Check if spaCy is available"""
        try:
            import spacy
            return True
        except:
            return False

    def _init_logging(self):
        """Initialize logging configuration"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'logs/ghost_{datetime.now():%Y%m%d}.log'),
                logging.StreamHandler()
            ]
        )

    def get(self, key, default=None):
        """Get configuration value with dot notation support"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save_config()

    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_api_key(self, service):
        """Get API key for service"""
        return self.get(f'api_keys.{service}')

    def set_api_key(self, service, key):
        """Set API key for service"""
        if 'api_keys' not in self.config:
            self.config['api_keys'] = {}
        self.config['api_keys'][service] = key
        self._save_config()

    def get_logger(self, name):
        """Get configured logger"""
        return logging.getLogger(name)
