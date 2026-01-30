"""
Pydantic Models for TCA RCA API
Request and response schemas
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class RCARequest(BaseModel):
    """Request to analyze a Sentry issue."""

    issue_id: str = Field(..., description="Sentry issue ID")
    sentry_org: Optional[str] = Field(None, description="Sentry organization slug")

    class Config:
        json_schema_extra = {
            "example": {
                "issue_id": "1234567890",
                "sentry_org": "altimate-inc",
            }
        }


class ApprovalRequest(BaseModel):
    """Request to approve/reject a proposed fix."""

    approved: bool = Field(..., description="Whether the fix is approved")
    comment: Optional[str] = Field(None, description="Optional comment")

    class Config:
        json_schema_extra = {
            "example": {
                "approved": True,
                "comment": "LGTM, let's proceed",
            }
        }


class WebhookEvent(BaseModel):
    """GitHub webhook event."""

    action: str = Field(..., description="Webhook action (opened, closed, etc)")
    pull_request: Dict[str, Any] = Field(..., description="PR data")
    repository: Dict[str, Any] = Field(..., description="Repository data")


# ============================================================================
# Response Models
# ============================================================================


class RCAAnalysisResponse(BaseModel):
    """Response after starting an analysis."""

    analysis_id: str = Field(..., description="Unique analysis ID")
    status: str = Field(..., description="Current status")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "abc123",
                "status": "analyzing",
                "created_at": "2026-01-28T10:00:00Z",
            }
        }


class IssueInfo(BaseModel):
    """Information about same-file issues found."""

    line: int
    pattern: str
    needs_fix: bool


class Evidence(BaseModel):
    """Evidence collected during RCA analysis from various platforms."""

    signoz_metrics: Optional[Dict[str, Any]] = Field(None, description="APM metrics from SignOz")
    posthog_sessions: Optional[Dict[str, Any]] = Field(None, description="User session data from PostHog")
    aws_logs: Optional[Dict[str, Any]] = Field(None, description="Infrastructure logs from AWS CloudWatch")
    github_context: Optional[Dict[str, Any]] = Field(None, description="Related code context from GitHub")

    class Config:
        json_schema_extra = {
            "example": {
                "signoz_metrics": {
                    "service": "backend-api",
                    "error_rate": 0.15,
                    "latency_p99": 2500
                },
                "posthog_sessions": {
                    "affected_users": 45,
                    "session_recordings": ["rec_123", "rec_456"]
                },
                "aws_logs": {
                    "log_group": "/aws/lambda/payment-processor",
                    "error_count": 23
                }
            }
        }


class RCAResult(BaseModel):
    """Complete RCA analysis result."""

    issue_id: str
    sentry_url: str
    root_cause: str
    fix_explanation: str
    fix_approach: str
    file_path: str
    function_name: str
    same_file_issues: List[IssueInfo]
    codebase_issues: List[str]
    related_sentry_issues: List[str]
    fix_code: str
    test_code: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    analysis_time_seconds: float
    frontend_impact: str  # "YES" or "NO"
    requires_approval: bool
    learned_context: str

    # Evidence fields (collected during analysis)
    evidence: Optional[Dict[str, Any]] = Field(None, description="Evidence collected from infrastructure/user platforms")
    infrastructure_correlation: Optional[float] = Field(None, ge=0.0, le=1.0, description="How strongly this issue correlates with infrastructure problems")
    user_impact_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Estimated user impact score")

    class Config:
        json_schema_extra = {
            "example": {
                "issue_id": "1234567890",
                "sentry_url": "https://sentry.io/issues/1234567890/",
                "root_cause": "TypeError occurs because...",
                "fix_explanation": "Add null check...",
                "fix_approach": "Defensive programming",
                "file_path": "app/service/queries.py",
                "function_name": "get_data",
                "same_file_issues": [],
                "codebase_issues": [],
                "related_sentry_issues": [],
                "fix_code": "def get_data()...",
                "test_code": "def test_get_data()...",
                "confidence": 0.85,
                "analysis_time_seconds": 4.5,
                "frontend_impact": "NO",
                "requires_approval": True,
                "learned_context": "Learned patterns...",
            }
        }


class HistoryItem(BaseModel):
    """History item for past analyses."""

    id: str
    issue_id: str
    created_at: datetime
    status: str  # "pending", "success", "failed"
    result: Optional[RCAResult] = None
    error: Optional[str] = None


class StatsResponse(BaseModel):
    """Learning system statistics."""

    total_patterns: int
    total_antipatterns: int
    high_confidence_patterns: int
    total_memories: int = 0
    mode: Optional[str] = None  # "MOCK" or None for real Mem0

    class Config:
        json_schema_extra = {
            "example": {
                "total_patterns": 42,
                "total_antipatterns": 8,
                "high_confidence_patterns": 35,
                "total_memories": 50,
                "mode": "MOCK",
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2026-01-28T10:00:00Z",
                "version": "1.0.0",
            }
        }


# ============================================================================
# SSE Event Models (for streaming)
# ============================================================================


class ProgressEvent(BaseModel):
    """Progress update event."""

    type: str = "progress"
    data: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "type": "progress",
                "data": {
                    "phase": "Phase 1.1",
                    "message": "Gathering bug information",
                    "step": 1,
                    "total": 10,
                },
            }
        }


class ResultEvent(BaseModel):
    """Result event with complete analysis."""

    type: str = "result"
    data: RCAResult


class ErrorEvent(BaseModel):
    """Error event."""

    type: str = "error"
    data: Dict[str, str]

    class Config:
        json_schema_extra = {
            "example": {
                "type": "error",
                "data": {
                    "message": "Failed to fetch Sentry issue",
                    "issue_id": "1234567890",
                },
            }
        }
