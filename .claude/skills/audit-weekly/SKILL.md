# Skill: audit-weekly

## Purpose
Trigger the weekly CEO briefing generation manually, or review existing briefings.
The briefing aggregates Odoo financials, social media metrics, and AI activity logs
into a single executive summary saved to `/Audits/Weekly/`.

## Trigger
User says: "generate CEO briefing", "weekly audit", "audit report", "generate briefing",
"show me this week's summary", "/audit-weekly"

## Steps

### 1. Check for Existing Briefing
- Look in `AI_Employee_Vault/Audits/Weekly/` for a recent briefing (within last 7 days)
- If found: read and display it, then ask if user wants a fresh one

### 2. Generate CEO Briefing
Use the `audit-generator` MCP server:
- Call `generate_ceo_briefing()` — this aggregates all data and writes the file

The briefing includes:
- **Period covered:** past 7 days
- **Total AI actions** from vault logs
- **Error count** and recent errors
- **Folder health** (Needs_Action, Pending_Approval, Error_Queue counts)
- **Odoo financial snapshot:** overdue invoices, outstanding receivables
- **Top 10 action types** by frequency

### 3. Display the Briefing
Read the generated file and present it to the user.

### 4. Identify Action Items
Based on the briefing, highlight:
- Any overdue invoices → suggest `/odoo-manager`
- Error queue items → suggest `/error-recovery`
- Pending approvals > 24h old → prompt user to review

### 5. Optional: Get Individual Summaries
- `get_weekly_summary()` — JSON activity data only
- `get_accounting_summary()` — Odoo financial data only

## Scheduling
The CEO Briefing is also auto-generated every Monday at 08:00 UTC by the orchestrator.
Manual trigger via this skill generates it immediately regardless of schedule.

## Output Location
`AI_Employee_Vault/Audits/Weekly/YYYY-MM-DD_CEO_Briefing.md`

This file is readable directly in Obsidian as a formatted report.

## Notes
- Odoo data is included only if ODOO_URL is reachable
- Log data comes from `AI_Employee_Vault/Logs/YYYY-MM-DD.json` files (past 7 days)
- All actions are logged as `ceo_briefing_generated` in the daily log
