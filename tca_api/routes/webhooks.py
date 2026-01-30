"""
GitHub Webhook Handler
Receives PR events to update learning system
"""

import hmac
import hashlib
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, Header

from ..models import WebhookEvent

# Import shared memory system
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ..shared import memory_system

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# GitHub webhook secret (set in .env)
import os

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload: Request body bytes
        signature: X-Hub-Signature-256 header value

    Returns:
        True if signature is valid
    """
    if not GITHUB_WEBHOOK_SECRET:
        # Skip verification in dry-run mode
        return True

    if not signature:
        return False

    # GitHub uses HMAC SHA256
    expected_signature = (
        "sha256="
        + hmac.new(
            GITHUB_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected_signature, signature)


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    """
    Handle GitHub webhook events.

    Learning loop:
    1. PR merged → Boost confidence for that fix pattern
    2. PR rejected → Create anti-pattern

    Args:
        request: FastAPI request with webhook payload
        x_hub_signature_256: GitHub signature header
        x_github_event: GitHub event type header

    Returns:
        Success message
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Only handle pull_request events
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"Event type {x_github_event} not handled"}

    # Extract event data
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_title = pr.get("title", "")
    pr_body = pr.get("body", "")
    merged = pr.get("merged", False)

    # Only handle closed PRs (merged or rejected)
    if action != "closed":
        return {"status": "ignored", "reason": f"Action {action} not handled"}

    # Check if this is a TCA-generated PR (contains "Sentry" in title or body)
    is_tca_pr = "sentry" in pr_title.lower() or "sentry" in pr_body.lower()

    if not is_tca_pr:
        return {"status": "ignored", "reason": "Not a TCA-generated PR"}

    # Extract error type and fix approach from PR body
    # (Would parse structured format in production)
    error_type = _extract_error_type(pr_body)
    fix_approach = _extract_fix_approach(pr_body)

    if merged:
        # PR was merged - boost confidence
        memory_system.update_on_pr_merged(
            error_type=error_type,
            fix_approach=fix_approach,
            pr_number=pr_number,
        )

        return {
            "status": "learned",
            "type": "success",
            "pr_number": pr_number,
            "message": f"Boosted confidence for {error_type}",
        }
    else:
        # PR was closed without merge - create anti-pattern
        # Extract rejection reason (would be from PR comments in production)
        reason = "PR closed without merge"

        memory_system.update_on_pr_rejected(
            error_type=error_type,
            fix_approach=fix_approach,
            reason=reason,
            pr_number=pr_number,
        )

        return {
            "status": "learned",
            "type": "antipattern",
            "pr_number": pr_number,
            "message": f"Created anti-pattern for {error_type}",
        }


def _extract_error_type(pr_body: str) -> str:
    """
    Extract error type from PR body.

    Args:
        pr_body: PR description text

    Returns:
        Error type (e.g., "TypeError", "AttributeError")
    """
    # Simple extraction - look for common error types
    common_errors = [
        "TypeError",
        "AttributeError",
        "KeyError",
        "ValueError",
        "IndexError",
        "NameError",
        "ZeroDivisionError",
    ]

    for error_type in common_errors:
        if error_type in pr_body:
            return error_type

    return "Unknown"


def _extract_fix_approach(pr_body: str) -> str:
    """
    Extract fix approach from PR body.

    Args:
        pr_body: PR description text

    Returns:
        Brief description of fix approach
    """
    # Look for "Fix:" or "Fix Explanation:" section
    if "Fix:" in pr_body:
        lines = pr_body.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("**Fix:"):
                # Get next non-empty line
                if i + 1 < len(lines):
                    return lines[i + 1].strip()[:100]

    # Fallback - use first 100 chars of body
    return pr_body[:100]


# Test endpoint (only in development)
@router.post("/github/test")
async def test_webhook():
    """
    Test webhook handler without GitHub.

    Useful for local testing.
    """
    # Simulate PR merged event
    memory_system.update_on_pr_merged(
        error_type="AttributeError",
        fix_approach="Add null check before accessing attribute",
        pr_number=999,
    )

    return {
        "status": "test_success",
        "message": "Simulated PR merge, check memory system stats",
    }
