import asyncio
import websockets
import json
import logging
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/ghost_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GhostMCPServer")

MCP_AUTH_TOKEN = "ghost-mcp-2024"  # As specified in docker-compose and quickstart

# --- Authentication Decorator ---
def authenticate(func):
    @wraps(func)
    async def wrapper(websocket, message):
        if "token" not in message or message["token"] != MCP_AUTH_TOKEN:
            await websocket.send(json.dumps({"error": "Authentication failed", "success": False}))
            logger.warning(f"Authentication failed for command {message.get('command')} from {websocket.remote_address}")
            return
        logger.info(f"Authenticated command {message.get('command')} from {websocket.remote_address}")
        return await func(websocket, message)
    return wrapper

# --- MCP Tool Implementations (Placeholders) ---

@authenticate
async def get_config_handler(websocket, message):
    # Placeholder: Implement interaction with ghost_config.py
    logger.info("Executing get_config command")
    # Example: from ghost_config import GhostConfig; config = GhostConfig(); data = config.config
    await websocket.send(json.dumps({"command": "get_config", "status": "success", "data": {"message": "get_config not fully implemented yet"}}))

@authenticate
async def run_crawl_handler(websocket, message):
    # Placeholder: Implement interaction with ghost_crawler.py
    logger.info("Executing run_crawl command")
    # Example: from ghost_crawler import GhostCrawler; from ghost_config import GhostConfig
    # config = GhostConfig(); crawler = GhostCrawler(config); results = crawler.search_mvno_policies()
    await websocket.send(json.dumps({"command": "run_crawl", "status": "success", "data": {"message": "run_crawl not fully implemented yet"}}))

@authenticate
async def parse_data_handler(websocket, message):
    # Placeholder: Implement interaction with ghost_parser.py
    # This might need input data (e.g., path to raw crawl results)
    logger.info("Executing parse_data command")
    # Example: from ghost_parser import GhostParser; from ghost_config import GhostConfig
    # config = GhostConfig(); parser = GhostParser(config);
    # search_results_file = message.get("payload", {}).get("search_results_file")
    # if search_results_file: parsed_data = parser.parse_results(json.load(open(search_results_file)))
    await websocket.send(json.dumps({"command": "parse_data", "status": "success", "data": {"message": "parse_data not fully implemented yet"}}))

@authenticate
async def get_report_handler(websocket, message):
    # Placeholder: Implement interaction with ghost_reporter.py
    logger.info("Executing get_report command")
    # Example: from ghost_reporter import GhostReporter; from ghost_config import GhostConfig
    # config = GhostConfig(); reporter = GhostReporter(config); report = reporter.generate_intelligence_brief()
    await websocket.send(json.dumps({"command": "get_report", "status": "success", "data": {"message": "get_report not fully implemented yet"}}))

@authenticate
async def query_database_handler(websocket, message):
    # Placeholder: Implement interaction with ghost_db.py
    # This will need specific query parameters, e.g., mvno_name, limit, days
    logger.info("Executing query_database command")
    # Example: from ghost_db import GhostDatabase; from ghost_config import GhostConfig
    # config = GhostConfig(); db = GhostDatabase(config);
    # query_type = message.get("payload", {}).get("query_type")
    # if query_type == "top_mvnos": data = db.get_top_mvnos(message.get("payload",{}).get("limit", 10))
    await websocket.send(json.dumps({"command": "query_database", "status": "success", "data": {"message": "query_database not fully implemented yet"}}))


# --- WebSocket Request Handler ---
async def mcp_handler(websocket, path):
    logger.info(f"Client connected: {websocket.remote_address}")
    try:
        async for message_str in websocket:
            logger.debug(f"Received message: {message_str}")
            try:
                message = json.loads(message_str)
                command = message.get("command")

                if command == "get_config":
                    await get_config_handler(websocket, message)
                elif command == "run_crawl":
                    await run_crawl_handler(websocket, message)
                elif command == "parse_data":
                    await parse_data_handler(websocket, message)
                elif command == "get_report":
                    await get_report_handler(websocket, message)
                elif command == "query_database":
                    await query_database_handler(websocket, message)
                # Example of a non-authenticated command (e.g. ping)
                elif command == "ping":
                    await websocket.send(json.dumps({"command": "pong", "original_message": message.get("payload")}))
                else:
                    logger.warning(f"Unknown command: {command}")
                    await websocket.send(json.dumps({"error": "Unknown command", "success": False, "command_received": command}))

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                await websocket.send(json.dumps({"error": "Invalid JSON format", "success": False}))
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send(json.dumps({"error": str(e), "success": False}))
    except websockets.exceptions.ConnectionClosedError:
        logger.info(f"Client disconnected: {websocket.remote_address} (ConnectionClosedError)")
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"Client disconnected: {websocket.remote_address} (ConnectionClosedOK)")
    except Exception as e:
        logger.error(f"Connection error: {e}", exc_info=True)
    finally:
        logger.info(f"Connection closed for {websocket.remote_address}")


# --- Main Server Function ---
async def main():
    # Ensure logs directory exists
    import os
    if not os.path.exists("logs"):
        os.makedirs("logs")

    server = await websockets.serve(mcp_handler, "0.0.0.0", 8765)
    logger.info("GHOST MCP Server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
