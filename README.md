# 🗂️ MCP Filesystem Server (Docker)

A self-contained **Model Context Protocol (MCP) server** that gives any MCP-compatible
client (Claude Desktop, Cursor, Continue, etc.) full read/write access to a local
directory — all running safely inside Docker.

---

## 📦 Project Structure

```
mcp-filesystem/
├── server.py                  # MCP server (12 tools with privacy & security guards)
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Compose orchestration (optional)
├── requirements.txt           # Python dependencies (mcp)
├── claude_desktop_config.json # Template config to paste into Claude Desktop
└── workspace/                 # Default mount target folder
```

---

## 🚀 Quick Start

### 1 — Build the image
Clone this repository and build the Docker image locally:
```bash
docker build -t mcp-filesystem:latest .
```

### 2 — Locate your Claude Desktop Config File

Open your Claude Desktop configuration file based on your operating system:

| Operating System | Config Path |
|------------------|-------------|
| **Windows**      | `%APPDATA%\Claude\claude_desktop_config.json` |
| **macOS**        | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Linux**        | `~/.config/Claude/claude_desktop_config.json` |

### 3 — Add the Server to `mcpServers`

Merge the following block into your config file under `"mcpServers"`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--name",
        "mcp-filesystem",
        "-e",
        "MCP_ROOT_DIR=/workspace",
        "--volume",
        "<YOUR_LOCAL_FOLDER_PATH>:/workspace",
        "--volume",
        "<PATH_TO_CLONED_REPO>/server.py:/app/server.py",
        "mcp-filesystem:latest"
      ]
    }
  }
}
```

> ⚠️ **Replace `<YOUR_LOCAL_FOLDER_PATH>` and `<PATH_TO_CLONED_REPO>` with your actual paths!** See [Dynamic Path Configuration](#-dynamic-path-configuration) below for copy-paste examples.

### 4 — Restart Claude Desktop

Completely quit and restart Claude Desktop. Claude will now display the 🔌 filesystem tools.

---

## ⚙️ Dynamic Path Configuration

When using this MCP server on different computers or operating systems, you need to configure the paths in `claude_desktop_config.json` dynamically:

### 1. What Each Path Means

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `--name mcp-filesystem` | **Static Container Name:** Prevents Docker from creating containers with random names (e.g. `zen_curie`, `sleepy_hawking`) on every launch. | Keep as `"mcp-filesystem"` or choose any name. |
| `--volume <LOCAL_FOLDER>:/workspace` | **Your Data Folder:** The folder or drive on your machine that Claude can browse and edit. | Windows: `"C:/Users/alex/projects:/workspace"`<br>macOS: `"/Users/alex/projects:/workspace"` |
| `--volume <REPO_PATH>/server.py:/app/server.py` | **Live Code Reload (Optional):** Mounts your local `server.py` into the container. Any edits made to `server.py` take effect **immediately** without rebuilding the Docker image. | Windows: `"C:/mcp-filesystem/server.py:/app/server.py"`<br>*(Omit this line if you just want to run the container image as built)* |
| `-e MCP_ROOT_DIR=/workspace` | **Default Workspace Root:** Tells the Python MCP server where your primary workspace is inside the container. | Default: `"/workspace"` |
| `-e MCP_ROOTS=...` | **Multiple Roots (Optional):** Comma-separated list of roots when exposing multiple folders or drives. | `"/workspace,/workspace/secondary"` |

---

### 2. Platform Copy-Paste Examples

#### 🪟 Windows (Single Drive / Project Folder)
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--name",
        "mcp-filesystem",
        "-e",
        "MCP_ROOT_DIR=/workspace",
        "--volume",
        "C:/Users/YOUR_USERNAME/projects:/workspace",
        "--volume",
        "C:/path/to/mcp-filesystem/server.py:/app/server.py",
        "mcp-filesystem:latest"
      ]
    }
  }
}
```
> **Tip for Windows:** Use forward slashes (`C:/Users/...`) or escaped backslashes (`C:\\Users\\...`) in JSON.

---

#### 🪟 Windows (Multiple Drives — e.g. D: and E: Drives)
If you want to expose entire drives (or multiple folders), mount secondary drives inside `/workspace/<drive_name>` and list them in `MCP_ROOTS`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--name",
        "mcp-filesystem",
        "-e",
        "MCP_ROOT_DIR=/workspace",
        "-e",
        "MCP_ROOTS=/workspace,/workspace/E_drive",
        "--volume",
        "D:/:/workspace",
        "--volume",
        "E:/:/workspace/E_drive",
        "--volume",
        "D:/mcp-filesystem/server.py:/app/server.py",
        "mcp-filesystem:latest"
      ]
    }
  }
}
```

---

#### 🍎 macOS / 🐧 Linux
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--name",
        "mcp-filesystem",
        "-e",
        "MCP_ROOT_DIR=/workspace",
        "--volume",
        "/Users/YOUR_USERNAME/projects:/workspace",
        "--volume",
        "/Users/YOUR_USERNAME/mcp-filesystem/server.py:/app/server.py",
        "mcp-filesystem:latest"
      ]
    }
  }
}
```

---

## 🔧 Available Tools

| Tool | Description |
|------|-------------|
| `list_allowed_directories` | Returns allowed root directories |
| `list_directory` | Browse folder contents (safely skips permission-restricted system files) |
| `read_file` | Read text file (with size limits and encoding safeguards) |
| `write_file` | Create or overwrite a file |
| `append_file` | Append text to a file |
| `create_directory` | Make new directories recursively |
| `delete_path` | Delete files or folders (protects directories containing media) |
| `move_path` | Move / rename files or folders |
| `copy_path` | Copy files or trees |
| `file_info` | Inspect size, dates, and type metadata |
| `search_files` | Glob pattern search (lazy iteration, max results capped) |
| `grep_files` | Full-text search with folder targeting & noisy directory exclusion |

---

## 🛡️ Security, Privacy & Compatibility

- **Media Privacy Filter** — Claude Desktop has **zero access** to photos, pictures, or videos.
  - Image extensions (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg`, `.ico`, `.heic`, `.raw`, `.psd`, etc.) and Video extensions (`.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, etc.) are blocked.
  - Media files are hidden from `list_directory` and `search_files`.
  - Operations like `read_file`, `write_file`, `copy_path`, `move_path`, `file_info` reject media files with `PermissionError`.
  - Recursive folder deletion will stop if a folder contains media files.
  - Can be customized via the `BLOCKED_EXTENSIONS` environment variable.
- **Path Traversal Protection** — Path resolution enforces strict Python `is_relative_to` checks against allowed roots to prevent escaping mounts.
- **Windows Path Normalization** — Backslashes (`\`) and drive letters (`D:\...`, `E:\...`) sent by Windows clients are automatically mapped to container roots (`/workspace`, `/workspace/E_drive`).
- **Permission Resilience** — Windows system files (e.g. `System Volume Information`, `$RECYCLE.BIN`) do not crash directory listings.
- **Unbuffered Stdio** — Runs with `PYTHONUNBUFFERED=1` to ensure instantaneous JSON-RPC messaging.

---

## 🐛 Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Conflict. The container name "/mcp-filesystem" is already in use` | If Claude Desktop crashed or shut down abruptly, remove the stopped container with `docker rm -f mcp-filesystem` |
| `Error: Cannot connect to MCP server` | Ensure Docker Desktop is running before starting Claude Desktop |
| `permission denied` | Check that Docker has access to your drive/folder in **Docker Desktop Settings → Resources → File Sharing** |
| Changes in `server.py` not appearing | Verify the volume mount points to your local `server.py` (`<YOUR_PATH>/server.py:/app/server.py`) |
| Windows path errors in JSON | Ensure paths in `claude_desktop_config.json` use forward slashes (`/`) or double backslashes (`\\`) |

---

## 👤 Author

**Rishabh Singh Kharwar**
- GitHub: [@rishabhkr157](https://github.com/rishabhkr157)

---

## 📄 License

MIT License
