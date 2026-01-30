"""
Historical Pattern Loader (REST API Version)
Uses Sentry REST API directly since MCP doesn't expose commit/activity data
"""

import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .config import SENTRY_AUTH_TOKEN, SENTRY_ORG


@dataclass
class HistoricalPattern:
    """Pattern extracted from a historically resolved Sentry issue."""
    error_type: str  # "KeyError", "AttributeError", etc.
    error_message: str
    file_path: Optional[str]  # From stack trace
    function_name: Optional[str]
    fix_approach: str  # Extracted from commit message
    github_commit_url: Optional[str]
    sentry_issue_id: str
    occurrences: int  # How many times this error appeared
    confidence: float  # 0.95 for historical (proven fixes)
    resolved_at: datetime
    project: str  # altimate-backend, etc.


class HistoricalLoaderREST:
    """Loads historical fix patterns from resolved Sentry issues using REST API."""

    def __init__(self, organization: str = None, auth_token: str = None):
        """
        Initialize historical loader.

        Args:
            organization: Sentry organization slug
            auth_token: Sentry API token
        """
        self.organization = organization or SENTRY_ORG
        self.auth_token = auth_token or SENTRY_AUTH_TOKEN
        self.base_url = "https://sentry.io/api/0"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

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
            projects: List of Sentry project slugs
            max_issues_per_project: Max issues to fetch per project
            min_occurrences: Only load high-volume issues
            months_back: How far back to look

        Returns:
            List of historical patterns ready for memory bootstrap
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
        Query Sentry REST API for resolved issues.
        """
        patterns = []

        try:
            # Step 1: Search for resolved issues using organization endpoint
            search_url = f"{self.base_url}/organizations/{self.organization}/issues/"

            # Use start/end params and project filter in query
            end_date = datetime.utcnow()
            params = {
                "query": f"is:resolved project:{project}",
                "start": start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                "end": end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                "sort": "freq",  # Most frequent first
                "limit": max_issues
            }

            print(f"   🔍 Searching for resolved issues...")

            # Fetch all pages (cursor-based pagination)
            issues = []
            cursor = None
            page = 1

            while len(issues) < max_issues:
                if cursor:
                    params["cursor"] = cursor

                response = requests.get(search_url, headers=self.headers, params=params, timeout=30)

                if response.status_code != 200:
                    print(f"   ❌ Failed to search issues: {response.status_code}")
                    break

                page_issues = response.json()
                issues.extend(page_issues)

                # Check for next page in Link header
                link_header = response.headers.get("Link", "")
                next_cursor = None

                if 'rel="next"' in link_header and 'results="true"' in link_header:
                    # Parse cursor from Link header
                    import re
                    match = re.search(r'cursor=([^>]+)>; rel="next"; results="true"', link_header)
                    if match:
                        next_cursor = match.group(1)

                if not next_cursor or not page_issues:
                    break  # No more pages

                cursor = next_cursor
                page += 1
                print(f"      Fetching page {page}...")

            print(f"   📊 Found {len(issues)} resolved issues across {page} page(s)")

            # Step 2: Get details + activity for each issue
            for issue in issues:
                try:
                    # Skip if below threshold
                    occurrences = int(issue.get("count", 0))
                    if occurrences < min_occurrences:
                        continue

                    issue_id = issue["id"]

                    # Get full issue details including activity
                    details_url = f"{self.base_url}/organizations/{self.organization}/issues/{issue_id}/"
                    details_response = requests.get(details_url, headers=self.headers, timeout=10)

                    if details_response.status_code != 200:
                        continue

                    details = details_response.json()
                    activity = details.get("activity", [])

                    # Look for resolution commit in activity
                    commit_data = None
                    for act in activity:
                        if act.get("type") == "set_resolved_in_commit":
                            commit_data = act.get("data", {}).get("commit")
                            break

                    if not commit_data:
                        continue  # Skip if no commit found

                    # Extract pattern data
                    pattern = self._extract_pattern(
                        issue=issue,
                        details=details,
                        commit_data=commit_data,
                        project=project
                    )

                    if pattern:
                        patterns.append(pattern)
                        print(f"   ✅ Extracted: {pattern.error_type} ({pattern.occurrences} occurrences)")

                except Exception as e:
                    print(f"   ⚠️  Failed to process issue {issue.get('id')}: {e}")
                    continue

        except Exception as e:
            print(f"   ❌ Error querying issues: {e}")

        return patterns

    def _extract_pattern(
        self,
        issue: Dict,
        details: Dict,
        commit_data: Dict,
        project: str
    ) -> Optional[HistoricalPattern]:
        """Extract pattern from issue + commit data."""
        try:
            # Extract error type from title
            title = issue.get("title", "")
            error_type = "Unknown"

            # Common error patterns
            error_types = ["KeyError", "AttributeError", "TypeError", "ValueError",
                          "IndexError", "NameError", "ImportError", "RuntimeError"]
            for et in error_types:
                if et in title:
                    error_type = et
                    break

            # Extract fix approach from commit message
            commit_message = commit_data.get("message", "")
            fix_approach = self._extract_fix_from_commit(commit_message)

            # Get file path from culprit or metadata
            file_path = issue.get("culprit") or details.get("metadata", {}).get("filename")

            # Get function name from culprit
            function_name = None
            culprit = issue.get("culprit", "")
            if " in " in culprit:
                function_name = culprit.split(" in ")[-1]

            # Get GitHub URL
            repo_url = commit_data.get("repository", {}).get("url", "")
            commit_id = commit_data.get("id", "")
            github_url = f"{repo_url}/commit/{commit_id}" if repo_url and commit_id else None

            # Get resolution date
            resolved_at = datetime.fromisoformat(
                commit_data.get("dateCreated", datetime.utcnow().isoformat()).replace('Z', '+00:00')
            )

            pattern = HistoricalPattern(
                error_type=error_type,
                error_message=title[:200],
                file_path=file_path,
                function_name=function_name,
                fix_approach=fix_approach[:500],
                github_commit_url=github_url,
                sentry_issue_id=issue.get("shortId", ""),
                occurrences=issue.get("count", 0),
                confidence=0.95,  # High confidence for proven fixes
                resolved_at=resolved_at,
                project=project
            )

            return pattern

        except Exception as e:
            print(f"   ⚠️  Failed to extract pattern: {e}")
            return None

    def _extract_fix_from_commit(self, commit_message: str) -> str:
        """Extract fix description from commit message."""
        # Take first line (usually the summary)
        lines = commit_message.strip().split("\n")
        first_line = lines[0] if lines else commit_message

        # If there's more detail, include it
        fix_description = first_line

        # Look for detailed explanation
        for i, line in enumerate(lines):
            if line.lower().startswith(("root cause:", "changes:", "fix:")):
                # Include next few lines
                detail_lines = lines[i:i+3]
                fix_description += "\n" + "\n".join(detail_lines)
                break

        return fix_description.strip()


# Test function
async def test_loader():
    """Test historical pattern loading."""
    print("🧪 Testing Historical Pattern Loader (REST API)\\n")

    loader = HistoricalLoaderREST()

    # Load patterns from one project
    patterns = await loader.load_historical_patterns(
        projects=["altimate-backend"],
        max_issues_per_project=10,
        min_occurrences=50,
        months_back=6
    )

    print(f"\\n📊 Results:")
    print(f"   Total patterns: {len(patterns)}")

    if patterns:
        print(f"\\n   Sample pattern:")
        pattern = patterns[0]
        print(f"   - Error: {pattern.error_type}")
        print(f"   - File: {pattern.file_path}")
        print(f"   - Fix: {pattern.fix_approach[:100]}...")
        print(f"   - Occurrences: {pattern.occurrences}")
        print(f"   - GitHub: {pattern.github_commit_url}")
        print(f"   - Confidence: {pattern.confidence:.0%}")

    return patterns


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_loader())
