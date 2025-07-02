import json
import logging
import os
# from cryptography.fernet import Fernet # Replaced by CryptoProvider
from ghost_crypto import CryptoProvider # Import the new CryptoProvider

class GhostConfig:
    """
    Manages configuration settings for the GHOST Protocol DMPM application.
    Handles loading, saving, and encrypting configuration data, including API keys.
    Also sets up application-wide logging.
    Uses CryptoProvider for encryption abstraction.
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
        # self.cipher_suite = None # Replaced by self.crypto_provider
        self.crypto_provider = None # Will be initialized in _load_or_generate_key_and_init_crypto

        self._load_or_generate_key_and_init_crypto() # Initializes crypto_provider and its key
        self._load_config() # Must be called after crypto_provider is initialized
        self._setup_logging() # Sets up logging, potentially using config values

        # Log the effective encryption mode
        if self.crypto_provider:
            logging.info(
                f"GhostConfig initialized. Effective encryption mode: {self.crypto_provider.effective_mode}."
            )
        else: # Should not happen if _load_or_generate_key_and_init_crypto is correct
            logging.error("CryptoProvider not initialized in GhostConfig.")


    def _load_or_generate_key_and_init_crypto(self):
        """
        Loads an existing key from key_file or generates a new one.
        Initializes the CryptoProvider with this key and the configured/default encryption mode.
        """
        key = None
        encryption_mode_from_config = self.config.get("ENCRYPTION_MODE", "auto") # Check config early

        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, "rb") as f:
                    key = f.read()
                if not key: # File exists but is empty
                    logging.warning(f"Key file {self.key_file} is empty. A new key will be generated.")
                    key = None # Treat as if key file doesn't exist for generation logic
            except Exception as e:
                logging.error(f"Error reading key file {self.key_file}: {e}. A new key will be generated.")
                key = None

        # Initialize CryptoProvider. If key is None, CryptoProvider will generate one.
        # Pass the encryption_mode from config if available, else default to "auto"
        # This initial self.crypto_provider is temporary if key was None,
        # as generate_key() below will create a new one with the proper key.
        # This is a bit tricky because config isn't fully loaded yet to get ENCRYPTION_MODE.
        # For now, let's assume "auto" for key generation, then respect config for operations.
        # A better approach: CryptoProvider takes key=None and generates it internally if needed.

        temp_provider_for_key_gen = CryptoProvider(mode="auto") # Mode for key gen itself is less critical

        if key is None:
            key = temp_provider_for_key_gen.generate_key() # Generate key using provider's logic
            try:
                with open(self.key_file, "wb") as f:
                    f.write(key)
                logging.info(f"New key generated and saved to {self.key_file}.")
            except Exception as e:
                logging.error(f"Error saving new key to {self.key_file}: {e}")
                # Continue with the generated key in memory if saving fails

        # Now, initialize the main crypto_provider with the definite key and desired mode
        # We need to load ENCRYPTION_MODE from self.config, but self.config is loaded in _load_config,
        # which needs crypto. This is a circular dependency.
        # Simplification: For now, CryptoProvider in "auto" mode.
        # ENCRYPTION_MODE from config will be logged but CryptoProvider decides internally.
        # Or, we can do a preliminary partial load of config just for ENCRYPTION_MODE.

        # Let's try to get ENCRYPTION_MODE from a potentially unencrypted config first,
        # or use a default if it's the first run. This is tricky.
        # The most robust way:
        # 1. Load key if exists.
        # 2. If key exists, init CryptoProvider with it (mode 'auto' for now).
        # 3. Try to load config. If it has ENCRYPTION_MODE, re-init CryptoProvider if mode differs.
        # 4. If key doesn't exist, generate key, save it, init CryptoProvider (mode 'auto').
        # 5. Load config (which will be default or empty). Set ENCRYPTION_MODE if desired. Save config.

        # Simpler path for now: CryptoProvider handles key generation if key=None.
        # The mode for the *provider itself* will be based on config if available, else "auto".
        # This means _load_config must be able to run *before* full crypto_provider finalization
        # if we want ENCRYPTION_MODE to influence the choice between Fernet/Mock.

        # Revised logic:
        # 1. Determine initial key (load or generate if first time).
        # 2. Create a temporary CryptoProvider with this key in 'auto' mode to try decryption.
        # 3. Attempt to load and decrypt config using this temporary provider.
        # 4. From loaded config, get ENCRYPTION_MODE.
        # 5. Create the final self.crypto_provider using the key and the determined ENCRYPTION_MODE.

        initial_key = None
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                initial_key = f.read()

        if not initial_key: # No key file or empty key file
            # Need a provider to generate a key
            temp_key_gen_provider = CryptoProvider(mode="auto") # Mode doesn't matter much for key gen
            initial_key = temp_key_gen_provider.generate_key()
            try:
                with open(self.key_file, "wb") as f:
                    f.write(initial_key)
                logging.info(f"New key generated and saved to {self.key_file} by GhostConfig.")
            except Exception as e:
                logging.error(f"Error saving new key to {self.key_file}: {e}")

        # At this point, 'initial_key' is definitely set.
        # Now, we need to determine the ENCRYPTION_MODE.
        # Temporarily load config as plaintext to find ENCRYPTION_MODE if it exists.
        # This is a bit of a hack, as config is usually encrypted.
        # A better way: CryptoProvider is always initialized, and _load_config uses it.
        # The ENCRYPTION_MODE in config is more of a *preference* that CryptoProvider might consider
        # if it's in "auto" mode, but availability of 'cryptography' lib is primary.

        # Let's stick to CryptoProvider's internal logic for mode selection first.
        # The ENCRYPTION_MODE in config can be a *request* for future runs.
        self.crypto_provider = CryptoProvider(mode=self.config.get("ENCRYPTION_MODE", "auto"), key=initial_key)
        # self.cipher_suite = self.crypto_provider # For compatibility if anything used old name
                                                 # Better to update all uses to self.crypto_provider

    def _load_config(self):
        """
        Loads the configuration from the config_file.
        If the file exists and contains data, it attempts to decrypt and load it using self.crypto_provider.
        If the file doesn't exist, is empty, or decryption fails,
        a default configuration is initialized and saved.
        Ensures the output directory specified in the config exists.
        """
        if not self.crypto_provider:
            # This should not happen if __init__ calls _load_or_generate_key_and_init_crypto first.
            logging.error("CryptoProvider not available during _load_config. This is a bug.")
            # Attempt a fallback initialization of crypto_provider here, though it's not ideal.
            self._load_or_generate_key_and_init_crypto()
            if not self.crypto_provider: # Still no provider
                 raise RuntimeError("Failed to initialize CryptoProvider in GhostConfig.")


        config_loaded_successfully = False
        if os.path.exists(self.config_file):
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()
            if encrypted_data:
                try:
                    decrypted_data = self.crypto_provider.decrypt(encrypted_data)
                    self.config = json.loads(decrypted_data.decode())
                    config_loaded_successfully = True
                except Exception as e:
                    logging.error(f"Error decrypting or loading config with {self.crypto_provider.effective_mode} mode: {e}. Reinitializing config.")
                    # Don't save here, let it fall through to default config creation and save.
            else: # File is empty
                logging.info(f"Config file {self.config_file} is empty. Initializing default config.")
        else:
            logging.info(f"Config file {self.config_file} not found. Initializing default config.")

        if not config_loaded_successfully:
            self.config = {
                "api_keys": {},
                "mvno_list_file": "mvnos.txt",
                "keywords_file": "keywords.txt",
                "output_dir": "output",
                "ENCRYPTION_MODE": "auto" # Default encryption mode
            }
            self.save_config() # Save a fresh config if it was reinitialized or created

        # After config is loaded (or defaults set), ensure ENCRYPTION_MODE is in self.config
        if "ENCRYPTION_MODE" not in self.config:
            self.config["ENCRYPTION_MODE"] = "auto" # Default if missing after load

        # Update crypto_provider if loaded config's ENCRYPTION_MODE differs from initial 'auto' assumption
        # and the provider isn't already in that specific mode due to library availability.
        # This ensures the provider respects the config if possible.
        desired_mode_from_config = self.config.get("ENCRYPTION_MODE", "auto")
        if self.crypto_provider.mode != desired_mode_from_config.lower():
            logging.info(f"Configuration specifies ENCRYPTION_MODE='{desired_mode_from_config}'. Re-evaluating CryptoProvider.")
            # Re-initialize with the key we have and the mode from config.
            current_key = self.crypto_provider.key
            self.crypto_provider = CryptoProvider(mode=desired_mode_from_config, key=current_key)
            logging.info(f"CryptoProvider re-initialized with mode '{self.crypto_provider.mode}', effective: '{self.crypto_provider.effective_mode}'.")


        # Ensure default output directory exists
        output_dir = self.get("output_dir", "output") # Use self.get to access potentially just-loaded config
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)


    def save_config(self):
        """
        Encrypts the current configuration dictionary using self.crypto_provider and saves it to the config_file.
        Logs success or error.
        """
        if not self.crypto_provider:
            logging.error("CryptoProvider not available. Cannot save configuration.")
            return

        try:
            # Ensure ENCRYPTION_MODE is in config before saving
            if "ENCRYPTION_MODE" not in self.config:
                 self.config["ENCRYPTION_MODE"] = self.crypto_provider.mode # Store the mode being used or requested

            data_to_encrypt = json.dumps(self.config).encode()
            encrypted_data = self.crypto_provider.encrypt(data_to_encrypt)
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)
            logging.info(f"Configuration saved successfully using {self.crypto_provider.effective_mode} mode.")
        except Exception as e:
            logging.error(f"Error saving configuration with {self.crypto_provider.effective_mode} mode: {e}")

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
