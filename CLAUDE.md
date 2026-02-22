# AI Employee — Project Instructions

## Overview
This is a Personal AI Employee (Gold Tier) built for the Panaversity Hackathon 0. It uses Claude Code as the reasoning engine and an Obsidian vault as the knowledge base and dashboard.

## Vault Location
The Obsidian vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Architecture
- **Brain:** Claude Code (this agent) — reads tasks, makes decisions, writes reports
- **Memory/GUI:** Obsidian vault with Dashboard.md as the main status view
- **Watcher 1:** File System Watcher (Python/watchdog) monitors `Drop_Folder/` for new files
- **Watcher 2:** Gmail Watcher polls Gmail for unread important emails every 2 minutes
- **Watcher 3:** LinkedIn Poster publishes approved posts via Playwright every 15 minutes
- **Watcher 4:** Odoo Watcher polls Odoo accounting for alerts every 60 minutes [Gold]
- **Watcher 5:** Facebook Watcher monitors page comments/mentions every 10 minutes [Gold]
- **Watcher 6:** Twitter Watcher monitors mentions/replies every 10 minutes [Gold]
- **Orchestrator:** APScheduler coordinates all watchers (8 scheduled jobs)
- **MCP Server 1:** `mcp_servers/gmail_send/server.py` — send_email, draft_email, list_drafts
- **MCP Server 2:** `mcp_servers/odoo_api/server.py` — create_invoice, list_invoices, record_payment, get_balance, list_transactions [Gold]
- **MCP Server 3:** `mcp_servers/facebook_api/server.py` — post_to_page, get_page_insights, list_recent_posts, get_comments [Gold]
- **MCP Server 4:** `mcp_servers/twitter_api/server.py` — post_tweet, get_analytics, list_mentions, get_timeline [Gold]
- **MCP Server 5:** `mcp_servers/audit_generator/server.py` — generate_ceo_briefing, get_weekly_summary, get_accounting_summary [Gold]
- **MCP Server 6:** `mcp_servers/error_recovery/server.py` — queue_for_retry, list_error_queue, retry_failed_action, mark_unrecoverable [Gold]
- **Rules:** `Company_Handbook.md` defines all permission boundaries and behavior rules
- **Docs:** `ARCHITECTURE.md` — full Gold Tier system diagram

## Key Rules
1. **Always read `Company_Handbook.md` before taking sensitive actions** — it defines what's auto-approved vs. what needs human approval.
2. **Never delete files** — always move them to `/Done` for audit trail.
3. **Log everything** — append JSON entries to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`.
4. **Human-in-the-loop** — for sensitive actions (payments, new contacts, emails, LinkedIn/Facebook/Twitter posts, bulk operations), create approval files in `/Pending_Approval/` instead of acting directly.
5. **Update Dashboard** — after processing items, refresh `Dashboard.md` with current counts and status.
6. **Error recovery** — failed actions go to `/Error_Queue/`, use `/error-recovery` skill to retry with tenacity backoff.

## Available Skills
- `/process-inbox` — Process pending items in `/Needs_Action`
- `/update-dashboard` — Refresh Dashboard.md with current vault status
- `/vault-manager` — Manage vault files, create plans, check approvals, archive items
- `/gmail-checker` — Manually trigger Gmail check and process email action files
- `/linkedin-poster` — Draft a LinkedIn post and route through HITL approval
- `/create-plan` — Create a structured Plan.md using the reasoning loop
- `/odoo-manager` — Create invoices, record payments, check Odoo balance [Gold]
- `/social-summary` — Aggregate Facebook + Twitter metrics report [Gold]
- `/audit-weekly` — Trigger weekly CEO briefing generation [Gold]
- `/error-recovery` — Review and retry /Error_Queue items [Gold]
- `/ralph-loop-coordinator` — Autonomous multi-step task runner [Gold]

## Folder Structure
```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard (auto-updated every 10 min)
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # Action plans (Plan.md reasoning loop)
├── Pending_Approval/       # Needs human approval (HITL)
├── Approved/               # Approved actions (orchestrator executes)
├── Rejected/               # Rejected actions
├── Done/                   # Completed/archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
├── Audits/Weekly/          # CEO Briefings (auto Monday 08:00 UTC) [Gold]
├── Error_Queue/            # Failed actions awaiting retry [Gold]
├── Business_Domain/        # Cross-domain business items [Gold]
└── Drop_Folder/            # Watched by File System Watcher
```

## Starting the Orchestrator
Start all watchers with the orchestrator:
```bash
py watchers/orchestrator.py
```
Or start individual watchers:
```bash
py watchers/filesystem_watcher.py   # File system only
py watchers/gmail_watcher.py        # Gmail only
py watchers/linkedin_watcher.py     # LinkedIn poster only
py watchers/odoo_watcher.py         # Odoo only [Gold]
py watchers/facebook_watcher.py     # Facebook only [Gold]
py watchers/twitter_watcher.py      # Twitter only [Gold]
```

## MCP Servers
All 6 MCP servers are registered in `.mcp.json` and `~/.claude/settings.json`.
Start individually with `py mcp_servers/<name>/server.py`

## Docker (Full Stack)
```bash
docker-compose up -d          # Start Odoo + AI Employee
docker-compose up -d db odoo  # Start Odoo only (port 8069)
docker build -t ai-employee-gold .
```

## Python
Use `py` command (not `python`) to run Python scripts on this system.
