# AI Employee — Bronze Tier

> Personal AI Employee built for **Panaversity Hackathon 0** — an autonomous agent that manages tasks, maintains an audit trail, and keeps humans in the loop for sensitive actions.

## Overview

This project implements a Bronze Tier Personal AI Employee using **Claude Code** as the reasoning engine and an **Obsidian vault** as the knowledge base, memory, and dashboard.

## Architecture

| Component | Technology | Role |
|-----------|-----------|------|
| Brain | Claude Code (claude-sonnet-4-6) | Reads tasks, makes decisions, writes reports |
| Memory / GUI | Obsidian Vault | Dashboard, logs, plans, approvals |
| Senses | Python `watchdog` | Monitors `Drop_Folder/` for new files |
| Rules | `Company_Handbook.md` | Defines permission boundaries |

## Folder Structure

```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # Action plans
├── Pending_Approval/       # Needs human approval
├── Approved/               # Approved actions
├── Rejected/               # Rejected actions
├── Done/                   # Completed / archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
└── Drop_Folder/            # Watched by File System Watcher
```

## Key Rules

1. **Read `Company_Handbook.md` before sensitive actions** — it defines what is auto-approved vs. what needs human sign-off.
2. **Never delete files** — always move to `/Done` for a full audit trail.
3. **Log everything** — JSON entries appended to `Logs/YYYY-MM-DD.json`.
4. **Human-in-the-loop** — payments, new contacts, and bulk operations go to `/Pending_Approval/` first.
5. **Update Dashboard** — `Dashboard.md` is refreshed after every processing run.

## Getting Started

### Prerequisites

- Python 3.13+
- [Obsidian](https://obsidian.md/) (optional, for the GUI dashboard)
- Claude Code CLI

### Install dependencies

```bash
pip install watchdog
```

### Start the File Watcher

```bash
py watchers/filesystem_watcher.py
```

The watcher monitors `AI_Employee_Vault/Drop_Folder/` and automatically creates action files in `/Needs_Action` when new files are dropped in.

### Available Claude Code Skills

| Skill | Description |
|-------|-------------|
| `/process-inbox` | Process pending items in `/Needs_Action` |
| `/update-dashboard` | Refresh `Dashboard.md` with current vault status |
| `/vault-manager` | Manage vault files, create plans, check approvals, archive items |

## License

MIT
