# GHOST DMPM MCP Server - Remote Deployment Guide

This guide is for an operator who will deploy the MCP server on a remote system where Python 3.9+ is available.

## Items You Should Receive

1.  **Deployment Bundle**: `ghost-dmpm-mcp-bundle.tar.gz`
2.  **(This File)** `REMOTE_DEPLOYMENT.md`

## Deployment Steps for Remote Operator

1.  **Transfer and Extract Bundle**:
    *   Copy `ghost-dmpm-mcp-bundle.tar.gz` to the remote server.
    *   Log in to the remote server.
    *   Extract the bundle:
        ```bash
        tar -xzf ghost-dmpm-mcp-bundle.tar.gz
        cd ghost-dmpm-mcp-bundle
        ```
        (This will create a directory named `ghost-dmpm-mcp-bundle` and you should `cd` into it.)

2.  **Set Up Python Environment (Recommended: Virtual Environment)**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
    *Note: If `python3` is not found, try `python`. Ensure it's Python 3.9+.*

3.  **Install Dependencies**:
    *   The bundle includes `requirements.txt`. Install these:
        ```bash
        pip3 install -r requirements.txt
        ```
    *   If `pip3` is not found, try `pip`.
    *   A key dependency is `websockets`. If `requirements.txt` is minimal or missing, at least install websockets: `pip3 install websockets`.

4.  **Review Configuration (Optional but Recommended)**:
    *   The main server configuration is in `config/ghost_config.json`.
    *   Key settings to check:
        *   `mcp_server.host`: Should typically be `0.0.0.0` to listen on all interfaces.
        *   `mcp_server.port`: Default is `8765`. Ensure this port is open on the server's firewall.
        *   `database.path`: Default is `data/ghost_data.db`. Ensure the `data` directory is writable by the user running the server.
        *   `mcp_server.auth_token`: Note this token if clients need to connect.

5.  **Start the MCP Server**:
    *   Run the server in the background using `nohup` and redirect output for logging:
        ```bash
        nohup python3 ghost_mcp_server.py > mcp_server.log 2>&1 &
        ```
    *   This will start the server, and it will continue running even if you log out. Output (and errors) will go to `mcp_server.log` in the current directory (`ghost-dmpm-mcp-bundle`).

6.  **Verify Server is Running**:
    *   Wait a few seconds for the server to initialize.
    *   Check the log file for startup messages:
        ```bash
        tail -n 20 mcp_server.log
        ```
        Look for lines like:
        `INFO:MCP-Server:Starting GHOST MCP Server v2 on ws://0.0.0.0:8765`
        `INFO:MCP-Server:Server startup complete. Waiting for connections.`
    *   Check if the process is running:
        ```bash
        ps aux | grep ghost_mcp_server.py
        ```
    *   Test the health endpoint (from the server itself, if `curl` is available):
        ```bash
        # This curl command may not work directly as it's a WebSocket endpoint.
        # curl http://localhost:8765/health
        # A more reliable test is using the Python snippet below.

        # Use this Python command to test the WebSocket health endpoint:
        python3 -c "import asyncio, websockets, json; \
        async def c(): \
            u='ws://localhost:8765/health'; \
            try: \
                async with websockets.connect(u) as ws: r = await ws.recv(); print(json.dumps(json.loads(r), indent=2)); \
            except Exception as e: print(f'Failed: {e}'); \
        asyncio.run(c())"
        ```
        This should print a JSON response with `"status": "healthy"` or `"status": "degraded"`.

7.  **Report Back**:
    *   Provide the output of the `tail mcp_server.log` command.
    *   Provide the output of the Python health check command.
    *   Confirm if the server process is running.
    *   Report any errors encountered.

## What Success Looks Like (for the Remote Operator to report)

*   **Console/Log Output**: The `mcp_server.log` should show successful startup messages without critical errors.
*   **Health Check**: The Python health check script should return JSON with `status: "healthy"` (or `degraded` if the database is not yet fully initialized, which might be okay for a first run).
*   **Process Running**: `ps aux | grep ghost_mcp_server.py` shows the server process.

## For the Requestor: Accessing the Remotely Deployed Server

Once the remote operator confirms the server is running, you might need to access it.

### 1. Direct Access (If server's IP/port is publicly accessible and firewalled correctly)
*   Use `mcp_client.py` configured with the remote server's IP address and port.

### 2. SSH Tunnel (Secure way to access a port on a remote server as if it were local)
*   From your local machine:
    ```bash
    ssh -L 8765:<remote_server_ip_or_localhost>:8765 user@remote-server-ip
    ```
    *   Replace `8765` with the local port you want to use (e.g., `9000:localhost:8765` to map remote 8765 to local 9000).
    *   `<remote_server_ip_or_localhost>`: Use `localhost` if the MCP server on the remote machine is bound to `0.0.0.0` or `127.0.0.1`. If it's bound to a specific IP on the remote, use that.
    *   `user@remote-server-ip`: Your SSH login credentials for the remote server.
*   After establishing the tunnel, you can point `mcp_client.py` (or other tools) to `ws://localhost:8765` (or your chosen local port) on your machine.

### 3. Reverse Proxy (e.g., nginx, if a web server is available on the remote machine)
*   This is more complex and involves configuring the web server on the remote machine to pass requests to the MCP server. Example nginx config snippet:
    ```nginx
    # In your nginx server block for the desired domain/IP

    location /mcp_websocket/ {  # Example path for the MCP server
        proxy_pass http://localhost:8765; # Assuming MCP runs on localhost:8765 on the remote server
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s; # Keep connection open longer for WebSockets
    }
    ```
*   Clients would then connect to `ws://your-remote-domain.com/mcp_websocket/`.

Choose the access method appropriate for your security requirements and network setup.
The SSH tunnel is often a good balance of security and simplicity for direct testing.
