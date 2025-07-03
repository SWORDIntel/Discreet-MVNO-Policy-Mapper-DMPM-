#!/usr/bin/env python3
"""
GHOST DMPM Operations Dashboard
Comprehensive monitoring and control interface
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import glob
import time
import subprocess
import threading
import logging
from collections import defaultdict
import base64

# Initialize Flask app
# Imports for GhostConfig will be done after project_root is available for Flask app setup
# app = Flask(__name__) # Will be initialized in run_dashboard or after config
# app.config['SECRET_KEY'] = os.environ.get('GHOST_SECRET_KEY', 'ghost-protocol-2024')
# Global app instance
app = Flask(__name__) # Initialize Flask app globally
app.config['SECRET_KEY'] = os.environ.get('GHOST_SECRET_KEY', 'ghost-protocol-2024-default-key') # Set secret key early

# Globals for other components, to be initialized by initialize_app_components
config = None
db = None
logger = None

# Authentication
auth = HTTPBasicAuth()

# User database (replace with secure storage in production)
users = {
    "commander": generate_password_hash("ghost_protocol_2024"),
    "operator": generate_password_hash("ghost_ops_2024")
}

# Global stats cache
stats_cache = {
    'last_update': None,
    'data': {},
    'cache_duration': None  # Will be set from config in initialize_app_components
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Helper functions
def _get_data_dir_path():
    """Helper to get the absolute path to the data/output directory."""
    if not config:
        # This case should ideally not happen if config is initialized early
        logger.error("Config not initialized when trying to get data_dir_path.")
        return Path('data') # Fallback, potentially problematic
    # Assuming 'output_dir' in config is relative to project_root
    # or that config.get already handles this if it's a special path.
    # For consistency with other modules, we resolve it against project_root.
    # Changed to use get_absolute_path for robustness.
    output_dir_str = config.get('output_dir', 'data') # Default relative path
    abs_path = config.get_absolute_path(output_dir_str)
    if not abs_path:
        logger.error(f"Dashboard data directory '{output_dir_str}' could not be resolved. Operations may fail.")
        # Fallback to a relative Path object, which might work if CWD is project root.
        return Path(output_dir_str)
    return abs_path

def _get_latest_file(pattern):
    """Get most recent file matching pattern from the data directory."""
    data_dir = _get_data_dir_path()
    # Ensure data_dir is Path object for globbing
    search_path = Path(data_dir) / pattern
    files = glob.glob(str(search_path)) # glob expects string path
    return max(files, key=os.path.getctime) if files else None

def _file_age(filepath):
    """Get human-readable file age"""
    if not filepath or not os.path.exists(filepath):
        return 'Never'

    age = datetime.now() - datetime.fromtimestamp(os.path.getctime(filepath))

    if age.days > 0:
        return f"{age.days} days ago"
    elif age.seconds > 3600:
        return f"{age.seconds // 3600} hours ago"
    elif age.seconds > 60:
        return f"{age.seconds // 60} minutes ago"
    else:
        return "Just now"

def _calculate_trend(mvno_name):
    """Calculate trend direction for MVNO"""
    if not db:
        return "unknown"

    try:
        history = db.get_historical_trends(mvno_name, days=7)
        if len(history) < 2:
            return "stable"

        recent_avg = sum(h['leniency_score'] for h in history[-3:]) / 3
        older_avg = sum(h['leniency_score'] for h in history[:3]) / 3

        if recent_avg > older_avg * 1.1:
            return "rising"
        elif recent_avg < older_avg * 0.9:
            return "falling"
        else:
            return "stable"
    except Exception as e:
        logger.error(f"Error calculating trend for {mvno_name}: {e}")
        return "unknown" # Or "stable" if preferred as a safe default

def _get_system_metrics():
    """Get comprehensive system metrics"""
    metrics = {
        'cpu_usage': 'N/A',
        'memory_usage': 'N/A',
        'disk_usage': 'N/A',
        'docker_status': 'N/A'
    }

    try:
        # Disk usage
        disk_stats = os.statvfs('/')
        disk_total = disk_stats.f_blocks * disk_stats.f_frsize
        disk_free = disk_stats.f_available * disk_stats.f_frsize
        disk_used_percent = ((disk_total - disk_free) / disk_total) * 100
        metrics['disk_usage'] = f"{disk_used_percent:.1f}%"

        # Docker status
        docker_check = subprocess.run(['docker', 'info'], capture_output=True, timeout=5)
        metrics['docker_status'] = 'Running' if docker_check.returncode == 0 else 'Stopped'

        # CPU and Memory (Linux specific)
        if os.path.exists('/proc/stat'):
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
                # Simple CPU calculation (would need previous value for accurate %)
                metrics['cpu_usage'] = 'Active'

        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                # Parse memory info
                mem_total = int([x for x in meminfo.split('\n') if 'MemTotal' in x][0].split()[1])
                mem_available = int([x for x in meminfo.split('\n') if 'MemAvailable' in x][0].split()[1])
                mem_used_percent = ((mem_total - mem_available) / mem_total) * 100
                metrics['memory_usage'] = f"{mem_used_percent:.1f}%"
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")

    return metrics

# Cache decorator
def cached(seconds=None): # Default to None
    def decorator(f):
        # Each decorated function gets its own cache and effective_seconds
        func_cache = {'time': None, 'value': None}

        # Determine effective_seconds once when decorator is applied
        # It will use the global stats_cache['cache_duration'] if seconds is None
        # This means stats_cache['cache_duration'] must be set before routes are decorated.
        # This is handled by initialize_app_components() being called before app.run().
        effective_seconds = seconds

        @wraps(f)
        def wrapper(*args, **kwargs):
            nonlocal effective_seconds # Allow modification if we want to refresh it dynamically, but not needed here.

            # If effective_seconds wasn't set at decoration time (e.g. because config wasn't ready)
            # or if it was explicitly None to always use global, try to get it.
            current_cache_duration_setting = effective_seconds
            if current_cache_duration_setting is None:
                 # Fallback to global config if decorator was called with cached(None)
                current_cache_duration_setting = stats_cache.get('cache_duration')
                if current_cache_duration_setting is None: # If global is also None, default to a value
                    logger.warning(f"Cache duration for {f.__name__} not set, defaulting to 30s.")
                    current_cache_duration_setting = 30

            now = time.time()
            if func_cache['time'] is None or now - func_cache['time'] > current_cache_duration_setting:
                func_cache['value'] = f(*args, **kwargs)
                func_cache['time'] = now
            return func_cache['value']
        return wrapper
    return decorator

# API Routes
@app.route('/')
@auth.login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
@auth.login_required
def system_status():
    """Get comprehensive system status"""
    latest_crawl = _get_latest_file('raw_search_results_*.json')
    latest_parsed = _get_latest_file('parsed_mvno_data_*.json')

    # Get system metrics
    metrics = _get_system_metrics()

    # Check scheduler status
    scheduler_status = 'Unknown'
    scheduler_pid_file = _get_data_dir_path() / 'scheduler.pid'
    if scheduler_pid_file.exists():
        try:
            with open(scheduler_pid_file, 'r') as f:
                pid = int(f.read().strip())
                os.kill(pid, 0) # Check if process is running
                scheduler_status = 'Running'
        except (OSError, ValueError, TypeError): # More specific exceptions
            scheduler_status = 'Stopped'
    else:
        scheduler_status = 'Not Found'


    from ghost_dmpm import __version__ as app_version

    return jsonify({
        'status': 'OPERATIONAL',
        'timestamp': datetime.now().isoformat(),
        'last_crawl': _file_age(latest_crawl),
        'last_parse': _file_age(latest_parsed),
        'api_mode': config.get('google_search_mode', 'unknown') if config else 'unknown',
        'encryption_mode': 'ENABLED' if config and hasattr(config, 'features') and config.features.get('encryption') else 'PLAINTEXT',
        'scheduler_status': scheduler_status,
        'scheduler_enabled': config.get('scheduler.enabled', False) if config else False,
        'metrics': metrics,
        'data_directory': str(_get_data_dir_path()),
        'version': app_version
    })

@app.route('/api/mvnos/top/<int:n>')
@auth.login_required
@cached(None) # Cache duration will be set from config
def top_mvnos(n=10):
    """Get top N lenient MVNOs with detailed info"""
    if not isinstance(n, int) or not 1 <= n <= config.get('dashboard.max_top_mvnos', 100):
        return jsonify({'error': f"Invalid value for n. Must be an integer between 1 and {config.get('dashboard.max_top_mvnos', 100)}."}), 400

    latest_parsed = _get_latest_file('parsed_mvno_data_*.json')
    if not latest_parsed:
        return jsonify({'error': 'No data available', 'suggestion': 'Run crawler first'}), 404

    try:
        with open(latest_parsed, 'r') as f:
            data = json.load(f)

        # Calculate additional metrics
        mvno_list = []
        for name, info in data.items():
            mvno_data = {
                'name': name,
                'score': info.get('average_leniency_score', 0),
                'mentions': info.get('mentions', 0),
                'positive_mentions': info.get('positive_sentiment_mentions', 0),
                'negative_mentions': info.get('negative_sentiment_mentions', 0),
                'trend': _calculate_trend(name),
                'keywords': list(info.get('policy_keywords', {}).keys())[:5],
                'last_seen': _file_age(latest_parsed)
            }
            mvno_list.append(mvno_data)

        # Sort by score
        sorted_mvnos = sorted(mvno_list, key=lambda x: x['score'], reverse=True)[:n]

        return jsonify({
            'mvnos': sorted_mvnos,
            'total_mvnos': len(data),
            'data_timestamp': _file_age(latest_parsed)
        })
    except Exception as e:
        logger.error(f"Error loading MVNO data: {e}")
        return jsonify({'error': 'Failed to load data', 'details': str(e)}), 500

@app.route('/api/mvnos/search/<query>')
@auth.login_required
def search_mvnos(query):
    """Search for specific MVNOs"""
    latest_parsed = _get_latest_file('parsed_mvno_data_*.json')
    if not latest_parsed:
        return jsonify({'error': 'No data available'}), 404

    try:
        with open(latest_parsed, 'r') as f:
            data = json.load(f)

        # Case-insensitive search
        results = []
        query_lower = query.lower()

        for name, info in data.items():
            if query_lower in name.lower():
                results.append({
                    'name': name,
                    'score': info.get('average_leniency_score', 0),
                    'mentions': info.get('mentions', 0),
                    'keywords': info.get('policy_keywords', {})
                })

        return jsonify({
            'query': query,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        logger.error(f"Error searching MVNOs: {e}")
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500

@app.route('/api/alerts/recent')
@auth.login_required
def recent_alerts():
    """Get recent policy alerts with filtering"""
    days = request.args.get('days', 7, type=int)
    alert_type = request.args.get('type', None)

    if not isinstance(days, int) or days <= 0:
        return jsonify({'error': 'Invalid value for days. Must be a positive integer.'}), 400
    if alert_type is not None and not isinstance(alert_type, str):
        return jsonify({'error': 'Invalid value for type. Must be a string.'}), 400

    alerts_file = _get_data_dir_path() / 'alerts_log.json' # Path object
    if not alerts_file.exists():
        return jsonify({'alerts': [], 'total': 0})

    try:
        with open(alerts_file, 'r') as f:
            alerts = json.load(f)

        # Filter by date
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [a for a in alerts if a.get('timestamp', '') > cutoff]

        # Filter by type if specified
        if alert_type:
            recent = [a for a in recent if a.get('alert_type') == alert_type]

        # Sort by timestamp
        sorted_alerts = sorted(recent, key=lambda x: x.get('timestamp', ''), reverse=True)

        return jsonify({
            'alerts': sorted_alerts[:50],  # Limit to 50
            'total': len(sorted_alerts),
            'filter': {
                'days': days,
                'type': alert_type
            }
        })
    except Exception as e:
        logger.error(f"Error loading alerts: {e}")
        return jsonify({'error': 'Failed to load alerts', 'details': str(e)}), 500

@app.route('/api/trends/<mvno>')
@auth.login_required
def mvno_trends(mvno):
    """Get detailed historical trends for specific MVNO"""
    if not db:
        return jsonify({'error': 'Database not available'}), 503

    days = request.args.get('days', 30, type=int)
    if not isinstance(days, int) or days <= 0:
        return jsonify({'error': 'Invalid value for days. Must be a positive integer.'}), 400
    if not mvno or not isinstance(mvno, str): # Basic check for mvno path variable
        return jsonify({'error': 'Invalid MVNO name.'}), 400

    try:
        historical_data = db.get_historical_trends(mvno, days=days)

        if not historical_data:
            return jsonify({
                'mvno': mvno,
                'error': 'No historical data available'
            }), 404

        # Calculate statistics
        scores = [h['leniency_score'] for h in historical_data]
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0

        # Detect significant changes
        changes = []
        for i in range(1, len(historical_data)):
            prev = historical_data[i-1]['leniency_score']
            curr = historical_data[i]['leniency_score']
            if abs(curr - prev) > 0.5:  # Significant change threshold
                changes.append({
                    'date': historical_data[i]['timestamp'],
                    'from': prev,
                    'to': curr,
                    'change': curr - prev
                })

        return jsonify({
            'mvno': mvno,
            'period_days': days,
            'data_points': len(historical_data),
            'statistics': {
                'average': round(avg_score, 2),
                'max': round(max_score, 2),
                'min': round(min_score, 2),
                'current': round(scores[-1], 2) if scores else 0,
                'trend': _calculate_trend(mvno)
            },
            'significant_changes': changes,
            'historical_data': historical_data
        })
    except Exception as e:
        logger.error(f"Error getting trends for {mvno}: {e}")
        return jsonify({'error': 'Failed to get trends', 'details': str(e)}), 500

@app.route('/api/reports/list')
@auth.login_required
def list_reports():
    """List available reports"""
    reports_dir = _get_data_dir_path() / 'reports' # Path object
    if not reports_dir.exists():
        return jsonify({'reports': []})

    try:
        reports = []
        for filename in os.listdir(reports_dir):
            if filename.endswith('.json.enc') or filename.endswith('.pdf'):
                filepath = os.path.join(reports_dir, filename)
                reports.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'created': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat(),
                    'type': 'encrypted_json' if filename.endswith('.json.enc') else 'pdf'
                })

        # Sort by creation date
        reports.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'reports': reports,
            'total': len(reports)
        })
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({'error': 'Failed to list reports', 'details': str(e)}), 500

@app.route('/api/system/logs')
@auth.login_required
def system_logs():
    """Get recent system logs"""
    lines = request.args.get('lines', 100, type=int)
    if not isinstance(lines, int) or lines <= 0:
        return jsonify({'error': 'Invalid value for lines. Must be a positive integer.'}), 400

    # Assuming logs are in project_root/logs as per GhostConfig changes
    log_dir_path = config.project_root / config.get("logging.directory", "logs") if config else Path("logs")
    log_pattern = config.get("logging.file_name_pattern", "*.log") # e.g. ghost_*.log or just *.log
    log_files = glob.glob(str(log_dir_path / log_pattern))

    if not log_files:
        return jsonify({'logs': [], 'message': f'No log files found in {log_dir_path} matching {log_pattern}'})

    try:
        # Get most recent log file
        latest_log = max(log_files, key=os.path.getmtime)

        # Read last N lines
        with open(latest_log, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]

        return jsonify({
            'log_file': os.path.basename(latest_log),
            'lines': recent_lines,
            'total_lines': len(all_lines)
        })
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({'error': 'Failed to read logs', 'details': str(e)}), 500

@app.route('/api/crawler/status')
@auth.login_required
def crawler_status():
    """Get detailed crawler statistics"""
    try:
        # Find all raw results files
        raw_files_pattern = _get_data_dir_path() / 'raw_search_results_*.json'
        raw_files = glob.glob(str(raw_files_pattern))

        if not raw_files:
            return jsonify({
                'status': 'No crawl data',
                'total_crawls': 0
            })

        # Get latest crawl stats
        latest_raw = max(raw_files, key=os.path.getctime)
        with open(latest_raw, 'r') as f:
            latest_data = json.load(f)

        # Count URLs by domain
        domains = defaultdict(int)
        for item in latest_data:
            if 'link' in item:
                domain = item['link'].split('/')[2] if '/' in item['link'] else 'unknown'
                domains[domain] += 1

        return jsonify({
            'status': 'Active',
            'total_crawls': len(raw_files),
            'last_crawl': {
                'timestamp': _file_age(latest_raw),
                'results_count': len(latest_data),
                'domains': dict(domains),
                'file': os.path.basename(latest_raw)
            },
            'crawl_history': [
                {
                    'file': os.path.basename(f),
                    'timestamp': datetime.fromtimestamp(os.path.getctime(f)).isoformat(),
                    'size': os.path.getsize(f)
                }
                for f in sorted(raw_files, key=os.path.getctime, reverse=True)[:10]
            ]
        })
    except Exception as e:
        logger.error(f"Error getting crawler status: {e}")
        return jsonify({'error': 'Failed to get crawler status', 'details': str(e)}), 500

@app.route('/api/config')
@auth.login_required
def get_config():
    """Get current configuration (sanitized)"""
    try:
        # Get config but hide sensitive values
        if not config:
            return jsonify({'error': 'Configuration not loaded'}), 500

        safe_config = {
            'output_dir': str(_get_data_dir_path()), # Show absolute path for clarity
            'google_search_mode': config.get('google_search_mode', 'unknown'),
            'crawler_delay_base': config.get('crawler.delay_base', 2.0),
            'scheduler_enabled': config.get('scheduler.enabled', False),
            'alert_thresholds': config.get('alerts.thresholds', {}), # Example path
            'logging_level': config.get('logging.level', 'INFO'),
            'api_key_configured': bool(config.get('api_keys.google_search'))
        }
        return jsonify(safe_config)
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': 'Failed to get configuration', 'details': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint (no auth required)"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/disk-usage')
@auth.login_required
def disk_usage():
    """Get current disk usage statistics"""
    try:
        # Get disk stats
        stat = os.statvfs('/')
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_available * stat.f_frsize
        used = total - free

        # Get project directory size
        project_size = 0
        for dirpath, dirnames, filenames in os.walk('.'):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    project_size += os.path.getsize(fp)

        # Get data directory size
        data_dir = config.get('output_dir', 'data')
        data_size = 0
        if os.path.exists(data_dir):
            for dirpath, dirnames, filenames in os.walk(data_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        data_size += os.path.getsize(fp)

        return jsonify({
            'filesystem': {
                'total': total,
                'used': used,
                'free': free,
                'percent_used': round((used / total) * 100, 1),
                'human_readable': {
                    'total': f"{total / (1024**3):.1f} GB",
                    'used': f"{used / (1024**3):.1f} GB",
                    'free': f"{free / (1024**3):.1f} GB"
                }
            },
            'project': {
                'size': project_size,
                'human_readable': f"{project_size / (1024**2):.1f} MB"
            },
            'data_directory': {
                'size': data_size,
                'human_readable': f"{data_size / (1024**2):.1f} MB",
                'path': data_dir
            }
        })
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return jsonify({'error': 'Failed to get disk usage', 'details': str(e)}), 500

# Control endpoints
@app.route('/api/crawler/trigger', methods=['POST'])
@auth.login_required
def trigger_crawl():
    """Manually trigger a crawl cycle"""
    # TODO: Implement actual crawl triggering mechanism.
    # This should ideally interact with the scheduler or a dedicated crawl manager.
    # For example, it might add a one-time job to the scheduler,
    # or send a message to a running crawler process if one exists.
    # Consider security implications if this can be triggered rapidly.
    logger.info("Manual crawl trigger requested via API.")
    try:
        # Placeholder for actual triggering logic
        # e.g., subprocess.Popen(['python', 'main.py', '--force-crawl'])
        # or if using a job queue: queue.put('trigger_crawl_now')
        message = "Crawl cycle initiated (simulated - actual implementation pending)."
        if config:
            message = config.get("dashboard.messages.crawl_triggered", message)

        return jsonify({
            'status': 'triggered',
            'message': message,
            'estimated_completion': config.get("dashboard.crawl_estimate_minutes", "5-10") + " minutes"
        })
    except Exception as e:
        logger.error(f"Error triggering crawl: {e}")
        return jsonify({'error': 'Failed to trigger crawl', 'details': str(e)}), 500

@app.route('/api/scheduler/toggle', methods=['POST'])
@auth.login_required
def toggle_scheduler():
    """Toggle scheduler on/off"""
    try:
        current_state = config.get('scheduler', {}).get('enabled', False)
        new_state = not current_state

        # Update config
        if not config:
            return jsonify({'error': 'Configuration not loaded'}), 500

        # Assuming config.set works as expected after project_root integration
        # This part might need careful testing with how GhostConfig saves changes.
        config.set('scheduler.enabled', new_state) # Set specific key

        return jsonify({
            'previous_state': current_state,
            'new_state': new_state,
            'message': f"Scheduler {'enabled' if new_state else 'disabled'}"
        })
    except Exception as e:
        logger.error(f"Error toggling scheduler: {e}")
        return jsonify({'error': 'Failed to toggle scheduler', 'details': str(e)}), 500

# Error monitoring
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'type': type(e).__name__,
        'message': str(e)
    }), 500

# CLI integration
def initialize_app_components():
    """Initialize global config, db, logger, and Flask app for the dashboard."""
    global app, config, db, logger

    # Standard library imports that were at top-level
    from pathlib import Path # Moved here as it's used by _get_data_dir_path called by Flask routes

    try:
        from ghost_dmpm.core.config import GhostConfig
        from ghost_dmpm.core.database import GhostDatabase

        config = GhostConfig()

        template_folder_abs = config.project_root / "templates"
        app = Flask(__name__, template_folder=str(template_folder_abs))
        app.config['SECRET_KEY'] = os.environ.get('GHOST_SECRET_KEY', config.get('dashboard.secret_key', 'ghost-protocol-2024-default-key'))

        # Initialize cache duration from config
        global stats_cache
        stats_cache['cache_duration'] = config.get('dashboard.cache_duration_seconds', 30)

        # Initialize @cached decorator with configured duration for top_mvnos
        # This requires re-registering the route or modifying the decorator itself.
        # Simpler: ensure @cached uses stats_cache['cache_duration'] if its arg is None.
        # The decorator `cached` needs to be modified to use this global if its arg is None.
        # For now, we assume the @cached(None) will pick up the global or we adjust it.
        # Let's modify the `cached` decorator to use the global if no specific duration is passed.

        if db is None and config.get("database.path"):
            db = GhostDatabase(config)

        logger = config.get_logger("GhostDashboard")
        logger.info(f"Dashboard components initialized. Cache duration set to {stats_cache['cache_duration']}s.")

    except ImportError as e:
        # Fallback for minimal deployment or if core components are missing
        # This part needs to be carefully managed if such a fallback is truly desired.
        # For now, let's log the error and potentially raise it or exit.
        logging.basicConfig(level=logging.INFO) # Basic logging if config failed
        logger = logging.getLogger("GhostDashboard_Fallback")
        logger.error(f"Failed to import core GHOST DMPM components: {e}", exc_info=True)
        logger.error("Dashboard will run in a degraded mode or fail to start if core components are essential.")
        # To actually run in degraded mode, MockConfig and MockDB would be needed here.
        # For now, assume core components are necessary.
        # If GhostConfig fails, the app might not be usable, but routes should still register.
        # raise RuntimeError(f"Failed to initialize dashboard due to missing core components: {e}")
        # Instead of raising, let it proceed; some routes might work or show errors gracefully.
        pass # Allow app to run in a very degraded state if config fails.


def run_dashboard(host=None, port=None, debug=None):
    """Run the dashboard with specified settings, loading from config if not provided."""
    # Initialize components if not already done (e.g. if run directly via __main__)
    if config is None: # A proxy for checking if initialize_app_components has run successfully
        try:
            initialize_app_components()
        except RuntimeError as e:
            # If core components (like GhostConfig) are absolutely essential for even basic app run,
            # then we might need to stop here. For now, assume app can start and show errors.
            if logger: # logger might be None if initialize_app_components failed early
                logger.critical(f"Dashboard cannot start due to core component initialization failure: {e}", exc_info=True)
            else: # Basic print if logger itself failed
                print(f"CRITICAL: Dashboard cannot start due to core component initialization failure: {e}", file=sys.stderr)
            # Depending on desired behavior, either sys.exit(1) or let Flask try to run (might fail).
            # For robustness in a web server context, usually you'd let it start and serve error pages.
            # However, if config is None, many routes will fail badly.
            # Let's make initialize_app_components more resilient or ensure it's always called once.
            # The current structure with global 'app' and 'config' initialized by initialize_app_components
            # means this function is the main entry point to ensure they are set.
            # If initialize_app_components itself raises RuntimeError, it won't get here.
            # The concern is if it completes but 'config' remains None.
            # The modified initialize_app_components tries to prevent config from being None
            # by having a fallback (though that fallback is now removed).
            # If GhostConfig fails, config will be None.
            if not config: # Check again after initialize_app_components
                print("FATAL: GhostConfig failed to initialize. Dashboard cannot run.", file=sys.stderr)
                sys.exit(1)


    # Get config values if not passed as arguments
    # These defaults in config.get are for when the key itself is missing from ghost_config.json
    # The environment variables provide overrides.
    final_host = host if host is not None else os.environ.get('GHOST_DASHBOARD_HOST', config.get('dashboard.host', '0.0.0.0'))
    final_port = port if port is not None else int(os.environ.get('GHOST_DASHBOARD_PORT', config.get('dashboard.port', 5000)))
    final_debug = debug if debug is not None else os.environ.get('GHOST_DEBUG', str(config.get('dashboard.debug', False))).lower() == 'true'

    # Update users from config if available
    global users
    config_users = config.get('dashboard.users')
    if isinstance(config_users, dict):
        users = {u: generate_password_hash(p) for u, p in config_users.items()}
        logger.info(f"Loaded {len(users)} users from configuration for dashboard.")
    else:
        # Fallback to default users if not in config or wrong type
        users = {
            "commander": generate_password_hash(config.get('dashboard.default_password_commander', "ghost_protocol_2024")),
            "operator": generate_password_hash(config.get('dashboard.default_password_operator', "ghost_ops_2024"))
        }
        logger.info("Using default dashboard users as 'dashboard.users' not found or invalid in config.")


    logger.info(f"Starting GHOST Dashboard on http://{final_host}:{final_port} (Debug: {final_debug})")

    # Note: app.run() is not recommended for production. Use a WSGI server like Gunicorn.
    app.run(host=final_host, port=final_port, debug=final_debug)

if __name__ == '__main__':
    # This block is for direct execution (python src/ghost_dmpm/api/dashboard.py)
    # It should correctly find its way to project_root via GhostConfig's internal logic.
    # initialize_app_components() # This is now called at the start of run_dashboard if needed

    # Default users might be updated by run_dashboard if configured in ghost_config.json
    default_user_display = list(users.keys())[0] if users else "commander"
    default_pass_display = "CONFIGURED_PASSWORD" # Avoid printing actual default password

    print(f"""
    ╔═══════════════════════════════════════╗
    ║     GHOST DMPM Operations Dashboard   ║
    ╚═══════════════════════════════════════╝

    Starting dashboard server...
    Auth: Default user '{default_user_display}' / Password '{default_pass_display}' (Check config)
    (Further details like URL will be printed by run_dashboard)

    Press Ctrl+C to stop
    """)
    run_dashboard() # Uses configured or default host/port/debug
