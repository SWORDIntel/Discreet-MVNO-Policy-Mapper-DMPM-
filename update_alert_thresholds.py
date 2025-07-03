from ghost_config import GhostConfig

config = GhostConfig() # Loads root config.json

new_thresholds = {
    "score_change": 0.30,  # 30% change
    "new_mvno_score": 4.0  # Minimum score for a new MVNO to be considered high-score
}

config.set("alert_thresholds", new_thresholds)
print("Alert thresholds updated in config.json.")
print(f"New alert_thresholds: {config.get('alert_thresholds')}")
