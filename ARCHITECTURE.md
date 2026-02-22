# AI Employee — Gold Tier Architecture

**Version:** 0.3.0 | **Tier:** Gold | **Hackathon:** Panaversity Hackathon 0

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI EMPLOYEE — GOLD TIER                       │
│                                                                       │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐   │
│  │  Claude Code │◄───│              MCP Servers (6)              │   │
│  │  (Brain /    │───►│  gmail-send │ odoo-api │ facebook-api    │   │
│  │   Reasoner)  │    │  twitter-api │ audit-generator │ error-  │   │
│  └──────┬───────┘    │  recovery                                │   │
│         │            └──────────────────────────────────────────┘   │
│         │                           │                                │
│  ┌──────▼──────────────────────────▼──────────────────────────────┐ │
│  │                    Obsidian Vault (Memory / GUI)                 │ │
│  │  Dashboard.md │ Company_Handbook.md │ Logs/ │ Plans/            │ │
│  │  Needs_Action/ │ Pending_Approval/ │ Approved/ │ Done/          │ │
│  │  Audits/Weekly/ │ Error_Queue/ │ Business_Domain/ │ Drop_Folder/ │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│         ▲                                                             │
│  ┌──────┴──────────────────────────────────────────────────────────┐ │
│  │              Orchestrator (APScheduler — 8 jobs)                 │ │
│  │                                                                   │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │ │
│  │  │File Watcher │  │Gmail Watcher│  │LinkedIn     │             │ │
│  │  │(continuous) │  │(every 2min) │  │(every 15min)│             │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │ │
│  │  │Odoo Watcher │  │Facebook     │  │Twitter      │  [GOLD]     │ │
│  │  │(every 60min)│  │(every 10min)│  │(every 10min)│             │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │ │
│  │  ┌─────────────┐  ┌─────────────────────────────┐              │ │
│  │  │Error        │  │CEO Briefing                  │  [GOLD]     │ │
│  │  │Recovery     │  │(cron Mon 08:00 UTC)          │             │ │
│  │  │(every 30min)│  └─────────────────────────────┘             │ │
│  │  └─────────────┘                                               │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                   External Services                               │ │
│  │  Gmail API │ LinkedIn (Playwright) │ Facebook Graph API v19+     │ │
│  │  Twitter API v2 (Tweepy) │ Odoo 19 (JSON-RPC via Docker)        │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### Brain: Claude Code
- Model: `claude-sonnet-4-6`
- Reads task files from `/Needs_Action/`, makes decisions, executes tools
- Accesses all 6 MCP servers for external integrations
- Implements 11 skills (6 Silver + 5 Gold)

### Orchestrator (`watchers/orchestrator.py`)
APScheduler `BackgroundScheduler` managing 8 concurrent jobs:

| Job ID | Trigger | Function |
|--------|---------|----------|
| `gmail_watcher` | interval 120s | Poll Gmail for important emails |
| `linkedin_poster` | interval 900s | Post approved LinkedIn content |
| `dashboard_update` | interval 600s | Refresh Dashboard.md |
| `odoo_watcher` | interval 3600s | Check Odoo for invoice alerts |
| `facebook_watcher` | interval 600s | Monitor Facebook page activity |
| `twitter_watcher` | interval 600s | Monitor Twitter/X mentions |
| `error_recovery` | interval 1800s | Scan and log Error_Queue |
| `ceo_briefing` | cron Mon 08:00 UTC | Generate weekly CEO briefing |

### Watchers

| Watcher | File | Tier | Extends |
|---------|------|------|---------|
| File System | `watchers/filesystem_watcher.py` | Bronze | `BaseWatcher` |
| Gmail | `watchers/gmail_watcher.py` | Silver | `BaseWatcher` |
| LinkedIn | `watchers/linkedin_watcher.py` | Silver | `BaseWatcher` |
| Odoo | `watchers/odoo_watcher.py` | **Gold** | `BaseWatcher` |
| Facebook | `watchers/facebook_watcher.py` | **Gold** | `BaseWatcher` |
| Twitter | `watchers/twitter_watcher.py` | **Gold** | `BaseWatcher` |

All watchers implement `check_for_updates()` → `create_action_file()` interface.

### MCP Servers

| Server | Path | Tools | External API |
|--------|------|-------|-------------|
| `gmail-send` | `mcp_servers/gmail_send/server.py` | `send_email`, `draft_email`, `list_drafts` | Gmail API |
| `odoo-api` | `mcp_servers/odoo_api/server.py` | `create_invoice`, `list_invoices`, `record_payment`, `get_balance`, `list_transactions` | Odoo JSON-RPC |
| `facebook-api` | `mcp_servers/facebook_api/server.py` | `post_to_page`, `get_page_insights`, `list_recent_posts`, `get_comments` | Facebook Graph API v19+ |
| `twitter-api` | `mcp_servers/twitter_api/server.py` | `post_tweet`, `get_analytics`, `list_mentions`, `get_timeline` | Twitter API v2 (Tweepy) |
| `audit-generator` | `mcp_servers/audit_generator/server.py` | `generate_ceo_briefing`, `get_weekly_summary`, `get_accounting_summary` | Odoo + vault logs |
| `error-recovery` | `mcp_servers/error_recovery/server.py` | `queue_for_retry`, `list_error_queue`, `retry_failed_action`, `mark_unrecoverable` | Vault filesystem |

### Skills (Claude Code Agent Skills)

| Skill | Trigger | Tier |
|-------|---------|------|
| `/process-inbox` | Process /Needs_Action items | Silver |
| `/update-dashboard` | Refresh Dashboard.md | Silver |
| `/vault-manager` | Manage vault files | Silver |
| `/gmail-checker` | Trigger Gmail check | Silver |
| `/linkedin-poster` | Draft LinkedIn post | Silver |
| `/create-plan` | Create structured Plan.md | Silver |
| `/odoo-manager` | Create invoices, record payments | **Gold** |
| `/social-summary` | Aggregate Facebook + Twitter metrics | **Gold** |
| `/audit-weekly` | Trigger CEO briefing generation | **Gold** |
| `/error-recovery` | Review and retry Error_Queue | **Gold** |
| `/ralph-loop-coordinator` | Autonomous multi-step task runner | **Gold** |

---

## Data Flow: Normal Action

```
External Event (email / Odoo alert / social mention)
        ↓
  Watcher detects it
        ↓
  create_action_file() → /Needs_Action/ACTION_TYPE_timestamp.md
        ↓
  Claude Code reads file (via /process-inbox skill or direct)
        ↓
  Decision:
    Safe action? → Execute immediately → /Done/
    Sensitive?   → /Pending_Approval/ → Human approves → /Approved/
                                      → Orchestrator executes → /Done/
    Error?       → /Error_Queue/ → /error-recovery → retry → /Done/
```

## Data Flow: HITL Approval

```
Claude drafts action (email, post, invoice, payment > $100)
        ↓
Creates file in /Pending_Approval/
        ↓
Human reviews in Obsidian
        ↓
Moves to /Approved/  ─→  Orchestrator or next Claude session executes
Moves to /Rejected/  ─→  Moved to /Done/ (audit trail)
```

---

## Docker Architecture

```
docker-compose.yml
├── db          (postgres:15-alpine)  — Odoo database
├── odoo        (odoo:17)             — Odoo Community, port 8069
└── ai-employee (ai-employee-gold)    — Orchestrator + all watchers
```

Volumes:
- `./AI_Employee_Vault` → `/app/AI_Employee_Vault` (shared with host)
- `./credentials` → `/app/credentials` (OAuth tokens, never in image)
- `odoo-db-data` → PostgreSQL data (persistent)
- `odoo-web-data` → Odoo file storage (persistent)

---

## Security Model

- **Credentials**: `.env` only — never in vault, never committed to git
- **Secrets**: `GMAIL_CLIENT_SECRET`, `FACEBOOK_ACCESS_TOKEN`, `TWITTER_API_KEY`, `ODOO_PASSWORD` — `.gitignore`d
- **HITL boundary**: All external write actions (posts, emails to new contacts, payments > $100) require human sign-off
- **Audit trail**: Every action logged to `Logs/YYYY-MM-DD.json` — immutable JSON lines
- **Error isolation**: Failed actions → `/Error_Queue/` → never silently discarded

---

## Environment Variables

| Variable | Component | Default |
|----------|-----------|---------|
| `VAULT_PATH` | All | `AI_Employee_Vault` |
| `GMAIL_CREDENTIALS_PATH` | Gmail | `./credentials/gmail_credentials.json` |
| `ODOO_URL` | Odoo | `http://localhost:8069` |
| `ODOO_DB` | Odoo | `ai_employee_db` |
| `FACEBOOK_PAGE_ID` | Facebook | *(required)* |
| `FACEBOOK_ACCESS_TOKEN` | Facebook | *(required)* |
| `TWITTER_BEARER_TOKEN` | Twitter | *(required)* |
| `SCHEDULE_ODOO_INTERVAL` | Orchestrator | `3600` |
| `SCHEDULE_FACEBOOK_INTERVAL` | Orchestrator | `600` |
| `SCHEDULE_TWITTER_INTERVAL` | Orchestrator | `600` |
| `SCHEDULE_ERROR_RECOVERY_INTERVAL` | Orchestrator | `1800` |
| `AUDIT_SCHEDULE_DAY` | Orchestrator | `mon` |
| `AUDIT_SCHEDULE_HOUR` | Orchestrator | `8` |

See `.env.example` for the complete list.

---

*AI Employee v0.3 — Gold Tier — Panaversity Hackathon 0*
