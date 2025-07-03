#!/bin/bash
echo "=== GHOST MCP Server Test ==="

# Check if MCP container is running
if docker ps | grep -q ghost-mcp-server; then
    echo "[✓] MCP container running"
else
    echo "[!] MCP container not running"
    echo "    Attempting to start MCP server via docker-compose from project root..."
    # Assuming this script is run from project root: ./scripts/test_mcp.sh
    if docker-compose -f docker/docker-compose.yml up -d ghost-mcp; then
        echo "[✓] MCP server started successfully."
        echo "    Waiting for server to initialize..."
        sleep 5 # Give server a moment to start
    else
        echo "[✗] Failed to start MCP server via docker-compose."
        echo "    Please ensure Docker and Docker Compose are correctly set up,"
        echo "    and the ghost-mcp service is defined in your docker-compose.yml."
        exit 1
    fi
fi

# Test WebSocket connection using the Python client
echo ""
echo "[*] Testing MCP connection using 'python -m ghost_dmpm.api.mcp_client'..."
# Ensure PYTHONPATH includes the 'src' directory, or run from project root.
# If running this script from the 'scripts' directory:
PYTHON_CMD="python3 -m ghost_dmpm.api.mcp_client"
if [ "$(basename $(pwd))" == "scripts" ]; then
    PYTHON_CMD="python3 -m ghost_dmpm.api.mcp_client"
    # For this to work, PYTHONPATH should include ../src or the script should be run from project root
    # Or, more robustly, ensure we are in project root context:
    # (cd .. && python3 -m ghost_dmpm.api.mcp_client)
    # For simplicity, assume user is in project root or PYTHONPATH is set.
    # If running from scripts/ dir, then python path needs adjustment.
    # Let's make it relative to the project root for execution from scripts/
    PYTHON_CMD="python3 -m ghost_dmpm.api.mcp_client"
    # This command needs to be run from the project root, or have src in PYTHONPATH.
    # The script itself is in scripts/, so to make `python -m` work, we need to be one level up
    # or add `../src` to PYTHONPATH.
    # For a script in `scripts/`, it's better to make paths explicit or change CWD.
    # Let's assume the script is run from the project root, e.g. `./scripts/test_mcp.sh`
fi

if $PYTHON_CMD; then
    echo "[✓] MCP client test executed successfully."
else
    echo "[✗] MCP client test reported an error or failed to run."
    echo "    Check the output above for details from the client."
    # Optionally, try to show server logs if client fails, as it might indicate server-side issues
    echo ""
    echo "[*] Recent MCP logs (last 20 lines in case of client error):"
    docker logs ghost-mcp-server --tail 20
    exit 1 # Exit if client script fails
fi

# Show logs regardless of client success for more info
echo ""
echo "[*] Recent MCP logs (last 10 lines):"
docker logs ghost-mcp-server --tail 10

echo ""
echo "=== Test Complete ==="
