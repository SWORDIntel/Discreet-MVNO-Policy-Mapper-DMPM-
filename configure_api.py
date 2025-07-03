#!/usr/bin/env python3
from ghost_config import GhostConfig
import os # Import os for path manipulation

# Initialize config
# To ensure this script affects the main 'test_output_main_integration' config
# as used by main.py, we'll point it there.
# Otherwise, it creates a config in the root.
# The prompt implies this configuration should be central.
# However, main.py explicitly creates its config in 'test_output_main_integration'.
# Let's make this script configure a general config.json in root,
# and then ensure main.py can pick it up or we adjust main.py if needed.
# For now, let's assume a general root config.json is fine for API credentials.
# Later steps might require pointing main.py to this, or copying.

# Decision: The prompt's COMMAND 1 implies a general configuration.
# Let's use the default config file path for GhostConfig, which is 'config.json' in the root.
# Subsequent steps will either use this config or we'll adjust.
config = GhostConfig()

# Set Google Search API credentials
config.set_api_key("google_search", "AIzaSyBia6w4jr6tXeceUk9rv3WlKkgCqlMjiuA")
config.set("google_programmable_search_engine_id", "a5cd1ab6c3709436c")
config.set("google_search_mode", "real")  # Force real mode

# Enable advanced features
config.set("nlp_mode", "spacy")  # Enable NLP if available
config.set("html_fetch_enabled", True) # This key is conceptual based on prompt, GhostConfig doesn't have it by default
config.set("alert_thresholds", {
    "score_change": 0.2,
    "new_mvno_score": 3.0
})

# Add a specific setting for HTML fetch if it's meant to be a distinct config item
if not config.get("html_fetch_enabled"): # Check if it was set by the general set command
    config.set("html_fetch_enabled", True)


print("API credentials configured successfully")
print(f"Config file used/created: {os.path.abspath(config.config_file)}")
print(f"Google Search API Key: {config.get_api_key('google_search')}")
print(f"Google Search Mode: {config.get('google_search_mode')}")
print(f"CX ID: {config.get('google_programmable_search_engine_id')}")
print(f"NLP Mode: {config.get('nlp_mode')}")
print(f"Alert Thresholds: {config.get('alert_thresholds')}")
print(f"HTML Fetch Enabled: {config.get('html_fetch_enabled')}")
