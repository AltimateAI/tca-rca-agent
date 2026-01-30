"""
Historical Pattern Loader
Bootstraps memory system with patterns from resolved Sentry issues
"""

import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage
from .config import MCP_SERVERS


@dataclass
class HistoricalPattern:
    """Pattern extracted from a historically resolved Sentry issue."""
    error_type: str  # "KeyError", "AttributeError", etc.
    error_message: str
    file_path: Optional[str]  # From stack trace
    function_name: Optional[str]
    fix_approach: str  # Extracted from PR description
    github_pr_url: Optional[str]
    sentry_issue_id: str
    occurrences: int  # How many times this error appeared
    confidence: float  # 0.95 for historical (proven fixes)
    resolved_at: datetime
    project: str  # altimate-backend, etc.


class HistoricalLoader:
    """Loads historical fix patterns from resolved Sentry issues."""

    def __init__(self, organization: str = None):
        """
        Initialize historical loader.

        Args:
            organization: Sentry organization slug
        """
        self.organization = organization or os.getenv("SENTRY_ORG") or os.getenv("TCA_SENTRY_ORG")

    async def load_historical_patterns(
        self,
        projects: List[str],
        max_issues_per_project: int = 50,
        min_occurrences: int = 20,
        months_back: int = 6
    ) -> List[HistoricalPattern]:
        """
        Load patterns from historically resolved Sentry issues.

        Args:
            projects: List of Sentry project slugs (e.g., ["altimate-backend"])
            max_issues_per_project: Max issues to fetch per project
            min_occurrences: Only load high-volume issues
            months_back: How far back to look (default: 6 months)

        Returns:
            List of historical patterns ready for memory bootstrap

        Cost: ~$0.50 to load 50 issues (using prompt caching)
        """
        all_patterns = []

        # Calculate time range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months_back * 30)

        print(f"\n🔍 Loading historical patterns from {len(projects)} projects...")
        print(f"   Time range: {start_date.date()} to {end_date.date()}")
        print(f"   Min occurrences: {min_occurrences}")

        for project in projects:
            print(f"\n📦 Processing project: {project}")

            # Query resolved issues
            patterns = await self._query_resolved_issues(
                project=project,
                max_issues=max_issues_per_project,
                min_occurrences=min_occurrences,
                start_date=start_date
            )

            print(f"   ✅ Found {len(patterns)} patterns")
            all_patterns.extend(patterns)

        print(f"\n✨ Total patterns loaded: {len(all_patterns)}")
        return all_patterns

    async def _query_resolved_issues(
        self,
        project: str,
        max_issues: int,
        min_occurrences: int,
        start_date: datetime
    ) -> List[HistoricalPattern]:
        """
        Query Sentry for resolved issues and extract patterns.

        Uses Claude Agent SDK + Sentry MCP for efficient querying.
        """
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=15,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""Use mcp__sentry__search_issues to find resolved issues from Sentry.

Organization: {self.organization}
Project: {project}

Query Parameters:
- status: resolved
- level: error
- start: {start_date.isoformat()}
- sort: count (most frequent first)
- limit: {max_issues}

For EACH resolved issue (up to {max_issues} issues):
1. Check if it has GitHub PR/commit links (check the 'activity' or 'links' field)
2. If NO GitHub link: SKIP this issue
3. If HAS GitHub link: Extract the following data

Required data to extract:
1. Error type (KeyError, AttributeError, etc.) - from issue title/culprit
2. Error message - from issue title
3. File path - from stack trace or culprit field
4. Function name - from stack trace or culprit field
5. Number of occurrences (count field)
6. Resolution date (resolvedAt or lastSeen field)
7. Sentry issue ID
8. GitHub PR/commit URL - from activity or metadata

For issues WITH GitHub links, also use mcp__github__* tools to:
1. Fetch the PR/commit details
2. Extract fix approach from PR title + description
3. Understand what code change was made

Filter rules:
- Only include issues with {min_occurrences}+ occurrences
- Only include issues that have an actual GitHub PR/commit URL
- Skip issues without GitHub links

Return ONLY a JSON array:
[
  {{
    "error_type": "KeyError",
    "error_message": "...",
    "file_path": "api/routes/users.py",
    "function_name": "get_user_email",
    "fix_approach": "Added .get() with default value to handle missing keys",
    "github_pr_url": "https://github.com/...",
    "sentry_issue_id": "ALTIMATE-BACKEND-42K",
    "occurrences": 1247,
    "resolved_at": "2026-01-15T10:30:00Z"
  }},
  ...
]

CRITICAL OUTPUT RULES:
- You MUST return ONLY a raw JSON array, nothing else
- NO explanatory text before or after the array
- NO markdown code blocks (no ```json)
- If you find NO issues with GitHub links, return an empty array: []
- If you find issues, return the array with those issues
- Do NOT explain why there are no results - just return []

Examples:
No results: []
With results: [{{"error_type": "KeyError", ...}}, ...]

START YOUR RESPONSE WITH THE [ CHARACTER AND END WITH THE ] CHARACTER.
"""

        # Execute query
        result_text = None
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage) and not msg.is_error:
                result_text = msg.result
                break

        if not result_text:
            print(f"   ⚠️  No response from Sentry query")
            return []

        # Debug: Print what Claude returned
        print(f"   📝 Claude response preview: {result_text[:300]}...")

        # Parse JSON response
        import json
        import re

        try:
            # Try to extract JSON array
            match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if match:
                issues_data = json.loads(match.group(0))
            else:
                issues_data = json.loads(result_text)

            # Convert to HistoricalPattern objects
            patterns = []
            for issue in issues_data:
                try:
                    pattern = HistoricalPattern(
                        error_type=issue.get("error_type", "Unknown"),
                        error_message=issue.get("error_message", "")[:200],
                        file_path=issue.get("file_path"),
                        function_name=issue.get("function_name"),
                        fix_approach=issue.get("fix_approach", "")[:500],
                        github_pr_url=issue.get("github_pr_url"),
                        sentry_issue_id=issue.get("sentry_issue_id", ""),
                        occurrences=issue.get("occurrences", 0),
                        confidence=0.95,  # High confidence for proven fixes
                        resolved_at=datetime.fromisoformat(
                            issue.get("resolved_at", datetime.utcnow().isoformat()).replace('Z', '+00:00')
                        ),
                        project=project
                    )
                    patterns.append(pattern)
                except Exception as e:
                    print(f"   ⚠️  Failed to parse issue: {e}")
                    continue

            return patterns

        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse JSON: {e}")
            print(f"   Response: {result_text[:500]}")
            return []
        except Exception as e:
            print(f"   ❌ Error processing issues: {e}")
            return []


# Test function
async def test_loader():
    """Test historical pattern loading."""
    print("🧪 Testing Historical Pattern Loader\n")

    loader = HistoricalLoader()

    # Load patterns from one project
    patterns = await loader.load_historical_patterns(
        projects=["altimate-backend"],
        max_issues_per_project=10,
        min_occurrences=10,
        months_back=6
    )

    print(f"\n📊 Results:")
    print(f"   Total patterns: {len(patterns)}")

    if patterns:
        print(f"\n   Sample pattern:")
        pattern = patterns[0]
        print(f"   - Error: {pattern.error_type}")
        print(f"   - File: {pattern.file_path}")
        print(f"   - Fix: {pattern.fix_approach[:100]}...")
        print(f"   - Occurrences: {pattern.occurrences}")
        print(f"   - Confidence: {pattern.confidence:.0%}")

    return patterns


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_loader())
