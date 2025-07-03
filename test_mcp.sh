#!/bin/bash
echo "=== GHOST MCP Server Test ==="

# Check if MCP container is running
if docker ps | grep -q ghost-mcp-server; then
    echo "[✓] MCP container running"
else
    echo "[!] MCP container not running"
    echo "    Attempting to start MCP server via docker-compose..."
    if docker-compose up -d ghost-mcp; then
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
echo "[*] Testing MCP connection using mcp_client.py..."
if python3 mcp_client.py; then
    echo "[✓] mcp_client.py executed successfully."
else
    echo "[✗] mcp_client.py reported an error or failed to run."
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
