"""Odoo Watcher — Gold Tier.

Polls Odoo Community for accounting events every 3600 seconds:
  - Overdue invoices (past due date, unpaid)
  - New payments received (since last check)
  - Low balance alert (if assets drop below threshold)

Creates action files in /Needs_Action:
  - ODOO_INVOICE_<id>_<timestamp>.md  — overdue invoice details
  - ODOO_ALERT_<type>_<timestamp>.md  — balance / payment alerts

Usage:
    py watchers/odoo_watcher.py
    py watchers/odoo_watcher.py --vault D:/path/to/vault --interval 3600

Environment variables:
    VAULT_PATH      Obsidian vault path
    ODOO_URL        Odoo base URL (default: http://localhost:8069)
    ODOO_DB         Odoo database name
    ODOO_USERNAME   Odoo admin username
    ODOO_PASSWORD   Odoo admin password
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


ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "ai_employee_db")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")
LOW_BALANCE_THRESHOLD = float(os.getenv("ODOO_LOW_BALANCE_THRESHOLD", "1000"))


class OdooWatcher(BaseWatcher):
    """Polls Odoo Community accounting for alerts and overdue items."""

    def __init__(self, vault_path: str, check_interval: int = 3600):
        super().__init__(vault_path=vault_path, check_interval=check_interval)
        self._seen_invoice_ids: set[int] = set()
        self._last_payment_check: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── JSON-RPC helpers ──────────────────────────────────────────────────────

    def _call(self, service: str, method: str, args: list):
        payload = {"jsonrpc": "2.0", "method": "call", "id": 1,
                   "params": {"service": service, "method": method, "args": args}}
        try:
            resp = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            return None if "error" in result else result.get("result")
        except Exception as exc:
            self.logger.warning(f"Odoo RPC failed: {exc}")
            return None

    def _authenticate(self) -> int | None:
        uid = self._call("common", "authenticate", [ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {}])
        return uid if uid else None

    def _execute(self, model: str, method: str, domain: list, fields: list, limit: int = 50):
        uid = self._authenticate()
        if not uid:
            return []
        return self._call("object", "execute_kw",
                          [ODOO_DB, uid, ODOO_PASSWORD, model, method,
                           [domain], {"fields": fields, "limit": limit}]) or []

    # ── Checks ────────────────────────────────────────────────────────────────

    def _check_overdue_invoices(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        invoices = self._execute(
            "account.move", "search_read",
            [["state", "=", "posted"],
             ["invoice_date_due", "<", today],
             ["payment_state", "!=", "paid"],
             ["move_type", "in", ["out_invoice", "in_invoice"]]],
            ["id", "name", "partner_id", "amount_total", "invoice_date_due", "move_type"],
        )
        new_overdue = [inv for inv in invoices if inv["id"] not in self._seen_invoice_ids]
        self._seen_invoice_ids.update(inv["id"] for inv in invoices)
        return [{"type": "overdue_invoice", **inv} for inv in new_overdue]

    def _check_new_payments(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_payment_check == today:
            return []
        payments = self._execute(
            "account.payment", "search_read",
            [["date", "=", self._last_payment_check], ["state", "=", "posted"]],
            ["id", "name", "partner_id", "amount", "payment_type", "date"],
        )
        self._last_payment_check = today
        return [{"type": "new_payment", **p} for p in payments]

    def _check_balance_alert(self) -> list[dict]:
        uid = self._authenticate()
        if not uid:
            return []
        accounts = self._call("object", "execute_kw",
                              [ODOO_DB, uid, ODOO_PASSWORD,
                               "account.account", "search_read",
                               [[["account_type", "like", "asset_cash"]]],
                               {"fields": ["name", "code", "current_balance"], "limit": 10}]) or []
        total_cash = sum(acc.get("current_balance", 0) or 0 for acc in accounts)
        if total_cash < LOW_BALANCE_THRESHOLD:
            return [{"type": "low_balance", "total_cash": total_cash, "threshold": LOW_BALANCE_THRESHOLD}]
        return []

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        items = []
        try:
            items.extend(self._check_overdue_invoices())
            items.extend(self._check_new_payments())
            items.extend(self._check_balance_alert())
            self.log_action("odoo_check", f"Odoo check complete: {len(items)} item(s) found")
        except Exception as exc:
            self.log_action("odoo_check", f"Error: {exc}", result="error")
        return items

    def create_action_file(self, item: dict) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        item_type = item.get("type", "unknown")

        if item_type == "overdue_invoice":
            inv_id = item.get("id", "X")
            partner = item.get("partner_id", ["", "Unknown"])[1] if isinstance(item.get("partner_id"), list) else "Unknown"
            amount = item.get("amount_total", 0)
            due_date = item.get("invoice_date_due", "")
            inv_name = item.get("name", f"INV-{inv_id}")
            filename = self.needs_action / f"ODOO_INVOICE_{inv_id}_{ts}.md"
            content = f"""---
type: odoo_overdue_invoice
invoice_id: {inv_id}
invoice_name: {inv_name}
partner: {partner}
amount: {amount}
due_date: {due_date}
created: {datetime.now(timezone.utc).isoformat()}
---

# Overdue Invoice: {inv_name}

**Partner:** {partner}
**Amount Due:** ${amount:,.2f}
**Due Date:** {due_date}
**Invoice Type:** {item.get('move_type', 'N/A')}

## Suggested Actions
- [ ] Send payment reminder to {partner}
- [ ] Check if partial payment has been received
- [ ] Escalate if > 30 days overdue

## Instructions
Process this invoice and move file to `/Done/` when handled.
"""

        elif item_type == "new_payment":
            pay_id = item.get("id", "X")
            partner = item.get("partner_id", ["", "Unknown"])[1] if isinstance(item.get("partner_id"), list) else "Unknown"
            amount = item.get("amount", 0)
            pay_type = item.get("payment_type", "")
            date = item.get("date", "")
            filename = self.needs_action / f"ODOO_PAYMENT_{pay_id}_{ts}.md"
            content = f"""---
type: odoo_new_payment
payment_id: {pay_id}
partner: {partner}
amount: {amount}
payment_type: {pay_type}
date: {date}
created: {datetime.now(timezone.utc).isoformat()}
---

# New Payment Received: ${amount:,.2f}

**Partner:** {partner}
**Type:** {pay_type}
**Date:** {date}

## Instructions
Verify payment has been reconciled. Move to `/Done/` when confirmed.
"""

        else:  # low_balance or other alerts
            cash = item.get("total_cash", 0)
            threshold = item.get("threshold", LOW_BALANCE_THRESHOLD)
            filename = self.needs_action / f"ODOO_ALERT_{item_type.upper()}_{ts}.md"
            content = f"""---
type: odoo_alert
alert_type: {item_type}
current_cash: {cash}
threshold: {threshold}
created: {datetime.now(timezone.utc).isoformat()}
priority: high
---

# Odoo Alert: {item_type.replace('_', ' ').title()}

**Current Cash Balance:** ${cash:,.2f}
**Alert Threshold:** ${threshold:,.2f}

## Action Required
Cash balance is below the alert threshold. Review Odoo accounts immediately.

## Instructions
Take appropriate action and move to `/Done/` when resolved.
"""

        filename.write_text(content, encoding="utf-8")
        self.log_action("odoo_action_file", f"Created {filename.name}")
        return filename


def main():
    parser = argparse.ArgumentParser(description="Odoo Watcher — Gold Tier")
    parser.add_argument("--vault", default=os.getenv("VAULT_PATH", "AI_Employee_Vault"))
    parser.add_argument("--interval", type=int, default=int(os.getenv("SCHEDULE_ODOO_INTERVAL", "3600")))
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    watcher = OdooWatcher(vault_path=args.vault, check_interval=args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
