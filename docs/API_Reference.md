# API Reference

This document provides a reference for the available APIs in the GHOST DMPM system.

## REST API (Dashboard - Default Port 5000)

The dashboard provides a RESTful API for interacting with system data and triggering actions.

### Authentication

-   **Type**: HTTP Basic Authentication
-   **Default Credentials**:
    -   Username: `admin`
    -   Password: `ghost2024`
    *(Note: These credentials should be changed in your `config/ghost_config.json` for production deployments.)*

### Endpoints

All endpoints are prefixed with `/api`.

---

#### 1. System Status

-   **Endpoint**: `GET /api/status`
-   **Description**: Retrieves a comprehensive status of the GHOST DMPM system, including last crawl times, API mode, and system metrics.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 http://localhost:5000/api/status
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "api_mode": "mock",
      "data_directory": "/app/data",
      "encryption_mode": "ENABLED",
      "last_crawl": "Just now",
      "last_parse": "Just now",
      "metrics": {
        "cpu_usage": "Active",
        "disk_usage": "50.0%",
        "docker_status": "Running",
        "memory_usage": "30.0%"
      },
      "scheduler_enabled": false,
      "scheduler_status": "Not Found",
      "status": "OPERATIONAL",
      "timestamp": "2025-07-03T12:00:00.000000Z",
      "version": "1.0.0"
    }
    ```

---

#### 2. Top MVNOs

-   **Endpoint**: `GET /api/mvnos/top/<int:n>`
-   **Description**: Gets the top `n` most lenient MVNOs based on current data.
-   **Path Parameter**:
    -   `n` (integer): Number of MVNOs to retrieve.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 http://localhost:5000/api/mvnos/top/5
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "data_timestamp": "Just now",
      "mvnos": [
        {
          "keywords": ["keyword1", "keyword2"],
          "last_seen": "Just now",
          "mentions": 10,
          "name": "Mint Mobile",
          "negative_mentions": 1,
          "positive_mentions": 5,
          "score": 3.3,
          "trend": "stable"
        }
      ],
      "total_mvnos": 20
    }
    ```

---

#### 3. Search MVNOs

-   **Endpoint**: `GET /api/mvnos/search/<query>`
-   **Description**: Searches for MVNOs matching the given query string.
-   **Path Parameter**:
    -   `query` (string): The search term for MVNO names.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 http://localhost:5000/api/mvnos/search/Mobile
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "count": 1,
      "query": "Mobile",
      "results": [
        {
          "keywords": {"keyword1": 5},
          "mentions": 10,
          "name": "US Mobile",
          "score": 3.3
        }
      ]
    }
    ```

---

#### 4. Recent Alerts

-   **Endpoint**: `GET /api/alerts/recent`
-   **Description**: Retrieves recent policy change alerts.
-   **Query Parameters**:
    -   `days` (integer, optional, default: 7): Number of past days to fetch alerts for.
    -   `type` (string, optional): Filter by a specific alert type (e.g., "SCORE_CHANGE", "NEW_POLICY_KEYWORD").
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 "http://localhost:5000/api/alerts/recent?days=14&type=SCORE_CHANGE"
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "alerts": [
        {
          "alert_type": "SCORE_CHANGE",
          "details": "Score changed from 3.0 to 3.3",
          "mvno_name": "Mint Mobile",
          "timestamp": "2025-07-03T10:00:00.000000Z"
        }
      ],
      "filter": {
        "days": 14,
        "type": "SCORE_CHANGE"
      },
      "total": 1
    }
    ```

---

#### 5. List Reports

-   **Endpoint**: `GET /api/reports/list`
-   **Description**: Lists available generated reports.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 http://localhost:5000/api/reports/list
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "reports": [
        {
          "created": "2025-07-03T09:00:00.000000Z",
          "filename": "intel_brief_20250703.pdf",
          "size": 102400,
          "type": "pdf"
        }
      ],
      "total": 1
    }
    ```

---

#### 6. System Logs

-   **Endpoint**: `GET /api/system/logs`
-   **Description**: Retrieves recent lines from the system log file.
-   **Query Parameters**:
    -   `lines` (integer, optional, default: 100): Number of recent log lines to retrieve.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 "http://localhost:5000/api/system/logs?lines=50"
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "lines": [
        "2025-07-03 12:00:00,000 - INFO - System initialized.",
        "2025-07-03 12:01:00,000 - WARNING - API key not found for service X."
      ],
      "log_file": "ghost_dmpm.log",
      "total_lines": 5000
    }
    ```

---

#### 7. Get Configuration

-   **Endpoint**: `GET /api/config`
-   **Description**: Retrieves a sanitized version of the current system configuration. Sensitive values like API keys and passwords are omitted.
-   **Request Example (curl)**:
    ```bash
    curl -u admin:ghost2024 http://localhost:5000/api/config
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "api_key_configured": true,
      "crawler_delay_base": 2.0,
      "google_search_mode": "mock",
      "logging_level": "INFO",
      "output_dir": "/app/data",
      "scheduler_enabled": false
    }
    ```
---

#### 8. Health Check

-   **Endpoint**: `GET /api/health`
-   **Description**: A simple health check endpoint. No authentication required.
-   **Request Example (curl)**:
    ```bash
    curl http://localhost:5000/api/health
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "status": "healthy",
      "timestamp": "2025-07-03T12:00:00.000000Z"
    }
    ```

---

#### 9. Trigger Crawl

-   **Endpoint**: `POST /api/crawler/trigger`
-   **Description**: Manually initiates a new intelligence gathering (crawl) cycle.
-   **Request Example (curl)**:
    ```bash
    curl -X POST -u admin:ghost2024 http://localhost:5000/api/crawler/trigger
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "status": "triggered",
      "message": "Crawl cycle initiated",
      "estimated_completion": "5-10 minutes"
    }
    ```
*(Further endpoints like `/api/trends/<mvno>`, `/api/crawler/status`, `/api/disk-usage`, `/api/scheduler/toggle` follow similar patterns and are omitted for brevity but should be documented fully in a complete reference.)*

## WebSocket API (MCP Server - Default Port 8765)

The Model Context Protocol (MCP) server provides a WebSocket API for real-time interaction and data retrieval, primarily designed for AI assistant integration.

### Connection

-   **URL**: `ws://localhost:8765`
-   **Path for Health Check**: `/health` (Connect to this path for a health status message; does not use JSON-RPC).

### Authentication

-   **Type**: Token-based. The first message sent by the client after connection must be an `authenticate` method call.
-   **Token**: The required token is `ghost-mcp-2024`.
    *(Note: This token is configurable in `config/ghost_config.json` under `mcp_server.auth_token` and should be changed for production.)*

### Message Format

Communication uses JSON-RPC like messages:
-   **Request**:
    ```json
    {
      "id": "unique_request_id_string", // Optional, but recommended
      "method": "method_name",
      "params": { /* method-specific parameters */ }
    }
    ```
-   **Response**:
    ```json
    {
      "id": "unique_request_id_string", // Mirrors request ID if provided
      "timestamp": "YYYY-MM-DDTHH:MM:SS.ffffffZ",
      "result": { /* method-specific result */ },
      // OR
      "error": "Error message if something went wrong"
    }
    ```

### Methods

---

#### 1. `authenticate`

-   **Description**: Authenticates the client session. This must be the first message sent after establishing the WebSocket connection.
-   **Parameters**:
    -   `token` (string): The authentication token.
-   **Request Example (Python)**:
    ```python
    import asyncio
    import websockets
    import json

    async def mcp_authenticate():
        uri = "ws://localhost:8765"
        async with websockets.connect(uri) as websocket:
            auth_payload = {
                "method": "authenticate",
                "params": {"token": "ghost-mcp-2024"}
            }
            await websocket.send(json.dumps(auth_payload))
            response = await websocket.recv()
            print(f"Authentication Response: {response}")
            # Example: Proceed with other methods if authenticated
            # if json.loads(response).get("result", {}).get("authenticated"):
            #     ...

    # asyncio.run(mcp_authenticate())
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "timestamp": "2025-07-03T12:00:00.000000Z",
      "result": {"authenticated": true}
    }
    ```
    Or on failure:
    ```json
    {
      "timestamp": "2025-07-03T12:00:00.000000Z",
      "result": {"authenticated": false, "error": "Authentication failed"}
    }
    ```

---

#### 2. `get_top_mvnos`

-   **Description**: Retrieves the top N most lenient MVNOs.
-   **Parameters**:
    -   `n` (integer, optional, default: 10): Number of MVNOs to retrieve.
-   **Request Example (Python, assuming `websocket` is an authenticated connection)**:
    ```python
    # async with websockets.connect(uri) as websocket:
    #     # ... after authentication ...
    #     top_mvnos_payload = {
    #         "id": "req1",
    #         "method": "get_top_mvnos",
    #         "params": {"n": 3}
    #     }
    #     await websocket.send(json.dumps(top_mvnos_payload))
    #     response = await websocket.recv()
    #     print(f"Top MVNOs Response: {response}")
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "id": "req1",
      "timestamp": "2025-07-03T12:01:00.000000Z",
      "result": {
        "mvnos": [
          {
            "rank": 1,
            "name": "Mint Mobile",
            "score": 3.3,
            "assessment": "LENIENT - Basic verification only",
            "last_updated": "2025-07-03T11:12:48.129570Z"
          }
          // ... other MVNOs ...
        ],
        "total_count": 3
      }
    }
    ```

---

#### 3. `search_mvno`

-   **Description**: Searches for details of a specific MVNO by name.
-   **Parameters**:
    -   `mvno_name` (string): The name of the MVNO to search for.
-   **Request Example (Python)**:
    ```python
    # search_payload = {
    #     "id": "req2",
    #     "method": "search_mvno",
    #     "params": {"mvno_name": "Mint Mobile"}
    # }
    # await websocket.send(json.dumps(search_payload))
    # response = await websocket.recv()
    # print(f"Search MVNO Response: {response}")
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "id": "req2",
      "timestamp": "2025-07-03T12:02:00.000000Z",
      "result": {
        "mvno": {
          "name": "Mint Mobile",
          "score": 3.3,
          "assessment": "LENIENT - Basic verification only",
          "policy_snapshot": {"privacy_policy_url": "...", "requires_id": false},
          "last_updated": "2025-07-03T11:12:48.129570Z",
          "source_url": "http://example.com/mintmobile_info"
        }
      }
    }
    ```
    If not found:
    ```json
    {
      "id": "req2",
      "timestamp": "2025-07-03T12:02:00.000000Z",
      "result": {"error": "MVNO 'Unknown Mobile' not found."}
    }
    ```

---

#### 4. `get_recent_alerts`

-   **Description**: Retrieves recent policy change alerts.
-   **Parameters**:
    -   `days` (integer, optional, default: 7): Number of past days to fetch alerts from.
-   **Request Example (Python)**:
    ```python
    # alerts_payload = {
    #     "id": "req3",
    #     "method": "get_recent_alerts",
    #     "params": {"days": 14}
    # }
    # await websocket.send(json.dumps(alerts_payload))
    # response = await websocket.recv()
    # print(f"Recent Alerts Response: {response}")
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "id": "req3",
      "timestamp": "2025-07-03T12:03:00.000000Z",
      "result": {
        "alerts": [
          {
            "mvno_name": "Mint Mobile",
            "change_type": "SCORE_ADJUSTMENT",
            "old_value": "3.0",
            "new_value": "3.3",
            "detected_timestamp": "2025-07-03T10:00:00.000000Z"
          }
        ],
        "total_count": 1
      }
    }
    ```

---

#### 5. `get_system_status`

-   **Description**: Retrieves the overall system status, database statistics, and server uptime.
-   **Parameters**: None.
-   **Request Example (Python)**:
    ```python
    # status_payload = {
    #     "id": "req4",
    #     "method": "get_system_status",
    #     "params": {}
    # }
    # await websocket.send(json.dumps(status_payload))
    # response = await websocket.recv()
    # print(f"System Status Response: {response}")
    ```
-   **Response Example (JSON)**:
    ```json
    {
      "id": "req4",
      "timestamp": "2025-07-03T12:04:00.000000Z",
      "result": {
        "database_status": "connected",
        "total_mvnos_tracked": 20,
        "last_policy_update": "2025-07-03T11:12:48.129570Z",
        "total_policy_changes_logged": 5,
        "server_uptime": "0d 1h 30m",
        "active_connections": 1
      }
    }
    ```

*(The method `get_mvno_trend` follows a similar pattern and is omitted for brevity but should be documented fully in a complete reference.)*

---

### Health Check (WebSocket Path)

-   **Path**: `/health`
-   **Description**: Connect a WebSocket client directly to the `/health` path (e.g., `ws://localhost:8765/health`). The server will send a JSON message with health status and then close the connection. This does not use the JSON-RPC message structure.
-   **Response Example (JSON, sent by server upon connection to `/health`)**:
    ```json
    {
        "status": "healthy",
        "timestamp": "2025-07-03T12:05:00.000000Z",
        "version": "2.0.0",
        "uptime": "0d 1h 35m",
        "components": {
            "database": "healthy",
            "websocket": "healthy"
        },
        "metrics": {
            "connected_clients": 0, // Excludes the current health check connection
            "tracked_mvnos": 20
        }
    }
    ```
