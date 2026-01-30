"""
RCA API Routes
Endpoints for root cause analysis
"""

import uuid
import json
import asyncio
from typing import Dict, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from ..models import (
    RCARequest,
    RCAAnalysisResponse,
    RCAResult,
    HistoryItem,
    StatsResponse,
)

# Import TCA core
import sys
from pathlib import Path

# Add parent directory to path to import tca_core
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tca_core.rca_agent import RCAAgent

# Import shared memory system
from ..shared import memory_system

router = APIRouter(prefix="/api/rca", tags=["RCA"])

# In-memory storage for analyses (replace with DB in production)
analyses: Dict[str, Dict] = {}

# Store running tasks and agents so we can cancel them
running_tasks: Dict[str, asyncio.Task] = {}
running_agents: Dict[str, 'RCAAgent'] = {}  # Track agent instances for cancellation


@router.post("/analyze", response_model=RCAAnalysisResponse)
async def start_analysis(request: RCARequest):
    """
    Start RCA analysis for a Sentry issue.

    Phases 1-4 of fix-sentry-bug.md workflow:
    - Gather bug information
    - Research best practices
    - Impact analysis
    - Present findings

    Returns analysis ID for streaming progress.
    """
    # Generate unique analysis ID
    analysis_id = str(uuid.uuid4())

    # Store analysis info
    analyses[analysis_id] = {
        "id": analysis_id,
        "issue_id": request.issue_id,
        "sentry_org": request.sentry_org,
        "status": "analyzing",
        "created_at": datetime.utcnow(),
        "result": None,
        "error": None,
    }

    # Start analysis in background and store task reference
    task = asyncio.create_task(_run_analysis(analysis_id, request))
    running_tasks[analysis_id] = task

    return RCAAnalysisResponse(
        analysis_id=analysis_id,
        status="analyzing",
        created_at=datetime.utcnow(),
    )


async def _run_analysis(analysis_id: str, request: RCARequest):
    """Run analysis in background."""
    agent = None
    try:
        agent = RCAAgent(memory_system=memory_system)

        # Store agent reference so we can cancel it
        running_agents[analysis_id] = agent

        # Store events for SSE streaming
        analyses[analysis_id]["events"] = []

        async for event in agent.analyze_issue(
            request.issue_id, request.sentry_org
        ):
            # Check if cancellation was requested
            if agent._cancelled:
                print(f"🛑 Analysis {analysis_id}: Stopping due to cancellation")
                analyses[analysis_id]["error"] = "Analysis cancelled by user - no more API calls"
                analyses[analysis_id]["status"] = "cancelled"
                break  # Stop consuming events - this stops API calls!

            # Store event for streaming
            analyses[analysis_id]["events"].append(event)

            if event["type"] == "result":
                analyses[analysis_id]["result"] = event["data"]
                analyses[analysis_id]["status"] = "completed"
            elif event["type"] == "error":
                analyses[analysis_id]["error"] = event["data"]["message"]
                analyses[analysis_id]["status"] = "failed"

    except asyncio.CancelledError:
        # Task was cancelled by user
        if agent:
            agent.cancel()  # Signal the agent to stop
        analyses[analysis_id]["error"] = "Analysis cancelled by user"
        analyses[analysis_id]["status"] = "cancelled"
        print(f"⚠️ Analysis {analysis_id} cancelled by user")
        raise  # Re-raise to properly cancel the task
    except Exception as e:
        analyses[analysis_id]["error"] = str(e)
        analyses[analysis_id]["status"] = "failed"
    finally:
        # Clean up references
        if analysis_id in running_tasks:
            del running_tasks[analysis_id]
        if analysis_id in running_agents:
            del running_agents[analysis_id]


@router.get("/stream/{analysis_id}")
async def stream_analysis(analysis_id: str):
    """
    Stream analysis progress via Server-Sent Events (SSE).

    Returns real-time progress updates as they happen.
    """
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    async def event_generator():
        """Generate SSE events from stored analysis events."""
        analysis = analyses[analysis_id]
        sent_count = 0

        # Stream events as they arrive
        while True:
            events = analysis.get("events", [])

            # Send any new events
            for event in events[sent_count:]:
                yield {
                    "event": "message",
                    "data": json.dumps(event),
                }
                sent_count += 1

                # Check if analysis is complete
                if event["type"] in ["result", "error"]:
                    return

            # Check if analysis was cancelled or failed before any events
            if analysis["status"] in ["cancelled", "failed"] and not events:
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "error",
                        "data": {"message": analysis.get("error", "Unknown error")},
                    }),
                }
                return

            # Check if analysis was cancelled during streaming
            if analysis["status"] == "cancelled":
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "error",
                        "data": {"message": "Analysis cancelled by user"},
                    }),
                }
                return

            # Wait a bit before checking for new events
            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())


@router.post("/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str):
    """
    Cancel a running analysis.

    This stops the Claude agent process to prevent wasting credits.

    Returns:
        Status of the cancellation
    """
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis = analyses[analysis_id]

    # Check if analysis is still running
    if analysis["status"] not in ["analyzing"]:
        return {
            "status": "not_running",
            "message": f"Analysis is {analysis['status']}, cannot cancel",
            "analysis_id": analysis_id
        }

    # Check if we have a task reference
    if analysis_id not in running_tasks:
        # Task already completed or was never stored
        analysis["status"] = "cancelled"
        return {
            "status": "already_stopped",
            "message": "Analysis task already completed or not found",
            "analysis_id": analysis_id
        }

    # First, signal the agent to stop (prevents more API calls)
    if analysis_id in running_agents:
        agent = running_agents[analysis_id]
        agent.cancel()
        print(f"🛑 Signaled agent {analysis_id} to stop - no more API calls will be made")

    # Then cancel the running task
    task = running_tasks[analysis_id]
    task.cancel()

    # Update status
    analysis["status"] = "cancelled"
    analysis["error"] = "Cancelled by user - API calls stopped"

    print(f"🛑 Cancelled analysis {analysis_id}")

    return {
        "status": "cancelled",
        "message": "Analysis cancelled successfully. Agent stopped - no more API calls or credit usage.",
        "analysis_id": analysis_id
    }


@router.get("/history", response_model=List[HistoryItem])
async def get_history(limit: int = 50):
    """
    Get history of past analyses.

    Args:
        limit: Maximum number of items to return

    Returns:
        List of past analyses with results
    """
    # Convert analyses dict to sorted list
    history = []
    for analysis_id, data in analyses.items():
        history.append(
            HistoryItem(
                id=data["id"],
                issue_id=data["issue_id"],
                created_at=data["created_at"],
                status=data["status"],
                result=data.get("result"),
                error=data.get("error"),
            )
        )

    # Sort by created_at descending
    history.sort(key=lambda x: x.created_at, reverse=True)

    return history[:limit]


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get learning system statistics.

    Returns:
        Statistics about learned patterns and anti-patterns
    """
    stats = memory_system.get_stats()
    return StatsResponse(**stats)


@router.get("/{analysis_id}/result", response_model=RCAResult)
async def get_result(analysis_id: str):
    """
    Get analysis result by ID.

    Args:
        analysis_id: Analysis ID from start_analysis

    Returns:
        Complete RCA result

    Raises:
        404: If analysis not found or not completed
    """
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis = analyses[analysis_id]

    if analysis["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed (status: {analysis['status']})",
        )

    if not analysis.get("result"):
        raise HTTPException(status_code=404, detail="Result not available")

    return RCAResult(**analysis["result"])


@router.post("/{analysis_id}/create-pr")
async def create_pr(analysis_id: str, background_tasks: BackgroundTasks):
    """
    Create GitHub PR with the analyzed fix.

    Phases 5-7 of fix-sentry-bug.md workflow:
    - Implement fix
    - Write tests
    - Create PR

    Returns immediately with "creating" status. Use GET /{analysis_id} to check PR creation status.
    """
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis = analyses[analysis_id]

    if analysis["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed (status: {analysis['status']})",
        )

    result = analysis.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not available")

    # Check confidence threshold
    if result.get("fix_confidence", 0) < 0.5:
        raise HTTPException(
            status_code=400,
            detail=f"Fix confidence too low ({result['fix_confidence']:.0%}). Manual review required.",
        )

    # Check if PR is already being created or was created
    if analysis.get("pr_status") == "creating":
        return {
            "status": "creating",
            "message": "PR creation already in progress. Check status later."
        }

    if analysis.get("pr_url"):
        return {
            "status": "exists",
            "pr_url": analysis["pr_url"],
            "pr_number": analysis["pr_number"],
            "message": "PR already exists"
        }

    # Mark as creating
    analysis["pr_status"] = "creating"

    # Run PR creation in background to avoid async context issues
    background_tasks.add_task(_create_pr_background, analysis_id, result)

    return {
        "status": "creating",
        "message": "PR creation started. Check status in a few moments.",
        "analysis_id": analysis_id
    }


async def _create_pr_background(analysis_id: str, result: dict):
    """Background task to create PR without async context issues."""
    try:
        import asyncio

        # Create new event loop for this background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create PR using RCA agent
            agent = RCAAgent(memory_system=memory_system)
            pr_result = loop.run_until_complete(agent.create_github_pr(result))

            # Update analysis with PR info
            analyses[analysis_id]["pr_url"] = pr_result["url"]
            analyses[analysis_id]["pr_number"] = pr_result["number"]
            analyses[analysis_id]["pr_branch"] = pr_result["branch"]
            analyses[analysis_id]["pr_status"] = "created"

            print(f"✅ PR created successfully: {pr_result['url']}")

        finally:
            loop.close()

    except Exception as e:
        analyses[analysis_id]["pr_status"] = "failed"
        analyses[analysis_id]["pr_error"] = str(e)
        print(f"❌ PR creation failed: {str(e)}")


@router.get("/{analysis_id}/pr-status")
async def get_pr_status(analysis_id: str):
    """
    Check the status of a GitHub PR created for this analysis.

    Returns:
        PR status including state, checks, and merge readiness
    """
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis = analyses[analysis_id]

    # Check if PR was created
    pr_number = analysis.get("pr_number")
    if not pr_number:
        raise HTTPException(
            status_code=404,
            detail="No PR created for this analysis. Click 'Create PR' first.",
        )

    try:
        # Check PR status using RCA agent
        agent = RCAAgent(memory_system=memory_system)
        pr_status = await agent.check_pr_status(pr_number)

        # Update analysis with latest PR status
        analyses[analysis_id]["pr_status"] = pr_status
        analyses[analysis_id]["pr_last_checked"] = datetime.utcnow().isoformat()

        return pr_status

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check PR status: {str(e)}"
        )
