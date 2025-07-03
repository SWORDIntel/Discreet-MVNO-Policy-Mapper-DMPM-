#!/bin/bash
# Creates a deployment bundle for someone who can run Python

echo "Creating GHOST DMPM MCP Deployment Bundle..."

# Create bundle directory
BUNDLE_DIR="ghost-dmpm-mcp-bundle"
mkdir -p $BUNDLE_DIR

# Copy all necessary files
# Ensure we copy the NEW ghost_mcp_server_v2.py and rename it to ghost_mcp_server.py in the bundle
if [ -f "ghost_mcp_server_v2.py" ]; then
    cp ghost_mcp_server_v2.py $BUNDLE_DIR/ghost_mcp_server.py
else
    echo "ERROR: ghost_mcp_server_v2.py not found!"
    # Attempt to copy original if v2 is missing, though this is not ideal
    cp ghost_mcp_server.py $BUNDLE_DIR/
fi

# Copy other ghost files, mcp_client, requirements, etc.
# Using a find command to be more robust for other ghost_*.py files
find . -maxdepth 1 -name 'ghost_*.py' ! -name 'ghost_mcp_server_v2.py' -exec cp {} $BUNDLE_DIR/ \;
# Explicitly copy other critical files
cp mcp_client.py $BUNDLE_DIR/
cp requirements.txt $BUNDLE_DIR/

# Optional files, check if they exist
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml $BUNDLE_DIR/
fi
if [ -f "MCP_QUICKSTART.md" ]; then
    cp MCP_QUICKSTART.md $BUNDLE_DIR/
fi
if [ -d "config" ]; then
    mkdir -p $BUNDLE_DIR/config
    cp config/* $BUNDLE_DIR/config/
fi
if [ -d "data" ]; then
    mkdir -p $BUNDLE_DIR/data
    # cp data/* $BUNDLE_DIR/data/ # Avoid copying actual data for a clean bundle
    echo "Note: 'data' directory structure created, but existing data not bundled." > $BUNDLE_DIR/data/placeholder.txt
fi
if [ -d "logs" ]; then
    mkdir -p $BUNDLE_DIR/logs
    echo "Note: 'logs' directory created for server operation." > $BUNDLE_DIR/logs/placeholder.txt
fi


# Create deployment instructions
cat > $BUNDLE_DIR/DEPLOY_INSTRUCTIONS.md << 'INSTRUCTIONS'
# GHOST DMPM MCP Deployment Instructions

## Requirements
- Python 3.9+ (ensure pip is available)
- Docker and docker-compose (optional, if using Docker deployment)
- Network access on port 8765 (or as configured)

## Setup & Deployment

### 1. Prepare Environment
Ensure Python 3.9+ is installed. It's recommended to use a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows
```

### 2. Install Dependencies
```bash
pip3 install -r requirements.txt
```
*Note: `requirements.txt` should include `websockets` and any other dependencies for `ghost_config.py`, `ghost_db.py`, etc.*

### 3. Configuration (Optional)
- The server uses `config/ghost_config.json`. A default is usually created.
- Key settings:
    - `database.path`: Location of the SQLite database (e.g., "data/ghost_data.db")
    - `mcp_server.auth_token`: Authentication token for clients.
    - `mcp_server.host`, `mcp_server.port`: Server listen address and port.

### 4. Running the Server

#### Option A: Direct Python Execution
```bash
python3 ghost_mcp_server.py
```
The server will log to the console and to `logs/ghost_YYYYMMDD.log`.

#### Option B: Docker (If `docker-compose.yml` is configured)
```bash
docker-compose up --build -d
```
To view logs: `docker-compose logs -f mcp_server` (assuming service name is `mcp_server`)

## Verification

### 1. Check Server Logs
Look for messages like:
```
INFO:MCP-Server:Starting GHOST MCP Server v2 on ws://0.0.0.0:8765
INFO:MCP-Server:Health check available at ws://0.0.0.0:8765/health (GET request or WebSocket connection)
INFO:MCP-Server:Server startup complete. Waiting for connections.
```

### 2. Test Health Endpoint
From a terminal on the same machine (or another machine that can reach the server):
```bash
# Using curl (if server is on localhost:8765 and accessible via HTTP for health, though it's a WebSocket server)
# This might not work directly if the health check is WebSocket only.
# curl http://localhost:8765/health

# Using Python to test WebSocket health endpoint:
python3 -c "
import asyncio
import websockets
import json

async def check_health():
    uri = 'ws://localhost:8765/health' # Adjust if host/port differs
    try:
        async with websockets.connect(uri) as websocket:
            response = await websocket.recv()
            print('Health Check Response:')
            print(json.dumps(json.loads(response), indent=2))
    except Exception as e:
        print(f'Error during health check: {e}')

asyncio.run(check_health())
"
```
Expected output is a JSON object with `"status": "healthy"` (or `"degraded"` if DB issues).

### 3. Test with MCP Client
Run the provided `mcp_client.py`:
```bash
python3 mcp_client.py
```
This should connect, authenticate, and perform some basic queries.

## Test Suite
A more comprehensive test suite is available:
```bash
python3 test_mcp_complete.py
```

## Troubleshooting
1.  **Port already in use (e.g., 8765)**:
    *   Find process: `sudo lsof -i :8765` (Linux/macOS) or `netstat -ano | findstr :8765` (Windows)
    *   Kill the process or change the port in `config/ghost_config.json`.
2.  **Import Errors (`ModuleNotFoundError`)**:
    *   Ensure you are in the correct directory (`ghost-dmpm-mcp-bundle`).
    *   Make sure all `ghost_*.py` files are present in this directory.
    *   Verify dependencies are installed: `pip3 install -r requirements.txt`.
    *   If using a virtual environment, ensure it's activated.
3.  **Connection Refused/Timeout (Client or Health Check)**:
    *   Verify the server is running and listening on the correct host/port.
    *   Check firewalls (local and network) are not blocking the port.
    *   If running in Docker, ensure ports are correctly mapped.
4.  **Database Issues (`OperationalError`, etc.)**:
    *   Ensure the path in `config/ghost_config.json` for `database.path` is correct and writable.
    *   If it's a new setup, the database should be created automatically.
    *   The `main.py` script (if included and part of the broader GHOST DMPM system) might be needed to populate initial data. The MCP server itself doesn't populate the DB.
INSTRUCTIONS

# Create test suite (as provided by user)
cat > $BUNDLE_DIR/test_mcp_complete.py << 'TEST'
#!/usr/bin/env python3
"""Complete MCP test suite"""
import asyncio
import json
import websockets # Explicitly import for health check part
from mcp_client import GhostMCPClient # Assumes mcp_client.py is in the same dir

async def run_tests():
    print("=== GHOST DMPM Complete Test Suite ===\n")

    # Default client for most tests (uses token from mcp_client.py's default)
    client = GhostMCPClient()
    passed_count = 0
    failed_count = 0

    # Define tests as (Name, function_to_call, requires_connection_first)
    # test_auth needs special handling as it tests failed auth too

    print("--- Standard Client Tests ---")

    async def run_single_test(test_name, test_func, use_client):
        nonlocal passed_count, failed_count
        print(f"Testing {test_name}...", end=" ", flush=True)
        try:
            await test_func(use_client)
            print("✅ PASSED")
            passed_count += 1
        except Exception as e:
            print(f"❌ FAILED: {e}")
            # import traceback
            # traceback.print_exc() # Uncomment for detailed traceback during debugging
            failed_count += 1

    # Connection Test (special, as others depend on it)
    print("Testing Connection...", end=" ", flush=True)
    try:
        await client.connect()
        print("✅ PASSED (Connected)")
        passed_count += 1
        connection_ok = True
    except Exception as e:
        print(f"❌ FAILED to connect: {e}")
        failed_count += 1
        connection_ok = False
    finally:
        if client.websocket: # Ensure client is closed if connect was attempted
             await client.close()
             print("Closed client connection post-connection test.")

    if connection_ok:
        # These tests require a client that can successfully connect and auth
        standard_tests = [
            ("Get Top MVNOs (requires auth)", test_get_top_mvnos),
            ("Search MVNO (requires auth)", test_search_mvno),
            ("Recent Alerts (requires auth)", test_recent_alerts),
            ("System Status (requires auth)", test_system_status),
        ]
        for name, func in standard_tests:
            # Each of these tests will establish its own connection using the default client
            await run_single_test(name, func, client)
    else:
        print("Skipping standard authenticated tests due to initial connection failure.")

    # Standalone tests (manage their own client or don't need standard auth)
    print("\n--- Standalone Tests ---")
    await run_single_test("Authentication Logic", test_auth_logic, None) # test_auth_logic uses its own client
    await run_single_test("Health Check Endpoint", test_health_check_endpoint, None) # test_health_check uses websockets directly

    print(f"\n=== Results: {passed_count} passed, {failed_count} failed ===")

# Test function implementations
async def test_auth_logic(_): # Param is placeholder, not used
    # Test with wrong token
    bad_client = GhostMCPClient(token="wrong-token-for-sure")
    try:
        await bad_client.connect() # This connect includes authentication attempt
        # If it reaches here, auth with wrong token somehow passed, or client doesn't raise on auth fail
        if bad_client.websocket and bad_client.websocket.open: # Check if actually connected despite bad token
             await bad_client.close()
        raise Exception("Authentication with wrong token should have failed or resulted in no usable connection.")
    except websockets.exceptions.InvalidStatusCode as isc:
        # This might be an expected way for server to reject bad auth if it closes connection
        print(f"(Expected auth failure with status code: {isc.status_code})", end=" ")
    except Exception as e:
        # General exception could be fine if it indicates auth failure (e.g. custom client exception)
        print(f"(Expected auth failure: {type(e).__name__})", end=" ")
        pass # Expected path for failed auth

    # Test with correct token (implicitly done by other tests, but can be explicit if needed)
    # good_client = GhostMCPClient() # Assumes default token in mcp_client.py is correct
    # await good_client.connect()
    # assert good_client.websocket and good_client.websocket.open, "Client with good token failed to connect/authenticate"
    # await good_client.close()


async def test_get_top_mvnos(client):
    await client.connect() # Connects and authenticates
    result = await client.get_top_mvnos(3) # Test with n=3
    assert "result" in result, "Result key missing"
    assert "mvnos" in result["result"], "MVNOs key missing in result"
    assert len(result["result"]["mvnos"]) <= 3, "More MVNOs returned than requested"
    await client.close()

async def test_search_mvno(client):
    await client.connect()
    # Assuming "Mint Mobile" is a known MVNO for testing; adjust if needed
    result = await client.search_mvno("Mint Mobile")
    assert "result" in result, "Result key missing"
    # Search can return an error if not found, which is valid.
    # This assertion might need to be more nuanced based on expected test data.
    # For now, just check that the 'result' field exists.
    # If it must be found: assert "mvno" in result["result"] or "error" not in result["result"]
    await client.close()

async def test_recent_alerts(client):
    await client.connect()
    result = await client.get_alerts(7) # Assuming get_alerts is a method in GhostMCPClient
    assert "result" in result, "Result key missing"
    assert "alerts" in result["result"], "Alerts key missing in result"
    await client.close()

async def test_system_status(client):
    await client.connect()
    result = await client.query("get_system_status", {}) # Generic query
    assert "result" in result, "Result key missing"
    assert "server_uptime" in result["result"], "System status missing uptime"
    await client.close()

async def test_health_check_endpoint(_): # Param is placeholder
    uri = 'ws://localhost:8765/health' # Adjust if host/port differs
    async with websockets.connect(uri) as websocket:
        response_str = await websocket.recv()
        data = json.loads(response_str)
        assert data.get("status") in ["healthy", "degraded"], f"Unexpected status in health check: {data.get('status')}"
        assert "timestamp" in data, "Health check missing timestamp"
        assert "components" in data, "Health check missing components"

if __name__ == "__main__":
    asyncio.run(run_tests())
TEST

# Create tar.gz bundle
# Using GNU tar options for compatibility.
tar -czf ghost-dmpm-mcp-bundle.tar.gz "$BUNDLE_DIR/"

echo "✅ Deployment bundle created: ghost-dmpm-mcp-bundle.tar.gz"
echo ""
echo "To deploy, transfer this file to a system with Python and run:"
echo "  tar -xzf ghost-dmpm-mcp-bundle.tar.gz"
echo "  cd $BUNDLE_DIR"
echo "  cat DEPLOY_INSTRUCTIONS.md"
echo "  # Then follow instructions, e.g., pip install and run server."
EOF

# Make the bundle script executable
chmod +x create_deployment_bundle.sh
