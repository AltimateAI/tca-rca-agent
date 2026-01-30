#!/bin/bash
# Automated Sentry Issue Fixer using Claude Code CLI
# Uses your Claude Pro/Team subscription instead of API

set -e

# Configuration
SENTRY_ORG="${SENTRY_ORG:-altimate-inc}"
SENTRY_AUTH_TOKEN="${SENTRY_AUTH_TOKEN}"
GITHUB_REPO="${GITHUB_REPO:-altimate-inc/altimate-backend}"
SLACK_WEBHOOK="${SLACK_WEBHOOK}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Fetch unresolved Sentry issues
fetch_sentry_issues() {
    log "Fetching unresolved Sentry issues..."

    curl -s "https://sentry.io/api/0/organizations/${SENTRY_ORG}/issues/" \
        -H "Authorization: Bearer ${SENTRY_AUTH_TOKEN}" \
        -G \
        --data-urlencode "query=is:unresolved" \
        --data-urlencode "sort=freq" \
        --data-urlencode "limit=10" \
        > /tmp/sentry_issues.json

    # Count issues
    issue_count=$(jq '. | length' /tmp/sentry_issues.json)
    log "Found ${issue_count} unresolved issues"
}

# Process each issue with Claude Code
process_issue() {
    local issue_id=$1
    local issue_title=$2
    local issue_count=$3

    log "Processing issue: ${issue_id} - ${issue_title} (${issue_count} occurrences)"

    # Create a context file for Claude Code
    cat > /tmp/claude_context_${issue_id}.md <<EOF
# Sentry Issue Analysis Task

## Issue Details
- **ID**: ${issue_id}
- **Title**: ${issue_title}
- **Occurrences**: ${issue_count}
- **Sentry URL**: https://sentry.io/organizations/${SENTRY_ORG}/issues/${issue_id}/

## Your Task
1. Use the Sentry MCP tool to fetch full issue details including stack trace
2. Use GitHub MCP to find the affected file and read the buggy code
3. Analyze the root cause
4. Generate a fix with tests
5. Create a GitHub PR with:
   - Fix implementation
   - Unit tests
   - Descriptive commit message
   - PR description explaining the issue and fix

## Output Format
Return a JSON object with:
{
  "analysis": "Root cause explanation",
  "fix_applied": true/false,
  "pr_url": "https://github.com/...",
  "confidence": 0.0-1.0
}
EOF

    # Run Claude Code with Opus model for better analysis
    log "Running Claude Code analysis (using Opus)..."

    claude -p "$(cat /tmp/claude_context_${issue_id}.md)" \
        --model opus \
        --allowedTools "mcp__sentry__search_issues" "mcp__sentry__get_issue_details" \
        "mcp__github__get_file_contents" "mcp__github__create_pull_request" \
        "Read" "Write" "Edit" "Bash" \
        > /tmp/claude_result_${issue_id}.json 2>&1

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        log "✅ Successfully analyzed issue ${issue_id}"

        # Extract PR URL if created
        pr_url=$(jq -r '.pr_url // empty' /tmp/claude_result_${issue_id}.json 2>/dev/null)

        if [ -n "$pr_url" ]; then
            log "🚀 Created PR: ${pr_url}"

            # Send Slack notification
            send_slack_notification "$issue_title" "$pr_url" "success"
        else
            warn "No PR created for issue ${issue_id}"
        fi
    else
        error "Failed to analyze issue ${issue_id}"
        send_slack_notification "$issue_title" "" "failed"
    fi

    # Cleanup
    rm -f /tmp/claude_context_${issue_id}.md /tmp/claude_result_${issue_id}.json
}

# Send Slack notification
send_slack_notification() {
    local issue_title=$1
    local pr_url=$2
    local status=$3

    if [ -z "$SLACK_WEBHOOK" ]; then
        warn "SLACK_WEBHOOK not set, skipping notification"
        return
    fi

    local color="good"
    local message="✅ Auto-fixed Sentry issue and created PR"

    if [ "$status" = "failed" ]; then
        color="danger"
        message="❌ Failed to auto-fix Sentry issue"
    fi

    local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "${color}",
            "title": "${issue_title}",
            "text": "${message}",
            "fields": [
                {
                    "title": "PR URL",
                    "value": "${pr_url:-N/A}",
                    "short": false
                }
            ]
        }
    ]
}
EOF
    )

    curl -s -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "$payload" > /dev/null
}

# Main execution
main() {
    log "Starting Sentry Auto-Fix Bot (powered by Claude Code)"

    # Validate environment
    if [ -z "$SENTRY_AUTH_TOKEN" ]; then
        error "SENTRY_AUTH_TOKEN not set"
        exit 1
    fi

    # Fetch issues
    fetch_sentry_issues

    # Process top 5 issues
    jq -r '.[:5] | .[] | "\(.id)|\(.title)|\(.count)"' /tmp/sentry_issues.json | \
    while IFS='|' read -r issue_id issue_title issue_count; do
        process_issue "$issue_id" "$issue_title" "$issue_count"

        # Rate limiting: wait 30s between issues
        sleep 30
    done

    log "✅ Completed auto-fix run"

    # Cleanup
    rm -f /tmp/sentry_issues.json
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
