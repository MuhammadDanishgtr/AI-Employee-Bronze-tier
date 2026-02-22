# Skill: error-recovery

## Purpose
Review failed actions in `/Error_Queue/` and retry them with exponential backoff,
or mark them as permanently unrecoverable if all retries are exhausted.

## Trigger
User says: "check error queue", "retry failed actions", "error recovery", "what failed",
"fix errors", "/error-recovery"

## Steps

### 1. List Error Queue
Use `error-recovery` MCP server:
- Call `list_error_queue()` — returns all items with retry counts and status

If queue is empty: report "Error Queue is empty — all systems nominal" and exit.

### 2. Review Each Item
For each queued item:
- Show: action_type, description, retry_count, created date
- Determine if retryable:
  - `queued` with retry_count < 3 → **retryable**
  - `retrying` with retry_count < 3 → **retryable**
  - retry_count >= 3 → **unrecoverable** (max retries exceeded)

### 3. Retry Recoverable Items
For each retryable item:
- Call `retry_failed_action(filename=<filename>)` — moves to `/Needs_Action/`
- The `RETRY_*.md` file in Needs_Action will be picked up by `/process-inbox`

### 4. Mark Unrecoverable Items
For items that have exceeded max retries OR are clearly unrecoverable (auth errors, etc.):
- Call `mark_unrecoverable(filename=<filename>, reason=<reason>)`
- This moves the item to `/Done/` for audit trail

### 5. Report Summary
Present a summary:
```
## Error Recovery Report

| File | Action | Retries | Result |
|------|--------|---------|--------|
| ERROR_gmail_... | gmail_send | 1/3 | → Moved to Needs_Action |
| ERROR_odoo_...  | record_payment | 3/3 | → Marked Unrecoverable |
```

### 6. Suggest Follow-up
- If items were moved to Needs_Action: run `/process-inbox` to reprocess them
- If auth errors: check `.env` credentials for the relevant service
- If persistent failures: review `Logs/YYYY-MM-DD.json` for patterns

## Retry Logic
The `error-recovery` MCP server uses **tenacity** exponential backoff:
- Max attempts: 3
- Base wait: 2 seconds
- Max wait: 16 seconds
- Backoff multiplier: 2x

## Important Rules (from Company Handbook)
- **Payment actions are NEVER retried automatically** — human must confirm
- Authentication errors → stop immediately, log, alert human
- Logic errors → move to Needs_Action with error note (human review)

## Queuing Failed Actions
When other skills encounter errors, they can queue items:
```
Use error-recovery MCP: queue_for_retry(
    action_type="gmail_send",
    description="Failed to send reply to john@example.com",
    payload={"to": "john@example.com", "subject": "..."},
    original_error="Connection timeout"
)
```
