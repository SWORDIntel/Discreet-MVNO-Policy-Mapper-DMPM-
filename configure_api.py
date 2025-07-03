#!/usr/bin/env python3
"""Configure GHOST DMPM API Keys"""
from ghost_config import GhostConfig

def configure():
    config = GhostConfig()

    # Set Google Search API credentials from handover document
    config.set_api_key("google_search", "AIzaSyBia6w4jr6tXeceUk9rv3WlKkgCqlMjiuA")
    config.set("google_programmable_search_engine_id", "a5cd1ab6c3709436c")
    config.set("google_search_mode", "real")  # Switch from mock to real

    print("[*] API Configuration Complete:")
    print(f"    - Google API Key: {config.get_api_key('google_search')[:10]}...")
    print(f"    - Search Engine ID: {config.get('google_programmable_search_engine_id')}")
    print(f"    - Mode: {config.get('google_search_mode')}")

if __name__ == "__main__":
    configure()
