# Skill: ralph-loop-coordinator

## Purpose
Autonomous multi-step task runner using the Ralph Wiggum reasoning loop.
Breaks complex goals into sequential sub-tasks, executes each step, checks outcomes,
and handles errors — all with minimal human interruption.

## Trigger
User says: "run autonomously", "ralph loop", "autonomous task", "run the loop",
"multi-step autonomous", "/ralph-loop-coordinator"

## What is the Ralph Loop?
The Ralph Wiggum loop is an autonomous reasoning pattern:
1. **Plan** — decompose the goal into ordered steps
2. **Execute** — run each step using available tools/MCP servers
3. **Observe** — check the result of each step
4. **Recover** — if a step fails, queue it to Error_Queue and continue or pause
5. **Report** — summarize what was accomplished and what needs human attention

## Steps

### 1. Receive the Goal
Ask the user for a clear goal statement if not provided.
Example: "Send a weekly business summary email, post to LinkedIn, and generate a CEO briefing"

### 2. Decompose into Sub-tasks
Create a structured plan in `/Plans/RALPH_<timestamp>.md`:
```markdown
# Ralph Loop Plan: [GOAL]
## Sub-tasks
1. [ ] Step 1: [description] — Tool: [MCP/skill]
2. [ ] Step 2: [description] — Tool: [MCP/skill]
3. [ ] Step 3: [description] — Tool: [MCP/skill]
```

### 3. Execute Each Sub-task
For each step:
- Run the appropriate tool/MCP call
- Mark step as [x] if successful, [!] if failed
- On failure: call `queue_for_retry` via `error-recovery` MCP, log the error
- Continue to next step unless blocked by failure

### 4. HITL Checkpoints
Pause and wait for human approval when:
- Any step creates a `/Pending_Approval/` file
- A payment action is triggered
- A public post (LinkedIn/Facebook/Twitter) is drafted
- More than 3 consecutive steps fail

### 5. Generate Loop Report
After all steps, write a report to `/Briefings/RALPH_REPORT_<timestamp>.md`:
```markdown
# Ralph Loop Report: [GOAL]
**Completed:** [N] / [Total] steps
**Errors:** [N]
**Pending Approval:** [list]
**Unrecoverable:** [list]
```

### 6. Update Dashboard
Call the `update-dashboard` skill to reflect new state.

## Example Use Cases

**Weekly business routine:**
1. Check Gmail for important emails → create action files
2. Generate CEO briefing → `/Audits/Weekly/`
3. Draft LinkedIn post from briefing highlights → `/Pending_Approval/`
4. Check Odoo for overdue invoices → create action files
5. Scan Error Queue and retry recoverable items

**Social media cycle:**
1. Get Facebook insights
2. Get Twitter mentions
3. Draft responses → `/Pending_Approval/`
4. Generate social summary report → `/Briefings/`

## Safety Rules
- Never skip HITL checkpoints for sensitive actions
- Never retry payment actions (from Company Handbook)
- Max autonomous depth: 10 steps without human check-in
- Log every step in `Logs/YYYY-MM-DD.json` with action_type="ralph_loop"

## Available Tools in the Loop
| Domain | MCP Server | Key Tools |
|--------|-----------|-----------|
| Email | gmail-send | send_email, draft_email |
| Accounting | odoo-api | create_invoice, get_balance |
| Facebook | facebook-api | get_page_insights, list_recent_posts |
| Twitter | twitter-api | list_mentions, get_timeline |
| Audit | audit-generator | generate_ceo_briefing |
| Recovery | error-recovery | queue_for_retry, retry_failed_action |
| Vault | Skills | process-inbox, update-dashboard, vault-manager |
