# Troubleshooting Guide

This guide helps resolve common issues encountered while installing, configuring, or running GHOST DMPM.

## Installation Issues

### 1. `ModuleNotFoundError: No module named 'some_module'`

-   **Symptom**: Python raises an error indicating a specific module cannot be found.
-   **Cause**: Usually means a required dependency is not installed or not accessible in your Python environment.
-   **Solutions**:
    1.  **Activate Virtual Environment**: If you installed in a virtual environment, ensure it's activated:
        ```bash
        source venv/bin/activate  # Linux/macOS
        .\venv\Scripts\activate    # Windows
        ```
    2.  **Install Requirements**: Run (or re-run) the installation of dependencies.
        -   For core dependencies:
            ```bash
            pip install -r requirements.txt
            ```
        -   For optional features (like Excel/PDF export, NLP):
            ```bash
            pip install -r requirements/optional.txt
            ```
        -   If you cloned the repository and want to run editable mode (recommended for development):
            ```bash
            pip install -e .
            pip install -r requirements.txt # Then install other requirements
            ```
    3.  **Check Python Version**: Ensure you are using Python 3.9 or newer. `python --version` or `python3 --version`.
    4.  **PYTHONPATH Issues**: If running scripts directly from subdirectories (e.g., `src/ghost_dmpm/api/`), Python might not find the main package. Try running scripts as modules from the project root if applicable (e.g., `python -m src.ghost_dmpm.api.mcp_server`) or ensure the project is installed via `pip install -e .`.

### 2. Errors during `pip install` (e.g., build failures for `psycopg2`, `lxml`, etc.)

-   **Symptom**: `pip install` fails, often with errors related to compiling C extensions.
-   **Cause**: Missing system-level development libraries or build tools.
-   **Solutions**:
    -   **Debian/Ubuntu**:
        ```bash
        sudo apt-get update
        sudo apt-get install python3-dev build-essential libpq-dev libxml2-dev libxslt1-dev
        ```
    -   **Fedora/CentOS/RHEL**:
        ```bash
        sudo yum groupinstall "Development Tools"
        sudo yum install python3-devel postgresql-devel libxml2-devel libxslt-devel
        ```
    -   **macOS**: Ensure Xcode Command Line Tools are installed:
        ```bash
        xcode-select --install
        ```
        You might also need `openssl` and `libpq` via Homebrew: `brew install openssl libpq`.
    -   **Windows**: Build tools for Visual Studio might be required. Consider using pre-compiled binaries via `pip install <package_name>-binary` if available, or use WSL (Windows Subsystem for Linux).

## Runtime Errors

### 1. Database Connection Failed / `sqlite3.OperationalError: unable to open database file`

-   **Symptom**: Application components (main cycle, dashboard, MCP server) fail to connect to the SQLite database.
-   **Cause**:
    -   Database file path in `config/ghost_config.json` (under `database.path`) is incorrect.
    -   The directory for the database file does not exist, and the application doesn't have permission to create it.
    -   File permissions issue for the database file or its directory.
-   **Solutions**:
    1.  **Verify Config**: Check `config/ghost_config.json`. Ensure `database.path` (e.g., `"data/ghost_data.db"`) points to the correct location relative to your project root.
    2.  **Create Directory**: Ensure the directory (e.g., `data/`) exists. If not, create it: `mkdir data`.
    3.  **Permissions**: Ensure the application has read/write permissions for the database file and its parent directory.
    4.  **Absolute Paths**: If relative paths are problematic, try using an absolute path in the configuration.

### 2. API Rate Limits (e.g., for Google Search API)

-   **Symptom**: Crawling fails or returns errors related to API usage quotas.
-   **Cause**: Exceeded the usage limits for an external API (like Google Custom Search JSON API).
-   **Solutions**:
    1.  **Check API Dashboard**: Visit the Google Cloud Console (or other API provider's dashboard) to check your quota usage and limits.
    2.  **Increase Quotas**: Request a quota increase if necessary.
    3.  **Use Mock Mode**: For development or testing, set `google_search_mode` to `"mock"` in `config/ghost_config.json` to use mock data and avoid API calls.
    4.  **Adjust Crawler Settings**: In `config/ghost_config.json`, increase `crawler.delay_base` to slow down requests.
    5.  **API Key**: Ensure your `api_keys.google_search` and `google_programmable_search_engine_id` are correctly set up in the config.

### 3. Memory Issues / High CPU Usage

-   **Symptom**: System becomes slow, unresponsive, or the GHOST DMPM process is terminated by the OS.
-   **Cause**:
    -   Processing very large datasets or numerous search results.
    -   NLP processing (spaCy) can be memory-intensive.
    -   Long-running crawl cycles without sufficient resources.
-   **Solutions**:
    1.  **Resource Allocation**: Ensure your system (or Docker container) has sufficient RAM and CPU resources.
    2.  **Limit MVNO List**: Reduce the number of MVNOs in `mvno_list` in `config/ghost_config.json` for initial runs.
    3.  **NLP Mode**: If spaCy is causing issues, you can try setting `parser.nlp_mode` to `"basic"` or ensure spaCy models are downloaded correctly (e.g., `python -m spacy download en_core_web_sm`).
    4.  **Docker Resources**: If using Docker, adjust the memory/CPU limits for the GHOST DMPM container(s).
    5.  **Logging Level**: Set `logging.level` to `"INFO"` or `"WARNING"` for production to reduce I/O overhead from debug logs.

### 4. WebSocket Connection Issues (MCP Server)

-   **Symptom**: `mcp_client.py` or other WebSocket clients cannot connect to `ws://localhost:8765`.
-   **Cause**:
    -   MCP Server (`ghost_mcp_server.py`) is not running.
    -   Firewall blocking the port.
    -   Incorrect URL or port used by the client.
    -   Authentication token mismatch.
-   **Solutions**:
    1.  **Ensure Server is Running**: Start `ghost_mcp_server.py` (e.g., `python src/ghost_dmpm/api/mcp_server.py`). Check its logs for startup errors.
    2.  **Check Port**: Verify the server is listening on the correct port (default 8765). Use `netstat -tulnp | grep 8765` (Linux) or Resource Monitor (Windows).
    3.  **Firewall**: Ensure your system or network firewall isn't blocking connections to the port.
    4.  **Client Configuration**: Verify the client is using the correct URL (`ws://localhost:8765` or the configured host/port) and the correct authentication token (see `mcp_server.auth_token` in `config/ghost_config.json`).

## Docker Problems

### 1. Container Won't Start / Exits Immediately

-   **Symptom**: `docker-compose up` shows a container starting and then stopping, or `docker ps` doesn't show it running.
-   **Cause**:
    -   Errors in the application startup script within the container.
    -   Configuration issues (e.g., missing files mapped as volumes, incorrect environment variables).
    -   Port conflicts if a port defined in `docker-compose.yml` is already in use on the host.
-   **Solutions**:
    1.  **Check Logs**: Use `docker-compose logs <service_name>` (e.g., `docker-compose logs app` or `docker-compose logs dashboard`) to see the error messages from within the container. This is the most important step.
    2.  **Volume Mounts**: Verify any volume mounts in `docker-compose.yml` point to existing directories on your host if they are bind mounts. Ensure `config/ghost_config.json` is present and correctly configured if mounted.
    3.  **Build Issues**: Try rebuilding the image: `docker-compose build --no-cache <service_name>`.
    4.  **Entrypoint/Command**: Check the `entrypoint` or `command` in your `Dockerfile` or `docker-compose.yml` for correctness.

### 2. Port Conflicts

-   **Symptom**: Error messages like "port is already allocated" or "bind: address already in use".
-   **Cause**: Another application on your host machine (or another Docker container) is using a port that GHOST DMPM services (e.g., Dashboard on 5000, MCP on 8765) are trying to use.
-   **Solutions**:
    1.  **Identify Conflicting Process**: Use `sudo netstat -tulnp | grep <port_number>` (Linux) or `resmon.exe` (Windows Resource Monitor, Network tab, Listening Ports) to find what's using the port.
    2.  **Stop Conflicting Process**: Stop the other application or container.
    3.  **Change GHOST DMPM Ports**:
        -   In `docker-compose.yml`, change the host-side port mapping. For example, change `"5000:5000"` to `"5001:5000"` to map host port 5001 to container port 5000.
        -   Update `config/ghost_config.json` for `dashboard.port` and `mcp_server.port` if you need to change the port *inside* the container (less common for this issue).

## Common Error Messages & Solutions

| Error Message Snippet                      | Potential Cause & Solution                                                                                                                               |
| :----------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ImportError: No module named 'ghost_dmpm'` | Usually when running a script directly from a subdirectory. Try `pip install -e .` from project root, or run as module: `python -m src.ghost_dmpm...`. |
| `FileNotFoundError: [Errno 2] No such file or directory: 'config/ghost_config.json'` | Ensure `ghost_config.json` exists in the `config/` directory. Copy from `ghost_config.json.example` if needed. Run from project root. |
| `PermissionError: [Errno 13] Permission denied: 'data/ghost_data.db'` | Check file/directory permissions for `data/` and the db file. The application needs read/write access.                                    |
| `requests.exceptions.ConnectionError`      | Network issue trying to reach an external API or internal service. Check connectivity, proxy settings.                                                     |
| `json.JSONDecodeError` in MCP Server/Client | Malformed JSON message sent or received. Check client/server message construction.                                                                       |
| `TypeError: X missing 1 required positional argument: 'Y'` in API/Server | Often due to library version mismatches or incorrect handler signatures. Check recent changes or library docs (e.g. `websockets`).       |
| `Authentication failed` (MCP Client)       | Token in `mcp_client.py` does not match `mcp_server.auth_token` in `config/ghost_config.json`. Ensure they are identical.                            |
| `[✗] Connection or query failed: Multiple exceptions: [Errno 111] Connect call failed` | MCP server is likely not running or not reachable at the address/port the client is trying to connect to. |

## Log File Locations

Log files provide crucial details for diagnosing issues.
-   **Main Application Logs**: Defined by `logging.log_file_path` in `config/ghost_config.json`. Default is `logs/ghost_dmpm.log` relative to the project root.
-   **Docker Container Logs**: Access via `docker-compose logs <service_name>` (e.g., `app`, `dashboard`, `mcp_server` if they are separate services).
-   **Web Server Logs (if using Gunicorn/Nginx)**: Check the standard log locations for your web server setup.

## Diagnostic Commands

-   **Check Python environment and GHOST DMPM installation**:
    ```bash
    # From project root, with virtual environment activated
    pip list | grep ghost-dmpm  # Should show ghost-dmpm if installed via -e .
    python -c "import ghost_dmpm; print(ghost_dmpm.__version__)"
    ```
-   **Verify Configuration**:
    ```bash
    # Manually inspect config/ghost_config.json
    # You can also use a Python script to load and print specific config values:
    # python -c "from ghost_dmpm.core.config import GhostConfig; cfg = GhostConfig(); print(cfg.get('database.path'))"
    ```
-   **Test Database Connection (Conceptual)**:
    ```python
    # Small script to test SQLite connection based on config
    # from ghost_dmpm.core.config import GhostConfig
    # from ghost_dmpm.core.database import GhostDatabase
    # try:
    #     config = GhostConfig()
    #     db = GhostDatabase(config)
    #     print(f"Database stats: {db.get_database_stats()}")
    #     print("Database connection successful.")
    # except Exception as e:
    #     print(f"Database connection failed: {e}")
    ```
-   **Test MCP Server Locally**:
    1.  Run `python src/ghost_dmpm/api/mcp_server.py`.
    2.  In another terminal, run `python src/ghost_dmpm/api/mcp_client.py --method get_system_status`.

## FAQ

**Q1: How do I change the default username/password for the Dashboard?**
A1: Edit `config/ghost_config.json`. Under the `dashboard` section, modify the `username` and `password` fields. If these fields don't exist, you can add them based on the structure in `ghost_config.json.example` (which might use `dashboard.users` dictionary). Restart the dashboard service after changes.

**Q2: How do I switch from `mock` Google Search mode to `live` mode?**
A2:
1.  Ensure you have a Google API Key and a Programmable Search Engine ID.
2.  Edit `config/ghost_config.json`:
    -   Set `google_search_mode` to `"live"`.
    -   Fill in `api_keys.google_search` with your API key.
    -   Fill in `google_programmable_search_engine_id` with your CX ID.
3.  Restart the GHOST DMPM application (main cycle or relevant components).

**Q3: Where are crawled data and reports stored?**
A3:
-   **Raw Search Results**: Usually in `test_output/raw_search_results_*.json` (path configurable).
-   **Parsed Data**: Usually in `test_output/parsed_mvno_data_*.json` (path configurable).
-   **Intelligence Reports**: In the directory specified by `reports.output_dir` in `config/ghost_config.json` (default: `reports/`).
-   **Database**: The SQLite database file location is set by `database.path` in the config (default: `data/ghost_data.db`).

**Q4: The application is slow. How can I improve performance?**
A4: Refer to "Memory Issues / High CPU Usage" section above. Key areas:
    - Increase system resources (RAM/CPU).
    - Adjust `crawler.delay_base` in config.
    - Reduce number of MVNOs/keywords if processing large amounts.
    - Ensure logging is not set to DEBUG in production.

If you encounter an issue not covered here, please check the application logs for detailed error messages.
```
