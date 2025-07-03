FROM python:3.11-alpine
RUN adduser -D ghost
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir flask flask-httpauth requests beautifulsoup4
COPY --chown=ghost . .
USER ghost
CMD ["python", "ghost_dashboard.py"]
