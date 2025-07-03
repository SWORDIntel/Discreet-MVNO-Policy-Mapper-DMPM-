# MCP Server v2 Verification Checklist

## For the Operator Deploying the Server

This checklist helps ensure the GHOST DMPM MCP Server (v2 with Health Check) is deployed and functioning correctly.

### I. Pre-Deployment Checks
- [ ] **Python Version**: Python 3.9+ is installed and accessible (`python3 --version`).
- [ ] **Port Availability**: Port 8765 (or the configured port for MCP) is available and not in use by another application.
    *   *To check (Linux/macOS)*: `sudo lsof -i :8765`
    *   *To check (Windows)*: `netstat -ano | findstr :8765`
- [ ] **Files Present**: All necessary files from the `ghost-dmpm-mcp-bundle` are present in the deployment directory:
    - [ ] `ghost_mcp_server.py` (this is the renamed `ghost_mcp_server_v2.py`)
    - [ ] `ghost_config.py`
    - [ ] `ghost_db.py`
    - [ ] `mcp_client.py`
    - [ ] `requirements.txt`
    - [ ] `test_mcp_complete.py`
    - [ ] `DEPLOY_INSTRUCTIONS.md`
    - [ ] `config/` directory (if default config is used, or with `ghost_config.json` if customized)
    - [ ] `data/` directory (will be created by server if not present, for the database)
    - [ ] `logs/` directory (will be created by server if not present)
- [ ] **Dependencies**: Python package dependencies are ready to be installed from `requirements.txt`.
    *   Consider using a Python virtual environment.

### II. Deployment & Initial Startup
1. [ ] **Navigate to Bundle Directory**: `cd ghost-dmpm-mcp-bundle`
2. [ ] **(Recommended) Activate Virtual Environment**:
    *   `python3 -m venv .venv`
    *   `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows)
3. [ ] **Install Dependencies**: `pip3 install -r requirements.txt`
    *   Verify successful installation without errors.
4. [ ] **Start MCP Server**: `python3 ghost_mcp_server.py`
    *   Observe console output for startup messages.
5. [ ] **Confirm Startup Messages**: Check console for logs similar to:
    ```
    Initializing GHOST MCP Server v2...
    Attempting to run server on <host>:<port>...
    INFO:MCP-Server:Starting GHOST MCP Server v2 on ws://<host>:<port>
    INFO:MCP-Server:Health check available at ws://<host>:<port>/health (GET request or WebSocket connection)
    INFO:MCP-Server:Server startup complete. Waiting for connections.
    ```
    *   Note any error messages during startup.

### III. Health Check Verification
1. [ ] **Access Health Endpoint**: Use the Python script from `DEPLOY_INSTRUCTIONS.md` or `test_mcp_complete.py`'s health check function.
    ```bash
    python3 -c "
    import asyncio
    import websockets
    import json

    async def check_health():
        uri = 'ws://localhost:8765/health' # Adjust host/port if not default
        try:
            async with websockets.connect(uri) as websocket:
                response = await websocket.recv()
                print('Health Check Response:')
                data = json.loads(response)
                print(json.dumps(data, indent=2))
                if data.get('status') in ['healthy', 'degraded']:
                    print('\n✅ Health status field is valid.')
                else:
                    print('\n❌ Health status field is MISSING or INVALID.')
        except Exception as e:
            print(f'Error during health check: {e}')

    asyncio.run(check_health())
    "
    ```
2. [ ] **Verify Health JSON Response**: The output should be a JSON object similar to:
    ```json
    {
      "status": "healthy",  // or "degraded" if DB has issues
      "timestamp": "YYYY-MM-DDTHH:MM:SS.ffffff",
      "version": "2.0.0",
      "uptime": "Xd Yh Zm", // Example: "0d 0h 5m"
      "components": {
        "database": "healthy", // or "degraded"
        "websocket": "healthy"
      },
      "metrics": {
        "connected_clients": 0, // Initially 0
        "tracked_mvnos": 0  // Or actual count if DB is populated
      }
    }
    ```
    *   Check for `"status": "healthy"` (or `"degraded"` if database is not yet fully populated/accessible but server is up).
    *   Confirm `version` is `"2.0.0"`.
    *   Ensure `components.database` and `components.websocket` statuses are present.

### IV. Basic Client Connectivity Test
1. [ ] **Run MCP Client Test**: Execute `python3 mcp_client.py` (ensure it's configured with the correct auth token if not using the default).
2. [ ] **Observe Client Output**: Look for successful connection, authentication, and query results. Example snippet:
    ```
    [✓] Connected to GHOST MCP Server
    [✓] Authenticated successfully.
    [✓] get_top_mvnos (Sample): ...
    [✓] get_system_status (Sample): ...
    [✓] get_recent_alerts (Sample): ...
    Connection closed.
    ```
    *   Note any errors like "Authentication failed" or "Connection refused".

### V. Comprehensive Test Suite (Optional but Recommended)
1. [ ] **Run Full Test Suite**: `python3 test_mcp_complete.py`
2. [ ] **Review Test Results**: Check the summary for passed/failed tests. Address any failures.

### VI. Final Operational Checks
- [ ] **Server Stability**: Server remains running without crashing after tests.
- [ ] **Log Review**: Briefly check `logs/ghost_YYYYMMDD.log` and `logs/ghost_mcp_server.log` (if configured differently by GhostConfig) for any unexpected errors or excessive warnings.

### Success Indicators
- ✅ Health endpoint returns valid JSON with an acceptable status (`healthy` or `degraded`).
- ✅ MCP server starts without critical errors logged to console.
- ✅ `mcp_client.py` can connect, authenticate, and retrieve data.
- ✅ `test_mcp_complete.py` shows a high number of passed tests.
- ✅ Server remains operational after tests.

### Common Troubleshooting Points (Refer to `DEPLOY_INSTRUCTIONS.md` for more details)
*   **Port Conflicts**: Ensure port 8765 (or configured port) is free.
*   **Python Import Errors**: Check virtual environment, `requirements.txt` installation, and file locations.
*   **Database Issues**: Verify `config/ghost_config.json` points to a writable database location. If the GHOST DMPM system requires it, run `main.py` (or equivalent data population script) to populate the database.
*   **Firewall**: Ensure the server port is not blocked by local or network firewalls.
*   **Authentication Token**: Ensure `mcp_client.py` and any other clients are using the correct `mcp_server.auth_token` defined in `config/ghost_config.json`.
