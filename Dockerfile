# ── MCP Filesystem Server ─────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="Rishabh Singh Kharwar"
LABEL description="MCP Filesystem Server — exposes a local directory to MCP clients"

# Ensure Python output is sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server
COPY server.py .

# Default workspace mount point
ENV MCP_ROOT_DIR=/workspace

# MCP servers communicate over stdio — no port needed
ENTRYPOINT ["python", "-u", "server.py"]
