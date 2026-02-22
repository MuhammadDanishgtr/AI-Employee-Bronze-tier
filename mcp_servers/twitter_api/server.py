"""Twitter / X API MCP Server — Gold Tier.

Provides Twitter API v2 tools via Tweepy:
  - post_tweet      Post a tweet (HITL required)
  - get_analytics   Get tweet engagement analytics
  - list_mentions   Get recent mentions of the account
  - get_timeline    Get recent tweets from the account timeline

All tweets are routed through HITL /Pending_Approval/ before publishing.

Environment variables:
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_TOKEN_SECRET
  TWITTER_BEARER_TOKEN
  VAULT_PATH
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

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("TwitterAPIServer")

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")


def _get_client():
    """Build and return an authenticated Tweepy client."""
    try:
        import tweepy
    except ImportError:
        raise RuntimeError("tweepy not installed — run: pip install tweepy")

    if not TWITTER_BEARER_TOKEN:
        raise RuntimeError("TWITTER_BEARER_TOKEN not configured")

    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def _log(action_type: str, details: str, result: str = "success"):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "TwitterAPIServer",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _create_hitl(tweet_text: str, reply_to_id: str | None = None) -> Path:
    """Create HITL approval file for a tweet."""
    folder = VAULT_PATH / "Pending_Approval"
    folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = folder / f"TWITTER_TWEET_{ts}.md"
    reply_note = f"\n**Reply to tweet:** {reply_to_id}" if reply_to_id else ""
    content = f"""---
type: twitter_post_approval
created: {datetime.now(timezone.utc).isoformat()}
status: pending
---

# Twitter Post Approval Required
{reply_note}

## Tweet Content ({len(tweet_text)}/280 chars)
```
{tweet_text}
```

## Instructions
Move to `/Approved/` to publish, or `/Rejected/` to cancel.
"""
    fname.write_text(content, encoding="utf-8")
    return fname


# ── Tool implementations ──────────────────────────────────────────────────────

def post_tweet(text: str, reply_to_tweet_id: str = "") -> dict:
    """Route a tweet through HITL approval before posting."""
    try:
        hitl_path = _create_hitl(text, reply_to_tweet_id or None)
        _log("twitter_post_hitl", f"Tweet queued for approval: {hitl_path.name}", result="pending_approval")
        return {
            "success": True,
            "status": "pending_approval",
            "approval_file": str(hitl_path),
            "char_count": len(text),
            "message": "Tweet saved to /Pending_Approval/ — move to /Approved/ to publish.",
        }
    except Exception as exc:
        _log("twitter_post_hitl", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def _publish_tweet(text: str, reply_to_tweet_id: str | None = None) -> dict:
    """Actually post a tweet (called after HITL approval)."""
    try:
        client = _get_client()
        kwargs: dict = {"text": text}
        if reply_to_tweet_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_tweet_id
        response = client.create_tweet(**kwargs)
        tweet_id = response.data["id"]
        _log("twitter_tweet_published", f"Tweet ID: {tweet_id}")
        return {"success": True, "tweet_id": tweet_id, "text": text}
    except Exception as exc:
        _log("twitter_tweet_published", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def get_analytics(tweet_id: str) -> dict:
    """Get engagement metrics for a specific tweet."""
    try:
        client = _get_client()
        response = client.get_tweet(
            tweet_id,
            tweet_fields=["public_metrics", "created_at", "text"],
        )
        if not response.data:
            return {"success": False, "error": "Tweet not found"}
        metrics = response.data.get("public_metrics", {})
        _log("twitter_analytics", f"Analytics for tweet {tweet_id}: {metrics}")
        return {
            "success": True,
            "tweet_id": tweet_id,
            "text": response.data.get("text", ""),
            "metrics": metrics,
        }
    except Exception as exc:
        _log("twitter_analytics", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def list_mentions(max_results: int = 10) -> dict:
    """Get recent mentions of the authenticated account."""
    try:
        client = _get_client()
        # Get the authenticated user's ID first
        me = client.get_me()
        if not me.data:
            return {"success": False, "error": "Could not retrieve authenticated user"}
        user_id = me.data.id
        response = client.get_users_mentions(
            user_id,
            max_results=max_results,
            tweet_fields=["created_at", "author_id", "public_metrics", "text"],
        )
        mentions = []
        if response.data:
            for tweet in response.data:
                mentions.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": str(tweet.created_at),
                    "author_id": tweet.author_id,
                    "metrics": tweet.public_metrics,
                })
        _log("twitter_list_mentions", f"Retrieved {len(mentions)} mentions")
        return {"success": True, "count": len(mentions), "mentions": mentions}
    except Exception as exc:
        _log("twitter_list_mentions", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def get_timeline(max_results: int = 10) -> dict:
    """Get recent tweets from the authenticated account's timeline."""
    try:
        client = _get_client()
        me = client.get_me()
        if not me.data:
            return {"success": False, "error": "Could not retrieve authenticated user"}
        user_id = me.data.id
        response = client.get_users_tweets(
            user_id,
            max_results=max_results,
            tweet_fields=["created_at", "public_metrics", "text"],
        )
        tweets = []
        if response.data:
            for tweet in response.data:
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": str(tweet.created_at),
                    "metrics": tweet.public_metrics,
                })
        _log("twitter_get_timeline", f"Retrieved {len(tweets)} timeline tweets")
        return {"success": True, "count": len(tweets), "tweets": tweets}
    except Exception as exc:
        _log("twitter_get_timeline", str(exc), result="error")
        return {"success": False, "error": str(exc)}


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("twitter-api")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="post_tweet",
            description="Draft a tweet and route it through HITL approval before posting to Twitter/X.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Tweet text (max 280 chars)"},
                    "reply_to_tweet_id": {"type": "string", "description": "Tweet ID to reply to (optional)"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="get_analytics",
            description="Get engagement metrics (likes, retweets, impressions) for a specific tweet.",
            inputSchema={
                "type": "object",
                "properties": {"tweet_id": {"type": "string", "description": "Tweet ID"}},
                "required": ["tweet_id"],
            },
        ),
        Tool(
            name="list_mentions",
            description="Get recent mentions of the authenticated Twitter/X account.",
            inputSchema={
                "type": "object",
                "properties": {"max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}},
            },
        ),
        Tool(
            name="get_timeline",
            description="Get recent tweets from the authenticated account's own timeline.",
            inputSchema={
                "type": "object",
                "properties": {"max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = {}
    if name == "post_tweet":
        result = post_tweet(**arguments)
    elif name == "get_analytics":
        result = get_analytics(**arguments)
    elif name == "list_mentions":
        result = list_mentions(**arguments)
    elif name == "get_timeline":
        result = get_timeline(**arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
