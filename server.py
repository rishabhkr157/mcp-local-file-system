#!/usr/bin/env python3
"""
MCP Filesystem Server - Multi-root support with Media Filtering
"""

import os
import re
import json
import shutil
import asyncio
import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

_roots_env = os.environ.get("MCP_ROOTS", "")
if _roots_env:
    ROOT_DIRS = [Path(p.strip()) for p in _roots_env.split(",") if p.strip()]
else:
    ROOT_DIRS = [Path(os.environ.get("MCP_ROOT_DIR", "/workspace"))]

ROOT_DIR = ROOT_DIRS[0]

# ── Media File Blocking ────────────────────────────────────────────────────────
DEFAULT_BLOCKED_EXTENSIONS = {
    # Pictures / Images
    ".png", ".jpg", ".jpeg", ".jpe", ".jif", ".jfif", ".jfi",
    ".gif", ".webp", ".bmp", ".dib", ".ico", ".tiff", ".tif",
    ".svg", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
    ".arw", ".psd", ".ai", ".eps",
    # Videos
    ".mp4", ".m4v", ".mkv", ".avi", ".mov", ".qt", ".wmv",
    ".flv", ".webm", ".vob", ".ts", ".mts", ".m2ts", ".3gp",
    ".3g2", ".mpg", ".mpeg", ".ogv"
}

_blocked_env = os.environ.get("BLOCKED_EXTENSIONS", "")
if _blocked_env:
    BLOCKED_EXTENSIONS = {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in _blocked_env.split(",") if ext.strip()
    }
else:
    BLOCKED_EXTENSIONS = DEFAULT_BLOCKED_EXTENSIONS

def is_blocked(path: Path) -> bool:
    """Return True if the path corresponds to a restricted media file."""
    return path.suffix.lower() in BLOCKED_EXTENSIONS

app = Server("filesystem-mcp")

def safe_path(relative: str, check_blocked: bool = False) -> Path:
    if not relative:
        relative = "."
    # 1. Normalize backslashes (common when client runs on Windows)
    clean = str(relative).strip().replace("\\", "/")

    # 2. Handle Windows drive letter prefixes (e.g. D:/..., E:/...)
    # Maps D: -> /workspace and E: -> /workspace/E_drive based on mounted volumes
    m = re.match(r"^([a-zA-Z]):/(.*)$", clean)
    if m:
        drive = m.group(1).upper()
        rest = m.group(2)
        if drive == "D":
            clean = f"/workspace/{rest}"
        elif drive == "E":
            clean = f"/workspace/E_drive/{rest}"
        else:
            clean = rest

    candidate = Path(clean)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (ROOT_DIR / clean).resolve()

    allowed = False
    for root in ROOT_DIRS:
        root_resolved = root.resolve()
        if resolved == root_resolved or resolved.is_relative_to(root_resolved):
            allowed = True
            break

    if not allowed:
        raise PermissionError(
            f"Access denied: '{relative}' resolved to '{resolved}' which is outside all allowed roots: {[str(r) for r in ROOT_DIRS]}"
        )

    if check_blocked and is_blocked(resolved):
        raise PermissionError(
            f"Access denied: Access to media files (pictures/videos: '{resolved.name}') is restricted."
        )

    return resolved

def format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def rel_display(path: Path) -> str:
    for root in sorted(ROOT_DIRS, key=lambda p: len(str(p.resolve())), reverse=True):
        try:
            return str(path.relative_to(root.resolve()))
        except ValueError:
            continue
    return str(path)

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_allowed_directories",
            description="Returns allowed directory roots.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="list_directory",
            description="List files and folders in a directory. Use '.' for root.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (defaults to '.')."},
                    "show_hidden": {"type": "boolean", "description": "Include hidden files (starting with .)."}
                },
                "required": []
            }
        ),
        Tool(
            name="read_file",
            description="Read file content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "encoding": {"type": "string", "description": "File encoding (default 'utf-8')."}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file (creates directories if needed).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "Text content to write."},
                    "encoding": {"type": "string", "description": "File encoding (default 'utf-8')."}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="append_file",
            description="Append content to an existing or new file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "Text content to append."}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="create_directory",
            description="Create a directory (and parents if needed).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory."}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="delete_path",
            description="Delete a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete."},
                    "recursive": {"type": "boolean", "description": "Recursively delete directories."}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="move_path",
            description="Move or rename a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path."},
                    "destination": {"type": "string", "description": "Destination path."}
                },
                "required": ["source", "destination"]
            }
        ),
        Tool(
            name="copy_path",
            description="Copy a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path."},
                    "destination": {"type": "string", "description": "Destination path."}
                },
                "required": ["source", "destination"]
            }
        ),
        Tool(
            name="file_info",
            description="Get file or directory metadata (size, dates, type).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to inspect."}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="search_files",
            description="Glob search for files and folders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py' or '**/*.json')."},
                    "base_path": {"type": "string", "description": "Base directory to search from (defaults to '.')."},
                    "max_results": {"type": "integer", "description": "Maximum number of results (default 200)."}
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="grep_files",
            description="Search text within files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text substring to find."},
                    "path": {"type": "string", "description": "Folder or file to search in (defaults to '.')."},
                    "pattern": {"type": "string", "description": "File glob pattern to match (default '**/*')."},
                    "case_sensitive": {"type": "boolean", "description": "Case-sensitive search (default true)."},
                    "max_results": {"type": "integer", "description": "Maximum match lines to return (default 50)."}
                },
                "required": ["query"]
            }
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "list_allowed_directories":
            result = json.dumps({"directories": [str(r) for r in ROOT_DIRS]}, indent=2)

        elif name == "list_directory":
            path = safe_path(arguments.get("path", "."), check_blocked=False)
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: '{arguments.get('path', '.')}'")
            if not path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: '{arguments.get('path', '.')}'")

            show_hidden = arguments.get("show_hidden", False)
            raw_entries = []
            try:
                for entry in path.iterdir():
                    raw_entries.append(entry)
            except PermissionError as e:
                raise PermissionError(f"Permission denied accessing directory: {e}")

            def get_sort_key(p: Path):
                try:
                    return (not p.is_dir(), p.name.lower())
                except Exception:
                    return (True, p.name.lower())

            lines = [f"📁 {rel_display(path)}/\n"]
            for entry in sorted(raw_entries, key=get_sort_key):
                if not show_hidden and entry.name.startswith("."):
                    continue
                # Hide restricted media files (pictures/videos) completely
                if is_blocked(entry):
                    continue
                try:
                    if entry.is_file():
                        try:
                            size = f"  ({format_size(entry.stat().st_size)})"
                        except Exception:
                            size = ""
                        lines.append(f"  📄 {entry.name}{size}")
                    elif entry.is_dir():
                        lines.append(f"  📁 {entry.name}/")
                    else:
                        lines.append(f"  ❓ {entry.name}")
                except (PermissionError, OSError):
                    lines.append(f"  🔒 {entry.name} (access restricted)")

            result = "\n".join(lines) if len(lines) > 1 else "  (empty directory)"

        elif name == "read_file":
            path = safe_path(arguments["path"], check_blocked=True)
            if not path.exists():
                raise FileNotFoundError(f"File not found: '{arguments['path']}'")
            if path.is_dir():
                raise IsADirectoryError(f"Path is a directory, not a file: '{arguments['path']}'")

            # Check file size (guard against reading huge files into memory)
            stat = path.stat()
            max_size = 10 * 1024 * 1024  # 10 MB limit
            if stat.st_size > max_size:
                raise ValueError(
                    f"File '{arguments['path']}' is too large ({format_size(stat.st_size)}). "
                    f"Maximum readable size is 10 MB."
                )

            content = path.read_text(
                encoding=arguments.get("encoding", "utf-8"),
                errors="replace"
            )
            result = f"--- {arguments['path']} ---\n{content}"

        elif name == "write_file":
            path = safe_path(arguments["path"], check_blocked=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding=arguments.get("encoding", "utf-8"))
            result = f"✅ Written {format_size(path.stat().st_size)} to '{arguments['path']}'"

        elif name == "append_file":
            path = safe_path(arguments["path"], check_blocked=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=arguments.get("encoding", "utf-8")) as f:
                f.write(arguments["content"])
            result = f"✅ Appended to '{arguments['path']}'"

        elif name == "create_directory":
            path = safe_path(arguments["path"], check_blocked=False)
            path.mkdir(parents=True, exist_ok=True)
            result = f"✅ Created '{arguments['path']}'"

        elif name == "delete_path":
            path = safe_path(arguments["path"], check_blocked=True)
            if not path.exists():
                raise FileNotFoundError(f"Path not found: '{arguments['path']}'")
            if path.is_dir():
                if arguments.get("recursive"):
                    for p in path.rglob("*"):
                        if is_blocked(p):
                            raise PermissionError(
                                f"Access denied: Directory contains restricted media file '{p.name}'."
                            )
                    shutil.rmtree(path)
                else:
                    path.rmdir()
            else:
                path.unlink()
            result = f"🗑️ Deleted '{arguments['path']}'"

        elif name == "move_path":
            src = safe_path(arguments["source"], check_blocked=True)
            dst = safe_path(arguments["destination"], check_blocked=True)
            shutil.move(str(src), str(dst))
            result = f"✅ Moved '{arguments['source']}' → '{arguments['destination']}'"

        elif name == "copy_path":
            src = safe_path(arguments["source"], check_blocked=True)
            dst = safe_path(arguments["destination"], check_blocked=True)
            shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
            result = f"✅ Copied '{arguments['source']}' → '{arguments['destination']}'"

        elif name == "file_info":
            path = safe_path(arguments["path"], check_blocked=True)
            if not path.exists():
                raise FileNotFoundError(f"Path not found: '{arguments['path']}'")
            stat = path.stat()
            result = json.dumps(
                {
                    "name": path.name,
                    "type": "directory" if path.is_dir() else "file",
                    "size": format_size(stat.st_size),
                    "size_bytes": stat.st_size,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "absolute_path": str(path)
                },
                indent=2
            )

        elif name == "search_files":
            base = safe_path(arguments.get("base_path", "."), check_blocked=False)
            if not base.is_dir():
                raise NotADirectoryError(f"Base path is not a directory: '{arguments.get('base_path', '.')}'")
            pattern = arguments["pattern"]
            max_results = arguments.get("max_results", 200)

            matches = []
            try:
                for m in base.glob(pattern):
                    # Exclude restricted media files from search results
                    if is_blocked(m):
                        continue
                    matches.append(m)
                    if len(matches) >= max_results:
                        break
            except PermissionError:
                pass

            if not matches:
                result = f"No files matched pattern '{pattern}' in '{rel_display(base)}'."
            else:
                hit_note = f" (showing first {max_results})" if len(matches) >= max_results else ""
                lines = [f"Found {len(matches)}{hit_note} match(es) in '{rel_display(base)}':"]
                for m in matches:
                    try:
                        icon = '📁' if m.is_dir() else '📄'
                    except Exception:
                        icon = '📄'
                    lines.append(f"  {icon} {rel_display(m)}")
                result = "\n".join(lines)

        elif name == "grep_files":
            query = arguments["query"]
            case_sensitive = arguments.get("case_sensitive", True)
            max_results = arguments.get("max_results", 50)
            search_target = safe_path(arguments.get("path", arguments.get("base_path", ".")), check_blocked=False)
            pattern = arguments.get("pattern", "**/*")

            # Directory exclusions for performance and safety
            IGNORE_DIRS = {
                ".git", "node_modules", "__pycache__", ".venv", "venv",
                "$RECYCLE.BIN", "System Volume Information"
            }

            hits = []
            cmp_q = query if case_sensitive else query.lower()

            candidates = [search_target] if search_target.is_file() else search_target.glob(pattern)

            for fp in candidates:
                # Exclude restricted media files from grep
                if is_blocked(fp):
                    continue
                if any(part in IGNORE_DIRS for part in fp.parts):
                    continue
                try:
                    if not fp.is_file():
                        continue
                    # Skip files larger than 2MB to prevent long hangs
                    if fp.stat().st_size > 2 * 1024 * 1024:
                        continue
                    for i, line in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        line_cmp = line if case_sensitive else line.lower()
                        if cmp_q in line_cmp:
                            hits.append(f"{rel_display(fp)}:{i}: {line.strip()}")
                            if len(hits) >= max_results:
                                break
                except Exception:
                    continue
                if len(hits) >= max_results:
                    break

            result = f"Found {len(hits)} match(es):\n\n" + "\n".join(hits) if hits else f"No matches for '{query}' in '{rel_display(search_target)}'"

        else:
            result = f"Unknown tool: {name}"

    except PermissionError as e:
        result = f"🚫 {e}"
    except FileNotFoundError as e:
        result = f"❌ {e}"
    except Exception as e:
        result = f"💥 {type(e).__name__}: {e}"

    return [TextContent(type="text", text=result)]

async def main():
    import sys
    print(f"Filesystem MCP Server starting | roots: {[str(r) for r in ROOT_DIRS]}", flush=True, file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
