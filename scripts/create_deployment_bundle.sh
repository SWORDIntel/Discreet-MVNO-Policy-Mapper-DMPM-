#!/bin/bash
# Creates a deployment bundle for someone who can run Python

echo "Creating GHOST DMPM MCP Deployment Bundle..."

# Create bundle directory
BUNDLE_DIR="ghost-dmpm-mcp-bundle"
# Clean existing bundle directory if it exists
if [ -d "$BUNDLE_DIR" ]; then
    echo "Cleaning up existing bundle directory: $BUNDLE_DIR"
    rm -rf "$BUNDLE_DIR"
fi
mkdir -p "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/src" # To place the package

# Copy the main package
echo "Copying ghost_dmpm package..."
cp -R ../src/ghost_dmpm "$BUNDLE_DIR/src/" # Assumes script is run from scripts/ dir

# Create helper scripts in the bundle root
echo "Creating helper scripts in bundle..."

# run_mcp_server.py
cat > "$BUNDLE_DIR/run_mcp_server.py" << 'RUN_SERVER_SCRIPT'
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add bundled src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ghost_dmpm.api.mcp_server import run_server
from ghost_dmpm.core.config import GhostConfig

if __name__ == "__main__":
    config = GhostConfig() # Uses default config name "ghost_config.json", project_root is bundle root
    # Ensure the 'config' and 'data' directories exist relative to the bundle root for GhostConfig
    (Path(__file__).parent / "config").mkdir(exist_ok=True)
    (Path(__file__).parent / "data").mkdir(exist_ok=True)
    (Path(__file__).parent / "logs").mkdir(exist_ok=True)

    host = config.get('mcp_server.host', '0.0.0.0')
    port = int(config.get('mcp_server.port', 8765))

    print(f"Attempting to run MCP server on {host}:{port} from bundle...")
    import asyncio
    asyncio.run(run_server(host=host, port=port)) # run_server from mcp_server.py should take config
RUN_SERVER_SCRIPT
chmod +x "$BUNDLE_DIR/run_mcp_server.py"

# run_mcp_client.py
cat > "$BUNDLE_DIR/run_mcp_client.py" << 'RUN_CLIENT_SCRIPT'
#!/usr/bin/env python3
import sys
from pathlib import Path
import asyncio

# Add bundled src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ghost_dmpm.api.mcp_client import GhostMCPClient # Assuming test_mcp_connection is what we want to run
# Or define a main function in mcp_client if it has one

async def main():
    # Example client usage, adapt from original mcp_client.py __main__ or test_mcp_connection
    client = GhostMCPClient() # Uses defaults ws://localhost:8765
    print("Attempting to connect to MCP server...")
    try:
        if await client.connect():
            print("Connected. Getting system status...")
            status = await client.get_system_status()
            print("System Status:", json.dumps(status, indent=2))
            await client.close()
        else:
            print("Could not connect or authenticate.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client.websocket:
            await client.close()

if __name__ == "__main__":
    # Need to import json for the print statement in main()
    import json
    asyncio.run(main())
RUN_CLIENT_SCRIPT
chmod +x "$BUNDLE_DIR/run_mcp_client.py"


# Copy requirements files
echo "Copying requirements..."
mkdir -p "$BUNDLE_DIR/requirements"
cp ../requirements/base.txt "$BUNDLE_DIR/requirements/"
cp ../requirements/optional.txt "$BUNDLE_DIR/requirements/"
# Create a single requirements.txt for the bundle for simplicity
cat "$BUNDLE_DIR/requirements/base.txt" "$BUNDLE_DIR/requirements/optional.txt" > "$BUNDLE_DIR/requirements.txt"


# Optional files, check if they exist relative to project root (parent of scripts/)
if [ -f "../docker/docker-compose.yml" ]; then
    mkdir -p "$BUNDLE_DIR/docker"
    cp ../docker/docker-compose.yml "$BUNDLE_DIR/docker/"
fi
if [ -f "../MCP_QUICKSTART.md" ]; then # Assuming it's in project root
    cp ../MCP_QUICKSTART.md "$BUNDLE_DIR/"
fi

# Config examples and necessary directory structure
echo "Copying config examples and creating directories..."
mkdir -p "$BUNDLE_DIR/config"
if [ -f "../config/ghost_config.json.example" ]; then
    cp ../config/ghost_config.json.example "$BUNDLE_DIR/config/"
fi
# Create data, logs, reports, test_output in the bundle so the app can write there
mkdir -p "$BUNDLE_DIR/data"
    mkdir -p $BUNDLE_DIR/data
mkdir -p "$BUNDLE_DIR/logs"
mkdir -p "$BUNDLE_DIR/reports"
mkdir -p "$BUNDLE_DIR/test_output"
echo "Note: 'data', 'logs', 'reports', 'test_output' directory structures created for application use." > "$BUNDLE_DIR/data/placeholder.txt"
echo "Bundle expects config at: $BUNDLE_DIR/config/ghost_config.json" >> "$BUNDLE_DIR/data/placeholder.txt"


# Create deployment instructions
cat > "$BUNDLE_DIR/DEPLOY_INSTRUCTIONS.md" << 'INSTRUCTIONS'
# GHOST DMPM MCP Deployment Instructions (Bundled)

This bundle contains the GHOST DMPM MCP server and related components.

## Requirements
- Python 3.9+ (ensure pip is available)
- Network access on port 8765 (or as configured in `config/ghost_config.json`)

## Setup & Deployment

### 1. Prepare Environment
Ensure Python 3.9+ is installed. It's recommended to use a virtual environment:
\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows
\`\`\`

### 2. Install Dependencies
All required Python packages are listed in `requirements.txt`.
\`\`\`bash
pip3 install -r requirements.txt
\`\`\`
*Note: This bundle's `requirements.txt` includes base dependencies and optional ones for crypto/NLP.*

### 3. Configuration (Important!)
- Copy the example configuration `config/ghost_config.json.example` to `config/ghost_config.json`.
  \`\`\`bash
  cp config/ghost_config.json.example config/ghost_config.json
  \`\`\`
- **Edit `config/ghost_config.json`**:
    - **Crucially, update `mcp_server.auth_token`**. This is the token clients will use.
    - Adjust `database.path` if needed (default is `data/ghost_data.db` relative to bundle root).
    - Configure `mcp_server.host` and `mcp_server.port` if defaults (0.0.0.0:8765) are not suitable.
    - Review other settings like logging, API keys (if using non-mock modes for other components, though MCP server itself doesn't directly use them).

### 4. Running the Server
Use the provided helper script:
\`\`\`bash
python3 run_mcp_server.py
\`\`\`
The server will log to the console and to files in the `logs/` directory (as configured).
The `run_mcp_server.py` script automatically adds the bundled `src/` directory to `PYTHONPATH` so imports work correctly.

### 5. (Optional) Docker Deployment
If you have Docker and `docker-compose.yml` was included and configured for this bundle:
\`\`\`bash
# This typically requires a Dockerfile specific to the bundle structure or building from the main project.
# The included docker-compose.yml might need adjustments for a bundled deployment.
# docker-compose -f docker/docker-compose.yml up --build -d
\`\`\`
*Note: Docker deployment from the bundle might be more complex than direct Python execution and may require a custom Dockerfile that understands the bundle's layout.*

## Verification

### 1. Check Server Logs
Look for messages like:
\`\`\`
INFO:ghost_dmpm_app.MCP-Server:Starting GHOST DMPM MCP Server v2 on ws://0.0.0.0:8765
INFO:ghost_dmpm_app.MCP-Server:Health check available at ws://0.0.0.0:8765/health (GET request or WebSocket connection)
INFO:ghost_dmpm_app.MCP-Server:Server startup complete. Waiting for connections.
\`\`\`
Log files are typically in the `logs/` directory within the bundle.

### 2. Test Health Endpoint
From a terminal (ensure the server is running):
\`\`\`bash
# Using Python to test WebSocket health endpoint:
python3 -c "
import asyncio
import websockets
import json

async def check_health():
    uri = 'ws://localhost:8765/health' # Adjust if host/port differs from default
    try:
        async with websockets.connect(uri) as websocket:
            response_str = await websocket.recv()
            response = json.loads(response_str)
            print('Health Check Response:')
            print(json.dumps(response, indent=2))
            if response.get('status') == 'healthy':
                print('\nHealth check PASSED.')
                return 0
            else:
                print('\nHealth check indicates issues.')
                return 1
    except Exception as e:
        print(f'Error during health check: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(check_health()))
"
\`\`\`
Expected output includes a JSON object with `"status": "healthy"`.

### 3. Test with MCP Client
Use the provided `run_mcp_client.py` script:
\`\`\`bash
python3 run_mcp_client.py
\`\`\`
This script will attempt to connect, authenticate (using default token "ghost-mcp-2024" - change this in the script if your server token is different or make the client configurable), and perform a basic query.
Ensure the token in `run_mcp_client.py` (or however it gets it) matches `mcp_server.auth_token` in your `config/ghost_config.json`.

## Troubleshooting
1.  **Port already in use (e.g., 8765)**:
    *   Find process: `sudo lsof -i :8765` (Linux/macOS) or `netstat -ano | findstr :8765` (Windows).
    *   Kill the process or change the port in `config/ghost_config.json` and restart `run_mcp_server.py`.
2.  **Import Errors (`ModuleNotFoundError`)**:
    *   Ensure you are in the root of the `ghost-dmpm-mcp-bundle` directory when running scripts.
    *   The `run_mcp_server.py` and `run_mcp_client.py` scripts handle `PYTHONPATH` for the bundled `src/` directory. If running modules directly, ensure `src/` is in your `PYTHONPATH`.
    *   Verify dependencies are installed: `pip3 install -r requirements.txt`.
    *   If using a virtual environment, ensure it's activated.
3.  **Authentication Failed (Client)**:
    *   Ensure the token used by the client matches `mcp_server.auth_token` in `config/ghost_config.json`. The default in example client scripts might need updating.
4.  **Connection Refused/Timeout**:
    *   Verify the server (`run_mcp_server.py`) is running and listening on the correct host/port.
    *   Check firewalls (local and network).
5.  **Database Issues (`OperationalError`, etc.)**:
    *   Ensure `config/ghost_config.json` has a correct `database.path` (e.g., `data/ghost_data.db`). The `data` directory should be writable by the server process.
    *   The database is typically created automatically by `GhostDatabase` on first run if it doesn't exist.
INSTRUCTIONS

# The test_mcp_complete.py script is very complex and assumes a lot about the
# environment and direct file layout. For a bundle, it's better to provide
# instructions on how to use the run_mcp_client.py for basic verification.
# Recreating the full test suite inside the bundle is out of scope for this script.
# Users can run the main project's test suite if they clone the full repository.
echo "NOTE: The original 'test_mcp_complete.py' is not included in this bundle." > "$BUNDLE_DIR/test_suite_note.txt"
echo "Please use 'run_mcp_client.py' for basic client testing, or clone the full" >> "$BUNDLE_DIR/test_suite_note.txt"
echo "repository to run the complete test suite against this bundled server." >> "$BUNDLE_DIR/test_suite_note.txt"


# The original script had sections to add NLP module and update test suite/instructions for NLP.
# Since we are copying the whole ghost_dmpm package, NLP module (processor.py) is already included.
# The run_mcp_server.py will use it if NLP features are called.
# The DEPLOY_INSTRUCTIONS.md can mention NLP capabilities if desired, but the
# NLPEnhancedMCPServer wrapper is an application-level detail not directly handled by this bundle script.
# The user would integrate NLP by using the GhostNLPProcessor with their client logic if needed.

# Create tar.gz bundle
echo "Creating tarball..."
# Assumes script is run from scripts/ dir, so bundle is created in scripts/
# It's better to create the tarball in the project root (parent directory)
tar -czf "../${BUNDLE_DIR}.tar.gz" -C "." "$BUNDLE_DIR"
# The -C "." "$BUNDLE_DIR" part ensures that the tarball contains the BUNDLE_DIR
# itself, not its contents flatly. Or, if we want the contents flatly, we'd do:
# tar -czf "../${BUNDLE_DIR}.tar.gz" -C "$BUNDLE_DIR" .

echo "✅ Deployment bundle created: ${BUNDLE_DIR}.tar.gz in project root."
echo ""
echo "To deploy, transfer this file to a system with Python and run:"
echo "  tar -xzf ${BUNDLE_DIR}.tar.gz"
echo "  cd $BUNDLE_DIR"
echo "  cat DEPLOY_INSTRUCTIONS.md"
echo "  # Then follow instructions, e.g., pip install and run server."
EOF

# Make the bundle script executable
# This chmod is on the source script, not the one in the bundle.
# chmod +x create_deployment_bundle.sh # This should be done once on the repo's script.
# The scripts inside the bundle (run_mcp_server.py, run_mcp_client.py) have chmod +x applied.

# Remove the temporary BUNDLE_DIR from the scripts/ directory after tarball creation
# if the tarball is made in the parent directory.
if [ -f "../${BUNDLE_DIR}.tar.gz" ]; then
    echo "Cleaning up temporary bundle directory ./$BUNDLE_DIR"
    rm -rf "$BUNDLE_DIR"
fi

async def test_nlp_queries(client):
    """Test natural language processing"""
    print("\n=== Testing NLP Queries ===")

    # Import NLP processor
    try:
        from ghost_mcp_nlp import GhostNLPProcessor
        nlp = GhostNLPProcessor()
    except ImportError:
        print("⚠️  NLP module not available")
        return

    test_queries = [
        "Which carriers don't check ID?",
        "Tell me about Mint Mobile",
        "Recent changes",
    ]

    for query in test_queries:
        method, params = nlp.parse_query(query)
        print(f"\nQuery: '{query}'")
        print(f"  Parsed as: {method}({params})")

        # Test actual query
        await client.connect() # Ensure client is connected for each query
        result = await client.query(method, params)

        # Format response
        formatted = nlp.format_response(method, result.get("result", {}))
        print(f"  Response preview: {formatted[:100]}...")

        await client.close() # Close client after each query
NLPTEST

# Add NLP usage to instructions
cat >> $BUNDLE_DIR/DEPLOY_INSTRUCTIONS.md << 'NLPINST'

## Natural Language Interface

The MCP server includes an NLP layer for natural language queries:

```python
from ghost_mcp_nlp import GhostNLPProcessor, NLPEnhancedMCPServer

# Assuming 'mcp_server' is your initialized GhostMCPServerV2 instance
# Wrap your MCP server with NLP
nlp_server = NLPEnhancedMCPServer(mcp_server)

# Handle natural language (example usage in a client or integrated component)
# async def handle_query(query_text):
#     result = await nlp_server.handle_natural_language(query_text)
#     print(result["formatted_response"])

# Example:
# asyncio.run(handle_query("Which carriers don't need ID?"))
```

### Example Natural Language Queries
- "Which carriers don't require ID?"
- "Check Mint Mobile policy"
- "What changed recently?"
- "Show Cricket trends for 2 weeks"
- "Is the system working?"
NLPINST

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
