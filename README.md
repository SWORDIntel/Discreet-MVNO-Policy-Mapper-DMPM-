# GHOST DMPM - Discreet MVNO Policy Mapper

[![Version](https://img.shields.io/badge/Version-1.0.0-blue)](https://github.com/your-repo/ghost-dmpm)
[![Python Version](https://img.shields.io/badge/Python-3.9+-brightgreen)](https://www.python.org/downloads/release/python-390/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue)](Dockerfile)
[![License](https://img.shields.io/github/license/your-repo/ghost-dmpm)](LICENSE.md)
[![Build Status](https://img.shields.io/github/actions/workflow/status/your-repo/ghost-dmpm/main.yml?branch=main)](https://github.com/your-repo/ghost-dmpm/actions)
<!-- Replace 'your-repo/ghost-dmpm' with the actual repository path -->

## 🎯 Overview
The GHOST Protocol Discreet MVNO Policy Mapper (DMPM) is an automated intelligence gathering system designed to continuously map the US Mobile Virtual Network Operator (MVNO) landscape. It identifies and ranks MVNOs based on their perceived leniency regarding prepaid SIM card identity verification and the ease of anonymous acquisition. The system operates with a minimal digital footprint, optimizing for data freshness and relevance, and aims to provide actionable intelligence for privacy-conscious users and security researchers.

Key use cases include:
- Identifying MVNOs with low barriers to anonymous SIM card activation.
- Tracking policy changes related to identity verification across various MVNOs.
- Supporting research into MVNO operational security and privacy practices.
- Providing data for risk assessment in scenarios requiring untraceable communications.

## 🚀 Quick Start

Get GHOST DMPM up and running in three simple steps:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-repo/ghost-dmpm.git # Replace with your actual repository URL
    cd ghost-dmpm
    ```
2.  **Launch with Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
3.  **Explore the Dashboard:**
    Open your web browser and go to `http://localhost:5000`.
    (Default login: `commander` / `ghost_protocol_2024` - It's crucial to change these in `config/ghost_config.json` or `ghost_dashboard.py` for any non-testing use!)

This sequence starts all GHOST DMPM services, including the web dashboard and the MCP server for AI integration. The system will automatically initiate its first intelligence gathering cycle using default settings.

## ✨ Features
The GHOST DMPM system offers a comprehensive suite of features for MVNO policy intelligence:

-   **Real-time MVNO Policy Tracking**: Continuously gathers and updates information on MVNO policies using automated web crawling.
-   **Leniency Scoring Algorithm**: Ranks MVNOs based on a configurable algorithm that assesses the ease of anonymous SIM acquisition.
-   **Natural Language Queries via MCP**: Interact with the system using natural language through the Model Context Protocol (MCP) server, enabling AI assistant integration.
-   **AI Assistant Integration**: Designed for easy integration with AI platforms like OpenAI, Claude, and Gemini. See [AI Integration Guide](docs/Integration.md).
-   **Automated Alerts and Reporting**: Generates regular intelligence briefs and can be configured for real-time alerts on significant policy changes.
-   **Predictive Analytics**: Employs analytics to forecast potential policy shifts and identify emerging trends (via `ghost_analytics.py`).
-   **Multi-format Exports**: Export gathered intelligence and reports in various formats including CSV, JSON, and PDF (via `ghost_export.py`).
-   **Webhook Notifications**: Send alerts and updates to Slack, Discord, Email, and MS Teams (via `ghost_webhooks.py`).
-   **Scheduled Operations**: Automate intelligence cycles, report generation, and notifications using a flexible scheduler (via `ghost_scheduler.py`).
-   **Modular Design**: Core components (crawler, parser, reporter, database, dashboard, analytics, webhooks, export, scheduler) are built as distinct Python modules for flexibility and scalability.
-   **Data Persistence**: Stores processed MVNO data, policy changes, and crawl history in an SQLite database.
-   **Encrypted Reporting**: Option to generate intelligence reports in an encrypted format.
-   **Web Dashboard**: Provides a Flask-based web interface to view key findings, system status, and manage operations.
-   **Dockerized Deployment**: Includes Dockerfile and `docker-compose.yml` for easy, consistent, and secure deployment.
-   **Security Conscious**: Emphasizes secure API key handling, encrypted outputs, and provides security guidelines.

## 📊 Live Demo

*(Illustrative placeholders for live demo elements. Actual screenshots/GIFs should be added to the repository and linked here.)*

**GHOST Dashboard - MVNO Leniency Overview:**
```
[Placeholder for Screenshot of GHOST Dashboard showing MVNO rankings and scores]
```
*Caption: The GHOST Dashboard provides a visual overview of MVNO leniency scores, recent policy changes, and system status.*

**Example Intelligence Report Snippet (Text Output):**
```
========================================
GHOST DMPM - INTELLIGENCE BRIEF
========================================
Date: 2025-01-15 14:30 UTC
Analysis Period: 2025-01-08 to 2025-01-15

Top 3 Lenient MVNOs:
1. Alpha Mobile (Score: 4.8/5.0) - Consistent policy, multiple anonymous payment options.
2. Beta Wireless (Score: 4.5/5.0) - No ID explicitly required for online activation.
3. Gamma SIM (Score: 4.2/5.0) - Cash top-ups widely available, minimal data collection.

Key Policy Changes Detected:
- ZetaNet: Score decreased (3.5 -> 2.9). New ID verification step noted during checkout.
- OmegaTelco: Score increased (3.1 -> 3.6). Forum discussions indicate easier cash purchases.

Operational Recommendations:
- Monitor ZetaNet for further policy tightening.
- Investigate OmegaTelco's new cash purchase process for confirmation.
========================================
```
*Caption: A sample snippet from a generated text-based intelligence brief, highlighting key findings.*

**MCP Client Query Example (Conceptual):**
```
$ python mcp_client.py --method get_top_mvnos --params '{"n": 3}'
{
  "status": "success",
  "data": [
    {"mvno_name": "Alpha Mobile", "score": 4.8, "details": "..."},
    {"mvno_name": "Beta Wireless", "score": 4.5, "details": "..."},
    {"mvno_name": "Gamma SIM", "score": 4.2, "details": "..."}
  ]
}
```
*Caption: Conceptual output from querying the MCP server for the top 3 lenient MVNOs.*

## 🏗️ Architecture
The GHOST DMPM system is designed as a modular pipeline. Configuration is centralized, and components interact through well-defined interfaces, primarily exchanging data via JSON files and an SQLite database.

```mermaid
graph LR
    subgraph User Interaction
        UI_Browser[Browser User]
        UI_AI[AI Assistant/API User]
    end

    subgraph Core System
        Config(ghost_config.py)
        Main(main.py Orchestrator)
        Scheduler(ghost_scheduler.py)
        Crawler(ghost_crawler.py)
        Parser(ghost_parser.py)
        DB(ghost_db.py SQLite)
        Reporter(ghost_reporter.py)
        Crypto(ghost_crypto.py)
        Analytics(ghost_analytics.py)
    end

    subgraph External Interfaces
        MCP_Server(ghost_mcp_server.py)
        Dashboard(ghost_dashboard.py)
        Webhooks(ghost_webhooks.py)
        Export(ghost_export.py)
    end

    subgraph External Services
        SearchAPI[Google Search API]
        WebhookServices[Slack, Discord, Email, etc.]
    end

    UI_Browser --> Dashboard;
    UI_AI --> MCP_Server;

    Config --> Main;
    Config --> Scheduler;
    Config --> Crawler;
    Config --> Parser;
    Config --> DB;
    Config --> Reporter;
    Config --> Crypto;
    Config --> Dashboard;
    Config --> MCP_Server;
    Config --> Webhooks;
    Config --> Export;
    Config --> Analytics;

    Scheduler -- Triggers --> Main;
    Main -- Runs --> Crawler;
    Main -- Runs --> Parser;
    Main -- Runs --> DB;
    Main -- Runs --> Reporter;

    Crawler -- Uses --> SearchAPI;
    Crawler -- Raw Data --> Parser;
    Parser -- Parsed Data --> DB;
    DB -- Data --> Reporter;
    DB -- Data --> Dashboard;
    DB -- Data --> MCP_Server;
    DB -- Data --> Analytics;
    Analytics -- Insights --> Reporter;
    Analytics -- Insights --> Dashboard;

    Reporter -- Reports --> Export;
    Reporter -- Alerts --> Webhooks;
    Webhooks -- Notifications --> WebhookServices;
    Crypto -- Encryption --> Reporter;
    Crypto -- Encryption --> Export;

    Reporter -- Generates Reports --> Filesystem[Report Files];
    Export -- Exports Data --> Filesystem;

    Scheduler -- Manages Scheduled Tasks --> Main;
    Scheduler -- Manages Scheduled Tasks --> Reporter;
    Scheduler -- Manages Scheduled Tasks --> Export;
    Scheduler -- Manages Scheduled Tasks --> Webhooks;
```
*Caption: System components and data flow in GHOST DMPM.*

Further details on architecture, data flow, and database schema can be found in the original README sections, which will be migrated to `docs/Architecture.md` or similar.

## 📦 Installation
GHOST DMPM can be installed manually or deployed using Docker. Docker is recommended for ease of use and consistency.

### Prerequisites
*   Python 3.9+
*   Docker & Docker Compose (for Docker deployment)
*   Git
*   Build essentials (e.g., `build-essential python3-dev` on Debian)
*   (Optional) Access to Google Search API for `live` mode.

### Option 1: Docker (Recommended)
This is the quickest and most reliable way to get GHOST DMPM running.

1.  **Clone the repository:** (If not already done)
    ```bash
    git clone <your-repository-url>
    cd ghost-dmpm
    ```
2.  **Build and start services:**
    ```bash
    docker-compose up --build -d
    ```
3.  **Access:**
    *   Dashboard: `http://localhost:5000`
    *   MCP Server: `ws://localhost:8765`
4.  **Stop services:**
    ```bash
    docker-compose down
    ```

### Option 2: Manual Installation
1.  **Clone and set up environment:**
    ```bash
    git clone <your-repository-url>
    cd ghost-dmpm
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Initialize Configuration and Directories:**
    ```bash
    mkdir -p data logs reports test_output config templates
    # Run python ghost_config.py to generate default config if needed
    ```
4.  **Run application components as needed:**
    *   `python main.py` (Full cycle)
    *   `python ghost_dashboard.py` (Dashboard)
    *   `python ghost_mcp_server.py` (MCP Server)


### Option 3: Cloud Deployment
(Placeholder: Guidance for deploying to AWS, GCP, Azure, etc.)

## 🔧 Configuration
GHOST DMPM is configured via `config/ghost_config.json`. A default configuration is generated if it doesn't exist.
Refer to `ghost_config.py` and the generated `config/ghost_config.json` for all options.

**Key Sections:**
*   `mvno_list`, `keywords`
*   `google_search_mode`, `api_keys` (Use environment variables for production secrets!)
*   `crawler`, `parser`, `database`
*   `dashboard` (Change default credentials!)
*   `logging`, `reports`
*   `webhooks`, `export`, `scheduler`, `analytics`

**Security Note:** For production, use environment variables for sensitive data like API keys and passwords rather than storing them directly in `ghost_config.json`.

## 📖 Usage Guide

### Basic Usage (Full Cycle)
```bash
python main.py
```
Output and logs are generated in respective directories (`reports/`, `logs/`, `data/`, `test_output/`).

### Natural Language Queries (via MCP)
1.  Start MCP server: `python ghost_mcp_server.py` (or via Docker Compose).
2.  Use `mcp_client.py`:
    ```bash
    python mcp_client.py --method get_top_mvnos --params '{"n": 5}'
    ```
    See `MCP_QUICKSTART.md` or [AI Integration Guide](docs/Integration.md).

### API Integration
-   **Direct Module Usage**: Import classes like `GhostCrawler` in Python.
-   **MCP Server**: Connect via WebSocket.
-   **Dashboard API**: RESTful endpoints (see `ghost_dashboard.py`).

### Webhook Setup
Configure in `config/ghost_config.json` under `webhooks`. Example:
```json
"webhooks": {
  "slack_url": "YOUR_SLACK_WEBHOOK_URL",
  "email": { "smtp_server": "smtp.example.com", "smtp_user": "user" /* ... */ }
}
```
See `examples/webhook_setup.py`.

### Scheduled Reports
Configure in `config/ghost_config.json` under `scheduler.jobs`. Example:
```json
"scheduler": {
  "enabled": true,
  "jobs": [{ "name": "daily_brief", "cron_schedule": "0 2 * * *" /* ... */ }]
}
```
See `examples/automated_reports.py`.

## 🤖 AI Integration
GHOST DMPM integrates with AI platforms (OpenAI, Claude, Gemini) via the **Model Context Protocol (MCP) Server** (`ghost_mcp_server.py`).
This WebSocket server allows AI assistants to retrieve data and insights.

➡️ **Detailed Guide: [docs/Integration.md](docs/Integration.md)**

## 📡 API Reference
Comprehensive API documentation for modules:
➡️ **[docs/API_Reference.md](docs/API_Reference.md)**

**Key MCP Server Methods (Summary):**
| Method                | Description                     |
|-----------------------|---------------------------------|
| `authenticate`        | Authenticate client             |
| `get_top_mvnos`       | Get top N lenient MVNOs         |
| `search_mvno`         | Search for an MVNO's details    |
| `get_recent_alerts`   | Get recent policy changes       |
| `get_mvno_trend`      | Get historical score trend      |
| `get_system_status`   | Get GHOST system status         |
| `trigger_export`      | Request data export             |
| `get_analytics_insight`| Get analytical insight          |

## 🔍 Examples
Working code examples:
➡️ **[examples/](examples/)** directory.
- `basic_usage.py`
- `ai_integration/` (OpenAI, Claude, Gemini examples)
- `webhook_setup.py`
- `automated_reports.py`
- `advanced_analytics.py`
- `custom_export.py`

## 📈 Performance
Performance depends on network, targets, and resources.
*(Placeholder for benchmarks)*

**Optimization Tips:**
- Adjust crawler delays (`crawler.delay_base`).
- Use appropriate log levels (`INFO` for production).
- For more, see [docs/Performance_Tuning.md](docs/Performance_Tuning.md).

## 🛠️ Troubleshooting
Common issues and solutions.
- Installation: Check Python version, build tools.
- Configuration: Validate `config/ghost_config.json`.
- API Keys: Verify keys and quotas for `live` mode.
- Dashboard: Check server status, credentials.

➡️ **Comprehensive Guide: [docs/Troubleshooting.md](docs/Troubleshooting.md)**

## 🤝 Contributing
We welcome contributions to GHOST DMPM! Whether you're fixing a bug, adding a feature, or improving documentation, your help is valued.

\[2025-07-03 09:17 GMT]

Absolutely. Here's the laid-back, swear-friendly version:

---

**Contributin**

1. Fork the damn repo, make a new branch:
   `git checkout -b whatever-shit-you’re-working-on`
2. Write your code. Try not to break the style (PEP8 or whatever).
3. Add some tests if you’re adding/fixing stuff. Don’t be lazy *here*, ironically.
4. Run the tests. If shit breaks, fix it.
5. Docs? Yeah, update that crap too if anything changed.
6. Commit with a message that isn’t total gibberish. Use Conventional Commits if you wanna look pro.
7. Make a pull request to `main`. Say what you did. Try not to be vague as hell.
That’s it. Go grab a coffee.

**Code of Conduct:**
All contributors are expected to adhere to a very low standard of professional conduct. Please dont be respectful or considerate in all interactions..

## 📄 License
GHOST DMPM is released under the **MIT License**.

In essence, this means you are free to:
- Give me credit,except in court in which case i had no idea you could do crime or what crime is

The software is provided "AS IS" without warranty of any kind.
