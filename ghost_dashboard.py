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
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('GHOST_SECRET_KEY', 'ghost-protocol-2024')

# Authentication
auth = HTTPBasicAuth()

# User database (replace with secure storage in production)
users = {
    "commander": generate_password_hash("ghost_protocol_2024"),
    "operator": generate_password_hash("ghost_ops_2024")
}

# Initialize components with error handling
try:
    from ghost_config import GhostConfig
    from ghost_db import GhostDatabase
    config = GhostConfig()
    db = GhostDatabase(config)
except ImportError:
    # Fallback for minimal deployment
    class MockConfig:
        def get(self, key, default=None):
            return {
                'output_dir': 'data',
                'google_search_mode': 'mock',
                'scheduler': {'enabled': False}
            }.get(key, default)

        def get_logger(self, name):
            return logging.getLogger(name)

    config = MockConfig()
    db = None

# Setup logging
logger = config.get_logger("GhostDashboard")

# Global stats cache
stats_cache = {
    'last_update': None,
    'data': {},
    'cache_duration': 30  # seconds
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
def _get_latest_file(pattern):
    """Get most recent file matching pattern"""
    files = glob.glob(os.path.join(config.get('output_dir', 'data'), pattern))
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
    except:
        return "stable"

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
def cached(seconds=30):
    def decorator(f):
        cache = {'time': None, 'value': None}

        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            if cache['time'] is None or now - cache['time'] > seconds:
                cache['value'] = f(*args, **kwargs)
                cache['time'] = now
            return cache['value']
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
    scheduler_pid_file = os.path.join(config.get('output_dir', 'data'), 'scheduler.pid')
    if os.path.exists(scheduler_pid_file):
        try:
            with open(scheduler_pid_file, 'r') as f:
                pid = int(f.read().strip())
                # Check if process is running
                os.kill(pid, 0)
                scheduler_status = 'Running'
        except:
            scheduler_status = 'Stopped'

    return jsonify({
        'status': 'OPERATIONAL',
        'timestamp': datetime.now().isoformat(),
        'last_crawl': _file_age(latest_crawl),
        'last_parse': _file_age(latest_parsed),
        'api_mode': config.get('google_search_mode', 'unknown'),
        'encryption_mode': 'ENABLED' if hasattr(config, 'cipher_suite') else 'PLAINTEXT',
        'scheduler_status': scheduler_status,
        'scheduler_enabled': config.get('scheduler', {}).get('enabled', False),
        'metrics': metrics,
        'data_directory': config.get('output_dir', 'data'),
        'version': '1.0.0'
    })

@app.route('/api/mvnos/top/<int:n>')
@auth.login_required
@cached(60)
def top_mvnos(n=10):
    """Get top N lenient MVNOs with detailed info"""
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

    alerts_file = os.path.join(config.get('output_dir', 'data'), 'alerts_log.json')
    if not os.path.exists(alerts_file):
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
    reports_dir = os.path.join(config.get('output_dir', 'data'), 'reports')
    if not os.path.exists(reports_dir):
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

    log_files = glob.glob(os.path.join(config.get('output_dir', 'data'), '*.log'))
    if not log_files:
        return jsonify({'logs': [], 'message': 'No log files found'})

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
        raw_files = glob.glob(os.path.join(config.get('output_dir', 'data'), 'raw_search_results_*.json'))

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
        safe_config = {
            'output_dir': config.get('output_dir', 'data'),
            'google_search_mode': config.get('google_search_mode', 'unknown'),
            'search_delay_seconds': config.get('search_delay_seconds', 5),
            'scheduler': config.get('scheduler', {}),
            'alert_thresholds': config.get('alert_thresholds', {}),
            'log_level': config.get('log_level', 'INFO'),
            'api_key_configured': bool(config.get('api_keys', {}).get('google_search'))
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
    try:
        # This would normally trigger the crawler
        # For now, return a mock response
        return jsonify({
            'status': 'triggered',
            'message': 'Crawl cycle initiated',
            'estimated_completion': '5-10 minutes'
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
        scheduler_config = config.get('scheduler', {})
        scheduler_config['enabled'] = new_state
        config.set('scheduler', scheduler_config)

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
def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Run the dashboard with specified settings"""
    logger.info(f"Starting GHOST Dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    # Get configuration from environment
    host = os.environ.get('GHOST_DASHBOARD_HOST', '0.0.0.0')
    port = int(os.environ.get('GHOST_DASHBOARD_PORT', 5000))
    debug = os.environ.get('GHOST_DEBUG', 'false').lower() == 'true'

    print(f"""
    ╔═══════════════════════════════════════╗
    ║     GHOST DMPM Operations Dashboard   ║
    ╚═══════════════════════════════════════╝

    Starting dashboard server...
    URL: http://{host}:{port}
    Auth: commander / ghost_protocol_2024

    Press Ctrl+C to stop
    """)

    run_dashboard(host=host, port=port, debug=debug)
