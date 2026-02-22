# Skill: social-summary

## Purpose
Aggregate and report on Facebook and Twitter/X social media metrics for the AI Employee.
Provides a unified view of page performance, engagement, and recent activity.

## Trigger
User says: "social media summary", "Facebook metrics", "Twitter analytics", "how's our social media doing",
"show me engagement stats", "social report"

## Steps

### 1. Gather Facebook Metrics
Use `facebook-api` MCP server:
- Call `get_page_insights(metric="page_impressions,page_engaged_users,page_fans", period="week")`
- Call `list_recent_posts(limit=5)` — get recent posts with engagement

### 2. Gather Twitter Metrics
Use `twitter-api` MCP server:
- Call `get_timeline(max_results=5)` — recent tweets
- Call `list_mentions(max_results=10)` — recent mentions

### 3. Check Pending Social Actions
Read `/Needs_Action/` for any FACEBOOK_* or TWITTER_* files that need attention.
Read `/Pending_Approval/` for any pending social media posts awaiting human approval.

### 4. Format the Report
Present a consolidated summary:

```markdown
## Social Media Summary — [DATE]

### Facebook
| Metric | Value |
|--------|-------|
| Page Impressions (7d) | ... |
| Engaged Users (7d) | ... |
| Total Fans | ... |

**Recent Posts:** [list with like/comment counts]

### Twitter/X
**Recent Tweets:** [list with engagement]
**New Mentions:** [count and preview]

### Action Items
- [N] Facebook items in Needs_Action
- [N] Twitter items in Needs_Action
- [N] Posts awaiting approval in Pending_Approval
```

### 5. Suggest Next Actions
- If mentions > 0: suggest using `/odoo-manager` or manually processing them
- If pending posts: remind user to review `/Pending_Approval/`
- If no API credentials: show which env vars are missing

## Error Handling
- If `FACEBOOK_ACCESS_TOKEN` not set: skip Facebook section, show notice
- If `TWITTER_BEARER_TOKEN` not set: skip Twitter section, show notice
- Partial results are still reported with a note about missing data

## Notes
- Facebook page insights require a Page access token (not user token)
- Twitter API v2 requires Bearer Token for read operations
- All API calls are logged to `Logs/YYYY-MM-DD.json`
