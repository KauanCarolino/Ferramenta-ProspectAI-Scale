"""Adapters de canais externos."""

from adapters.instagram import (
    AccountStatusInfo,
    InboxReply,
    InstagrapiAdapter,
    InstagramAdapter,
    LoginResult,
    SendResult,
    StubInstagramAdapter,
    get_instagram_adapter,
)

__all__ = [
    "AccountStatusInfo",
    "InboxReply",
    "InstagrapiAdapter",
    "InstagramAdapter",
    "LoginResult",
    "SendResult",
    "StubInstagramAdapter",
    "get_instagram_adapter",
]
