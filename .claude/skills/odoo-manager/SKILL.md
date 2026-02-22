# Skill: odoo-manager

## Purpose
Manage Odoo accounting — create invoices, record payments, and check financial balances.
Routes sensitive payments (> $100) through HITL approval automatically.

## Trigger
User says: "create invoice", "record payment", "check Odoo balance", "list invoices", "Odoo accounting"

## Steps

### 1. Understand the Request
Determine which accounting action is needed:
- **Create Invoice** → `create_invoice` tool
- **Record Payment** → `record_payment` tool (HITL if > $100)
- **Check Balance** → `get_balance` tool
- **List Invoices** → `list_invoices` tool (optionally filter by state)
- **Transactions** → `list_transactions` tool

### 2. Gather Required Information
Ask user for any missing details:
- For invoices: partner name, amount, description, type (customer/vendor)
- For payments: invoice ID, amount, optional memo

### 3. Execute via MCP Tool
Use the `odoo-api` MCP server tools. All tools return JSON results.
- If payment > $100: explain that an approval file has been created in `/Pending_Approval/`
- On Odoo connection error: check ODOO_URL, ensure Docker is running (`docker-compose up`)

### 4. Report Results
Summarize what was done:
- Invoice created: show invoice ID and amount
- Payment: show status (success or pending_approval)
- Balance: show asset/liability/equity summary table
- On error: suggest checking Odoo Docker status

### 5. Log the Action
The MCP server automatically logs all actions to `Logs/YYYY-MM-DD.json`.

## Example Interactions

**User:** "Create an invoice for Acme Corp for $500 for consulting services"
→ Call `create_invoice(partner_name="Acme Corp", amount=500, description="Consulting services")`

**User:** "What's our current balance?"
→ Call `get_balance()` → format result as markdown table

**User:** "Record payment of $150 for invoice 42"
→ Call `record_payment(invoice_id=42, amount=150)` → routes to HITL (> $100 threshold)

## Error Recovery
If Odoo is unreachable:
1. Check `docker-compose ps` — ensure odoo container is healthy
2. Verify ODOO_URL in `.env` matches the Docker service
3. Queue the action in `/Error_Queue/` using the `error-recovery` MCP server

## Notes
- Payments ≤ $100 are auto-approved; > $100 require human sign-off
- Recurring payments < $50 are auto-approved per Company Handbook
- All Odoo actions appear in `AI_Employee_Vault/Logs/YYYY-MM-DD.json`
