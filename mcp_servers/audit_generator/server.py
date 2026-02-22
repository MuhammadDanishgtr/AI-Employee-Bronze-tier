"""Audit Generator MCP Server — Gold Tier.

Generates CEO briefings and weekly audit reports by aggregating:
  - Odoo financial data (balance, overdue invoices)
  - Social media metrics (Facebook, Twitter)
  - Email/task log counts from vault logs

Tools:
  - generate_ceo_briefing   Full weekly CEO briefing → /Audits/Weekly/
  - get_weekly_summary      JSON summary of weekly activity
  - get_accounting_summary  Financial snapshot from Odoo

Environment variables:
  VAULT_PATH     Path to Obsidian vault
  ODOO_URL / ODOO_DB / ODOO_USERNAME / ODOO_PASSWORD  (optional Odoo connection)
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("AuditGeneratorServer")

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "ai_employee_db")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")


# ── Log helpers ───────────────────────────────────────────────────────────────

def _log(action_type: str, details: str, result: str = "success"):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "AuditGeneratorServer",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _read_week_logs() -> list[dict]:
    """Read all log entries from the past 7 days."""
    entries = []
    today = datetime.now(timezone.utc).date()
    for i in range(7):
        day = today - timedelta(days=i)
        log_file = VAULT_PATH / "Logs" / f"{day.isoformat()}.json"
        if log_file.exists():
            for line in log_file.read_text(encoding="utf-8").strip().splitlines():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _count_folder(folder_name: str) -> int:
    folder = VAULT_PATH / folder_name
    if not folder.exists():
        return 0
    return sum(1 for f in folder.iterdir() if not f.name.startswith("."))


# ── Odoo connection ───────────────────────────────────────────────────────────

def _odoo_call(service: str, method: str, args: list) -> any:
    payload = {"jsonrpc": "2.0", "method": "call", "id": 1,
                "params": {"service": service, "method": method, "args": args}}
    try:
        resp = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            return None
        return result.get("result")
    except Exception:
        return None


def _get_odoo_summary() -> dict:
    """Fetch basic financial data from Odoo (graceful if unavailable)."""
    uid = _odoo_call("common", "authenticate", [ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {}])
    if not uid:
        return {"available": False, "reason": "Odoo authentication failed or server unreachable"}

    def execute(model, method, domain, fields):
        return _odoo_call("object", "execute_kw",
                          [ODOO_DB, uid, ODOO_PASSWORD, model, method, [domain], {"fields": fields, "limit": 100}]) or []

    overdue = execute("account.move", "search_read",
                      [["state", "=", "posted"], ["invoice_date_due", "<", datetime.now().strftime("%Y-%m-%d")],
                       ["payment_state", "!=", "paid"], ["move_type", "in", ["out_invoice", "in_invoice"]]],
                      ["name", "partner_id", "amount_total", "invoice_date_due"])

    receivable = execute("account.move", "search_read",
                         [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "!=", "paid"]],
                         ["name", "amount_total"])

    total_receivable = sum(inv.get("amount_total", 0) for inv in receivable)
    total_overdue = sum(inv.get("amount_total", 0) for inv in overdue)

    return {
        "available": True,
        "overdue_invoices": len(overdue),
        "total_overdue_amount": total_overdue,
        "outstanding_receivable": total_receivable,
        "overdue_details": overdue[:5],
    }


# ── Metric aggregation ────────────────────────────────────────────────────────

def get_weekly_summary() -> dict:
    """Aggregate weekly activity from vault logs."""
    entries = _read_week_logs()
    action_counts: dict[str, int] = {}
    errors = []
    for e in entries:
        atype = e.get("action_type", "unknown")
        action_counts[atype] = action_counts.get(atype, 0) + 1
        if e.get("result") == "error":
            errors.append(e)

    folder_counts = {
        folder: _count_folder(folder)
        for folder in ["Needs_Action", "Pending_Approval", "Approved", "Done", "Error_Queue", "Audits/Weekly"]
    }

    return {
        "period": f"{(datetime.now(timezone.utc).date() - timedelta(days=6)).isoformat()} to "
                  f"{datetime.now(timezone.utc).date().isoformat()}",
        "total_log_entries": len(entries),
        "action_breakdown": action_counts,
        "error_count": len(errors),
        "recent_errors": errors[-3:] if errors else [],
        "folder_counts": folder_counts,
    }


def get_accounting_summary() -> dict:
    """Get financial snapshot from Odoo."""
    summary = _get_odoo_summary()
    _log("accounting_summary", f"Odoo available: {summary.get('available', False)}")
    return summary


def generate_ceo_briefing() -> dict:
    """Generate a full weekly CEO briefing and save to /Audits/Weekly/."""
    now = datetime.now(timezone.utc)
    week_summary = get_weekly_summary()
    accounting = get_accounting_summary()

    # Folder counts
    fc = week_summary["folder_counts"]
    action_rows = "\n".join(
        f"| {action} | {count} |"
        for action, count in sorted(week_summary["action_breakdown"].items(), key=lambda x: -x[1])[:10]
    ) or "| — | 0 |"

    overdue_section = ""
    if accounting.get("available"):
        overdue_section = f"""
## Financial Snapshot (Odoo)
| Metric | Value |
|--------|-------|
| Overdue Invoices | {accounting['overdue_invoices']} |
| Total Overdue Amount | ${accounting['total_overdue_amount']:,.2f} |
| Outstanding Receivable | ${accounting['outstanding_receivable']:,.2f} |

{"### Overdue Invoice Details" if accounting['overdue_details'] else ""}
{"".join(f"- **{inv.get('name','')}** — {inv.get('partner_id',[''])[1] if isinstance(inv.get('partner_id'), list) else ''} — ${inv.get('amount_total',0):,.2f} (due {inv.get('invoice_date_due','')})" + chr(10) for inv in accounting['overdue_details'])}"""
    else:
        overdue_section = "\n## Financial Snapshot\n*Odoo unavailable — check ODOO_URL configuration.*\n"

    briefing = f"""---
title: Weekly CEO Briefing
date: {now.strftime('%Y-%m-%d')}
generated: {now.isoformat()}
tier: Gold
---

# Weekly CEO Briefing — {now.strftime('%B %d, %Y')}

**Period:** {week_summary['period']}
**Generated by:** AI Employee v0.3 Gold Tier

---

## Executive Summary
- **Total AI Actions This Week:** {week_summary['total_log_entries']}
- **Errors Encountered:** {week_summary['error_count']}
- **Items Pending Approval:** {fc.get('Pending_Approval', 0)}
- **Items in Error Queue:** {fc.get('Error_Queue', 0)}
- **Completed Items:** {fc.get('Done', 0)}

{overdue_section}

## Activity Breakdown (Top 10 Actions)
| Action Type | Count |
|-------------|-------|
{action_rows}

## Vault Health
| Folder | Items |
|--------|-------|
| Needs_Action | {fc.get('Needs_Action', 0)} |
| Pending_Approval | {fc.get('Pending_Approval', 0)} |
| Approved | {fc.get('Approved', 0)} |
| Done | {fc.get('Done', 0)} |
| Error_Queue | {fc.get('Error_Queue', 0)} |

## Errors (Last 3)
{"".join(f"- `{e.get('timestamp','')[:19]}` [{e.get('actor','')}] {e.get('details','')}\\n" for e in week_summary['recent_errors']) or "- None"}

---
*AI Employee Gold Tier — Auto-generated weekly briefing*
"""

    # Save to /Audits/Weekly/
    audit_dir = VAULT_PATH / "Audits" / "Weekly"
    audit_dir.mkdir(parents=True, exist_ok=True)
    briefing_file = audit_dir / f"{now.strftime('%Y-%m-%d')}_CEO_Briefing.md"
    briefing_file.write_text(briefing, encoding="utf-8")

    _log("ceo_briefing_generated", f"Briefing saved to {briefing_file.name}")
    return {
        "success": True,
        "file": str(briefing_file),
        "period": week_summary["period"],
        "total_actions": week_summary["total_log_entries"],
        "errors": week_summary["error_count"],
    }


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("audit-generator")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_ceo_briefing",
            description="Generate a full weekly CEO briefing (Odoo financials + social + activity) and save to /Audits/Weekly/.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_weekly_summary",
            description="Get a JSON summary of this week's AI Employee activity from vault logs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_accounting_summary",
            description="Get current financial snapshot from Odoo (overdue invoices, receivables).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = {}
    if name == "generate_ceo_briefing":
        result = generate_ceo_briefing()
    elif name == "get_weekly_summary":
        result = get_weekly_summary()
    elif name == "get_accounting_summary":
        result = get_accounting_summary()
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
