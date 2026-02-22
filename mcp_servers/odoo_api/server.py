"""Odoo API MCP Server — Gold Tier.

Provides accounting tools via Odoo JSON-RPC:
  - create_invoice      Create a customer/vendor invoice
  - list_invoices       List invoices with optional filters
  - record_payment      Record a payment against an invoice
  - get_balance         Get account balance summary
  - list_transactions   List recent accounting transactions

Payments > $100 are routed through HITL approval (/Pending_Approval/).

Environment variables:
  ODOO_URL       Base URL of Odoo instance (default: http://localhost:8069)
  ODOO_DB        Database name (default: ai_employee_db)
  ODOO_USERNAME  Admin username (default: admin)
  ODOO_PASSWORD  Admin password (default: admin)
  VAULT_PATH     Path to Obsidian vault
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
logger = logging.getLogger("OdooAPIServer")

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "ai_employee_db")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")
VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))

HITL_THRESHOLD = 100.0  # payments above this need approval


# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

def _call(service: str, method: str, args: list) -> dict:
    """Raw JSON-RPC call to Odoo."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {"service": service, "method": method, "args": args},
    }
    resp = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Odoo RPC error: {result['error']}")
    return result.get("result")


def _authenticate() -> int:
    """Authenticate and return user id (uid)."""
    uid = _call("common", "authenticate", [ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {}])
    if not uid:
        raise RuntimeError("Odoo authentication failed — check ODOO_USERNAME / ODOO_PASSWORD")
    return uid


def _execute(model: str, method: str, args: list, kwargs: dict | None = None) -> any:
    """Authenticated execute_kw call."""
    uid = _authenticate()
    return _call(
        "object",
        "execute_kw",
        [ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs or {}],
    )


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(action_type: str, details: str, result: str = "success"):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "OdooAPIServer",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _create_hitl(action_type: str, data: dict) -> Path:
    """Create a Human-in-the-Loop approval file."""
    folder = VAULT_PATH / "Pending_Approval"
    folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = folder / f"ODOO_{action_type.upper()}_{ts}.md"
    content = f"""---
type: odoo_approval
action: {action_type}
created: {datetime.now(timezone.utc).isoformat()}
status: pending
---

# Odoo Approval Required: {action_type}

**Amount exceeds auto-approve threshold (${HITL_THRESHOLD:.0f})**

## Action Details
```json
{json.dumps(data, indent=2)}
```

## Instructions
Move this file to `/Approved/` to confirm, or `/Rejected/` to cancel.
"""
    fname.write_text(content, encoding="utf-8")
    return fname


# ── Tool implementations ──────────────────────────────────────────────────────

def create_invoice(
    partner_name: str,
    amount: float,
    description: str,
    invoice_type: str = "out_invoice",
    currency: str = "USD",
) -> dict:
    """Create an invoice in Odoo."""
    try:
        # Look up or create partner
        partners = _execute("res.partner", "search_read",
                            [[["name", "ilike", partner_name]]],
                            {"fields": ["id", "name"], "limit": 1})
        if partners:
            partner_id = partners[0]["id"]
        else:
            partner_id = _execute("res.partner", "create", [{"name": partner_name}])

        invoice_vals = {
            "partner_id": partner_id,
            "move_type": invoice_type,
            "invoice_line_ids": [(0, 0, {
                "name": description,
                "quantity": 1,
                "price_unit": amount,
            })],
        }
        invoice_id = _execute("account.move", "create", [invoice_vals])
        _log("create_invoice", f"Invoice {invoice_id} for {partner_name} ${amount:.2f}")
        return {"success": True, "invoice_id": invoice_id, "partner": partner_name, "amount": amount}
    except Exception as exc:
        _log("create_invoice", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def list_invoices(state: str = "all", limit: int = 20) -> dict:
    """List invoices from Odoo."""
    try:
        domain = []
        if state != "all":
            domain = [["state", "=", state]]
        invoices = _execute(
            "account.move", "search_read",
            [domain],
            {"fields": ["name", "partner_id", "amount_total", "state", "invoice_date_due", "move_type"],
             "limit": limit, "order": "invoice_date_due asc"},
        )
        _log("list_invoices", f"Listed {len(invoices)} invoices (state={state})")
        return {"success": True, "count": len(invoices), "invoices": invoices}
    except Exception as exc:
        _log("list_invoices", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def record_payment(invoice_id: int, amount: float, memo: str = "") -> dict:
    """Record a payment against an invoice. Payments > $100 need HITL approval."""
    if amount > HITL_THRESHOLD:
        hitl_path = _create_hitl("payment", {
            "invoice_id": invoice_id,
            "amount": amount,
            "memo": memo,
        })
        _log("record_payment", f"Payment ${amount:.2f} routed to HITL: {hitl_path.name}", result="pending_approval")
        return {
            "success": True,
            "status": "pending_approval",
            "approval_file": str(hitl_path),
            "message": f"Payment of ${amount:.2f} exceeds ${HITL_THRESHOLD:.0f} threshold. Approval required.",
        }

    try:
        invoice = _execute("account.move", "read", [[invoice_id]], {"fields": ["name", "amount_residual"]})[0]
        _execute("account.move", "action_register_payment", [[invoice_id]])
        _log("record_payment", f"Payment ${amount:.2f} recorded for invoice {invoice['name']}")
        return {"success": True, "invoice": invoice["name"], "amount": amount}
    except Exception as exc:
        _log("record_payment", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def get_balance() -> dict:
    """Get a summary of account balances."""
    try:
        accounts = _execute(
            "account.account", "search_read",
            [[["deprecated", "=", False]]],
            {"fields": ["name", "code", "account_type", "current_balance"], "limit": 50},
        )
        summary = {"assets": 0.0, "liabilities": 0.0, "equity": 0.0, "income": 0.0, "expense": 0.0}
        for acc in accounts:
            balance = acc.get("current_balance", 0) or 0
            atype = acc.get("account_type", "")
            if "asset" in atype:
                summary["assets"] += balance
            elif "liability" in atype:
                summary["liabilities"] += balance
            elif "equity" in atype:
                summary["equity"] += balance
            elif "income" in atype:
                summary["income"] += balance
            elif "expense" in atype:
                summary["expense"] += balance

        _log("get_balance", f"Balance retrieved: assets=${summary['assets']:.2f}")
        return {"success": True, "summary": summary, "accounts": accounts[:10]}
    except Exception as exc:
        _log("get_balance", str(exc), result="error")
        return {"success": False, "error": str(exc)}


def list_transactions(limit: int = 30) -> dict:
    """List recent journal entries / transactions."""
    try:
        lines = _execute(
            "account.move.line", "search_read",
            [[["parent_state", "=", "posted"]]],
            {"fields": ["name", "account_id", "debit", "credit", "date", "move_id"],
             "limit": limit, "order": "date desc"},
        )
        _log("list_transactions", f"Listed {len(lines)} transaction lines")
        return {"success": True, "count": len(lines), "transactions": lines}
    except Exception as exc:
        _log("list_transactions", str(exc), result="error")
        return {"success": False, "error": str(exc)}


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("odoo-api")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_invoice",
            description="Create a customer or vendor invoice in Odoo accounting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "partner_name": {"type": "string", "description": "Customer or vendor name"},
                    "amount": {"type": "number", "description": "Invoice total amount"},
                    "description": {"type": "string", "description": "Line item description"},
                    "invoice_type": {"type": "string", "enum": ["out_invoice", "in_invoice"],
                                     "description": "out_invoice=customer, in_invoice=vendor"},
                    "currency": {"type": "string", "default": "USD"},
                },
                "required": ["partner_name", "amount", "description"],
            },
        ),
        Tool(
            name="list_invoices",
            description="List invoices from Odoo with optional state filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["all", "draft", "posted", "cancel"],
                              "default": "all"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="record_payment",
            description="Record a payment against an Odoo invoice. Payments > $100 require HITL approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "integer", "description": "Odoo invoice ID"},
                    "amount": {"type": "number", "description": "Payment amount"},
                    "memo": {"type": "string", "description": "Payment memo/reference"},
                },
                "required": ["invoice_id", "amount"],
            },
        ),
        Tool(
            name="get_balance",
            description="Get current account balance summary from Odoo (assets, liabilities, equity, income, expense).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_transactions",
            description="List recent accounting transactions/journal entries from Odoo.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 30}},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = {}
    if name == "create_invoice":
        result = create_invoice(**arguments)
    elif name == "list_invoices":
        result = list_invoices(**arguments)
    elif name == "record_payment":
        result = record_payment(**arguments)
    elif name == "get_balance":
        result = get_balance()
    elif name == "list_transactions":
        result = list_transactions(**arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
