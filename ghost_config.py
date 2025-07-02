import json
import logging
import os
from cryptography.fernet import Fernet

class GhostConfig:
    """
    Manages configuration settings for the GHOST Protocol DMPM application.
    Handles loading, saving, and encrypting configuration data, including API keys.
    Also sets up application-wide logging.
    """
    def __init__(self, config_file="config.json", key_file="secret.key"):
        """
        Initializes the GhostConfig manager.

        Args:
            config_file (str): Path to the configuration file (JSON, will be encrypted).
            key_file (str): Path to the file storing the encryption key.
        """
        self.config_file = config_file
        self.key_file = key_file
        self.config = {}
        self.cipher_suite = None
        self._load_key()
        self._load_config()
        self._setup_logging()

    def _generate_key(self):
        """
        Generates a new Fernet encryption key and saves it to the key_file.

        Returns:
            bytes: The generated encryption key.
        """
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as f:
            f.write(key)
        return key

    def _load_key(self):
        """Loads the encryption key from key_file or generates a new one if not found."""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                key = f.read()
        else:
            key = self._generate_key()
        self.cipher_suite = Fernet(key)

    def _load_config(self):
        """
        Loads the configuration from the config_file.
        If the file exists and contains data, it attempts to decrypt and load it.
        If the file doesn't exist, is empty, or decryption fails,
        a default configuration is initialized and saved.
        Ensures the output directory specified in the config exists.
        """
        if os.path.exists(self.config_file):
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()
            if encrypted_data:
                try:
                    decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                    self.config = json.loads(decrypted_data.decode())
                except Exception as e:
                    logging.error(f"Error decrypting or loading config: {e}. Reinitializing config.")
                    self.config = {"api_keys": {}, "mvno_list_file": "mvnos.txt", "keywords_file": "keywords.txt", "output_dir": "output"}
                    self.save_config() # Save a fresh config if decryption fails
            else: # File is empty
                self.config = {"api_keys": {}, "mvno_list_file": "mvnos.txt", "keywords_file": "keywords.txt", "output_dir": "output"}
                self.save_config()
        else:
            # Default configuration
            self.config = {"api_keys": {}, "mvno_list_file": "mvnos.txt", "keywords_file": "keywords.txt", "output_dir": "output"}
            self.save_config()

        # Ensure default output directory exists
        output_dir = self.get("output_dir", "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)


    def save_config(self):
        """
        Encrypts the current configuration dictionary and saves it to the config_file.
        Logs success or error.
        """
        try:
            data_to_encrypt = json.dumps(self.config).encode()
            encrypted_data = self.cipher_suite.encrypt(data_to_encrypt)
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)
            logging.info("Configuration saved successfully.")
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")

    def get(self, key, default=None):
        """
        Retrieves a configuration value for the given key.

        Args:
            key (str): The configuration key to retrieve.
            default (any, optional): The default value to return if the key is not found.
                                     Defaults to None.

        Returns:
            any: The value associated with the key, or the default value.
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """
        Sets a configuration value for the given key and saves the entire configuration.

        Args:
            key (str): The configuration key to set.
            value (any): The value to set for the key.
        """
        self.config[key] = value
        self.save_config()

    def get_api_key(self, service_name):
        """
        Retrieves a specific API key from the 'api_keys' dictionary in the configuration.

        Args:
            service_name (str): The name of the service for which to retrieve the API key
                                (e.g., "google_search").

        Returns:
            str or None: The API key if found, otherwise None.
        """
        return self.config.get("api_keys", {}).get(service_name)

    def set_api_key(self, service_name, api_key):
        """
        Sets a specific API key in the 'api_keys' dictionary and saves the configuration.

        Args:
            service_name (str): The name of the service for which to set the API key.
            api_key (str): The API key value.
        """
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        self.config["api_keys"][service_name] = api_key
        self.save_config()

    def _setup_logging(self):
        """
        Sets up basic logging for the application based on configuration values.
        Configures logging level, format, and handlers (file and stream).
        The log file path is determined by 'log_file' or defaults to 'output/ghost_app.log'.
        """
        log_level_str = self.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Remove existing handlers from the root logger before reconfiguring
        # This makes _setup_logging idempotent if called multiple times.
        root = logging.getLogger()
        if root.handlers:
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                handler.close() # Close the handler before removing

        log_file_path = self.get("log_file")
        if not log_file_path:
            # Fallback if log_file is somehow not set, though main.py should set it.
            log_file_path = os.path.join(self.get("output_dir", "output"), "ghost_app_fallback.log")
            # Ensure this fallback path directory exists
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            logging.warning(f"Log file path not explicitly configured, falling back to {log_file_path}")


        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file_path),
                logging.StreamHandler()
            ]
        )
        logging.info("Logging re-initialized via _setup_logging.") # Changed message for clarity

    def get_logger(self, name):
        """
        Returns a logger instance for the given name.

        Args:
            name (str): The name for the logger (e.g., module name or class name).

        Returns:
            logging.Logger: An instance of the logger.
        """
        return logging.getLogger(name)

if __name__ == '__main__':
    # Example Usage of GhostConfig
    # This demonstrates how to initialize, set, get configurations, and use logging.
    print("--- GhostConfig Example Usage ---")

    # Create unique names for this example to avoid conflicts if other modules also write these
    example_config_file = "example_app_config.json"
    example_key_file = "example_app_secret.key"
    example_output_dir = "example_output"

    if not os.path.exists(example_output_dir):
        os.makedirs(example_output_dir)

    config_manager = GhostConfig(config_file=example_config_file, key_file=example_key_file)
    # Override output_dir for this example if it was set by default config load
    config_manager.set("output_dir", example_output_dir) # Ensure logs for example go to example_output
    config_manager.set("log_file", os.path.join(example_output_dir, "ghost_config_example.log"))
    config_manager._setup_logging() # Re-init logging with example-specific paths

    print(f"Using config file: {example_config_file}, key file: {example_key_file}")

    # Set some example configurations
    config_manager.set("app_version", "1.0.0")
    config_manager.set("search_delay_seconds", 5)
    config_manager.set_api_key("google_search", "YOUR_GOOGLE_API_KEY_HERE") # Replace with a real key for actual use

    # Retrieve configurations
    print(f"App Version: {config_manager.get('app_version')}")
    print(f"Search Delay: {config_manager.get('search_delay_seconds')} seconds")
    print(f"Google API Key: {config_manager.get_api_key('google_search')}")

    # Test logging
    logger = config_manager.get_logger("GhostConfigExample")
    logger.info("GhostConfig example application started.")
    logger.warning("This is an example warning message from GhostConfig example.")
    logger.error("This is an example error message from GhostConfig example.")

    # Demonstrate loading an existing config
    print("\nReloading config from same files...")
    config_manager_reloaded = GhostConfig(config_file=example_config_file, key_file=example_key_file)
    print(f"Reloaded App Version: {config_manager_reloaded.get('app_version')}")
    print(f"Reloaded Google API Key: {config_manager_reloaded.get_api_key('google_search')}")
    print(f"Log file should be: {config_manager_reloaded.get('log_file')}")

    # Demonstrate resiliency: if config is corrupted or key is lost
    # To test: 1. Delete 'example_app_secret.key' -> new key will be generated, old config will be unreadable
    #          2. Corrupt 'example_app_config.json' (e.g. make it non-JSON) -> config will be reinitialized
    print(f"\nTo test resiliency, try deleting '{example_key_file}' or corrupting '{example_config_file}' and rerun this script.")
    print(f"All example outputs, including logs and config files, are in '{example_output_dir}/'")
