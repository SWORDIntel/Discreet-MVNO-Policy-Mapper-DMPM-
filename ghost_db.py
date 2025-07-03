#!/usr/bin/env python3
"""GHOST Protocol Database Management - Per Document #2, Section 4.5"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path

class GhostDatabase:
    def __init__(self, config):
        self.config = config
        self.db_path = Path(config.get("database.path", "data/ghost_data.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = config.get_logger("GhostDB")
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mvno_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mvno_name TEXT NOT NULL,
                    policy_snapshot TEXT,
                    leniency_score REAL,
                    crawl_timestamp TIMESTAMP,
                    data_hash TEXT UNIQUE,
                    source_url TEXT,
                    confidence REAL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS policy_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mvno_name TEXT,
                    change_type TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    detected_timestamp TIMESTAMP,
                    alert_sent BOOLEAN DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS crawl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crawl_timestamp TIMESTAMP,
                    mvnos_found INTEGER,
                    new_policies INTEGER,
                    changes_detected INTEGER,
                    errors INTEGER,
                    duration_seconds REAL
                )
            ''')

            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_mvno_name ON mvno_policies(mvno_name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON mvno_policies(crawl_timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_changes_mvno ON policy_changes(mvno_name)')

    def store_policy(self, mvno_name, policy_data, leniency_score, source_url=None):
        """Store MVNO policy with deduplication"""
        policy_json = json.dumps(policy_data, sort_keys=True)
        data_hash = hashlib.sha256(policy_json.encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            # Check if this exact policy already exists
            existing = conn.execute(
                'SELECT id FROM mvno_policies WHERE data_hash = ?',
                (data_hash,)
            ).fetchone()

            if existing:
                self.logger.info(f"Policy for {mvno_name} unchanged (hash: {data_hash[:8]})")
                return False

            # Check for previous policy to detect changes
            previous = conn.execute(
                '''SELECT leniency_score, policy_snapshot
                   FROM mvno_policies
                   WHERE mvno_name = ?
                   ORDER BY crawl_timestamp DESC
                   LIMIT 1''',
                (mvno_name,)
            ).fetchone()

            # Insert new policy
            conn.execute(
                '''INSERT INTO mvno_policies
                   (mvno_name, policy_snapshot, leniency_score, crawl_timestamp, data_hash, source_url)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (mvno_name, policy_json, leniency_score, datetime.now(), data_hash, source_url)
            )

            # Detect and log changes
            if previous:
                old_score = previous[0]
                if abs(old_score - leniency_score) > 0.5:  # Significant change threshold
                    change_type = "POLICY_RELAXED" if leniency_score > old_score else "POLICY_TIGHTENED"
                    conn.execute(
                        '''INSERT INTO policy_changes
                           (mvno_name, change_type, old_value, new_value, detected_timestamp)
                           VALUES (?, ?, ?, ?, ?)''',
                        (mvno_name, change_type, str(old_score), str(leniency_score), datetime.now())
                    )
                    self.logger.warning(f"{change_type}: {mvno_name} score {old_score} -> {leniency_score}")
            else:
                # New MVNO detected
                conn.execute(
                    '''INSERT INTO policy_changes
                       (mvno_name, change_type, old_value, new_value, detected_timestamp)
                       VALUES (?, ?, ?, ?, ?)''',
                    (mvno_name, "NEW_MVNO", "null", str(leniency_score), datetime.now())
                )
                self.logger.info(f"NEW_MVNO: {mvno_name} with score {leniency_score}")

            return True

    def get_top_mvnos(self, limit=10):
        """Get top lenient MVNOs"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                '''SELECT DISTINCT mvno_name, leniency_score, crawl_timestamp
                   FROM mvno_policies
                   WHERE crawl_timestamp = (
                       SELECT MAX(crawl_timestamp)
                       FROM mvno_policies p2
                       WHERE p2.mvno_name = mvno_policies.mvno_name
                   )
                   ORDER BY leniency_score DESC
                   LIMIT ?''',
                (limit,)
            ).fetchall()

    def get_recent_changes(self, days=7):
        """Get recent policy changes"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                '''SELECT * FROM policy_changes
                   WHERE detected_timestamp > datetime('now', '-' || ? || ' days')
                   ORDER BY detected_timestamp DESC''',
                (days,)
            ).fetchall()

    def log_crawl_stats(self, stats):
        """Log crawl statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO crawl_history
                   (crawl_timestamp, mvnos_found, new_policies, changes_detected, errors, duration_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (datetime.now(), stats.get('mvnos_found', 0), stats.get('new_policies', 0),
                 stats.get('changes_detected', 0), stats.get('errors', 0), stats.get('duration', 0))
            )

    def get_mvno_by_name(self, mvno_name):
        """Get the latest policy details for a specific MVNO by name."""
        self.logger.debug(f"Querying for MVNO: {mvno_name}")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                '''SELECT mvno_name, policy_snapshot, leniency_score, crawl_timestamp, source_url
                   FROM mvno_policies
                   WHERE mvno_name = ?
                   ORDER BY crawl_timestamp DESC
                   LIMIT 1''',
                (mvno_name,)
            ).fetchone()

    def get_mvno_policy_history(self, mvno_name, days):
        """Get policy history for a specific MVNO over the last 'days'."""
        self.logger.debug(f"Querying policy history for {mvno_name} over {days} days")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                '''SELECT mvno_name, policy_snapshot, leniency_score, crawl_timestamp, source_url
                   FROM mvno_policies
                   WHERE mvno_name = ? AND crawl_timestamp >= datetime('now', '-' || ? || ' days')
                   ORDER BY crawl_timestamp DESC''',
                (mvno_name, str(days))
            ).fetchall()

    def get_database_stats(self):
        """Get various statistics from the database."""
        self.logger.debug("Querying database statistics")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            total_mvnos = conn.execute(
                'SELECT COUNT(DISTINCT mvno_name) as count FROM mvno_policies'
            ).fetchone()['count']

            last_policy_update = conn.execute(
                'SELECT MAX(crawl_timestamp) as ts FROM mvno_policies'
            ).fetchone()['ts']

            total_changes = conn.execute(
                'SELECT COUNT(*) as count FROM policy_changes'
            ).fetchone()['count']

            return {
                "total_mvnos": total_mvnos,
                "last_policy_update_timestamp": last_policy_update,
                "total_changes": total_changes
            }
