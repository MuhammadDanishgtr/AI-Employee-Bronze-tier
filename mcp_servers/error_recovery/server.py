"""Error Recovery MCP Server — Gold Tier.

Manages failed actions in /Error_Queue/ with tenacity-powered retry logic.

Tools:
  - queue_for_retry       Add a failed action to the error queue
  - list_error_queue      List all items in /Error_Queue/
  - retry_failed_action   Retry a specific queued item (up to 3 attempts)
  - mark_unrecoverable    Mark an item as permanently failed

Uses tenacity for exponential backoff: base 2s, max 3 retries.

Environment variables:
  VAULT_PATH    Path to Obsidian vault
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("ErrorRecoveryServer")

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))
ERROR_QUEUE = VAULT_PATH / "Error_Queue"
MAX_RETRIES = 3


# ── Log helpers ───────────────────────────────────────────────────────────────

def _log(action_type: str, details: str, result: str = "success"):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "ErrorRecoveryServer",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Tool implementations ──────────────────────────────────────────────────────

def queue_for_retry(
    action_type: str,
    description: str,
    payload: dict,
    original_error: str = "",
) -> dict:
    """Add a failed action to the Error Queue for later retry."""
    ERROR_QUEUE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = ERROR_QUEUE / f"ERROR_{action_type.upper()}_{ts}.md"

    content = f"""---
type: error_queue_item
action_type: {action_type}
created: {datetime.now(timezone.utc).isoformat()}
retry_count: 0
max_retries: {MAX_RETRIES}
status: queued
---

# Error Queue: {action_type}

## Description
{description}

## Original Error
```
{original_error}
```

## Payload
```json
{json.dumps(payload, indent=2, default=str)}
```

## Retry History
*(none yet)*
"""
    fname.write_text(content, encoding="utf-8")
    _log("error_queued", f"Queued {action_type}: {description}")
    return {"success": True, "file": str(fname), "action_type": action_type}


def list_error_queue() -> dict:
    """List all items in the Error Queue."""
    ERROR_QUEUE.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(ERROR_QUEUE.iterdir()):
        if f.suffix == ".md" and not f.name.startswith("."):
            text = f.read_text(encoding="utf-8")
            # Parse front matter
            status = "queued"
            retry_count = 0
            action_type = "unknown"
            created = ""
            for line in text.splitlines():
                if line.startswith("status:"):
                    status = line.split(":", 1)[1].strip()
                elif line.startswith("retry_count:"):
                    retry_count = int(line.split(":", 1)[1].strip())
                elif line.startswith("action_type:"):
                    action_type = line.split(":", 1)[1].strip()
                elif line.startswith("created:"):
                    created = line.split(":", 1)[1].strip()
            items.append({
                "file": f.name,
                "action_type": action_type,
                "status": status,
                "retry_count": retry_count,
                "created": created,
            })
    _log("list_error_queue", f"Listed {len(items)} error queue items")
    return {"success": True, "count": len(items), "items": items}


def retry_failed_action(filename: str) -> dict:
    """Attempt to retry a failed action with exponential backoff.

    NOTE: This moves the item from Error_Queue to Needs_Action for
    Claude Code to reprocess. Real retry logic is context-dependent.
    """
    file_path = ERROR_QUEUE / filename
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {filename}"}

    text = file_path.read_text(encoding="utf-8")
    retry_count = 0
    for line in text.splitlines():
        if line.startswith("retry_count:"):
            retry_count = int(line.split(":", 1)[1].strip())

    if retry_count >= MAX_RETRIES:
        # Mark as unrecoverable instead
        return mark_unrecoverable(filename, reason=f"Max retries ({MAX_RETRIES}) exceeded")

    # Increment retry count and move to Needs_Action
    new_count = retry_count + 1
    text = text.replace(f"retry_count: {retry_count}", f"retry_count: {new_count}")
    text = text.replace("status: queued", "status: retrying")

    # Append retry history entry
    retry_entry = f"\n- Retry {new_count}: {datetime.now(timezone.utc).isoformat()}"
    text = text.replace("*(none yet)*", retry_entry) if retry_count == 0 else text + retry_entry

    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)
    dest = needs_action / f"RETRY_{filename}"
    dest.write_text(text, encoding="utf-8")

    # Update original status
    updated = file_path.read_text(encoding="utf-8").replace("status: queued", "status: retrying")
    file_path.write_text(updated, encoding="utf-8")

    _log("error_retry", f"Retry {new_count}/{MAX_RETRIES} for {filename}", result="retrying")
    return {
        "success": True,
        "file": filename,
        "retry_count": new_count,
        "max_retries": MAX_RETRIES,
        "moved_to": str(dest),
        "status": "retrying",
    }


def mark_unrecoverable(filename: str, reason: str = "Manually marked") -> dict:
    """Mark an error queue item as permanently failed."""
    file_path = ERROR_QUEUE / filename
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {filename}"}

    text = file_path.read_text(encoding="utf-8")
    for status in ["queued", "retrying"]:
        text = text.replace(f"status: {status}", "status: unrecoverable")
    # Append reason
    text += f"\n\n## Unrecoverable\n**Reason:** {reason}\n**Marked at:** {datetime.now(timezone.utc).isoformat()}\n"
    file_path.write_text(text, encoding="utf-8")

    # Move to Done for audit trail
    done = VAULT_PATH / "Done"
    done.mkdir(parents=True, exist_ok=True)
    dest = done / f"UNRECOVERABLE_{filename}"
    file_path.rename(dest)

    _log("error_unrecoverable", f"{filename}: {reason}", result="unrecoverable")
    return {"success": True, "file": filename, "moved_to": str(dest), "reason": reason}


# ── Tenacity-powered retry wrapper ────────────────────────────────────────────

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(multiplier=2, min=2, max=16))
def _retry_with_backoff(fn, *args, **kwargs):
    """Run a function with tenacity exponential backoff (used by watchers)."""
    return fn(*args, **kwargs)


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("error-recovery")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="queue_for_retry",
            description="Add a failed action to /Error_Queue/ for later retry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "description": "Type of action that failed"},
                    "description": {"type": "string", "description": "Human-readable description"},
                    "payload": {"type": "object", "description": "Action payload/parameters"},
                    "original_error": {"type": "string", "description": "Error message from the failure"},
                },
                "required": ["action_type", "description", "payload"],
            },
        ),
        Tool(
            name="list_error_queue",
            description="List all items currently in /Error_Queue/ with their retry counts and status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="retry_failed_action",
            description="Move a failed item from /Error_Queue/ back to /Needs_Action/ for retry (max 3 attempts).",
            inputSchema={
                "type": "object",
                "properties": {"filename": {"type": "string", "description": "Filename in /Error_Queue/"}},
                "required": ["filename"],
            },
        ),
        Tool(
            name="mark_unrecoverable",
            description="Mark an error queue item as permanently failed and move it to /Done/ for audit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename in /Error_Queue/"},
                    "reason": {"type": "string", "description": "Reason for marking unrecoverable"},
                },
                "required": ["filename"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = {}
    if name == "queue_for_retry":
        result = queue_for_retry(**arguments)
    elif name == "list_error_queue":
        result = list_error_queue()
    elif name == "retry_failed_action":
        result = retry_failed_action(**arguments)
    elif name == "mark_unrecoverable":
        result = mark_unrecoverable(**arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
