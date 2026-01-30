"""
RCA Agent - Root Cause Analysis with Claude Agent SDK
Uses MCP tools for Sentry/GitHub access (no manual REST calls)
"""

import os
import json
import re
import difflib
import asyncio
from typing import Optional, AsyncGenerator
from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock, ThinkingBlock
from .config import MCP_SERVERS, GITHUB_OWNER, GITHUB_REPO, validate_env
from .code_merger import CodeMerger


class RCAAgent:
    """
    Root Cause Analysis Agent using Claude Agent SDK + MCP tools.
    Simple, single-pass approach with prompt caching.
    """

    def __init__(self, memory_system=None):
        """
        Initialize RCA agent.

        Args:
            memory_system: Optional MemorySystem instance for pattern learning
        """
        validate_env()
        self.memory_system = memory_system
        self.code_merger = CodeMerger()
        self._cancelled = False  # Flag to track if analysis should stop
        self._cancel_requested = asyncio.Event()  # Event to signal cancellation

    def cancel(self):
        """
        Request cancellation of the current analysis.
        This sets a flag that will stop the query loop and prevent further API calls.
        """
        self._cancelled = True
        self._cancel_requested.set()
        print(f"🛑 RCA Agent: Cancellation requested")

    async def analyze_issue(
        self,
        issue_id: str,
        organization: str = None,
        project: str = None,
        error_type: str = None
    ) -> AsyncGenerator[dict, None]:
        """
        Analyze Sentry issue and generate fix.

        Args:
            issue_id: Sentry issue ID
            organization: Sentry org (uses env var if not provided)
            project: Sentry project (optional)
            error_type: Optional error type for filtered patterns (enables prompt caching)

        Yields:
            Progress events:
            {"type": "status", "message": "Fetching issue..."}
            {"type": "thinking", "content": "Analyzing..."}
            {"type": "complete", "result": {...}}

        Final result format:
            {
                "issue_id": str,
                "error_type": str,
                "error_message": str,
                "root_cause": str,
                "fix_confidence": float (0.0-1.0),
                "fix_code": str,
                "file_path": str,
                "function_name": str,
                "line_number": int,
                "test_cases": [...],
                "matched_pattern": bool,
                "can_auto_fix": bool
            }
        """

        organization = organization or os.getenv("SENTRY_ORG") or os.getenv("TCA_SENTRY_ORG")

        yield {"type": "status", "message": f"Analyzing Sentry issue {issue_id}..."}

        # Track analysis time
        import time
        start_time = time.time()

        # Configure agent with all MCP servers
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],  # Tool Search auto-enabled
            max_turns=20,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",  # Auto-approve all tool calls
        )

        # Build comprehensive prompt
        prompt = self._build_analysis_prompt(issue_id, organization, project, error_type)

        # Execute agent
        result_text = None
        async for msg in query(prompt=prompt, options=options):
            # Check for cancellation FIRST - before processing any messages
            if self._cancelled:
                print(f"🛑 Query loop: Cancellation detected, stopping iteration")
                yield {"type": "error", "data": {"message": "Analysis cancelled by user"}}
                break  # Stop consuming from query - this stops API calls!

            # Handle AssistantMessage (thinking/text blocks)
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ThinkingBlock):
                        yield {"type": "thinking", "content": block.thinking[:200]}
                    elif isinstance(block, TextBlock):
                        yield {"type": "thinking", "content": block.text[:200]}

            # Handle ResultMessage (final result)
            elif isinstance(msg, ResultMessage):
                if not msg.is_error and msg.result:
                    result_text = msg.result
                elif msg.is_error:
                    yield {
                        "type": "error",
                        "data": {"message": f"Agent returned error: {msg.result or 'Unknown error'}"}
                    }
                    return
                break

        if not result_text:
            yield {
                "type": "error",
                "data": {"message": "Agent did not return a result"}
            }
            return

        # Log result for debugging
        print(f"📝 Agent result length: {len(result_text)}")
        print(f"📝 Agent result (first 500 chars): {result_text[:500]}")

        # Parse result
        try:
            result = self._parse_json(result_text)
        except Exception as e:
            print(f"❌ JSON parse failed: {str(e)}")
            yield {
                "type": "error",
                "data": {"message": f"Failed to parse result: {str(e)}"}
            }
            return

        # Map fields to match RCAResult model
        result["issue_id"] = issue_id
        result["can_auto_fix"] = result.get("fix_confidence", 0) >= 0.9
        result["analysis_time_seconds"] = round(time.time() - start_time, 1)
        result["sentry_url"] = f"https://sentry.io/organizations/{organization}/issues/{issue_id}/"
        result["confidence"] = result.get("fix_confidence", 0.0)  # Rename fix_confidence to confidence
        result["fix_explanation"] = result.get("root_cause", "")  # Use root_cause as fix_explanation
        result["fix_approach"] = "automated"  # Default approach
        result["same_file_issues"] = []  # Empty list for now
        result["codebase_issues"] = []  # Empty list for now
        result["related_sentry_issues"] = []  # Empty list for now
        result["frontend_impact"] = "NO"  # Default to no
        result["requires_approval"] = result.get("fix_confidence", 0) < 0.9  # Require approval if confidence < 90%
        result["learned_context"] = f"Matched pattern: {result.get('matched_pattern', False)}"
        result["dry_run"] = False  # Not a dry run

        # Convert test_cases array to test_code string
        test_cases = result.get("test_cases", [])
        if test_cases:
            result["test_code"] = "\n\n".join([tc.get("code", "") for tc in test_cases if tc.get("code")])
        else:
            result["test_code"] = "# No tests generated"

        # DISABLED: Original code fetching causes hangs
        # The diff feature is nice-to-have but not critical
        # Users can still see the fix_code which is the important part
        result["original_code"] = None
        result["original_function"] = None

        # Uncomment below if you want to enable it later after fixing GitHub API issues
        # try:
        #     if result.get("file_path"):
        #         yield {"type": "status", "message": "Fetching original code for diff..."}
        #         try:
        #             original_code = await asyncio.wait_for(
        #                 self._get_file_contents(result["file_path"]),
        #                 timeout=30.0
        #             )
        #             result["original_code"] = original_code
        #             if result.get("function_name") and original_code:
        #                 result["original_function"] = self._extract_function(
        #                     original_code,
        #                     result["function_name"]
        #                 )
        #         except asyncio.TimeoutError:
        #             print(f"⚠️ Timeout fetching original code for {result['file_path']}")
        # except Exception as e:
        #     print(f"⚠️ Could not fetch original code: {e}")

        # Store pattern in memory if available
        if self.memory_system and result.get("error_type"):
            try:
                self.memory_system.store_pattern(
                    error_type=result.get("error_type", "Unknown"),
                    fix_approach=result.get("root_cause", "")[:200],
                    confidence=result.get("fix_confidence", 0.0),
                    additional_metadata={"issue_id": issue_id}
                )
            except Exception:
                pass  # Don't fail if memory storage fails

        yield {"type": "result", "data": result}

    async def analyze_issue_batch(
        self,
        issues: list,
        error_type: str,
        organization: str = None
    ) -> AsyncGenerator[dict, None]:
        """
        Analyze multiple similar issues in batch with prompt caching.

        This method is optimized for cost-efficiency by using Claude's prompt caching.
        Issues of the same error type share cached context (system instructions,
        learned patterns, workflow), reducing token costs by ~90% after the first issue.

        Args:
            issues: List of issue dicts with {id, title, count, priority, ...}
            error_type: Common error type (e.g., "KeyError", "DatabaseError")
            organization: Sentry org (uses env var if not provided)

        Yields:
            Progress events for each issue:
            {"type": "batch_start", "total": N, "error_type": "KeyError"}
            {"type": "issue_start", "issue_id": "...", "index": 0}
            {"type": "issue_complete", "issue_id": "...", "result": {...}}
            {"type": "batch_complete", "analyzed": N, "failed": M}
        """
        organization = organization or os.getenv("SENTRY_ORG") or os.getenv("TCA_SENTRY_ORG")

        yield {
            "type": "batch_start",
            "total": len(issues),
            "error_type": error_type
        }

        results = []
        failed = 0

        for idx, issue in enumerate(issues):
            issue_id = issue.get('id')

            yield {
                "type": "issue_start",
                "issue_id": issue_id,
                "index": idx,
                "title": issue.get('title', 'Unknown')
            }

            try:
                # Analyze issue with error_type for prompt caching optimization
                result_data = None
                async for event in self.analyze_issue(issue_id, organization, error_type=error_type):
                    if event['type'] == 'result':
                        result_data = event['data']
                    # Forward progress events
                    yield event

                if result_data:
                    results.append({
                        "issue_id": issue_id,
                        "status": "completed",
                        "result": result_data
                    })

                    yield {
                        "type": "issue_complete",
                        "issue_id": issue_id,
                        "index": idx,
                        "result": result_data
                    }
                else:
                    failed += 1
                    results.append({
                        "issue_id": issue_id,
                        "status": "failed",
                        "error": "No result returned"
                    })

            except Exception as e:
                failed += 1
                results.append({
                    "issue_id": issue_id,
                    "status": "failed",
                    "error": str(e)
                })

                yield {
                    "type": "issue_error",
                    "issue_id": issue_id,
                    "index": idx,
                    "error": str(e)
                }

        yield {
            "type": "batch_complete",
            "analyzed": len(issues) - failed,
            "failed": failed,
            "error_type": error_type,
            "results": results
        }

    def _build_analysis_prompt(
        self,
        issue_id: str,
        organization: str,
        project: Optional[str],
        error_type: Optional[str] = None
    ) -> str:
        """
        Build the analysis prompt for Claude Agent SDK.

        Args:
            issue_id: Sentry issue ID
            organization: Sentry organization
            project: Optional Sentry project
            error_type: Optional error type for filtered patterns (enables prompt caching)

        Returns:
            Formatted prompt string
        """

        # Get learned patterns if available
        # If error_type provided, filter patterns for better cache hits
        learned_context = ""
        if self.memory_system:
            try:
                if error_type:
                    # Get error-type-specific patterns (enables prompt caching)
                    patterns = self.memory_system.get_patterns_by_error_type(error_type)
                else:
                    # Get all patterns
                    patterns = self.memory_system.get_all_patterns()

                if patterns and len(patterns) > 50:
                    learned_context = f"\n## Learned Patterns for {error_type or 'All Errors'}\n{patterns}\n"
            except Exception:
                pass

        return f"""
Analyze Sentry issue {issue_id} from organization {organization}.

{learned_context}
## Your Workflow

### Phase 1: Investigation
1. Use mcp__sentry__get_issue to get issue details
2. Use mcp__sentry__get_issue_events to get stack traces
3. Extract:
   - error_type (e.g., KeyError, IntegrityError, TimeoutError)
   - error_message
   - file_path (from stack trace)
   - line_number (from stack trace)
   - function_name (from stack trace)
   - error_timestamp (lastSeen)

### Phase 1.5: Infrastructure & User Context (REQUIRED)
⚠️ IMPORTANT: You MUST collect evidence in this phase. Do NOT skip this step.

Gather additional context based on error type:

**For infrastructure errors (timeouts, connection errors, high latency):**
1. Use mcp__signoz__fetch_services to see service health
2. Use mcp__signoz__fetch_apm_metrics for error rates around error_timestamp
3. Use mcp__aws__get_cloudwatch_logs to check container logs
4. Use mcp__aws__get_xray_traces for distributed traces

**For user-facing errors:**
1. Use mcp__posthog__get_session_recordings to find affected user sessions
2. Use mcp__posthog__get_events to see user actions before error
3. Determine user impact and behavior patterns

**For all errors:**
- Always include github_context with recent commits and related files
- Calculate infrastructure_correlation (0.0-1.0) based on collected metrics
- Calculate user_impact_score (0.0-100.0) based on affected users/sessions

### Phase 2: Root Cause Analysis
Analyze the error and determine:
- Root cause (human-readable explanation)
- Error category (database | network | application | infrastructure)
- Fix confidence (0.0 to 1.0):
  * 0.8+ if error is clear and fix is obvious
  * 0.5-0.8 if error is clear but fix has some uncertainty
  * < 0.5 if error is unclear or complex

### Phase 3: Generate Fix
If fix_confidence >= 0.5:
1. Use mcp__github__get_file_contents to read the affected file
   Repository: {GITHUB_OWNER}/{GITHUB_REPO}
2. Generate a MINIMAL fix
   - Only fix the specific function
   - Do NOT return the entire file
   - Return just the fixed function code
3. Generate test cases:
   - Smoke test: Verify function doesn't crash
   - Regression test: Should fail before fix, pass after
   - Edge case test: Test null/empty/boundary values

### Phase 4: Return Result
Do NOT create a PR. Return analysis and fix code only.

## Output Format

Return ONLY a JSON object (no markdown formatting):

{{
  "error_type": "KeyError",
  "error_message": "...",
  "file_path": "api/routes/users.py",
  "line_number": 42,
  "function_name": "user_email",
  "root_cause": "Accessing dict key without checking if it exists",
  "fix_confidence": 0.85,
  "fix_code": "def user_email(user):\\n    return user.get('email', None)",
  "test_cases": [
    {{
      "name": "test_user_email_missing_key",
      "code": "def test_user_email_missing_key():\\n    assert user_email({{}}) is None",
      "type": "regression"
    }}
  ],
  "matched_pattern": false,
  "evidence": {{
    "signoz_metrics": {{"service": "backend-api", "error_rate": 0.15, "latency_p99": 2500}},
    "posthog_sessions": {{"affected_users": 45, "session_recordings": ["rec_123"]}},
    "aws_logs": {{"log_group": "/aws/lambda/payment", "error_count": 23}},
    "github_context": {{"recent_commits": ["abc123"], "related_files": ["utils.py"]}}
  }},
  "infrastructure_correlation": 0.85,
  "user_impact_score": 67.5
}}

IMPORTANT:
- Return ONLY the JSON object
- No markdown code blocks
- fix_code should be the FIXED FUNCTION only, not entire file
- ⚠️ REQUIRED: Always include the "evidence" object with data from Phase 1.5
  - If no infrastructure data available, use empty objects {{}} but include the fields
  - Always include github_context with at least recent commits
  - Always calculate infrastructure_correlation and user_impact_score
- infrastructure_correlation: 0.0-1.0 (how strongly issue correlates with infrastructure problems)
- user_impact_score: 0.0-100.0 (estimated user impact based on affected sessions/events)
- Be thorough but concise
"""

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from agent response with robust error handling."""
        original_text = text

        # Try to extract JSON from markdown code block
        match = re.search(r'```json\s*(.+?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"⚠️  Direct JSON parse failed: {e}")

            # Try to find JSON object in text
            start = text.find('{')
            end = text.rfind('}') + 1

            if start >= 0 and end > start:
                json_str = text[start:end]

                # Try to fix common issues
                # 1. Replace single quotes with double quotes (careful with strings)
                try:
                    # First try without modification
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"⚠️  Extracted JSON parse failed, trying fixes...")

                    # Log the problematic JSON for debugging
                    print(f"📝 First 500 chars of response:\n{json_str[:500]}")
                    print(f"📝 Last 200 chars of response:\n{json_str[-200:]}")

                    # Try with single quote replacement (risky but sometimes works)
                    try:
                        fixed = json_str.replace("'", '"')
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass

            # If all else fails, log and raise with helpful info
            print(f"❌ Failed to parse JSON. Response length: {len(original_text)}")
            print(f"📝 Full response (first 1000 chars):\n{original_text[:1000]}")
            raise ValueError(f"No valid JSON found in response. Parse error: {e}")

    # ===== PR Creation Methods =====

    async def create_github_pr(self, result: dict) -> dict:
        """
        Create GitHub PR with AI-powered smart decisions:
        - Finds code authors via git blame for reviewer assignments
        - Intelligently decides where to place tests (existing vs new file)
        - Uses full analysis context for better decisions

        Args:
            result: Full analysis result from analyze_issue()

        Returns:
            {
                "url": "https://github.com/...",
                "number": 123,
                "branch": "fix/keyerror-get-user-email",
                "files": [...],
                "reviewers": ["user1", "user2"]
            }
        """
        from .config import GITHUB_OWNER, GITHUB_REPO

        # Configure agent for PR creation with full context
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=20,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""
You are creating a GitHub Pull Request for an automatically generated bug fix.

## Full Analysis Context

**Issue**: {result.get('issue_id')}
**Sentry URL**: {result.get('sentry_url')}
**Error Type**: {result.get('error_type')}
**Root Cause**: {result.get('root_cause')}
**Confidence**: {result.get('confidence', 0):.0%}

**File**: {result['file_path']}
**Function**: {result['function_name']}

**Fix Code**:
```
{result['fix_code']}
```

**Test Code**:
```
{result.get('test_code', '')}
```

## Your Tasks

### 1. Get Git Blame Information
Use GitHub MCP to run `git blame` on {result['file_path']} around line {result.get('line_number', 1)}.
Find the authors who last modified this code. These will be good reviewers.

### 2. Analyze Test File Location
Check if tests exist for this file:
- Look for existing test files matching patterns like:
  * `tests/{result['file_path'].replace('.py', '_test.py')}`
  * `tests/test_{result['file_path']}`
  * `{result['file_path'].replace('.py', '_test.py')}`

Decision:
- If existing test file found → Add tests there
- If no test file → Create new one following project conventions

### 3. Create Branch
Branch name: `fix/{result.get('error_type', 'bug').lower()}-{result.get('function_name', 'unknown').lower()[:30]}`

### 4. Commit Changes
- Commit 1: Fix the bug in {result['file_path']}
- Commit 2: Add/update tests in the chosen test file

### 5. Create Pull Request
Title: `🐛 Fix: {result.get('error_type')} in {result.get('function_name')}`

Body:
```markdown
## 🐛 Bug Fix

**Sentry Issue**: {result.get('sentry_url')}
**Error**: {result.get('error_type')} in `{result.get('function_name')}`
**Confidence**: {result.get('confidence', 0):.0%}

### Root Cause
{result.get('root_cause')}

### Changes
- Fixed {result.get('error_type')} in `{result['file_path']}`
- Added regression tests

### Evidence
{{if evidence}}
- Infrastructure Correlation: {result.get('infrastructure_correlation', 0):.0%}
- User Impact Score: {result.get('user_impact_score', 0):.0f}/100
{{endif}}

### Testing
```bash
pytest <test-file-path>
```

---
🤖 Auto-generated by [TCA RCA Agent](https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})
```

### 6. Assign Reviewers
Based on git blame, assign the most relevant code authors as reviewers.

## Output Format

Return ONLY a JSON object:

{{
  "branch": "fix/error-type-function",
  "commits": [
    {{"path": "...", "message": "..."}},
    {{"path": "...", "message": "..."}}
  ],
  "pr_number": 123,
  "pr_url": "https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/pull/123",
  "reviewers": ["username1", "username2"],
  "test_file": "path/to/test_file.py",
  "test_strategy": "added_to_existing" | "created_new"
}}

IMPORTANT: Actually create the PR using GitHub MCP tools, don't just return a plan.
"""

        result_text = None
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                if not msg.is_error and msg.result:
                    result_text = msg.result
                break

        if not result_text:
            raise ValueError("Agent failed to create PR")

        # Parse JSON response
        pr_result = self._parse_json(result_text)

        return {
            "url": pr_result.get("pr_url"),
            "number": pr_result.get("pr_number"),
            "branch": pr_result.get("branch"),
            "files": [c["path"] for c in pr_result.get("commits", [])],
            "reviewers": pr_result.get("reviewers", []),
            "test_file": pr_result.get("test_file"),
            "test_strategy": pr_result.get("test_strategy")
        }
        pr = await self._create_pull_request(
            title=f"🐛 Fix: {result['error_type']} in `{result['function_name']}`",
            body=pr_description,
            head=branch,
            base="main"
        )

        return {
            "url": pr["url"],
            "number": pr["number"],
            "branch": branch,
            "files": [result['file_path'], test_path]
        }

    async def check_pr_status(self, pr_number: int, owner: str = None, repo: str = None) -> dict:
        """
        Check the status of a GitHub PR including CI checks.

        Args:
            pr_number: GitHub PR number
            owner: GitHub repository owner (uses config if not provided)
            repo: GitHub repository name (uses config if not provided)

        Returns:
            {
                "pr_number": 123,
                "state": "open" | "closed" | "merged",
                "mergeable": true/false,
                "checks": [
                    {
                        "name": "test",
                        "status": "completed",
                        "conclusion": "success" | "failure" | "pending"
                    }
                ],
                "all_checks_passed": true/false,
                "can_merge": true/false,
                "url": "https://github.com/...",
                "title": "Fix: ...",
                "created_at": "2024-01-29T...",
                "merged_at": "2024-01-29T..." or null
            }
        """
        from .config import GITHUB_OWNER, GITHUB_REPO

        owner = owner or GITHUB_OWNER
        repo = repo or GITHUB_REPO

        # Configure agent for GitHub API calls
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=5,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""
Get the status of GitHub pull request #{pr_number} from {owner}/{repo}.

Use the GitHub MCP tools to:
1. Get PR details (state, mergeable, title, etc.)
2. Get the latest commit SHA from the PR
3. Get CI check runs for that commit SHA

Return ONLY a JSON object (no markdown):

{{
  "pr_number": {pr_number},
  "state": "open|closed|merged",
  "mergeable": true/false,
  "checks": [
    {{
      "name": "check-name",
      "status": "completed|in_progress|queued",
      "conclusion": "success|failure|neutral|cancelled|skipped|null"
    }}
  ],
  "all_checks_passed": true/false,
  "can_merge": true/false,
  "url": "https://github.com/{owner}/{repo}/pull/{pr_number}",
  "title": "PR title",
  "created_at": "ISO timestamp",
  "merged_at": "ISO timestamp or null"
}}

IMPORTANT: Return ONLY the JSON object, no other text.
"""

        result_text = None
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                if not msg.is_error and msg.result:
                    result_text = msg.result
                break

        if not result_text:
            raise ValueError("Failed to get PR status from GitHub")

        # Parse JSON response
        pr_status = self._parse_json(result_text)
        return pr_status

    def _extract_function(self, code: str, function_name: str) -> str:
        """Extract a specific function from code."""
        if not code or not function_name:
            return code or ""

        lines = code.split('\n')
        function_lines = []
        in_function = False
        indent_level = 0

        for line in lines:
            # Check if this is the function definition
            if f'def {function_name}' in line or f'function {function_name}' in line or f'{function_name} =' in line:
                in_function = True
                indent_level = len(line) - len(line.lstrip())
                function_lines.append(line)
                continue

            if in_function:
                current_indent = len(line) - len(line.lstrip())
                # If we hit a line with same or less indentation (and it's not empty), function ended
                if line.strip() and current_indent <= indent_level:
                    break
                function_lines.append(line)

        return '\n'.join(function_lines) if function_lines else code

    def _generate_branch_name(self, result: dict) -> str:
        """Generate semantic branch name from analysis result."""
        error_type = result['error_type'].lower().replace('error', '')
        function_name = result['function_name'].lower().replace('_', '-')
        branch = f"fix/{error_type}-{function_name}"[:50]
        return branch

    def _determine_test_file_path(self, source_file: str) -> str:
        """Determine correct test file path mirroring source structure."""
        base = source_file.replace('.py', '')
        parts = base.split('/')
        filename = parts[-1]
        dirs = parts[:-1]
        test_path = f"tests/{'/'.join(dirs)}/test_{filename}.py"
        return test_path

    def _get_import_path(self, file_path: str) -> str:
        """Convert file path to Python import path."""
        import_path = file_path.replace('.py', '').replace('/', '.')
        return import_path

    def _generate_test_name(self, result: dict) -> str:
        """Generate descriptive test function name."""
        function = result['function_name']
        error_type = result['error_type'].lower()

        descriptions = {
            'keyerror': 'handles_missing_key',
            'attributeerror': 'handles_none_attribute',
            'typeerror': 'validates_input_type',
            'valueerror': 'validates_input_value',
            'indexerror': 'handles_empty_list',
            'timeouterror': 'handles_timeout',
            'connectionerror': 'handles_connection_failure',
        }

        description = descriptions.get(error_type, 'handles_error')
        return f"test_{function}_{description}"

    async def _prepare_test_content(self, result: dict, test_path: str, original_code: str) -> str:
        """Prepare test file content with proper imports and structure."""
        # Check if test file exists
        try:
            existing_content = await self._get_file_contents(test_path)
            mode = "append"
        except:
            existing_content = None
            mode = "create"

        # Generate test function from test_cases in result
        test_functions = []
        for test_case in result.get('test_cases', []):
            test_functions.append(test_case['code'])

        test_code = '\n\n'.join(test_functions)

        # Build content
        if mode == "create":
            import_path = self._get_import_path(result['file_path'])
            content = f"""import pytest
from {import_path} import {result['function_name']}


{test_code}
"""
        else:
            # Append to existing file
            content = existing_content.rstrip() + f"\n\n\n{test_code}\n"

        return content

    def _create_beautiful_diff(self, original_code: str, fixed_code: str, function_name: str) -> str:
        """Create beautiful GitHub-style diff with context."""
        original_lines = original_code.split('\n')
        fixed_lines = fixed_code.split('\n')

        # Find function in original code
        function_start = None
        for i, line in enumerate(original_lines):
            if f'def {function_name}' in line:
                function_start = i
                break

        if function_start is None:
            return fixed_code

        # Find function end
        function_end = len(original_lines)
        base_indent = len(original_lines[function_start]) - len(original_lines[function_start].lstrip())

        for i in range(function_start + 1, len(original_lines)):
            line = original_lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= base_indent:
                function_end = i
                break

        # Extract original function
        original_function = '\n'.join(original_lines[function_start:function_end])

        # Create unified diff
        diff_lines = list(difflib.unified_diff(
            original_function.split('\n'),
            fixed_lines,
            lineterm='',
            n=3
        ))

        # Format for GitHub markdown
        formatted_diff = []
        for line in diff_lines[2:]:  # Skip headers
            if line.startswith('@@'):
                formatted_diff.append(f"@@ Line {function_start + 1} @@")
            elif line.startswith('-'):
                formatted_diff.append(line)
            elif line.startswith('+'):
                formatted_diff.append(line)
            else:
                formatted_diff.append(' ' + line)

        return '\n'.join(formatted_diff)

    def _format_test_code(self, test_code: str) -> str:
        """Format test code with nice highlighting."""
        lines = test_code.split('\n')
        formatted = []

        for line in lines:
            if 'def test_' in line:
                formatted.append(f"# ✅ Test Case")
                formatted.append(line)
            elif 'assert' in line:
                formatted.append(f"{line}  # 🎯 Assertion")
            else:
                formatted.append(line)

        return '\n'.join(formatted)

    def _format_evidence_markdown(self, evidence: dict) -> str:
        """Format evidence in collapsible markdown sections."""
        sections = []

        if evidence.get('sentry'):
            sections.append(f"""**Sentry Data**:
```json
{json.dumps(evidence['sentry'], indent=2)[:500]}...
```""")

        if evidence.get('signoz'):
            sections.append(f"""**Infrastructure (SignOz)**:
- Services checked: {len(evidence['signoz'].get('services', []))}
- Error rate spike: {evidence['signoz'].get('error_spike', 'No')}
- P95 latency: {evidence['signoz'].get('p95_latency', 'Normal')}
- Infrastructure correlation: {evidence['signoz'].get('correlation', '0%')}""")

        if evidence.get('posthog'):
            sessions = evidence['posthog'].get('sessions', [])
            sections.append(f"""**User Impact (PostHog)**:
- Affected sessions: {len(sessions)}
- User actions before error: [View sessions]
- Common pattern: {evidence['posthog'].get('pattern', 'Unknown')}""")

        if evidence.get('aws'):
            logs = evidence['aws'].get('logs', [])
            sections.append(f"""**AWS Logs (CloudWatch)**:
```
{chr(10).join(str(log)[:200] for log in logs[:5])}
```""")

        return '\n\n'.join(sections) if sections else "No additional evidence collected."

    def _get_confidence_description(self, confidence: float) -> str:
        """Get confidence description with color indicator."""
        if confidence >= 0.9:
            return "🟢 Very High - Fix is straightforward and well-tested"
        elif confidence >= 0.7:
            return "🟡 High - Fix is clear with minor uncertainty"
        elif confidence >= 0.5:
            return "🟠 Medium - Fix should work but needs review"
        else:
            return "🔴 Low - Significant uncertainty, manual review required"

    def _generate_pr_description(self, result: dict, original_code: str, test_path: str) -> str:
        """Generate comprehensive PR description with visual diffs."""
        # Create beautiful diff
        fix_diff = self._create_beautiful_diff(original_code, result['fix_code'], result['function_name'])

        # Format test code
        test_code_formatted = '\n\n'.join([
            self._format_test_code(tc['code'])
            for tc in result.get('test_cases', [])
        ])

        return f"""## 🐛 Fix: {result['error_type']} in `{result['function_name']}`

### Sentry Issue
- **Issue ID**: [{result['issue_id']}]({result.get('sentry_url', '#')})
- **Occurrences**: {result.get('count', 'N/A')} times
- **Users Affected**: {result.get('user_count', 'N/A')} users
- **Last Seen**: {result.get('last_seen', 'N/A')}

### 📋 Root Cause
{result.get('root_cause', 'Analysis in progress')}

### 🔧 Fix Approach
{result.get('fix_explanation', result.get('root_cause', 'See code changes below'))}

---

## 📝 Changes

### Source Code Fix
**File**: `{result['file_path']}`

```diff
{fix_diff}
```

<details>
<summary>📊 Show full function</summary>

```python
{result['fix_code']}
```

</details>

---

### Test Case
**File**: `{test_path}`

```python
{test_code_formatted}
```

---

## 🎯 Fix Confidence

**{result.get('fix_confidence', 0):.0%}** - {self._get_confidence_description(result.get('fix_confidence', 0))}

<details>
<summary>📊 Show evidence that led to this analysis</summary>

{self._format_evidence_markdown(result.get('evidence', {}))}

</details>

---

## ✅ Testing Checklist
- [ ] Test passes locally (`pytest {test_path}`)
- [ ] No regressions in existing tests
- [ ] Edge cases covered
- [ ] Code review completed

---

## 📊 Analysis Details

| Metric | Value |
|--------|-------|
| Error Type | `{result['error_type']}` |
| File | `{result['file_path']}` |
| Function | `{result['function_name']}` |
| Line Number | {result.get('line_number', 'N/A')} |
| Fix Confidence | {result.get('fix_confidence', 0):.0%} |
| Analysis Time | {result.get('analysis_time', 'N/A')}s |

---

🤖 **Generated by TCA RCA Agent**
📊 **Confidence**: {result.get('fix_confidence', 0):.0%}
🔗 **Sentry Issue**: [{result['issue_id']}]({result.get('sentry_url', '#')})
"""

    async def _get_file_contents(self, path: str) -> str:
        """Get file contents from GitHub using direct API."""
        import aiohttp
        import base64

        github_token = os.getenv("GITHUB_TOKEN") or os.getenv("TCA_GITHUB_TOKEN")
        if not github_token:
            raise ValueError("GITHUB_TOKEN not configured")

        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 404:
                    raise FileNotFoundError(f"File not found: {path}")
                elif resp.status != 200:
                    raise Exception(f"GitHub API error: {resp.status}")

                data = await resp.json()

                # GitHub returns content as base64-encoded
                if 'content' in data:
                    content = base64.b64decode(data['content']).decode('utf-8')
                    return content
                else:
                    raise Exception(f"No content in GitHub response for {path}")

    async def _create_branch(self, branch: str) -> None:
        """Create a new branch."""
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=5,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""Use mcp__github__create_branch to create branch "{branch}" from "main" in repository {GITHUB_OWNER}/{GITHUB_REPO}.
If branch already exists, that's fine, skip it."""

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                break

    async def _commit_file(self, path: str, content: str, branch: str, message: str) -> None:
        """Commit a file to a branch."""
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=5,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""Use mcp__github__create_or_update_file to commit file {path} to branch "{branch}" in repository {GITHUB_OWNER}/{GITHUB_REPO}.

Commit message: {message}

File content:
{content}

Do it now."""

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                break

    async def _ensure_test_directories(self, test_path: str) -> None:
        """Create test directories if they don't exist."""
        parts = test_path.split('/')[:-1]

        for i in range(1, len(parts) + 1):
            dir_path = '/'.join(parts[:i])
            init_file = f"{dir_path}/__init__.py"

            try:
                await self._get_file_contents(init_file)
            except:
                # Directory doesn't exist, create __init__.py
                options = ClaudeAgentOptions(
                    mcp_servers=MCP_SERVERS,
                    allowed_tools=["mcp__*"],
                    max_turns=5,
                    model="claude-sonnet-4-20250514",
                    permission_mode="bypassPermissions",
                )

                prompt = f"""Use mcp__github__create_or_update_file to create {init_file} in repository {GITHUB_OWNER}/{GITHUB_REPO} on branch "main".
Content should be empty string.
Commit message: "chore: add test directory {dir_path}"

Do it now."""

                async for msg in query(prompt=prompt, options=options):
                    if isinstance(msg, ResultMessage):
                        break

    async def _create_pull_request(self, title: str, body: str, head: str, base: str) -> dict:
        """Create a pull request."""
        options = ClaudeAgentOptions(
            mcp_servers=MCP_SERVERS,
            allowed_tools=["mcp__*"],
            max_turns=5,
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
        )

        prompt = f"""Use mcp__github__create_pull_request to create PR in repository {GITHUB_OWNER}/{GITHUB_REPO}.

Title: {title}
Head branch: {head}
Base branch: {base}

Body:
{body}

Return the PR URL and number as JSON: {{"url": "...", "number": 123}}"""

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage) and not msg.is_error:
                try:
                    return json.loads(msg.result)
                except:
                    return {"url": msg.result, "number": 0}

        raise Exception("Failed to create PR")


# Test the agent
if __name__ == "__main__":
    import asyncio

    async def test_agent():
        print("Testing RCA Agent with Agent SDK\n")

        agent = RCAAgent()

        async for event in agent.analyze_issue("5849464050"):
            if event["type"] == "status":
                print(f"  Status: {event['message']}")
            elif event["type"] == "thinking":
                print(f"  Thinking: {event['content'][:100]}...")
            elif event["type"] == "complete":
                result = event["result"]
                print(f"\nAnalysis Complete:")
                print(f"   Error: {result.get('error_type')}")
                print(f"   Root Cause: {result.get('root_cause', '')[:100]}...")
                print(f"   Confidence: {result.get('fix_confidence', 0):.0%}")
            elif event["type"] == "error":
                print(f"\nError: {event['message']}")

    asyncio.run(test_agent())
