# AI Employee — Gold Tier

> Personal AI Employee built for **Panaversity Hackathon 0** — an autonomous agent that manages tasks, monitors Gmail, auto-posts to LinkedIn, integrates with Odoo accounting, monitors Facebook & Twitter, generates weekly CEO briefings, recovers from errors, and keeps humans in the loop for sensitive actions.

## Overview

This project implements a **Gold Tier** Personal AI Employee using **Claude Code** as the reasoning engine, an **Obsidian vault** as the knowledge base and dashboard, and multiple watchers coordinated by an APScheduler orchestrator running 8 concurrent jobs.

## Architecture

| Component | Technology | Role |
|-----------|-----------|------|
| Brain | Claude Code (claude-sonnet-4-6) | Reads tasks, makes decisions, writes reports |
| Memory / GUI | Obsidian Vault | Dashboard, logs, plans, approvals |
| Watcher 1 | Python `watchdog` | Monitors `Drop_Folder/` for new files |
| Watcher 2 | Gmail API + `google-auth` | Polls Gmail for unread important emails |
| Watcher 3 | Playwright (Chromium) | Auto-posts approved content to LinkedIn |
| Watcher 4 | Odoo JSON-RPC | Polls Odoo for overdue invoices & alerts |
| Watcher 5 | Facebook Graph API v19+ | Monitors page comments & mentions |
| Watcher 6 | Twitter API v2 (Tweepy) | Monitors mentions & replies |
| Orchestrator | APScheduler (8 jobs) | Coordinates all watchers on schedules |
| MCP Servers | `mcp` (6 servers) | Tools for Claude: Gmail, Odoo, Facebook, Twitter, Audit, Error Recovery |
| Rules | `Company_Handbook.md` | Defines permission boundaries |
| Accounting | Odoo 19 Community (Docker) | Invoice management, payments, balance |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system diagram.

## Folder Structure

```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard (auto-updated)
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # AI-generated action plans
├── Pending_Approval/       # Needs human approval (HITL)
├── Approved/               # Human-approved actions
├── Rejected/               # Human-rejected actions
├── Done/                   # Completed / archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
├── Audits/Weekly/          # CEO Briefings (auto Monday 08:00 UTC)
├── Error_Queue/            # Failed actions awaiting retry
├── Business_Domain/        # Cross-domain business items
└── Drop_Folder/            # Watched by File System Watcher
```

## Getting Started

### Prerequisites

- Python 3.13+
- Docker & Docker Compose (for Odoo)
- [Obsidian](https://obsidian.md/) (optional, for the GUI dashboard)
- Claude Code CLI

### Install dependencies

```bash
pip install watchdog google-auth google-auth-oauthlib google-api-python-client \
            apscheduler playwright python-dotenv mcp \
            tweepy tenacity requests requests-oauthlib
playwright install chromium
```

### Configure environment

```bash
cp .env.example .env
# Edit .env with your values (Gmail, LinkedIn, Facebook, Twitter, Odoo)
```

### Start Odoo (Docker)

```bash
docker-compose up -d db odoo
# Wait ~60s for Odoo to initialize, then open http://localhost:8069
# Create database 'ai_employee_db' with admin/admin credentials
```

### Start the Orchestrator (all watchers)

```bash
py watchers/orchestrator.py
```

The orchestrator starts all 8 scheduled jobs:
- **File System Watcher** — continuous, monitors `Drop_Folder/`
- **Gmail Watcher** — every 2 minutes
- **LinkedIn Poster** — every 15 minutes
- **Dashboard Update** — every 10 minutes
- **Odoo Watcher** — every 60 minutes (overdue invoices, balance alerts)
- **Facebook Watcher** — every 10 minutes (comments, mentions)
- **Twitter Watcher** — every 10 minutes (mentions, replies)
- **Error Recovery Scan** — every 30 minutes
- **CEO Briefing** — every Monday at 08:00 UTC

## Odoo Setup

1. Start Docker: `docker-compose up -d db odoo`
2. Open http://localhost:8069
3. Create database: `ai_employee_db` with master password from `odoo_config/odoo.conf`
4. Set credentials in `.env`:
   ```
   ODOO_URL=http://localhost:8069
   ODOO_DB=ai_employee_db
   ODOO_USERNAME=admin
   ODOO_PASSWORD=admin
   ```
5. Test: `/odoo-manager` → "check balance"

## Facebook Setup

1. Create a Facebook App at [developers.facebook.com](https://developers.facebook.com/)
2. Add "Pages API" permissions: `pages_manage_posts`, `pages_read_engagement`
3. Generate a long-lived page access token
4. Set in `.env`:
   ```
   FACEBOOK_PAGE_ID=your_page_id
   FACEBOOK_ACCESS_TOKEN=your_page_access_token
   ```

## Twitter / X Setup

1. Apply for Twitter API access at [developer.twitter.com](https://developer.twitter.com/)
2. Create a project and app with OAuth 1.0a (read/write)
3. Set in `.env`:
   ```
   TWITTER_API_KEY=...
   TWITTER_API_SECRET=...
   TWITTER_ACCESS_TOKEN=...
   TWITTER_ACCESS_TOKEN_SECRET=...
   TWITTER_BEARER_TOKEN=...
   ```

## Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API**
3. Create OAuth2 credentials (Desktop app type)
4. Download `credentials.json` → save as `credentials/gmail_credentials.json`
5. Run Gmail watcher once to authorize

## LinkedIn Setup

1. Set your LinkedIn credentials in `.env`
2. Run `/linkedin-poster` skill to create a draft post
3. Review and move the approval file to `/Approved/`

## MCP Servers

Six MCP servers are registered in `.mcp.json` and `~/.claude/settings.json`:

| Server | Tools |
|--------|-------|
| `gmail-send` | `send_email`, `draft_email`, `list_drafts` |
| `odoo-api` | `create_invoice`, `list_invoices`, `record_payment`, `get_balance`, `list_transactions` |
| `facebook-api` | `post_to_page`, `get_page_insights`, `list_recent_posts`, `get_comments` |
| `twitter-api` | `post_tweet`, `get_analytics`, `list_mentions`, `get_timeline` |
| `audit-generator` | `generate_ceo_briefing`, `get_weekly_summary`, `get_accounting_summary` |
| `error-recovery` | `queue_for_retry`, `list_error_queue`, `retry_failed_action`, `mark_unrecoverable` |

## Docker (Full Stack)

### Build and run everything

```bash
docker-compose up -d
```

This starts:
- `db` — PostgreSQL 15 for Odoo
- `odoo` — Odoo 17 Community on port 8069
- `ai-employee` — Gold Tier orchestrator with all watchers

### Build image only

```bash
docker build -t ai-employee-gold .
```

### View logs

```bash
docker logs -f ai-employee
docker logs -f odoo
```

## Available Claude Code Skills

| Skill | Description | Tier |
|-------|-------------|------|
| `/process-inbox` | Process pending items in `/Needs_Action` | Silver |
| `/update-dashboard` | Refresh `Dashboard.md` with current vault status | Silver |
| `/vault-manager` | Manage vault files, create plans, check approvals | Silver |
| `/gmail-checker` | Manually trigger Gmail check and process emails | Silver |
| `/linkedin-poster` | Draft a LinkedIn post and route through HITL approval | Silver |
| `/create-plan` | Create a structured Plan.md using the reasoning loop | Silver |
| `/odoo-manager` | Create invoices, record payments, check balance | **Gold** |
| `/social-summary` | Aggregate Facebook + Twitter metrics report | **Gold** |
| `/audit-weekly` | Trigger weekly CEO briefing generation | **Gold** |
| `/error-recovery` | Review and retry /Error_Queue items | **Gold** |
| `/ralph-loop-coordinator` | Autonomous multi-step task runner | **Gold** |

## HITL Workflow

```
AI drafts action
      ↓
Creates file in /Pending_Approval/
      ↓
Human reviews in Obsidian
      ↓
Move to /Approved  ──→  Orchestrator executes
Move to /Rejected  ──→  Archived to /Done
```

## Error Recovery Workflow

```
Action fails
      ↓
Queued to /Error_Queue/ (via error-recovery MCP)
      ↓
Orchestrator scans every 30 minutes
      ↓
/error-recovery skill → retry (max 3 attempts, exponential backoff)
      ↓
Success → /Done/    OR    Unrecoverable → /Done/ (with error note)
```

## Hackathon Tier

**Tier: Gold** — Panaversity Hackathon 0

| Requirement | Status |
|-------------|--------|
| Cross-domain integration (personal + business) | ✅ |
| Odoo Community accounting (Docker + JSON-RPC MCP) | ✅ |
| Facebook Graph API integration | ✅ |
| Twitter / X API v2 integration (Tweepy) | ✅ |
| Multiple MCP servers (6 total) | ✅ |
| Weekly CEO Briefing (APScheduler cron + audit-generator) | ✅ |
| Error recovery with tenacity retry + /Error_Queue/ | ✅ |
| Comprehensive audit logging (JSON lines + weekly rollup) | ✅ |
| Ralph Wiggum autonomous loop coordinator skill | ✅ |
| Architecture documentation (ARCHITECTURE.md) | ✅ |
| All functionality as Agent Skills (11 skills) | ✅ |
| Full Docker Compose stack | ✅ |

## Security

Credentials are **never** stored in the vault or committed to version control.

- All secrets loaded via **environment variables** from a `.env` file
- `.env` is in `.gitignore` — see `.env.example` for required variables
- `credentials/` directory is in `.gitignore` — mount as Docker volume
- All AI actions logged with timestamp, actor, and result in `Logs/YYYY-MM-DD.json`
- Sensitive actions require human approval before execution

## License

MIT
