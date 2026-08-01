"""Schemas Pydantic."""

from schemas.account import (
    AccountAuthResponse,
    AccountChallengeRequest,
    AccountCreate,
    AccountLoginRequest,
    AccountRead,
    AccountUpdate,
    InboxPollResult,
)
from schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate
from schemas.common import HealthResponse, MessageResponse
from schemas.dashboard import DashboardSummary
from schemas.importer import ImportConfirmRequest, ImportPreviewResponse, ImportRejectedRow
from schemas.lead import LeadCreate, LeadRead, LeadUpdate
from schemas.log import LogRead
from schemas.template import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateRead,
    TemplateUpdate,
)

__all__ = [
    "AccountAuthResponse",
    "AccountChallengeRequest",
    "AccountCreate",
    "AccountLoginRequest",
    "AccountRead",
    "AccountUpdate",
    "InboxPollResult",
    "CampaignCreate",
    "CampaignRead",
    "CampaignUpdate",
    "DashboardSummary",
    "HealthResponse",
    "ImportConfirmRequest",
    "ImportPreviewResponse",
    "ImportRejectedRow",
    "LeadCreate",
    "LeadRead",
    "LeadUpdate",
    "LogRead",
    "MessageResponse",
    "TemplateCreate",
    "TemplatePreviewRequest",
    "TemplatePreviewResponse",
    "TemplateRead",
    "TemplateUpdate",
]
