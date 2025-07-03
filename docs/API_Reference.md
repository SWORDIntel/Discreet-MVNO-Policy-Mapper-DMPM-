# API Reference

This document provides a reference for the GHOST DMPM APIs.

## Table of Contents
- [MCP Server API](#mcp-server-api)
  - [WebSocket Connection](#websocket-connection)
  - [Authentication](#authentication)
  - [Available Methods](#available-methods)
    - [`get_top_mvnos`](#get_top_mvnos)
    - [`search_mvno`](#search_mvno)
    - [`get_recent_alerts`](#get_recent_alerts)
    - [`get_mvno_trend`](#get_mvno_trend)
    - [`get_system_status`](#get_system_status)
- [Dashboard REST API](#dashboard-rest-api)
  - [Authentication](#authentication-1)
  - [Endpoints](#endpoints)
    - [`/api/status`](#apistatus)
    - [`/api/mvnos/top/<n>`](#apimvnostopn)
    - [`/api/alerts/recent`](#apialertsrecent)
- [Python Module APIs](#python-module-apis)
  - [`ghost_dmpm.core.config.GhostConfig`](#ghost_dmpmcoreconfigghostconfig)
  - [`ghost_dmpm.core.crawler.GhostCrawler`](#ghost_dmpmcorecrawlerghostcrawler)
  - [`ghost_dmpm.core.parser.GhostParser`](#ghost_dmpmcoreparserghostparser)
  - [`ghost_dmpm.core.database.GhostDatabase`](#ghost_dmpmcoredatabaseghostdatabase)
  - [`ghost_dmpm.core.reporter.GhostReporter`](#ghost_dmpmcorereporterghostreporter)

---

## MCP Server API

The Model Context Protocol (MCP) Server provides a WebSocket-based API for programmatic interaction, suitable for AI integrations or custom clients.

### WebSocket Connection
- **URL**: `ws://<host>:<port>/` (Default: `ws://localhost:8765/`)
- **Health Check**: `ws://<host>:<port>/health`

### Authentication
Authentication is required for most methods. The client must send an `authenticate` message first.
```json
{
  "method": "authenticate",
  "params": {"token": "YOUR_MCP_AUTH_TOKEN"}
}
```

### Available Methods

#### `get_top_mvnos`
Retrieves the top N most lenient MVNOs.
- **Request**:
  ```json
  {
    "method": "get_top_mvnos",
    "params": {"n": 5}
  }
  ```
- **Response**: (Structure of MVNO data)

*(Further details for each MCP method to be added here)*

---

## Dashboard REST API

The web dashboard provides a RESTful API for some functionalities.

### Authentication
Uses HTTP Basic Authentication. Credentials are set in the configuration.

### Endpoints

#### `/api/status`
Retrieves the current system status.

*(Further details for each REST endpoint to be added here)*

---

## Python Module APIs

The core Python modules can be used directly.

### `ghost_dmpm.core.config.GhostConfig`
*(Class methods and properties to be documented here)*

*(Documentation for other core modules to follow)*

---

*(This API reference is currently a placeholder and will be populated with detailed information.)*
