import asyncio
import websockets
import json
import logging
from datetime import datetime
from functools import wraps

# Assuming ghost_db and ghost_config will be available in the parent directory
# For direct execution, ensure PYTHONPATH is set or these are installed
try:
    from ghost_db import GhostDatabase
    from ghost_config import GhostConfig
except ImportError:
    # Fallback for cases where the script might be run directly and modules are in parent dir
    import sys
    sys.path.append('..')
    from ghost_db import GhostDatabase
    from ghost_config import GhostConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/ghost_mcp_server.log"),
        logging.StreamHandler()
    ]
)

class GhostMCPServer:
    def __init__(self, config):
        self.logger = logging.getLogger("GhostMCPServer")
        self.config = config
        self.db = GhostDatabase(config)
        self.auth_token = self.config.get("mcp_server.auth_token", "ghost-mcp-2024") # Get token from config or default
        self.authenticated_clients = set()

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

    async def handle_authentication(self, websocket, params):
        """Handles authentication message."""
        token = params.get("token")
        if token == self.auth_token:
            self.authenticated_clients.add(websocket)
            self.logger.info(f"Client {websocket.remote_address} authenticated.")
            return {"authenticated": True, "message": "Authentication successful."}
        else:
            self.logger.warning(f"Authentication failed for client {websocket.remote_address}.")
            return {"authenticated": False, "error": "Invalid token."}

    async def get_top_mvnos(self, n=10):
        """Get top N lenient MVNOs from database"""
        self.logger.info(f"Executing get_top_mvnos with n={n}")
        mvnos_data = self.db.get_top_mvnos(n) # This should return a list of dict-like objects

        return {
            "mvnos": [
                {
                    "rank": i + 1,
                    "name": mvno['mvno_name'],
                    "score": mvno['leniency_score'],
                    "assessment": self._assess_leniency(mvno['leniency_score']),
                    "last_updated": mvno['crawl_timestamp'] # Ensure this key exists in your DB output
                }
                for i, mvno in enumerate(mvnos_data)
            ],
            "total_count": len(mvnos_data),
            "generated_at": datetime.now().isoformat()
        }

    async def search_mvno(self, mvno_name):
        """Search for a specific MVNO by name"""
        self.logger.info(f"Executing search_mvno for {mvno_name}")
        if not mvno_name:
            return {"error": "MVNO name not provided."}

        mvno_data = self.db.get_mvno_by_name(mvno_name) # Requires implementation in GhostDatabase
        if mvno_data:
            return {
                "mvno": {
                    "name": mvno_data['mvno_name'],
                    "score": mvno_data['leniency_score'],
                    "assessment": self._assess_leniency(mvno_data['leniency_score']),
                    "policy_snapshot": json.loads(mvno_data['policy_snapshot']) if mvno_data.get('policy_snapshot') else None,
                    "last_updated": mvno_data['crawl_timestamp'],
                    "source_url": mvno_data.get('source_url')
                },
                "generated_at": datetime.now().isoformat()
            }
        else:
            return {"error": f"MVNO '{mvno_name}' not found."}

    async def get_recent_alerts(self, days=7):
        """Get recent policy changes/alerts"""
        self.logger.info(f"Executing get_recent_alerts for last {days} days")
        changes_data = self.db.get_recent_changes(days) # Assumes this method exists and returns list of dicts

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
            "total_count": len(changes_data),
            "generated_at": datetime.now().isoformat()
        }

    async def get_mvno_trend(self, mvno_name, days=30):
        """Get policy trend for a specific MVNO over a period"""
        self.logger.info(f"Executing get_mvno_trend for {mvno_name} over {days} days")
        if not mvno_name:
            return {"error": "MVNO name not provided."}

        history_data = self.db.get_mvno_policy_history(mvno_name, days) # Requires implementation in GhostDatabase
        return {
            "mvno_name": mvno_name,
            "trend": [
                {
                    "timestamp": record['crawl_timestamp'],
                    "score": record['leniency_score'],
                    "assessment": self._assess_leniency(record['leniency_score']),
                    # "policy_snapshot": json.loads(record['policy_snapshot']) # Optional: could be large
                }
                for record in history_data
            ],
            "total_count": len(history_data),
            "generated_at": datetime.now().isoformat()
        }

    async def get_system_status(self):
        """Get system health and statistics"""
        self.logger.info("Executing get_system_status")
        db_stats = self.db.get_database_stats() # Requires implementation in GhostDatabase

        # Example status structure, can be expanded
        return {
            "database_status": "connected", # Simplified, actual check might be needed
            "total_mvnos_tracked": db_stats.get("total_mvnos"),
            "last_policy_update": db_stats.get("last_policy_update_timestamp"),
            "total_policy_changes_logged": db_stats.get("total_changes"),
            "server_uptime": "N/A", # Could be implemented if server start time is tracked
            "active_connections": len(self.authenticated_clients), # Basic connection count
            "generated_at": datetime.now().isoformat()
        }

    async def handle_message(self, websocket, message_str):
        """Route messages to appropriate handlers"""
        try:
            data = json.loads(message_str)
            method = data.get('method')
            params = data.get('params', {})
            request_id = data.get('id')

            self.logger.info(f"Received method: {method} from {websocket.remote_address}")

            if method == 'authenticate':
                result = await self.handle_authentication(websocket, params)
                response = {"id": request_id, "result": result, "timestamp": datetime.now().isoformat()}
                await websocket.send(json.dumps(response))
                return

            # For all other methods, check authentication
            if websocket not in self.authenticated_clients:
                self.logger.warning(f"Unauthenticated request for method {method} from {websocket.remote_address}")
                error_response = {
                    "id": request_id,
                    "error": "Client not authenticated. Please authenticate first.",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(error_response))
                return

            if method == 'get_top_mvnos':
                result = await self.get_top_mvnos(params.get('n', 10))
            elif method == 'search_mvno':
                result = await self.search_mvno(params.get('mvno_name'))
            elif method == 'get_recent_alerts':
                result = await self.get_recent_alerts(params.get('days', 7))
            elif method == 'get_mvno_trend':
                result = await self.get_mvno_trend(
                    params.get('mvno_name'),
                    params.get('days', 30)
                )
            elif method == 'get_system_status':
                result = await self.get_system_status()
            else:
                result = {"error": f"Unknown method: {method}"}

            response = {
                "id": request_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(response))

        except json.JSONDecodeError:
            self.logger.error("Invalid JSON received")
            error_response = {"error": "Invalid JSON format", "timestamp": datetime.now().isoformat()}
            await websocket.send(json.dumps(error_response))
        except Exception as e:
            self.logger.error(f"Error handling message: {e}", exc_info=True)
            error_response = {
                "id": data.get('id') if 'data' in locals() and isinstance(data, dict) else None,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response))

from functools import partial

# --- WebSocket Connection Handler ---
async def mcp_connection_handler(websocket, path, server_instance):
    server_instance.logger.info(f"Client connected: {websocket.remote_address} from path {path}")
    try:
        async for message_str in websocket:
            await server_instance.handle_message(websocket, message_str)
    except websockets.exceptions.ConnectionClosedError:
        server_instance.logger.info(f"Client disconnected: {websocket.remote_address} (ConnectionClosedError)")
    except websockets.exceptions.ConnectionClosedOK:
        server_instance.logger.info(f"Client disconnected: {websocket.remote_address} (ConnectionClosedOK)")
    except Exception as e:
        server_instance.logger.error(f"Connection error with {websocket.remote_address}: {e}", exc_info=True)
    finally:
        server_instance.logger.info(f"Connection closed for {websocket.remote_address}")
        if websocket in server_instance.authenticated_clients:
            server_instance.authenticated_clients.remove(websocket)


# --- Main Server Function ---
async def main():
    import os
    if not os.path.exists("logs"):
        os.makedirs("logs", exist_ok=True)

    # Initialize configuration
    # This basic config is just for the server to run; DB and other components might need more.
    # In a real setup, GhostConfig would load from a file or environment.
    # GhostConfig will load from "config/ghost_config.json" by default,
    # which should contain necessary settings like "mcp_server.auth_token"
    # and "database.path".
    config = GhostConfig()

    mcp_server_instance = GhostMCPServer(config)

    async def intermediate_handler(websocket, *args):
        # Log what args contains to diagnose the path issue
        mcp_server_instance.logger.info(f"Intermediate handler called for {websocket.remote_address} with args: {args}")
        path = args[0] if args and len(args) > 0 else None
        await mcp_connection_handler(websocket, path, mcp_server_instance)

    server = await websockets.serve(intermediate_handler, "0.0.0.0", 8765)
    mcp_server_instance.logger.info("GHOST MCP Server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    # This ensures that if ghost_config.py is not fully set up for standalone run,
    # we provide a minimal viable config.
    if 'GhostConfig' not in globals() or 'GhostDatabase' not in globals():
        print("Error: GhostConfig or GhostDatabase not imported correctly. Ensure PYTHONPATH includes parent directory or modules are installed.")
        print("Attempting to run with basic mock config if possible...")
        # A very basic mock config if GhostConfig is problematic during standalone dev
        class MockGhostConfig:
            def __init__(self, initial_config=None):
                self._config = initial_config or {}
                self._config.setdefault("database.path", "data/ghost_data.db")
                self._config.setdefault("logging.level", "INFO")
                self._config.setdefault("mcp_server.auth_token", "ghost-mcp-2024")

            def get(self, key, default=None):
                return self._config.get(key, default)

            def get_logger(self, name):
                logger = logging.getLogger(name)
                # Basic setup if not already configured by main logging.basicConfig
                if not logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                    logger.setLevel(self.get("logging.level", "INFO"))
                return logger

        if 'GhostConfig' not in globals(): globals()['GhostConfig'] = MockGhostConfig
        # Mock GhostDatabase if needed for basic server startup, though operations will fail
        if 'GhostDatabase' not in globals():
            class MockGhostDatabase:
                def __init__(self, config): self.logger = config.get_logger("MockGhostDB")
                def get_top_mvnos(self, n): self.logger.warning("Using MockGhostDatabase: get_top_mvnos"); return []
                def get_mvno_by_name(self, name): self.logger.warning("Using MockGhostDatabase: get_mvno_by_name"); return None
                def get_recent_changes(self, days): self.logger.warning("Using MockGhostDatabase: get_recent_changes"); return []
                def get_mvno_policy_history(self, name, days): self.logger.warning("Using MockGhostDatabase: get_mvno_policy_history"); return []
                def get_database_stats(self): self.logger.warning("Using MockGhostDatabase: get_database_stats"); return {}
            globals()['GhostDatabase'] = MockGhostDatabase
            print("WARNING: Using MOCK GhostDatabase. Database operations will not work correctly.")


    asyncio.run(main())
