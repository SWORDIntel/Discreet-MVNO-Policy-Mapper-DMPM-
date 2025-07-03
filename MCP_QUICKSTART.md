# GHOST DMPM - MCP Quick Reference

## For AI Assistants (Copy this to your context)

### Connection
- URL: `ws://localhost:8765`
- Token: `ghost-mcp-2024`

### Top 5 Queries (Example Commands)

These are example JSON payloads you would send to the MCP server via WebSocket.

1.  **List anonymous carriers (Top 10)**
    ```json
    {
      "token": "ghost-mcp-2024",
      "command": "query_database",
      "payload": {
        "query_type": "get_top_mvnos",
        "limit": 10
      }
    }
    ```
    *MCP Function: `query_database` (internally uses `ghost_db.get_top_mvnos`)*

2.  **Check specific carrier (e.g., Mint Mobile)**
    ```json
    {
      "token": "ghost-mcp-2024",
      "command": "query_database",
      "payload": {
        "query_type": "get_mvno_details",
        "mvno_name": "Mint Mobile"
      }
    }
    ```
    *MCP Function: `query_database` (internally could use a new `ghost_db` method or search existing policies)*
    *(Note: `get_mvno_details` is an assumed function for this example; actual implementation might vary. The prompt's `search_mvno("Mint Mobile")` implies a direct search function which can be mapped to this.)*

3.  **Policy changes this week (last 7 days)**
    ```json
    {
      "token": "ghost-mcp-2024",
      "command": "query_database",
      "payload": {
        "query_type": "get_recent_changes",
        "days": 7
      }
    }
    ```
    *MCP Function: `query_database` (internally uses `ghost_db.get_recent_changes`)*

4.  **Predict changes (30-day forecast - conceptual)**
    *(This functionality is listed in the quickstart but not part of the initial 5 core modules. It's likely a future enhancement for Phase 3 or beyond. Placeholder command shown.)*
    ```json
    {
      "token": "ghost-mcp-2024",
      "command": "predict_changes",
      "payload": {
        "scope": "all",
        "days_ahead": 30
      }
    }
    ```
    *MCP Function: `predict_changes` (conceptual advanced feature)*

5.  **Generate OPSEC strategy (low risk - conceptual)**
    *(This functionality is also likely a future enhancement. Placeholder command shown.)*
    ```json
    {
      "token": "ghost-mcp-2024",
      "command": "generate_acquisition_plan",
      "payload": {
        "risk_profile": "low",
        "sim_cards_needed": 1
      }
    }
    ```
    *MCP Function: `generate_acquisition_plan` (conceptual advanced feature)*

### Natural Language Examples (To be processed by AI client into MCP commands)

These are illustrative examples of what an AI might ask. The `mcp_client.py` (to be built later) would translate these into the structured JSON commands above.

- "Which carriers don't check ID?"
  *(Likely maps to `query_database` with `get_top_mvnos` or a specific filter)*
- "Has Cricket's policy changed?"
  *(Likely maps to `query_database` with `get_recent_changes` filtered by "Cricket" or `get_mvno_details` for "Cricket")*
- "Best carrier for burner phone?"
  *(Likely maps to `query_database` with `get_top_mvnos` and specific parameters)*
- "Alert me to policy tightening."
  *(This implies a persistent monitoring setup, potentially a new MCP command or a client-side feature built on `get_recent_changes`.)*

---
**Note**: The MCP server functions `predict_changes` and `generate_acquisition_plan` are listed as per the prompt's quick start guide but are considered advanced features not part of the initial 5 core GHOST module integrations. Their command structures are conceptual. The primary focus for initial implementation will be commands related to config, crawl, parse, report, and database queries.
