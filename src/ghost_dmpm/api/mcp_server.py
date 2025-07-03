#!/usr/bin/env python3
"""GHOST Protocol MCP Server v2 - With Health Check"""
import asyncio
import websockets
import json
import logging
from datetime import datetime
from pathlib import Path
import sys

# Removed sys.path.append, imports will be absolute from package root
# sys.path.append(str(Path(__file__).resolve().parent)) # Old line

from ghost_dmpm.core.config import GhostConfig
from ghost_dmpm.core.database import GhostDatabase

class GhostMCPServer:
    def __init__(self, config):
        self.config = config
        self.db = GhostDatabase(config)
        self.logger = config.get_logger("MCP-Server") # Uses GhostConfig's logger
        self.authenticated_clients = set()
        self.start_time = datetime.now()

    def get_uptime(self):
        """Calculate server uptime"""
        delta = datetime.now() - self.start_time
        return f"{delta.days}d {delta.seconds//3600}h {(delta.seconds//60)%60}m"

    async def health_check_handler(self, websocket, path):
        """Handle health check requests on /health path"""
        if path == "/health":
            self.logger.info(f"Health check requested from {websocket.remote_address}")
            try:
                # Test database connection
                db_status_text = "healthy"
                db_mvnos_count = 0
                try:
                    # Ensure get_database_stats is robust or wrapped
                    stats = self.db.get_database_stats()
                    # The user's V2 template uses 'mvno_count', original uses 'total_mvnos'
                    # Let's try to be compatible or use a known key from original GhostDB if different
                    db_mvnos_count = stats.get("total_mvnos", stats.get("mvno_count", 0))
                except Exception as db_exc:
                    self.logger.error(f"Health check: Database stat query failed: {db_exc}")
                    db_status_text = "degraded"

                from ghost_dmpm import __version__ as app_version
                health_status = {
                    "status": "healthy", # Overall status, can be changed if critical components fail
                    "timestamp": datetime.now().isoformat(),
                    "version": app_version,
                    "uptime": self.get_uptime(),
                    "components": {
                        "database": db_status_text,
                        "websocket": "healthy"
                    },
                    "metrics": {
                        "connected_clients": len(self.authenticated_clients),
                        "tracked_mvnos": db_mvnos_count
                    }
                }

                await websocket.send(json.dumps(health_status))

            except Exception as e:
                self.logger.error(f"Error during health check: {e}", exc_info=True)
                error_status = {
                    "status": "error",
                    "error_message": str(e), # changed from "error" to avoid conflict with outer key
                    "timestamp": datetime.now().isoformat()
                }
                try:
                    await websocket.send(json.dumps(error_status))
                except Exception as send_err:
                    self.logger.error(f"Failed to send error status during health check: {send_err}")
            finally:
                # Ensure connection is closed for health checks
                try:
                    await websocket.close()
                except Exception:
                    pass # Ignore errors on close, it might already be closed
            return True # Indicates /health path was handled

        return False # Path was not /health

    async def authenticate(self, websocket, token):
        """Authenticate WebSocket connection"""
        # Using "mcp_server.auth_token" as per original, not "mcp.auth_token"
        expected_token = self.config.get("mcp_server.auth_token", "ghost-mcp-2024")

        if token == expected_token:
            self.authenticated_clients.add(websocket)
            self.logger.info(f"Client authenticated: {websocket.remote_address}")
            return True
        else:
            self.logger.warning(f"Authentication failed for client {websocket.remote_address} (token: {token[:10]}...)")
            return False

    async def handle_message(self, websocket, message_str):
        """Route messages to appropriate handlers based on JSON-RPC like structure"""
        request_id = None # For JSON-RPC
        try:
            data = json.loads(message_str)
            method = data.get('method')
            params = data.get('params', {})
            request_id = data.get('id')

            self.logger.info(f"Received method: {method} from {websocket.remote_address} (ID: {request_id})")

            # Handle authentication separately as it's a prerequisite for others
            if method == 'authenticate':
                token = params.get('token')
                is_authenticated = await self.authenticate(websocket, token)
                result_payload = {"authenticated": is_authenticated}
                if not is_authenticated:
                    result_payload["error"] = "Authentication failed"
                return self._format_response(result_payload, request_id)

            # Check authentication for all other methods
            if websocket not in self.authenticated_clients:
                self.logger.warning(f"Unauthenticated request for '{method}' from {websocket.remote_address}")
                return self._format_response(None, request_id, error="Client not authenticated. Please authenticate first.")

            # Route to method handlers
            if method == 'get_top_mvnos':
                result_data = await self.get_top_mvnos(params.get('n', 10))
            elif method == 'search_mvno':
                result_data = await self.search_mvno(params.get('mvno_name'))
            elif method == 'get_recent_alerts':
                result_data = await self.get_recent_alerts(params.get('days', 7))
            elif method == 'get_mvno_trend':
                result_data = await self.get_mvno_trend(
                    params.get('mvno_name'),
                    params.get('days', 30)
                )
            elif method == 'get_system_status':
                result_data = await self.get_system_status()
            else:
                self.logger.warning(f"Unknown method '{method}' requested by {websocket.remote_address}")
                return self._format_response(None, request_id, error=f"Unknown method: {method}")

            return self._format_response(result_data, request_id)

        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON received from {websocket.remote_address}: {message_str[:100]}")
            return self._format_response(None, request_id, error="Invalid JSON format")
        except Exception as e:
            self.logger.error(f"Error handling message for method {data.get('method', 'unknown')} from {websocket.remote_address}: {e}", exc_info=True)
            return self._format_response(None, request_id, error=str(e))

    def _format_response(self, result=None, request_id=None, error=None):
        """Helper to format JSON-RPC like responses"""
        response = {"timestamp": datetime.now().isoformat()}
        if request_id is not None:
            response["id"] = request_id

        if error:
            response["error"] = error
        else:
            response["result"] = result
        return response

    async def serve(self, websocket): # Removed path from signature
        """Handle WebSocket connections"""
        path = websocket.request.path # Get path from the request object

        # Health check is a special case, doesn't follow JSON-RPC message structure
        if await self.health_check_handler(websocket, path):
            # health_check_handler closes the websocket itself
            return

        self.logger.info(f"New connection from {websocket.remote_address} on path '{path}'")

        try:
            # Initial auth message is expected from client upon connection if not /health
            # This example structure assumes client sends auth first for other paths.
            # Alternatively, client can connect then send auth message.
            # For simplicity, we'll let handle_message manage auth flow.

            async for message_str in websocket:
                response_payload = await self.handle_message(websocket, message_str)
                await websocket.send(json.dumps(response_payload))

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed: {websocket.remote_address}")
        except websockets.exceptions.ConnectionClosedError:
            self.logger.info(f"Connection closed with error: {websocket.remote_address}")
        except websockets.exceptions.ConnectionClosedOK:
            self.logger.info(f"Connection closed gracefully: {websocket.remote_address}")
        except Exception as e:
            self.logger.error(f"Unexpected error in serve loop for {websocket.remote_address}: {e}", exc_info=True)
        finally:
            self.authenticated_clients.discard(websocket)
            self.logger.info(f"Cleaned up connection for {websocket.remote_address}. Current clients: {len(self.authenticated_clients)}")

    # --- Methods from original ghost_mcp_server.py ---
    def _assess_leniency(self, score):
        """Convert score to human-readable assessment"""
        if score is None:
            return "UNKNOWN"
        if score >= 4.0:
            return "HIGHLY LENIENT - Minimal verification"
        elif score >= 3.0:
            return "LENIENT - Basic verification only"
        elif score >= 2.0:
            return "MODERATE - Standard verification"
        else:
            return "STRINGENT - Enhanced verification"

    async def get_top_mvnos(self, n=None): # Default n handled by params.get later
        """Get top N lenient MVNOs from database"""
        # Validate n
        max_n = self.config.get("mcp_server.max_get_top_mvnos", 100)
        default_n = self.config.get("mcp_server.default_get_top_mvnos", 10)

        if n is None:
            n_val = default_n
        else:
            try:
                n_val = int(n)
            except (ValueError, TypeError):
                return {"error": f"Parameter 'n' must be an integer."}

        if not 1 <= n_val <= max_n:
            return {"error": f"Parameter 'n' must be between 1 and {max_n}."}

        self.logger.info(f"Executing get_top_mvnos with n={n_val}")
        mvnos_data = self.db.get_top_mvnos(n_val)

        return {
            "mvnos": [
                {
                    "rank": i + 1,
                    "name": mvno['mvno_name'],
                    "score": mvno['leniency_score'],
                    "assessment": self._assess_leniency(mvno['leniency_score']),
                    "last_updated": mvno['crawl_timestamp']
                }
                for i, mvno in enumerate(mvnos_data)
            ],
            "total_count": len(mvnos_data)
            # "generated_at" removed, now part of _format_response wrapper
        }

    async def search_mvno(self, mvno_name=None):
        """Search for a specific MVNO by name"""
        if not mvno_name or not isinstance(mvno_name, str) or not mvno_name.strip():
            return {"error": "Parameter 'mvno_name' must be a non-empty string."}

        # Optional: Sanitize or limit length if necessary
        # mvno_name = mvno_name.strip()[:100] # Example: trim and limit length

        self.logger.info(f"Executing search_mvno for {mvno_name}")
        mvno_data = self.db.get_mvno_by_name(mvno_name.strip())
        if mvno_data:
            return {
                "mvno": {
                    "name": mvno_data['mvno_name'],
                    "score": mvno_data['leniency_score'],
                    "assessment": self._assess_leniency(mvno_data['leniency_score']),
                    "policy_snapshot": json.loads(mvno_data['policy_snapshot']) if mvno_data.get('policy_snapshot') else None,
                    "last_updated": mvno_data['crawl_timestamp'],
                    "source_url": mvno_data.get('source_url')
                }
                # "generated_at" removed
            }
        else:
            # This structure is fine, handle_message will wrap it with "error" key if needed
            return {"error": f"MVNO '{mvno_name}' not found."}

    async def get_recent_alerts(self, days=None): # Default days handled by params.get later
        """Get recent policy changes/alerts"""
        default_days = self.config.get("mcp_server.default_alert_days", 7)
        max_days = self.config.get("mcp_server.max_alert_days", 90)

        if days is None:
            days_val = default_days
        else:
            try:
                days_val = int(days)
            except (ValueError, TypeError):
                return {"error": "Parameter 'days' must be an integer."}

        if not 1 <= days_val <= max_days:
            return {"error": f"Parameter 'days' must be between 1 and {max_days}."}

        self.logger.info(f"Executing get_recent_alerts for last {days_val} days")
        changes_data = self.db.get_recent_changes(days_val)

        return {
            "alerts": [
                {
                    "mvno_name": change['mvno_name'],
                    "change_type": change['change_type'],
                    "old_value": change['old_value'],
                    "new_value": change['new_value'],
                    "detected_timestamp": change['detected_timestamp']
                }
                for change in changes_data
            ],
            "total_count": len(changes_data)
            # "generated_at" removed
        }

    async def get_mvno_trend(self, mvno_name=None, days=None): # Defaults handled by params.get
        """Get policy trend for a specific MVNO over a period"""
        default_days = self.config.get("mcp_server.default_trend_days", 30)
        max_days = self.config.get("mcp_server.max_trend_days", 365)

        if not mvno_name or not isinstance(mvno_name, str) or not mvno_name.strip():
            return {"error": "Parameter 'mvno_name' must be a non-empty string."}

        # mvno_name_val = mvno_name.strip()[:100] # Optional sanitize/limit

        if days is None:
            days_val = default_days
        else:
            try:
                days_val = int(days)
            except (ValueError, TypeError):
                return {"error": "Parameter 'days' must be an integer."}

        if not 1 <= days_val <= max_days:
            return {"error": f"Parameter 'days' must be between 1 and {max_days}."}

        self.logger.info(f"Executing get_mvno_trend for {mvno_name.strip()} over {days_val} days")
        history_data = self.db.get_mvno_policy_history(mvno_name.strip(), days_val)
        return {
            "mvno_name": mvno_name.strip(),
            "trend": [
                {
                    "timestamp": record['crawl_timestamp'],
                    "score": record['leniency_score'],
                    "assessment": self._assess_leniency(record['leniency_score']),
                }
                for record in history_data
            ],
            "total_count": len(history_data)
            # "generated_at" removed
        }

    async def get_system_status(self):
        """Get system health and statistics"""
        self.logger.info("Executing get_system_status")
        db_stats = self.db.get_database_stats()

        return {
            "database_status": "connected",
            "total_mvnos_tracked": db_stats.get("total_mvnos"), # Ensure key matches GhostDB
            "last_policy_update": db_stats.get("last_policy_update_timestamp"),
            "total_policy_changes_logged": db_stats.get("total_changes"),
            "server_uptime": self.get_uptime(), # Use new get_uptime method
            "active_connections": len(self.authenticated_clients)
            # "generated_at" removed
        }
    # --- End of methods from original ghost_mcp_server.py ---

    async def run_server(self, host='0.0.0.0', port=8765): # Renamed from 'run' to avoid conflict if class named 'run'
        """Start the MCP server"""
        self.logger.info(f"Starting GHOST DMPM MCP Server v2 on ws://{host}:{port}") # DMPM added for consistency
        self.logger.info(f"Health check available at ws://{host}:{port}/health (GET request or WebSocket connection)")

        # Logs directory should be handled by GhostConfig's _init_logging method
        # which uses config.project_root. No need to create "logs" dir here explicitly.
        # log_dir = self.config.project_root / self.config.get("logging.directory", "logs")
        # log_dir.mkdir(parents=True, exist_ok=True) # This is done by GhostConfig

        server = await websockets.serve(self.serve, host, port)
        self.logger.info("Server startup complete. Waiting for connections.")
        await server.wait_closed()


if __name__ == "__main__":
    # Basic logging configuration for startup messages if GhostConfig hasn't set it up yet.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("Initializing GHOST MCP Server v2...")
    try:
        config = GhostConfig() # Assumes ghost_config.py is in the same directory or PYTHONPATH

        # Override spaCy check if it was causing issues - for robustness during deployment
        if hasattr(config, 'features'):
            config.features['nlp'] = False # Ensure NLP/spaCy is marked as unavailable to prevent hangs

        server = GhostMCPServer(config)

        print(f"Attempting to run server on {config.get('mcp_server.host', '0.0.0.0')}:{config.get('mcp_server.port', 8765)}")
        asyncio.run(server.run_server(
            host=config.get('mcp_server.host', '0.0.0.0'),
            port=config.get('mcp_server.port', 8765)
        ))
    except ImportError as e:
        print(f"ERROR: Failed to import required modules: {e}")
        print("Please ensure ghost_config.py and ghost_db.py are in the same directory or your PYTHONPATH is set correctly.")
        print("You might also need to install dependencies from requirements.txt (e.g., pip install websockets).")
    except websockets.exceptions.WebSocketException as wse:
        print(f"ERROR: WebSocket specific error during startup: {wse}")
        print("This could be due to port conflicts or network configuration issues.")
    except OSError as oe:
        print(f"ERROR: Operating system error during startup (e.g. port already in use): {oe}")
        print(f"If port {config.get('mcp_server.port', 8765)} is in use, please stop the other process or change the port in config.")
    except KeyboardInterrupt:
        print("\nShutting down GHOST MCP server (KeyboardInterrupt)...")
    except Exception as e:
        print(f"An unexpected error occurred during server startup or execution: {e}")
        logging.getLogger(__name__).error("Fatal error in __main__", exc_info=True)
    finally:
        print("GHOST MCP Server has shut down.")

# Ensure ghost_config.py has:
# class GhostConfig:
#     def get_logger(self, name):
#         logger = logging.getLogger(name)
#         # Basic setup if not already configured by main logging.basicConfig
#         if not logger.handlers: # Avoid adding handlers multiple times
#             handler = logging.StreamHandler() # Or your preferred handler
#             formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#             handler.setFormatter(formatter)
#             logger.addHandler(handler)
#             logger.setLevel(self.get("logging.level", "INFO")) # Use configured level
#         return logger
#
#     def get(self, key, default=None):
#         # ... (implementation of get)
#         # Example for mcp_server.host and mcp_server.port if not deeply nested:
#         # return self.config.get(key, default)
#         # If nested like "mcp_server": {"host": "0.0.0.0", "port": 8765}
#         keys = key.split('.')
#         value = self.config
#         for k_part in keys:
#             if isinstance(value, dict) and k_part in value:
#                 value = value[k_part]
#             else:
#                 return default
#         return value


# Ensure ghost_db.py has:
# class GhostDatabase:
#    def get_database_stats(self):
#        # Should return a dict like {"total_mvnos": X, "last_policy_update_timestamp": Y, "total_changes": Z}
#        # Or {"mvno_count": X ...} as per user's V2 template for health check
#        # Example:
#        # return {"total_mvnos": 100, "mvno_count": 100, ...}
#        pass
#
#    def get_top_mvnos(self, n): pass
#    def get_mvno_by_name(self, name): pass
#    def get_recent_changes(self, days): pass
#    def get_mvno_policy_history(self, name, days): pass
#
# Make sure the keys used (e.g. 'mvno_name', 'leniency_score', 'crawl_timestamp') match DB schema.
# Make sure policy_snapshot is handled (e.g. json.loads) if stored as TEXT.
# sys.path.append needed if ghost_config/ghost_db are not in same dir as server or in PYTHONPATH.
# The V2 template adds: sys.path.append(str(Path(__file__).parent))
# which is good if all ghost_*.py files are in the same directory.
# If ghost_config.py or ghost_db.py are in a *parent* directory, it should be:
# sys.path.append(str(Path(__file__).resolve().parent.parent))
# For now, assuming they are meant to be in the same directory as ghost_mcp_server_v2.py
# or that PYTHONPATH is correctly set by the deployment environment.
# Changed the sys.path.append to use resolve().parent for robustness.
# Added some more robust error handling and comments in __main__.
# Added placeholder comments for GhostConfig and GhostDatabase for clarity.
# Changed server.run() to server.run_server() to avoid potential name collision.
# Made health check db stats query more robust.
# Ensured health check websocket is closed.
# Adjusted auth token key in authenticate method to match original server.
# Refined JSON-RPC response formatting.
# Added more logging to serve() method, especially around connection lifecycle.
# Added explicit check for "total_mvnos" or "mvno_count" in health check from db_stats.
# Added some basic logging configuration in __main__ for early messages.
# Ensured logger in GhostMCPServer uses config.get_logger("MCP-Server").
# Added a note on disabling spaCy check in __main__ for GhostConfig for robustness.Tool output for `create_file_with_block`:
