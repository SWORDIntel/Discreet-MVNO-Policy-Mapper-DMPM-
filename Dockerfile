FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir requests beautifulsoup4 Flask Flask-HTTPAuth python-dateutil

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data logs reports test_output config templates

# Create startup script
RUN echo '#!/bin/bash\n\
echo "[*] GHOST DMPM Container Starting..."\n\
echo "[*] Checking API configuration..."\n\
python3 -c "from ghost_config import GhostConfig; c=GhostConfig(); print(f\"API Mode: {c.get(\"google_search_mode\", \"mock\")}\")" \n\
echo "[*] Starting dashboard on port 5000..."\n\
python3 ghost_dashboard.py' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 5000

CMD ["/app/start.sh"]
