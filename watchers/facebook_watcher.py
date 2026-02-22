"""Facebook Watcher — Gold Tier.

Polls Facebook Graph API every 600 seconds for:
  - New comments on page posts
  - New page mentions
  - Unread page messages (requires page messaging permission)

Creates action files in /Needs_Action:
  - FACEBOOK_MENTION_<id>_<timestamp>.md
  - FACEBOOK_COMMENT_<id>_<timestamp>.md
  - FACEBOOK_MESSAGE_<id>_<timestamp>.md

Usage:
    py watchers/facebook_watcher.py
    py watchers/facebook_watcher.py --vault D:/path/to/vault

Environment variables:
    VAULT_PATH              Obsidian vault path
    FACEBOOK_PAGE_ID        Numeric Facebook Page ID
    FACEBOOK_ACCESS_TOKEN   Page access token (long-lived)
    SCHEDULE_FACEBOOK_INTERVAL  Poll interval in seconds (default: 600)
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher


GRAPH_BASE = "https://graph.facebook.com/v19.0"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")


class FacebookWatcher(BaseWatcher):
    """Polls Facebook Page for new comments, mentions, and messages."""

    def __init__(self, vault_path: str, check_interval: int = 600):
        super().__init__(vault_path=vault_path, check_interval=check_interval)
        self._seen_comment_ids: set[str] = set()
        self._seen_mention_ids: set[str] = set()
        self._seen_message_ids: set[str] = set()

    def _graph(self, endpoint: str, params: dict | None = None) -> dict:
        if not ACCESS_TOKEN:
            return {}
        url = f"{GRAPH_BASE}/{endpoint}"
        merged = {"access_token": ACCESS_TOKEN, **(params or {})}
        try:
            resp = requests.get(url, params=merged, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            self.logger.warning(f"Facebook API error: {exc}")
            return {}

    def _check_comments(self) -> list[dict]:
        """Get new comments on recent page posts."""
        if not PAGE_ID:
            return []
        posts_data = self._graph(
            f"{PAGE_ID}/posts",
            {"fields": "id,message,created_time", "limit": 5},
        )
        new_comments = []
        for post in posts_data.get("data", []):
            post_id = post["id"]
            comments_data = self._graph(
                f"{post_id}/comments",
                {"fields": "id,message,from,created_time", "limit": 20},
            )
            for comment in comments_data.get("data", []):
                cid = comment["id"]
                if cid not in self._seen_comment_ids:
                    self._seen_comment_ids.add(cid)
                    new_comments.append({
                        "type": "comment",
                        "comment_id": cid,
                        "post_id": post_id,
                        "post_message": post.get("message", "")[:100],
                        "comment_message": comment.get("message", ""),
                        "from_name": comment.get("from", {}).get("name", "Unknown"),
                        "from_id": comment.get("from", {}).get("id", ""),
                        "created_time": comment.get("created_time", ""),
                    })
        return new_comments

    def _check_mentions(self) -> list[dict]:
        """Get page mentions (tagged posts)."""
        if not PAGE_ID:
            return []
        data = self._graph(
            f"{PAGE_ID}/tagged",
            {"fields": "id,message,from,created_time,permalink_url", "limit": 10},
        )
        new_mentions = []
        for mention in data.get("data", []):
            mid = mention["id"]
            if mid not in self._seen_mention_ids:
                self._seen_mention_ids.add(mid)
                new_mentions.append({
                    "type": "mention",
                    "mention_id": mid,
                    "message": mention.get("message", ""),
                    "from_name": mention.get("from", {}).get("name", "Unknown"),
                    "from_id": mention.get("from", {}).get("id", ""),
                    "created_time": mention.get("created_time", ""),
                    "permalink_url": mention.get("permalink_url", ""),
                })
        return new_mentions

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        if not ACCESS_TOKEN:
            self.log_action("facebook_check", "FACEBOOK_ACCESS_TOKEN not configured — skipping", result="skipped")
            return []
        items = []
        try:
            items.extend(self._check_comments())
            items.extend(self._check_mentions())
            self.log_action("facebook_check", f"Facebook check complete: {len(items)} item(s) found")
        except Exception as exc:
            self.log_action("facebook_check", f"Error: {exc}", result="error")
        return items

    def create_action_file(self, item: dict) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        item_type = item.get("type", "unknown")

        if item_type == "comment":
            cid = item.get("comment_id", "X")
            filename = self.needs_action / f"FACEBOOK_COMMENT_{cid}_{ts}.md"
            content = f"""---
type: facebook_comment
comment_id: {cid}
post_id: {item.get('post_id', '')}
from: {item.get('from_name', 'Unknown')}
created: {datetime.now(timezone.utc).isoformat()}
priority: medium
---

# Facebook Comment from {item.get('from_name', 'Unknown')}

**On Post:** {item.get('post_message', '')[:100]}

**Comment:**
> {item.get('comment_message', '')}

**Posted:** {item.get('created_time', '')}

## Suggested Actions
- [ ] Reply to this comment (requires HITL approval)
- [ ] Like the comment if positive
- [ ] Report if spam/inappropriate

## Instructions
Decide on response and move to `/Done/` when handled.
"""

        else:  # mention
            mid = item.get("mention_id", "X")
            filename = self.needs_action / f"FACEBOOK_MENTION_{mid}_{ts}.md"
            content = f"""---
type: facebook_mention
mention_id: {mid}
from: {item.get('from_name', 'Unknown')}
created: {datetime.now(timezone.utc).isoformat()}
priority: medium
---

# Facebook Mention by {item.get('from_name', 'Unknown')}

**Message:**
> {item.get('message', '')}

**Posted:** {item.get('created_time', '')}
**Link:** {item.get('permalink_url', '')}

## Suggested Actions
- [ ] Engage with the mention (like/comment — requires HITL approval)
- [ ] Share if positive brand mention

## Instructions
Decide on response and move to `/Done/` when handled.
"""

        filename.write_text(content, encoding="utf-8")
        self.log_action("facebook_action_file", f"Created {filename.name}")
        return filename


def main():
    parser = argparse.ArgumentParser(description="Facebook Watcher — Gold Tier")
    parser.add_argument("--vault", default=os.getenv("VAULT_PATH", "AI_Employee_Vault"))
    parser.add_argument("--interval", type=int, default=int(os.getenv("SCHEDULE_FACEBOOK_INTERVAL", "600")))
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    watcher = FacebookWatcher(vault_path=args.vault, check_interval=args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
