#!/bin/bash
# Quick demo: Analyze a single Sentry issue with Claude Code CLI
# This shows what your team saw in that LinkedIn video

set -e

ISSUE_ID="${1:-7088840785}"  # Default to a real issue from your Sentry

echo "🔍 Demo: Analyzing Sentry Issue $ISSUE_ID with Claude Code"
echo "=================================================="
echo ""

# Check if Claude Code is installed
if ! command -v claude &> /dev/null; then
    echo "❌ Claude Code CLI not found!"
    echo ""
    echo "Install it with:"
    echo "  npm install -g @anthropic/claude-code"
    echo "  claude auth login"
    exit 1
fi

# Create a demo prompt
PROMPT=$(cat <<'EOF'
# Sentry RCA Task

Analyze Sentry issue and create a fix.

## Step 1: Fetch Issue Details
Use the Sentry MCP tool to get full details:
- mcp__sentry__get_issue_details

## Step 2: Root Cause Analysis
1. Examine stack trace
2. Identify the buggy code
3. Determine root cause

## Step 3: Generate Fix
1. Read the affected file with GitHub MCP
2. Create a minimal fix
3. Write unit tests

## Step 4: Create PR
Use GitHub MCP to create a pull request with:
- Descriptive title
- Detailed description
- Fix code
- Tests

## Output Format
Return JSON:
{
  "issue_id": "...",
  "root_cause": "...",
  "confidence": 0.85,
  "fix_summary": "...",
  "pr_url": "https://github.com/...",
  "pr_number": 123
}

DO NOT apologize to users or send notifications - just analyze and fix.
EOF
)

echo "📝 Prompt prepared"
echo ""
echo "🚀 Launching Claude Code with Opus model..."
echo "   (This may take 1-2 minutes)"
echo ""

# Run Claude Code
# Note: Uncomment this when you're ready to test
# claude -p "$PROMPT" --model opus --output json > /tmp/claude_result.json

# For demo purposes, show what the command would be
echo "Command that will run:"
echo "=================="
echo "claude -p \"\$PROMPT\" --model opus --output json"
echo ""
echo "To actually run this:"
echo "1. Make sure you have SENTRY_ORG and SENTRY_AUTH_TOKEN set"
echo "2. Add Sentry MCP: claude mcp add --transport http sentry https://mcp.sentry.dev/mcp"
echo "3. Uncomment line 66 in this script"
echo "4. Run: ./demo-single-issue.sh $ISSUE_ID"
echo ""
echo "Expected output:"
echo "=================="
cat <<'JSON'
{
  "issue_id": "7088840785",
  "root_cause": "HTTPDriver for http://chi-production-cluster-main-0-1.clickhouse.svc:8123 received ClickHouse error code 81 - Database does not exist",
  "confidence": 0.92,
  "fix_summary": "Added database existence check before executing query. Falls back to default database if specified database not found.",
  "pr_url": "https://github.com/altimate-inc/altimate-backend/pull/456",
  "pr_number": 456,
  "files_changed": ["api/clickhouse/client.py"],
  "tests_added": ["tests/test_clickhouse_db_fallback.py"]
}
JSON

echo ""
echo "💡 This is essentially what you saw in the LinkedIn video!"
echo ""
echo "The key differences from your current system:"
echo "  ✅ Uses Claude Pro/Team subscription ($20-30/mo) instead of API ($300-500/mo)"
echo "  ✅ Access to Opus model (smarter than Sonnet)"
echo "  ✅ No backend to maintain"
echo "  ✅ Can be triggered from anywhere (Slack, cron, CI/CD)"
echo ""
echo "Next steps:"
echo "  1. Run this demo for real (uncomment line 66)"
echo "  2. Try the Slack bot (examples/slack-claude-bot.js)"
echo "  3. Set up cron for automated scanning (examples/sentry-autofix.sh)"
