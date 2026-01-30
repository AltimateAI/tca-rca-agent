"""
Discovery API Routes
Endpoints for proactive Sentry issue discovery and scanning
"""

import os
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from collections import defaultdict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..models import RCARequest
from .rca import start_analysis, analyses

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])

# Priority queue for discovered issues
issue_queue: List[dict] = []


class ScanRequest(BaseModel):
    """Request to scan Sentry for issues."""
    timeframe: str = "24h"  # 24h, 7d, 30d
    organization: Optional[str] = None
    min_occurrences: int = 10  # Minimum error count to consider
    auto_analyze: bool = False  # Auto-start analysis for high priority issues


class QueuedIssue(BaseModel):
    """Issue in the analysis queue."""
    issue_id: str
    priority: int
    error_count: int
    user_count: int
    last_seen: str
    title: str
    status: str  # queued | analyzing | completed | failed
    analysis_id: Optional[str] = None


def extract_error_type(title: str) -> str:
    """
    Extract error type from issue title.

    Examples:
    - "KeyError: 'user_id'" → "KeyError"
    - "TypeError: cannot unpack" → "TypeError"
    - "DatabaseError: connection failed" → "DatabaseError"
    - "TimeoutError" → "TimeoutError"
    - "Unknown error" → "Other"

    Returns:
        Error type string
    """
    # Common error patterns
    error_patterns = [
        r'(KeyError)',
        r'(TypeError)',
        r'(ValueError)',
        r'(AttributeError)',
        r'(IndexError)',
        r'(NameError)',
        r'(RuntimeError)',
        r'(DatabaseError|IntegrityError|OperationalError)',
        r'(TimeoutError|Timeout)',
        r'(ConnectionError|Connection)',
        r'(ValidationError)',
        r'(HTTPException|ApiError)',
    ]

    for pattern in error_patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            error_type = match.group(1)
            # Normalize similar errors
            if 'timeout' in error_type.lower():
                return 'TimeoutError'
            elif 'database' in error_type.lower() or 'integrity' in error_type.lower():
                return 'DatabaseError'
            elif 'connection' in error_type.lower():
                return 'ConnectionError'
            else:
                return error_type.title()

    return 'Other'


def group_issues_by_error_type(issues: List[dict]) -> Dict[str, List[dict]]:
    """
    Group issues by error type pattern for batch analysis with prompt caching.

    Groups:
    - KeyError → All issues with "KeyError" in title
    - TypeError → All issues with "TypeError" in title
    - DatabaseError → All DB-related errors
    - TimeoutError → All timeout-related errors
    - Other → Miscellaneous errors

    Returns:
        {"KeyError": [issue1, issue2], "TypeError": [issue3], ...}
    """
    groups = defaultdict(list)

    for issue in issues:
        title = issue.get('title', '')
        error_type = extract_error_type(title)
        groups[error_type].append(issue)

    return dict(groups)


def calculate_priority(issue: dict) -> int:
    """
    Calculate priority score for an issue.

    Algorithm:
    - Frequency: up to 50 points (1 point per 10 errors, max 500 errors)
    - User impact: up to 30 points (1 point per 10 users, max 300 users)
    - Recency: up to 20 points (max if last seen < 1 hour ago)

    Returns:
        Priority score (0-100)
    """
    score = 0

    # Frequency score (max 50 points)
    error_count = issue.get('count', 0)
    score += min(error_count / 10, 50)

    # User impact score (max 30 points)
    user_count = issue.get('userCount', 0)
    score += min(user_count / 10, 30)

    # Recency score (max 20 points)
    last_seen_str = issue.get('lastSeen')
    if last_seen_str:
        try:
            last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
            hours_ago = (datetime.now() - last_seen.replace(tzinfo=None)).total_seconds() / 3600
            recency_score = max(20 - hours_ago, 0)
            score += min(recency_score, 20)
        except:
            pass

    return int(score)


@router.post("/scan")
async def scan_sentry_issues(
    request: ScanRequest,
    background_tasks: BackgroundTasks
):
    """
    Scan Sentry for new issues in the specified timeframe.

    Args:
        request: Scan configuration

    Returns:
        {
            "queued": 15,
            "timeframe": "24h",
            "issues": [...]
        }
    """
    import requests
    import traceback

    try:
        # Calculate time range
        timeframe_hours = {
        "24h": 24,
        "7d": 168,
        "30d": 720
        }.get(request.timeframe, 24)

        start_time = datetime.utcnow() - timedelta(hours=timeframe_hours)
        end_time = datetime.utcnow()

        org = request.organization or os.getenv("SENTRY_ORG") or os.getenv("TCA_SENTRY_ORG")
        auth_token = os.getenv("SENTRY_AUTH_TOKEN") or os.getenv("TCA_SENTRY_AUTH_TOKEN")

        if not auth_token:
            raise HTTPException(status_code=500, detail="SENTRY_AUTH_TOKEN not configured")

        # Use Sentry REST API directly (more reliable than MCP for bulk queries)
        search_url = f"https://sentry.io/api/0/organizations/{org}/issues/"
        headers = {"Authorization": f"Bearer {auth_token}"}

        all_issues = []
        params = {
            "query": "is:unresolved",
            "start": start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "end": end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "sort": "freq",
            "limit": 100  # Fetch 100 per page
        }

        # Pagination loop
        max_pages = 10  # Limit to prevent excessive API calls
        page_count = 0

        while page_count < max_pages:
            print(f"🔍 Fetching Sentry issues page {page_count + 1}")
            print(f"   URL: {search_url}")
            print(f"   Params: {params}")

            response = requests.get(search_url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"❌ Sentry API error: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Sentry API error: {response.status_code} - {response.text[:200]}"
                )

            page_issues = response.json()
            print(f"📥 Received {len(page_issues)} issues on page {page_count + 1}")

            if not page_issues:
                break

            all_issues.extend(page_issues)
            page_count += 1

            # Check for pagination
            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header or 'results="true"' not in link_header:
                break  # No more pages

            # Extract cursor for next page
            import re
            match = re.search(r'cursor=([^>]+)>; rel="next"; results="true"', link_header)
            if not match:
                break

            params['cursor'] = match.group(1)

        # Transform to expected format
        print(f"✅ Total issues fetched from Sentry: {len(all_issues)}")

        issues = []
        for issue in all_issues:
            # Ensure numeric fields are integers
            count = issue.get('count', 0)
            user_count = issue.get('userCount', 0)

            issues.append({
                'id': issue.get('id'),
                'count': int(count) if count else 0,
                'userCount': int(user_count) if user_count else 0,
                'title': issue.get('title', 'Unknown'),
                'lastSeen': issue.get('lastSeen', '')
            })

        print(f"📋 Transformed {len(issues)} issues")
        if issues:
            print(f"   Sample issue counts: {[i['count'] for i in issues[:5]]}")

        # Filter by minimum occurrences
        filtered_issues = [
            issue for issue in issues
            if issue.get('count', 0) >= request.min_occurrences
        ]

        print(f"🔍 After filtering (min_occurrences >= {request.min_occurrences}): {len(filtered_issues)} issues")
        if not filtered_issues and issues:
            max_count = max([i['count'] for i in issues], default=0)
            print(f"   ℹ️  Highest issue count: {max_count} (< {request.min_occurrences})")

        # Calculate priorities
        for issue in filtered_issues:
            issue['priority'] = calculate_priority(issue)

        # Sort by priority (highest first)
        filtered_issues.sort(key=lambda x: x['priority'], reverse=True)

        # Group issues by error type for batch analysis
        issue_groups = group_issues_by_error_type(filtered_issues)
        print(f"📊 Grouped {len(filtered_issues)} issues into {len(issue_groups)} error types")
        for error_type, group in issue_groups.items():
            print(f"   - {error_type}: {len(group)} issues")

        # Add to queue
        queued_count = 0
        for issue in filtered_issues:
            # Check if already in queue or analyzing
            existing = next(
                (q for q in issue_queue if q['issue_id'] == issue['id']),
                None
            )

            if not existing:
                queued_issue = {
                    'issue_id': issue['id'],
                    'priority': issue['priority'],
                    'error_count': issue.get('count', 0),
                    'user_count': issue.get('userCount', 0),
                    'last_seen': issue.get('lastSeen', ''),
                    'title': issue.get('title', 'Unknown'),
                    'status': 'queued',
                    'analysis_id': None,
                    'queued_at': datetime.utcnow().isoformat()
                }
                issue_queue.append(queued_issue)
                queued_count += 1

        # Auto-analyze in batches by error type for prompt cache optimization
        if request.auto_analyze:
            for error_type, group_issues in issue_groups.items():
                # Filter high-priority issues within this group
                # Lower threshold for testing: priority >= 5 (captures most errors with >1 occurrence)
                high_priority = [
                    issue for issue in group_issues
                    if issue['priority'] >= 5 or issue.get('count', 0) >= 5
                ]

                if high_priority:
                    # Limit batch size to 5 issues per group for reasonable response time
                    batch = high_priority[:5]
                    print(f"🚀 Auto-analyzing {len(batch)} {error_type} issues in batch")

                    background_tasks.add_task(
                        _auto_analyze_batch,
                        error_type,
                        batch,
                        org
                    )

        # Return response after processing all issues
        return {
            "queued": queued_count,
            "total_found": len(filtered_issues),
            "timeframe": request.timeframe,
            "groups": {
                error_type: len(issues)
                for error_type, issues in issue_groups.items()
            },
            "issues": [
                {
                    "id": issue['id'],
                    "title": issue.get('title', 'Unknown'),
                    "priority": issue['priority'],
                    "error_count": issue.get('count', 0),
                    "user_count": issue.get('userCount', 0)
                }
                for issue in filtered_issues[:20]  # Return top 20
            ]
        }
    except Exception as e:
        print(f"Scan error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


async def _auto_analyze_batch(error_type: str, issues: List[dict], org: str):
    """
    Auto-analyze a batch of similar issues with prompt caching.

    This function uses the RCA agent's batch analysis method which optimizes
    for prompt caching - all issues of the same error type share cached context.

    Args:
        error_type: Common error type for this batch (e.g., "KeyError")
        issues: List of issue dicts with {id, title, count, priority, ...}
        org: Sentry organization
    """
    try:
        from tca_core.rca_agent import RCAAgent
        from tca_core.memory_system import MemorySystem

        print(f"🔄 Starting batch analysis for {len(issues)} {error_type} issues")

        # Initialize agent with memory system
        memory_system = MemorySystem()
        agent = RCAAgent(memory_system=memory_system)

        # Update queue status for all issues in batch
        for issue in issues:
            queued = next((q for q in issue_queue if q['issue_id'] == issue['id']), None)
            if queued:
                queued['status'] = 'analyzing'

        # Run batch analysis
        completed = 0
        failed = 0

        async for event in agent.analyze_issue_batch(issues, error_type, org):
            if event['type'] == 'issue_complete':
                issue_id = event['issue_id']
                result = event['result']

                # Store result in analyses dict
                analysis_id = f"batch_{error_type}_{issue_id}_{datetime.utcnow().timestamp()}"
                analyses[analysis_id] = {
                    'analysis_id': analysis_id,
                    'issue_id': issue_id,
                    'status': 'completed',
                    'result': result,
                    'created_at': datetime.utcnow().isoformat(),
                    'completed_at': datetime.utcnow().isoformat()
                }

                # Update queue
                queued = next((q for q in issue_queue if q['issue_id'] == issue_id), None)
                if queued:
                    queued['status'] = 'completed'
                    queued['analysis_id'] = analysis_id

                completed += 1

            elif event['type'] == 'issue_error':
                issue_id = event['issue_id']
                error_msg = event.get('error', 'Unknown error')

                # Update queue
                queued = next((q for q in issue_queue if q['issue_id'] == issue_id), None)
                if queued:
                    queued['status'] = 'failed'
                    queued['error'] = error_msg

                failed += 1

        print(f"✅ Batch analysis complete: {completed} succeeded, {failed} failed")

    except Exception as e:
        print(f"❌ Batch analysis error: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark all issues as failed
        for issue in issues:
            queued = next((q for q in issue_queue if q['issue_id'] == issue['id']), None)
            if queued:
                queued['status'] = 'failed'
                queued['error'] = f"Batch analysis failed: {str(e)}"


async def _auto_analyze_issue(issue_id: str, org: str, queued_issue: dict):
    """Auto-analyze a high priority issue."""
    try:
        # Update status
        queued_issue['status'] = 'analyzing'

        # Start analysis
        req = RCARequest(issue_id=issue_id, sentry_org=org)
        response = await start_analysis(req)

        # Update with analysis ID
        queued_issue['analysis_id'] = response.analysis_id

        # Wait for completion (check every 5 seconds for max 5 minutes)
        for _ in range(60):
            await asyncio.sleep(5)

            if response.analysis_id in analyses:
                analysis = analyses[response.analysis_id]
                if analysis['status'] in ['completed', 'failed']:
                    queued_issue['status'] = analysis['status']
                    break

    except Exception as e:
        queued_issue['status'] = 'failed'
        queued_issue['error'] = str(e)


@router.get("/queue", response_model=List[QueuedIssue])
async def get_queue(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    Get the current analysis queue.

    Args:
        status: Filter by status (queued | analyzing | completed | failed)
        limit: Maximum number of items to return

    Returns:
        List of queued issues sorted by priority
    """
    # Filter by status if provided
    filtered = issue_queue
    if status:
        filtered = [q for q in issue_queue if q['status'] == status]

    # Sort by priority (highest first)
    sorted_queue = sorted(filtered, key=lambda x: x['priority'], reverse=True)

    return sorted_queue[:limit]


@router.delete("/queue/{issue_id}")
async def remove_from_queue(issue_id: str):
    """
    Remove an issue from the queue.

    Args:
        issue_id: Sentry issue ID to remove

    Returns:
        {"removed": true}
    """
    global issue_queue

    original_len = len(issue_queue)
    issue_queue = [q for q in issue_queue if q['issue_id'] != issue_id]

    if len(issue_queue) == original_len:
        raise HTTPException(status_code=404, detail="Issue not found in queue")

    return {"removed": True}


@router.post("/queue/{issue_id}/analyze")
async def analyze_queued_issue(issue_id: str):
    """
    Start analysis for a queued issue.

    Args:
        issue_id: Sentry issue ID from queue

    Returns:
        {"analysis_id": "...", "status": "analyzing"}
    """
    # Find issue in queue
    queued = next(
        (q for q in issue_queue if q['issue_id'] == issue_id),
        None
    )

    if not queued:
        raise HTTPException(status_code=404, detail="Issue not found in queue")

    if queued['status'] != 'queued':
        raise HTTPException(
            status_code=400,
            detail=f"Issue already {queued['status']}"
        )

    # Start analysis
    import os
    org = os.getenv("SENTRY_ORG") or os.getenv("TCA_SENTRY_ORG")
    req = RCARequest(issue_id=issue_id, sentry_org=org)
    response = await start_analysis(req)

    # Update queue item
    queued['status'] = 'analyzing'
    queued['analysis_id'] = response.analysis_id

    return {
        "analysis_id": response.analysis_id,
        "status": "analyzing"
    }


class BootstrapRequest(BaseModel):
    """Request to bootstrap memory from historical issues."""
    projects: List[str] = ["altimate-backend", "altimate-frontend", "freemium-backend"]
    max_issues_per_project: int = 50
    min_occurrences: int = 20
    months_back: int = 6
    force: bool = False  # Force bootstrap even if done recently


@router.post("/bootstrap")
async def bootstrap_historical_patterns(request: BootstrapRequest):
    """
    Bootstrap memory system with patterns from historically resolved Sentry issues.

    This is a one-time operation (or runs every 6 months) to pre-seed the learning system
    with "golden patterns" from issues that have already been resolved in production.

    NOTE: This endpoint blocks until bootstrap completes (2-3 minutes).
    Only runs once every 6 months to avoid redundant work.

    Args:
        request: Bootstrap configuration

    Returns:
        {
            "status": "completed" | "skipped",
            "message": "...",
            "patterns_loaded": 127,
            "projects": [...],
            "elapsed_seconds": 142
        }
    """
    import sys
    from pathlib import Path
    import time
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from ..shared import memory_system
    from tca_core.historical_loader import HistoricalLoader

    # Check if bootstrap is needed
    if not request.force and not memory_system.check_bootstrap_needed():
        # Get tracker info
        tracker_path = memory_system._get_bootstrap_tracker_path()
        try:
            import json
            with open(tracker_path, "r") as f:
                tracker = json.load(f)

            return {
                "status": "skipped",
                "message": "Bootstrap done recently (< 6 months ago)",
                "last_bootstrap": tracker.get("last_bootstrap"),
                "patterns_loaded": tracker.get("patterns_loaded", 0),
                "projects": tracker.get("projects", [])
            }
        except:
            pass

    # Run bootstrap (await directly - this blocks the endpoint)
    start_time = time.time()

    print(f"\n🌱 Starting bootstrap from {len(request.projects)} projects...")

    # Load historical patterns using REST API (MCP doesn't expose commit data)
    from tca_core.historical_loader_rest import HistoricalLoaderREST
    loader = HistoricalLoaderREST()
    patterns = await loader.load_historical_patterns(
        projects=request.projects,
        max_issues_per_project=request.max_issues_per_project,
        min_occurrences=request.min_occurrences,
        months_back=request.months_back
    )

    if not patterns:
        print("⚠️  No historical patterns found")
        # Mark as complete to avoid retrying
        memory_system._mark_bootstrap_complete(0, request.projects)
        return {
            "status": "completed",
            "message": "No historical patterns found",
            "patterns_loaded": 0,
            "projects": request.projects,
            "elapsed_seconds": int(time.time() - start_time)
        }

    # Bootstrap memory system
    loaded_count = memory_system.bootstrap_from_historical_patterns(patterns)

    # Mark bootstrap complete
    memory_system._mark_bootstrap_complete(loaded_count, request.projects)

    elapsed = int(time.time() - start_time)
    print(f"\n✅ Bootstrap complete! Loaded {loaded_count} patterns in {elapsed}s")

    return {
        "status": "completed",
        "message": f"Successfully loaded {loaded_count} patterns from {len(request.projects)} projects",
        "patterns_loaded": loaded_count,
        "projects": request.projects,
        "elapsed_seconds": elapsed
    }


@router.get("/bootstrap/status")
async def get_bootstrap_status():
    """
    Get bootstrap status and history.

    Returns:
        {
            "last_bootstrap": "2026-01-15T10:30:00Z",
            "patterns_loaded": 127,
            "projects": ["altimate-backend", ...],
            "needs_bootstrap": false,
            "months_since_last": 2.3
        }
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from ..shared import memory_system

    tracker_path = memory_system._get_bootstrap_tracker_path()

    if not tracker_path.exists():
        return {
            "last_bootstrap": None,
            "patterns_loaded": 0,
            "projects": [],
            "needs_bootstrap": True,
            "months_since_last": None
        }

    try:
        import json
        with open(tracker_path, "r") as f:
            tracker = json.load(f)

        last_bootstrap = datetime.fromisoformat(tracker.get("last_bootstrap", ""))
        months_since = (datetime.utcnow() - last_bootstrap).days / 30

        return {
            "last_bootstrap": tracker.get("last_bootstrap"),
            "patterns_loaded": tracker.get("patterns_loaded", 0),
            "projects": tracker.get("projects", []),
            "needs_bootstrap": months_since >= 6,
            "months_since_last": round(months_since, 1)
        }

    except Exception as e:
        return {
            "error": str(e),
            "needs_bootstrap": True
        }
