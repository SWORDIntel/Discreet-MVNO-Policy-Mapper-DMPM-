# Deployment Guide

## Quick Start

### Local Development
```bash
# Install
pip install -e ".[dev]"

# Run tests
make test

# Start crawl
python -m ghost_dmpm.main
```

### Production Deployment

#### Option 1: Direct Python
```bash
# Install with production deps
pip install -e ".[crypto,nlp]"

# Configure
cp config/ghost_config.json.example config/ghost_config.json
# Edit config with your API keys

# Run services
python -m ghost_dmpm.api.dashboard &
python -m ghost_dmpm.api.mcp_server &
```

#### Option 2: Docker (Recommended)
```bash
# Build and run
docker-compose up -d

# Check status
docker-compose ps
```

## Configuration

### Required Settings
- `api_keys.google_search`: Your Google API key
- `google_programmable_search_engine_id`: Your CX ID

### Optional Settings
- `webhooks.*`: Notification endpoints
- `scheduler.*`: Automated task settings
