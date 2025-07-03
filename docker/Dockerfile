FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
# We'll copy the whole requirements directory, then install from specific files
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt

# Copy source code and setup files
COPY src/ src/
COPY main.py .
COPY setup.py .
COPY pyproject.toml .
COPY README.md .
# MANIFEST.in is not strictly needed for the build if setup.py/pyproject.toml handle includes,
# but can be copied if it has other uses or for sdist consistency.
# COPY MANIFEST.in .

# Copy other necessary assets that the application might expect at runtime
# relative to the project root (which is /app WORKDIR here)
COPY templates/ templates/
COPY config/ config/ # For ghost_config.json.example primarily

# Create directories that the application expects to write to, if not created by the app itself
# These should align with what GhostConfig and other components expect.
# GhostConfig itself creates ./config and ./logs if project_root is /app.
# Data, reports, test_output might be expected.
RUN mkdir -p data logs reports test_output

# Install package in editable mode (or regular mode if preferred for production)
# Editable mode is useful if you mount the src code for development.
# For a production build, `pip install .` might be more common after copying all files.
RUN pip install -e .
# If optional dependencies are needed in the image, install them:
# RUN pip install -e ".[crypto,nlp]"

EXPOSE 5000 8765

# The CMD should run one of the console scripts defined in setup.py
# For example, to run the main application cycle:
# CMD ["ghost-dmpm"]
# Or to run the MCP server:
# CMD ["ghost-mcp"]
# Or the dashboard:
# CMD ["ghost-dash"]

# The original prompt's Phase 5.3 specified: CMD ["python", "main.py"]
# This runs the root main.py script, which is a valid way to start the main cycle.
CMD ["python", "main.py"]
