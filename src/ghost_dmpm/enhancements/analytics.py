"""
Analytics engine for GHOST DMPM
Features: Trend analysis, predictions, anomaly detection (basic implementations).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import statistics # For mean, stdev

# Assuming GhostDatabase is accessible.
# from ghost_dmpm.core.database import GhostDatabase
# To avoid direct import if this class is meant to be more standalone or use a duck-typed db object:
# For now, let's assume a db_handler that has the required methods.

class GhostAnalytics:
    """
    Provides basic analytics capabilities for MVNO data.
    """
    def __init__(self, db_handler: Any, config_handler: Optional[Any] = None): # Added optional config_handler
        """
        Initializes the GhostAnalytics engine.

        Args:
            db_handler: A database handler object that provides methods like
                        `get_mvno_policy_history(mvno_name, days)` and
                        `get_all_current_mvno_scores()`. This would typically be an
                        instance of GhostDatabase.
            config_handler: Optional configuration handler (e.g., GhostConfig instance)
                            for accessing analytics-specific configurations.
        """
        self.db = db_handler
        self.config = config_handler # Store config if provided

        # Setup logger
        if hasattr(self.config, 'get_logger'):
            self.logger = self.config.get_logger("GhostAnalytics")
        else: # Fallback basic logger
            self.logger = logging.getLogger("GhostAnalytics")
            if not self.logger.handlers:
                logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


    # --- Helper Statistical Functions ---
    def _calculate_moving_average(self, scores: List[float], window_size: int) -> List[Optional[float]]:
        """Calculates moving average for a list of scores."""
        if not scores or window_size <= 0:
            return []
        if window_size > len(scores):
            return [None] * len(scores)

        averages = [None] * (window_size - 1)
        for i in range(window_size -1, len(scores)):
            window = scores[i - window_size + 1 : i + 1]
            averages.append(sum(window) / window_size if window else None)
        return averages

    def _calculate_std_dev(self, data: List[float]) -> Optional[float]:
        """Calculates standard deviation."""
        if len(data) < 2:
            return None
        try:
            return statistics.stdev(data)
        except statistics.StatisticsError: # Handles cases like all same values if stdev is 0
            return 0.0


    # --- Core Analytics Methods ---

    def analyze_trends(self, mvno_name: str, days: int = 30, window_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyzes historical score trends for a given MVNO.
        """
        if window_size is None: # Get window_size from config or use default
            window_size = self.config.get("analytics.trend_window_size", 7) if self.config else 7

        self.logger.info(f"Analyzing trends for MVNO '{mvno_name}' over {days} days (window: {window_size}).")
        if not hasattr(self.db, 'get_mvno_policy_history'):
            self.logger.error("Database handler does not support 'get_mvno_policy_history'.")
            return {"error": "Trend analysis unavailable due to DB handler incompatibility."}

        try:
            history = self.db.get_mvno_policy_history(mvno_name, days)
        except Exception as e:
            self.logger.error(f"Error fetching history for {mvno_name} from DB: {e}", exc_info=True)
            return {"error": f"Could not fetch history for {mvno_name}."}

        if not history:
            return {
                "mvno_name": mvno_name,
                "message": "No historical data found for the specified period.",
                "timestamps": [], "scores": [], "moving_average": [], "trend_direction": "unknown"
            }

        timestamps = [item['crawl_timestamp'] for item in history]
        scores = [item['leniency_score'] for item in history if isinstance(item.get('leniency_score'), (int, float))] # Ensure scores are numeric

        if not scores: # If all scores were non-numeric after filtering
             return {
                "mvno_name": mvno_name, "message": "No valid numeric scores found in historical data.",
                "timestamps": timestamps, "scores": [], "moving_average": [], "trend_direction": "unknown"
            }

        moving_avg = self._calculate_moving_average(scores, window_size)

        trend_direction = "stable"
        if len(scores) >= 2:
            # More robust trend: compare start and end of moving average if available
            valid_ma_points = [ma for ma in moving_avg if ma is not None]
            if len(valid_ma_points) >= 2:
                start_ma = valid_ma_points[0]
                end_ma = valid_ma_points[-1]
                # Define thresholds for trend from config or defaults
                up_threshold = self.config.get("analytics.trend_up_threshold", 1.05) if self.config else 1.05 # 5% increase
                down_threshold = self.config.get("analytics.trend_down_threshold", 0.95) if self.config else 0.95 # 5% decrease
                if end_ma > start_ma * up_threshold: trend_direction = "upward"
                elif end_ma < start_ma * down_threshold: trend_direction = "downward"
            elif scores[-1] > scores[0] * 1.1: # Fallback to raw scores if MA too short
                trend_direction = "upward"
            elif scores[-1] < scores[0] * 0.9:
                trend_direction = "downward"

        return {
            "mvno_name": mvno_name,
            "period_days": days,
            "timestamps": timestamps,
            "scores": scores,
            "moving_average": moving_avg,
            "trend_direction": trend_direction,
            "current_score": scores[-1] if scores else None
        }

    def detect_anomalies(self, days_history: Optional[int] = None, std_dev_multiplier: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Detects anomalies in MVNO scores based on standard deviation from their recent history.
        """
        if days_history is None:
            days_history = self.config.get("analytics.anomaly_days_history", 30) if self.config else 30
        if std_dev_multiplier is None:
            std_dev_multiplier = self.config.get("analytics.anomaly_std_dev_multiplier", 2.0) if self.config else 2.0

        self.logger.info(f"Detecting anomalies with history={days_history} days, multiplier={std_dev_multiplier}.")
        if not hasattr(self.db, 'get_all_mvno_names') or not hasattr(self.db, 'get_mvno_policy_history'):
            self.logger.error("Database handler does not support required methods for anomaly detection.")
            return [{"error": "Anomaly detection unavailable due to DB handler incompatibility."}]

        try:
            all_mvnos_tuples = self.db.get_all_mvno_names()
        except Exception as e:
            self.logger.error(f"Error fetching all MVNO names from DB: {e}", exc_info=True)
            return [{"error": "Could not fetch MVNO names for anomaly detection."}]

        if not all_mvnos_tuples:
            self.logger.info("No MVNOs found to analyze for anomalies.")
            return []

        anomalies = []

        for mvno_tuple in all_mvnos_tuples:
            mvno_name = mvno_tuple[0]
            try:
                history = self.db.get_mvno_policy_history(mvno_name, days_history)
            except Exception as e:
                self.logger.error(f"Error fetching history for {mvno_name} during anomaly detection: {e}")
                continue # Skip this MVNO

            if not history or len(history) < self.config.get("analytics.anomaly_min_data_points", 5) if self.config else 5:
                continue

            scores = [item['leniency_score'] for item in history if isinstance(item.get('leniency_score'), (int, float))]
            timestamps = [item['crawl_timestamp'] for item in history]

            if len(scores) < self.config.get("analytics.anomaly_min_data_points", 5) if self.config else 5:
                continue

            mean_score = statistics.mean(scores)
            std_dev = self._calculate_std_dev(scores)

            if std_dev is None or std_dev == 0:
                continue

            latest_score = scores[-1]
            latest_timestamp = timestamps[-1]

            if abs(latest_score - mean_score) > std_dev_multiplier * std_dev:
                anomalies.append({
                    "mvno_name": mvno_name, "timestamp": latest_timestamp,
                    "anomalous_score": latest_score, "historical_mean": round(mean_score, 2),
                    "historical_std_dev": round(std_dev, 2),
                    "deviation_multiple": round(abs(latest_score - mean_score) / std_dev, 1) if std_dev > 0 else float('inf'),
                    "type": "score_spike" if latest_score > mean_score else "score_drop"
                })

        self.logger.info(f"Anomaly detection complete. Found {len(anomalies)} anomalies.")
        return anomalies

    def predict_next_score(self, mvno_name: str, days_for_trend: Optional[int] = None) -> Optional[float]:
        """
        Predicts the next score for an MVNO using basic linear extrapolation or averaging.
        """
        if days_for_trend is None:
            days_for_trend = self.config.get("analytics.prediction_days_history", 14) if self.config else 14

        self.logger.info(f"Predicting next score for MVNO '{mvno_name}' using {days_for_trend} days history.")
        if not hasattr(self.db, 'get_mvno_policy_history'):
            self.logger.error("Database handler does not support 'get_mvno_policy_history'.")
            return None

        try:
            history = self.db.get_mvno_policy_history(mvno_name, days_for_trend)
        except Exception as e:
            self.logger.error(f"Error fetching history for {mvno_name} for prediction: {e}", exc_info=True)
            return None

        if not history:
            self.logger.warning(f"No history found for '{mvno_name}' to make a prediction.")
            return None

        scores = [item['leniency_score'] for item in history if isinstance(item.get('leniency_score'), (int, float))]

        if not scores:
            self.logger.warning(f"No valid numeric scores in history for '{mvno_name}'.")
            return None

        prediction = None
        min_score_range = self.config.get("analytics.score_min_range", 0.0) if self.config else 0.0
        max_score_range = self.config.get("analytics.score_max_range", 5.0) if self.config else 5.0

        if len(scores) >= 2:
            # Linear extrapolation: score_n+1 = score_n + (score_n - score_n-1)
            prediction = scores[-1] + (scores[-1] - scores[-2])
        elif scores: # Only one data point
            prediction = scores[-1]

        if prediction is not None:
            prediction = max(min_score_range, min(max_score_range, prediction))
            self.logger.info(f"Predicted next score for '{mvno_name}': {prediction:.2f}")
            return round(prediction, 2)

        self.logger.warning(f"Not enough data to predict score for '{mvno_name}'.")
        return None

    def placeholder_ml_features(self, mvno_name: str) -> Dict[str, Any]:
        self.logger.info(f"Placeholder ML feature analysis for {mvno_name}.")
        return {
            "mvno_name": mvno_name, "ml_prediction_score": None, "confidence": 0.0,
            "feature_importance": {}, "notes": "Machine Learning features are not yet implemented."
        }

    def get_visualization_data(self, mvno_name: str, days: Optional[int] = None) -> Dict[str, Any]:
        if days is None:
            days = self.config.get("analytics.viz_days_history", 30) if self.config else 30

        window_size = self.config.get("analytics.trend_window_size", 7) if self.config else 7

        trend_data = self.analyze_trends(mvno_name, days, window_size=window_size)
        if "error" in trend_data:
            return trend_data # Propagate error

        return {
            "mvno_name": mvno_name,
            "labels": trend_data.get("timestamps", []),
            "datasets": [
                {
                    "label": f"{mvno_name} Score", "data": trend_data.get("scores", []),
                    "borderColor": "rgb(75, 192, 192)", "tension": 0.1
                },
                {
                    "label": f"Moving Avg ({window_size}-day)", "data": trend_data.get("moving_average", []),
                    "borderColor": "rgb(255, 99, 132)", "borderDash": [5, 5], "tension": 0.1
                }
            ],
            "summary": {
                "current_score": trend_data.get("current_score"),
                "trend_direction": trend_data.get("trend_direction")
            }
        }

# Example usage (remains largely the same, just GhostAnalytics might take a config now)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("AnalyticsExampleMain")

    class MockDBHandler:
        def __init__(self):
            self._mvno_data = {
                "TestMVNO1": [{"crawl_timestamp": (datetime.now() - timedelta(days=i)).isoformat(), "leniency_score": 3.0 + (i % 3)*0.1 - (i % 2)*0.2} for i in range(29, -1, -1)],
                "TestMVNO2": [{"crawl_timestamp": (datetime.now() - timedelta(days=i)).isoformat(), "leniency_score": 4.5 - (i % 5)*0.2} for i in range(14, -1, -1)],
                "SpikyMVNO": [
                    {"crawl_timestamp": (datetime.now() - timedelta(days=10)).isoformat(), "leniency_score": 2.0}, {"crawl_timestamp": (datetime.now() - timedelta(days=9)).isoformat(), "leniency_score": 2.1},
                    {"crawl_timestamp": (datetime.now() - timedelta(days=8)).isoformat(), "leniency_score": 1.9}, {"crawl_timestamp": (datetime.now() - timedelta(days=7)).isoformat(), "leniency_score": 2.0},
                    {"crawl_timestamp": (datetime.now() - timedelta(days=6)).isoformat(), "leniency_score": 4.8}, {"crawl_timestamp": (datetime.now() - timedelta(days=5)).isoformat(), "leniency_score": 2.2},
                ],
                "FlatMVNO": [{"crawl_timestamp": (datetime.now() - timedelta(days=i)).isoformat(), "leniency_score": 3.0} for i in range(29, -1, -1)],
            }
            self.logger = logging.getLogger("MockDBHandler")

        def get_mvno_policy_history(self, mvno_name: str, days: int) -> List[Dict[str, Any]]:
            self.logger.debug(f"MockDB: Fetching history for {mvno_name} over {days} days.")
            if mvno_name in self._mvno_data:
                cutoff_date = datetime.now() - timedelta(days=days)
                return [d for d in self._mvno_data[mvno_name] if datetime.fromisoformat(d["crawl_timestamp"]) >= cutoff_date]
            return []

        def get_all_mvno_names(self) -> List[Tuple[str]]:
            return [(name,) for name in self._mvno_data.keys()]

    class MockAnalyticsConfig:
         def get(self, key, default=None):
             # Provide some defaults for analytics specific config if any
             if key == 'analytics.trend_window_size': return 5
             if key == 'analytics.anomaly_days_history': return 20
             if key == 'analytics.anomaly_std_dev_multiplier': return 1.8
             if key == 'analytics.anomaly_min_data_points': return 4
             if key == 'analytics.prediction_days_history': return 10
             if key == 'analytics.score_min_range': return 0.0
             if key == 'analytics.score_max_range': return 5.0
             if key == 'analytics.viz_days_history': return 30
             # Fallback for get_logger
             if key == "logging.level": return "DEBUG"
             return default

         def get_logger(self, name): # Ensure mock config has get_logger
            logger = logging.getLogger(name)
            logger.setLevel(self.get("logging.level", "INFO").upper())
            # Add handler if not present, to see output during testing
            if not logger.handlers:
                ch = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                ch.setFormatter(formatter)
                logger.addHandler(ch)
            return logger


    main_logger.info("GhostAnalytics Example Usage with MockConfig")
    mock_db = MockDBHandler()
    mock_config = MockAnalyticsConfig()

    analyzer = GhostAnalytics(db_handler=mock_db, config_handler=mock_config)

    # --- Test analyze_trends ---
    main_logger.info("\n--- Trend Analysis for TestMVNO1 ---")
    trend_mvno1 = analyzer.analyze_trends("TestMVNO1", days=30) # Uses config window_size
    if "error" not in trend_mvno1:
        main_logger.info(f"MVNO: {trend_mvno1['mvno_name']}, Trend: {trend_mvno1['trend_direction']}, Current Score: {trend_mvno1['current_score']}")
    else:
        main_logger.error(f"Error: {trend_mvno1['error']}")

    # --- Test detect_anomalies ---
    main_logger.info("\n--- Anomaly Detection ---")
    anomalies = analyzer.detect_anomalies() # Uses config days_history & multiplier
    if anomalies and ("error" not in anomalies[0] if isinstance(anomalies[0], dict) else True):
        for anomaly in anomalies: main_logger.info(f"Anomaly: {anomaly}")
    elif not anomalies: main_logger.info("No anomalies detected.")
    else: main_logger.error(f"Error in anomaly detection: {anomalies[0].get('error')}")

    # --- Test predict_next_score ---
    main_logger.info("\n--- Score Prediction for SpikyMVNO ---")
    predicted_score_spiky = analyzer.predict_next_score("SpikyMVNO") # Uses config days
    main_logger.info(f"Predicted next score for SpikyMVNO: {predicted_score_spiky if predicted_score_spiky is not None else 'Cannot predict'}")

    main_logger.info("\n--- Score Prediction for NonExistentMVNO ---")
    predicted_score_non = analyzer.predict_next_score("NonExistentMVNO")
    main_logger.info(f"Predicted next score for NonExistentMVNO: {predicted_score_non if predicted_score_non is not None else 'Cannot predict'}")


    # --- Test get_visualization_data ---
    main_logger.info("\n--- Visualization Data for TestMVNO1 ---")
    viz_data = analyzer.get_visualization_data("TestMVNO1") # Uses config days
    if "error" not in viz_data:
        main_logger.info(f"Viz Data for {viz_data['mvno_name']}: Summary: {viz_data['summary']}")
    else:
        main_logger.error(f"Error generating viz data: {viz_data['error']}")

    main_logger.info("\nExample usage finished.")
