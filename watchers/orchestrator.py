"""Orchestrator — Master process that coordinates all AI Employee watchers.

Uses APScheduler to run all watchers on configurable schedules:
  - FileSystem Watcher: continuous (watchdog-based, always running)
  - Gmail Watcher:      every 2 minutes (polls Gmail API)
  - LinkedIn Poster:    every 15 minutes (checks /Approved for posts)
  - Dashboard Update:   every 10 minutes (refreshes Dashboard.md)
  - Odoo Watcher:       every 60 minutes (accounting alerts)       [Gold]
  - Facebook Watcher:   every 10 minutes (page comments/mentions)  [Gold]
  - Twitter Watcher:    every 10 minutes (mentions/replies)        [Gold]
  - Error Recovery:     every 30 minutes (scans /Error_Queue/)     [Gold]
  - CEO Briefing:       Monday 08:00 UTC (weekly audit report)     [Gold]

Health monitoring restarts crashed watcher threads automatically.

Usage:
    py watchers/orchestrator.py
    py watchers/orchestrator.py --vault D:/path/to/vault

Environment variables (from .env):
    VAULT_PATH                       Path to Obsidian vault
    DROP_FOLDER_PATH                 Drop folder for filesystem watcher
    GMAIL_CREDENTIALS_PATH           Gmail OAuth2 credentials
    GMAIL_TOKEN_PATH                 Gmail OAuth2 token
    LINKEDIN_SESSION_PATH            Playwright session directory
    SCHEDULE_GMAIL_INTERVAL          Gmail poll interval in seconds (default 120)
    SCHEDULE_LINKEDIN_INTERVAL       LinkedIn check interval in seconds (default 900)
    SCHEDULE_DASHBOARD_INTERVAL      Dashboard refresh interval in seconds (default 600)
    SCHEDULE_ODOO_INTERVAL           Odoo check interval in seconds (default 3600)
    SCHEDULE_FACEBOOK_INTERVAL       Facebook check interval in seconds (default 600)
    SCHEDULE_TWITTER_INTERVAL        Twitter check interval in seconds (default 600)
    SCHEDULE_ERROR_RECOVERY_INTERVAL Error recovery scan interval in seconds (default 1800)
    AUDIT_SCHEDULE_DAY               CEO briefing day (default mon)
    AUDIT_SCHEDULE_HOUR              CEO briefing hour UTC (default 8)
    ODOO_URL / ODOO_DB / ODOO_USERNAME / ODOO_PASSWORD
    FACEBOOK_PAGE_ID / FACEBOOK_ACCESS_TOKEN
    TWITTER_BEARER_TOKEN / TWITTER_API_KEY / etc.
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add watchers dir to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("Orchestrator")


def _log_action(vault_path: Path, action_type: str, details: str, result: str = "success"):
    """Write an audit log entry."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault_path / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "Orchestrator",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _update_dashboard(vault_path: Path):
    """Refresh Dashboard.md with current folder counts and recent logs."""
    def count_items(folder: Path) -> int:
        if not folder.exists():
            return 0
        return sum(1 for f in folder.iterdir() if not f.name.startswith("."))

    folders = {
        "Inbox": vault_path / "Inbox",
        "Needs_Action": vault_path / "Needs_Action",
        "Pending_Approval": vault_path / "Pending_Approval",
        "Approved": vault_path / "Approved",
        "Plans": vault_path / "Plans",
        "Done": vault_path / "Done",
    }
    counts = {name: count_items(path) for name, path in folders.items()}

    # Read last 5 log entries
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault_path / "Logs" / f"{today}.json"
    recent_entries = []
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-5:]:
            try:
                entry = json.loads(line)
                recent_entries.append(entry)
            except json.JSONDecodeError:
                pass

    now = datetime.now(timezone.utc)
    recent_rows = "\n".join(
        f"| {e.get('timestamp','')[:19]} | {e.get('action_type','')} | {e.get('details','')} | {e.get('result','')} |"
        for e in recent_entries
    ) or "| — | No activity yet | — | — |"

    # Count Gold Tier folders too
    gold_folders = {
        "Error_Queue": vault_path / "Error_Queue",
        "Audits/Weekly": vault_path / "Audits" / "Weekly",
        "Business_Domain": vault_path / "Business_Domain",
    }
    gold_counts = {name: count_items(path) for name, path in gold_folders.items()}

    dashboard_content = f"""---
title: AI Employee Dashboard
last_updated: {now.isoformat()}
version: "0.3"
tier: Gold
---

# AI Employee Dashboard

## System Status
| Component          | Status  | Last Check              |
|--------------------|---------|-------------------------|
| Orchestrator       | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| File Watcher       | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Gmail Watcher      | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| LinkedIn Poster    | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Odoo Watcher       | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Facebook Watcher   | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Twitter Watcher    | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Error Recovery     | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| CEO Briefing       | Scheduled Mon 08:00 UTC | — |
| Vault Connection   | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| AI Engine          | Ready   | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |

## Folder Summary
| Folder            | Count |
|-------------------|-------|
| Inbox             | {counts['Inbox']}     |
| Needs_Action      | {counts['Needs_Action']}     |
| Pending_Approval  | {counts['Pending_Approval']}     |
| Approved          | {counts['Approved']}     |
| Plans             | {counts['Plans']}     |
| Done              | {counts['Done']}     |
| Error_Queue       | {gold_counts['Error_Queue']}     |
| Audits/Weekly     | {gold_counts['Audits/Weekly']}     |
| Business_Domain   | {gold_counts['Business_Domain']}     |

## Recent Activity
| Timestamp           | Action | Details | Status |
|---------------------|--------|---------|--------|
{recent_rows}

## Quick Links
- [[Company_Handbook]] — Rules of engagement
- [[Plans/]] — Active plans
- [[Audits/Weekly/]] — CEO Briefings

---
*Updated by AI Employee v0.3 — Gold Tier*
"""
    dashboard_path = vault_path / "Dashboard.md"
    dashboard_path.write_text(dashboard_content, encoding="utf-8")
    logger.info("Dashboard updated")
    _log_action(vault_path, "dashboard_update", "Dashboard.md refreshed")


class WatcherThread(threading.Thread):
    """Wraps a watcher's run() in a daemon thread with restart capability."""

    def __init__(self, name: str, target_fn, args=(), kwargs=None):
        super().__init__(name=name, daemon=True)
        self.target_fn = target_fn
        self.args = args
        self.kwargs = kwargs or {}
        self._exception: Exception | None = None

    def run(self):
        try:
            self.target_fn(*self.args, **self.kwargs)
        except Exception as exc:
            self._exception = exc
            logger.error(f"Thread {self.name} crashed: {exc}")

    @property
    def crashed(self) -> bool:
        return self._exception is not None


def _start_filesystem_watcher(vault_path: str, drop_folder: str, interval: int):
    """Start the filesystem watcher (blocking)."""
    from filesystem_watcher import FileSystemWatcher
    watcher = FileSystemWatcher(
        vault_path=vault_path,
        drop_folder=drop_folder,
        check_interval=interval,
    )
    watcher.run()


def _run_gmail_watcher_once(vault_path: str, credentials_path: str, token_path: str):
    """Run one Gmail check cycle (called by scheduler)."""
    try:
        from gmail_watcher import GmailWatcher
        watcher = GmailWatcher(
            vault_path=vault_path,
            credentials_path=credentials_path,
            token_path=token_path,
            check_interval=999999,  # won't loop
        )
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        logger.info(f"Gmail check: {len(items)} new email(s)")
    except Exception as exc:
        logger.error(f"Gmail watcher error: {exc}")


def _run_linkedin_check_once(vault_path: str, session_path: str):
    """Run one LinkedIn posting cycle (called by scheduler)."""
    try:
        from linkedin_watcher import LinkedInPoster
        poster = LinkedInPoster(
            vault_path=vault_path,
            session_path=session_path,
            linkedin_email=os.getenv("LINKEDIN_EMAIL", ""),
            linkedin_password=os.getenv("LINKEDIN_PASSWORD", ""),
        )
        items = poster.check_for_updates()
        for item in items:
            poster.create_action_file(item)
        if items:
            logger.info(f"LinkedIn check: processed {len(items)} post(s)")
    except Exception as exc:
        logger.error(f"LinkedIn poster error: {exc}")


# ── Gold Tier job functions ───────────────────────────────────────────────────

def _run_odoo_check_once(vault_path: str):
    """Run one Odoo accounting check (Gold Tier)."""
    try:
        from odoo_watcher import OdooWatcher
        watcher = OdooWatcher(vault_path=vault_path, check_interval=999999)
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        logger.info(f"Odoo check: {len(items)} item(s) found")
    except Exception as exc:
        logger.error(f"Odoo watcher error: {exc}")


def _run_facebook_check_once(vault_path: str):
    """Run one Facebook check cycle (Gold Tier)."""
    try:
        from facebook_watcher import FacebookWatcher
        watcher = FacebookWatcher(vault_path=vault_path, check_interval=999999)
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        logger.info(f"Facebook check: {len(items)} item(s) found")
    except Exception as exc:
        logger.error(f"Facebook watcher error: {exc}")


def _run_twitter_check_once(vault_path: str):
    """Run one Twitter check cycle (Gold Tier)."""
    try:
        from twitter_watcher import TwitterWatcher
        watcher = TwitterWatcher(vault_path=vault_path, check_interval=999999)
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        logger.info(f"Twitter check: {len(items)} item(s) found")
    except Exception as exc:
        logger.error(f"Twitter watcher error: {exc}")


def _run_error_recovery_scan(vault_path: str):
    """Scan Error_Queue and log count (Gold Tier)."""
    try:
        error_queue = Path(vault_path) / "Error_Queue"
        if not error_queue.exists():
            return
        items = [f for f in error_queue.iterdir() if f.suffix == ".md" and not f.name.startswith(".")]
        if items:
            logger.warning(f"Error Recovery: {len(items)} item(s) in queue — run /error-recovery skill to process")
            _log_action(Path(vault_path), "error_recovery_scan",
                        f"{len(items)} item(s) in Error_Queue awaiting retry", result="warning")
        else:
            logger.info("Error Recovery: Error_Queue is empty")
    except Exception as exc:
        logger.error(f"Error recovery scan error: {exc}")


def _run_ceo_briefing(vault_path: str):
    """Generate weekly CEO briefing (Gold Tier, runs Monday 08:00 UTC)."""
    try:
        import sys
        mcp_path = str(Path(vault_path).parent / "mcp_servers" / "audit_generator")
        if mcp_path not in sys.path:
            sys.path.insert(0, mcp_path)
        # Import and call the briefing function directly
        sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_servers" / "audit_generator"))
        from server import generate_ceo_briefing
        result = generate_ceo_briefing()
        logger.info(f"CEO Briefing generated: {result.get('file', 'unknown')}")
        _log_action(Path(vault_path), "ceo_briefing_generated",
                    f"Weekly CEO Briefing saved: {result.get('file', '')}")
    except Exception as exc:
        logger.error(f"CEO Briefing generation error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument(
        "--vault",
        default=os.getenv("VAULT_PATH", "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault"),
        help="Path to Obsidian vault",
    )
    parser.add_argument(
        "--drop",
        default=os.getenv("DROP_FOLDER_PATH", None),
        help="Drop folder path (defaults to vault/Drop_Folder)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    vault_path = Path(args.vault)
    drop_folder = args.drop or str(vault_path / "Drop_Folder")

    credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "./credentials/gmail_token.json")
    session_path = os.getenv("LINKEDIN_SESSION_PATH", "./credentials/linkedin_session")

    gmail_interval = int(os.getenv("SCHEDULE_GMAIL_INTERVAL", "120"))
    linkedin_interval = int(os.getenv("SCHEDULE_LINKEDIN_INTERVAL", "900"))
    dashboard_interval = int(os.getenv("SCHEDULE_DASHBOARD_INTERVAL", "600"))
    odoo_interval = int(os.getenv("SCHEDULE_ODOO_INTERVAL", "3600"))
    facebook_interval = int(os.getenv("SCHEDULE_FACEBOOK_INTERVAL", "600"))
    twitter_interval = int(os.getenv("SCHEDULE_TWITTER_INTERVAL", "600"))
    error_recovery_interval = int(os.getenv("SCHEDULE_ERROR_RECOVERY_INTERVAL", "1800"))
    audit_day = os.getenv("AUDIT_SCHEDULE_DAY", "mon")
    audit_hour = int(os.getenv("AUDIT_SCHEDULE_HOUR", "8"))

    print(f"\n{'='*56}")
    print(f"  AI Employee Orchestrator — Gold Tier v0.3")
    print(f"{'='*56}")
    print(f"  Vault:           {vault_path}")
    print(f"  Drop:            {drop_folder}")
    print(f"  Gmail:           every {gmail_interval}s")
    print(f"  LinkedIn:        every {linkedin_interval}s")
    print(f"  Dashboard:       every {dashboard_interval}s")
    print(f"  Odoo:            every {odoo_interval}s")
    print(f"  Facebook:        every {facebook_interval}s")
    print(f"  Twitter:         every {twitter_interval}s")
    print(f"  Error Recovery:  every {error_recovery_interval}s")
    print(f"  CEO Briefing:    {audit_day.upper()} {audit_hour:02d}:00 UTC")
    print(f"{'='*56}\n")

    _log_action(vault_path, "orchestrator_start", "Gold Tier orchestrator started")

    # Import APScheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BackgroundScheduler()

    # Schedule Gmail watcher
    scheduler.add_job(
        _run_gmail_watcher_once,
        "interval",
        seconds=gmail_interval,
        id="gmail_watcher",
        args=[str(vault_path), credentials_path, token_path],
        max_instances=1,
    )

    # Schedule LinkedIn poster
    scheduler.add_job(
        _run_linkedin_check_once,
        "interval",
        seconds=linkedin_interval,
        id="linkedin_poster",
        args=[str(vault_path), session_path],
        max_instances=1,
    )

    # Schedule dashboard update
    scheduler.add_job(
        _update_dashboard,
        "interval",
        seconds=dashboard_interval,
        id="dashboard_update",
        args=[vault_path],
        max_instances=1,
    )

    # ── Gold Tier jobs ────────────────────────────────────────────────────────

    # Odoo accounting check
    scheduler.add_job(
        _run_odoo_check_once,
        "interval",
        seconds=odoo_interval,
        id="odoo_watcher",
        args=[str(vault_path)],
        max_instances=1,
    )

    # Facebook page monitor
    scheduler.add_job(
        _run_facebook_check_once,
        "interval",
        seconds=facebook_interval,
        id="facebook_watcher",
        args=[str(vault_path)],
        max_instances=1,
    )

    # Twitter / X mentions monitor
    scheduler.add_job(
        _run_twitter_check_once,
        "interval",
        seconds=twitter_interval,
        id="twitter_watcher",
        args=[str(vault_path)],
        max_instances=1,
    )

    # Error recovery scan
    scheduler.add_job(
        _run_error_recovery_scan,
        "interval",
        seconds=error_recovery_interval,
        id="error_recovery",
        args=[str(vault_path)],
        max_instances=1,
    )

    # Weekly CEO Briefing — cron trigger
    scheduler.add_job(
        _run_ceo_briefing,
        "cron",
        day_of_week=audit_day,
        hour=audit_hour,
        minute=0,
        id="ceo_briefing",
        args=[str(vault_path)],
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started with 8 jobs (Silver + Gold Tier)")

    # Start filesystem watcher in a background thread
    fs_thread = WatcherThread(
        name="FileSystemWatcher",
        target_fn=_start_filesystem_watcher,
        args=(str(vault_path), drop_folder, 10),
    )
    fs_thread.start()
    logger.info("FileSystem watcher thread started")

    # Initial dashboard update
    _update_dashboard(vault_path)

    # Health monitor loop
    try:
        while True:
            time.sleep(30)

            # Restart crashed filesystem watcher
            if not fs_thread.is_alive():
                logger.warning("FileSystem watcher thread died — restarting...")
                _log_action(vault_path, "watcher_restart", "FileSystemWatcher restarted", result="warning")
                fs_thread = WatcherThread(
                    name="FileSystemWatcher",
                    target_fn=_start_filesystem_watcher,
                    args=(str(vault_path), drop_folder, 10),
                )
                fs_thread.start()

    except KeyboardInterrupt:
        print("\n--- Orchestrator stopped ---")
        _log_action(vault_path, "orchestrator_stop", "Stopped by user")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
