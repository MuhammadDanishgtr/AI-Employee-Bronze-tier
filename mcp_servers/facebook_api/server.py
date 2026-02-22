"""Facebook API MCP Server — Gold Tier.

Provides Facebook Graph API tools:
  - post_to_page        Post content to a Facebook Page (HITL required)
  - get_page_insights   Retrieve engagement metrics for the page
  - list_recent_posts   List recent posts on the page
  - get_comments        Get comments on a specific post

All page posts are routed through HITL /Pending_Approval/ before publishing.

Environment variables:
  FACEBOOK_PAGE_ID      Numeric Facebook Page ID
  FACEBOOK_ACCESS_TOKEN Page access token (long-lived)
  VAULT_PATH            Path to Obsidian vault
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("FacebookAPIServer")

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"
VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _graph(endpoint: str, method: str = "GET", params: dict | None = None, data: dict | None = None) -> dict:
    """Make a Facebook Graph API request."""
    if not ACCESS_TOKEN:
        raise RuntimeError("FACEBOOK_ACCESS_TOKEN not configured")
    url = f"{GRAPH_BASE}/{endpoint}"
    merged_params = {"access_token": ACCESS_TOKEN, **(params or {})}
    if method == "POST":
        resp = requests.post(url, params=merged_params, json=data or {}, timeout=30)
    else:
        resp = requests.get(url, params=merged_params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _log(action_type: str, details: str, result: str = "success"):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "FacebookAPIServer",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _create_hitl(content: str, scheduled_time: str | None = None) -> Path:
    """Create HITL approval file for a page post."""
    folder = VAULT_PATH / "Pending_Approval"
    folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = folder / f"FACEBOOK_POST_{ts}.md"
    preview = content[:200] + ("..." if len(content) > 200 else "")
    schedule_note = f"\n**Scheduled:** {scheduled_time}" if scheduled_time else ""
    file_content = f"""---
type: facebook_post_approval
page_id: {PAGE_ID}
created: {datetime.now(timezone.utc).isoformat()}
status: pending
---

# Facebook Post Approval Required
{schedule_note}

## Content Preview
{preview}

## Full Content
```
{content}
```

## Instructions
Move to `/Approved/` to publish, or `/Rejected/` to cancel.
The orchestrator will call the Facebook API on your behalf.
"""
    fname.write_text(file_content, encoding="utf-8")
    return fname


# ── Tool implementations ──────────────────────────────────────────────────────

def post_to_page(message: str, link: str = "", scheduled_publish_time: str = "") -> dict:
    """Route a Facebook page post through HITL approval."""
    try:
        hitl_path = _create_hitl(message, scheduled_publish_time or None)
        _log("facebook_post_hitl", f"Post queued for approval: {hitl_path.name}", result="pending_approval")
        return {
            "success": True,
            "status": "pending_approval",
            "approval_file": str(hitl_path),
            "message": "Post saved to /Pending_Approval/ — move to /Approved/ to publish.",
        }
    except Exception as exc:
        _log("facebook_post_hitl", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def _publish_post(message: str, link: str = "") -> dict:
    """Actually publish a post (called after HITL approval)."""
    try:
        data: dict = {"message": message}
        if link:
            data["link"] = link
        result = _graph(f"{PAGE_ID}/feed", method="POST", data=data)
        _log("facebook_post_published", f"Post ID: {result.get('id', 'unknown')}")
        return {"success": True, "post_id": result.get("id"), "page_id": PAGE_ID}
    except Exception as exc:
        _log("facebook_post_published", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def get_page_insights(metric: str = "page_impressions,page_engaged_users,page_fans", period: str = "day") -> dict:
    """Get Facebook Page insights/metrics."""
    try:
        if not PAGE_ID:
            return {"success": False, "error": "FACEBOOK_PAGE_ID not configured"}
        result = _graph(f"{PAGE_ID}/insights", params={"metric": metric, "period": period})
        _log("facebook_insights", f"Retrieved insights: {metric}")
        return {"success": True, "data": result.get("data", []), "paging": result.get("paging", {})}
    except Exception as exc:
        _log("facebook_insights", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def list_recent_posts(limit: int = 10) -> dict:
    """List recent posts on the Facebook Page."""
    try:
        if not PAGE_ID:
            return {"success": False, "error": "FACEBOOK_PAGE_ID not configured"}
        result = _graph(
            f"{PAGE_ID}/posts",
            params={"fields": "id,message,created_time,likes.summary(true),comments.summary(true)", "limit": limit},
        )
        _log("facebook_list_posts", f"Listed {len(result.get('data', []))} posts")
        return {"success": True, "posts": result.get("data", []), "count": len(result.get("data", []))}
    except Exception as exc:
        _log("facebook_list_posts", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def get_comments(post_id: str, limit: int = 20) -> dict:
    """Get comments on a specific Facebook post."""
    try:
        result = _graph(
            f"{post_id}/comments",
            params={"fields": "id,message,from,created_time", "limit": limit},
        )
        comments = result.get("data", [])
        _log("facebook_get_comments", f"Retrieved {len(comments)} comments for post {post_id}")
        return {"success": True, "post_id": post_id, "comments": comments, "count": len(comments)}
    except Exception as exc:
        _log("facebook_get_comments", str(exc), result="error")
        return {"success": False, "error": str(exc)}


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("facebook-api")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="post_to_page",
            description="Draft a Facebook Page post and route it through HITL approval before publishing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Post text content"},
                    "link": {"type": "string", "description": "Optional URL to attach"},
                    "scheduled_publish_time": {"type": "string", "description": "Optional ISO datetime for scheduling"},
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="get_page_insights",
            description="Retrieve Facebook Page engagement metrics (impressions, reach, fans).",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "default": "page_impressions,page_engaged_users,page_fans"},
                    "period": {"type": "string", "enum": ["day", "week", "days_28"], "default": "day"},
                },
            },
        ),
        Tool(
            name="list_recent_posts",
            description="List recent posts on the Facebook Page with engagement counts.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 10}},
            },
        ),
        Tool(
            name="get_comments",
            description="Get comments on a specific Facebook post.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Facebook post ID"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["post_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = {}
    if name == "post_to_page":
        result = post_to_page(**arguments)
    elif name == "get_page_insights":
        result = get_page_insights(**arguments)
    elif name == "list_recent_posts":
        result = list_recent_posts(**arguments)
    elif name == "get_comments":
        result = get_comments(**arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
