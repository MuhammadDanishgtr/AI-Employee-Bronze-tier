"""Twitter Watcher — Gold Tier.

Polls Twitter/X API v2 (via Tweepy) every 600 seconds for:
  - New mentions of the authenticated account
  - New replies to account tweets

Creates action files in /Needs_Action:
  - TWITTER_MENTION_<id>_<timestamp>.md

Usage:
    py watchers/twitter_watcher.py
    py watchers/twitter_watcher.py --vault D:/path/to/vault

Environment variables:
    VAULT_PATH
    TWITTER_BEARER_TOKEN
    TWITTER_API_KEY / TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_TOKEN_SECRET
    SCHEDULE_TWITTER_INTERVAL   Poll interval in seconds (default: 600)
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher


TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")


class TwitterWatcher(BaseWatcher):
    """Polls Twitter/X for mentions and replies."""

    def __init__(self, vault_path: str, check_interval: int = 600):
        super().__init__(vault_path=vault_path, check_interval=check_interval)
        self._seen_mention_ids: set[str] = set()
        self._user_id: str | None = None
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            import tweepy
        except ImportError:
            raise RuntimeError("tweepy not installed — run: pip install tweepy")
        if not TWITTER_BEARER_TOKEN:
            raise RuntimeError("TWITTER_BEARER_TOKEN not configured")
        self._client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True,
        )
        return self._client

    def _get_user_id(self) -> str | None:
        if self._user_id:
            return self._user_id
        try:
            client = self._get_client()
            me = client.get_me()
            if me.data:
                self._user_id = str(me.data.id)
                return self._user_id
        except Exception as exc:
            self.logger.warning(f"Twitter get_me failed: {exc}")
        return None

    def _check_mentions(self) -> list[dict]:
        try:
            client = self._get_client()
            user_id = self._get_user_id()
            if not user_id:
                return []
            response = client.get_users_mentions(
                user_id,
                max_results=10,
                tweet_fields=["created_at", "author_id", "public_metrics", "text", "conversation_id"],
                expansions=["author_id"],
                user_fields=["name", "username"],
            )
            new_mentions = []
            users_by_id = {}
            if response.includes and response.includes.get("users"):
                for u in response.includes["users"]:
                    users_by_id[str(u.id)] = {"name": u.name, "username": u.username}

            if response.data:
                for tweet in response.data:
                    tid = str(tweet.id)
                    if tid not in self._seen_mention_ids:
                        self._seen_mention_ids.add(tid)
                        author = users_by_id.get(str(tweet.author_id), {"name": "Unknown", "username": "unknown"})
                        new_mentions.append({
                            "type": "mention",
                            "tweet_id": tid,
                            "text": tweet.text,
                            "author_name": author["name"],
                            "author_username": author["username"],
                            "author_id": str(tweet.author_id),
                            "created_at": str(tweet.created_at),
                            "metrics": tweet.public_metrics or {},
                        })
            return new_mentions
        except Exception as exc:
            self.logger.warning(f"Twitter mentions check failed: {exc}")
            return []

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        if not TWITTER_BEARER_TOKEN:
            self.log_action("twitter_check", "TWITTER_BEARER_TOKEN not configured — skipping", result="skipped")
            return []
        items = []
        try:
            items.extend(self._check_mentions())
            self.log_action("twitter_check", f"Twitter check complete: {len(items)} item(s) found")
        except Exception as exc:
            self.log_action("twitter_check", f"Error: {exc}", result="error")
        return items

    def create_action_file(self, item: dict) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        tweet_id = item.get("tweet_id", "X")
        author = item.get("author_username", "unknown")
        author_name = item.get("author_name", "Unknown")
        metrics = item.get("metrics", {})

        filename = self.needs_action / f"TWITTER_MENTION_{tweet_id}_{ts}.md"
        content = f"""---
type: twitter_mention
tweet_id: {tweet_id}
author: @{author}
author_name: {author_name}
created: {datetime.now(timezone.utc).isoformat()}
priority: medium
---

# Twitter Mention by @{author}

**Tweet:**
> {item.get('text', '')}

**Posted:** {item.get('created_at', '')}

## Engagement
| Metric | Value |
|--------|-------|
| Likes | {metrics.get('like_count', 0)} |
| Retweets | {metrics.get('retweet_count', 0)} |
| Replies | {metrics.get('reply_count', 0)} |
| Quotes | {metrics.get('quote_count', 0)} |

## Suggested Actions
- [ ] Reply to this mention (requires HITL approval via /twitter-api post_tweet)
- [ ] Retweet if appropriate
- [ ] Quote-tweet with comment

## Twitter Link
https://twitter.com/i/web/status/{tweet_id}

## Instructions
Decide on response and move to `/Done/` when handled.
"""
        filename.write_text(content, encoding="utf-8")
        self.log_action("twitter_action_file", f"Created {filename.name}")
        return filename


def main():
    parser = argparse.ArgumentParser(description="Twitter Watcher — Gold Tier")
    parser.add_argument("--vault", default=os.getenv("VAULT_PATH", "AI_Employee_Vault"))
    parser.add_argument("--interval", type=int, default=int(os.getenv("SCHEDULE_TWITTER_INTERVAL", "600")))
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    watcher = TwitterWatcher(vault_path=args.vault, check_interval=args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
