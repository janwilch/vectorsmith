"""Build ``CallContext`` from an HTTP request (headers + optional claims)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from vectorsmith_core.api import CallContext
from vectorsmith_core.security.tenancy import bind_tenancy
from vectorsmith_core.tds.models import TenancyConfig


def call_context_from_request(
    *,
    tenancy: TenancyConfig,
    headers: Mapping[str, str] | None = None,
    claims: Mapping[str, Any] | None = None,
    principal: str | None = None,
    request_id: str | None = None,
) -> CallContext:
    """Resolve request-scoped tenancy. Claims come from auth (Feature 5)."""
    ctx = CallContext(
        request_id=request_id or str(uuid.uuid4()),
        principal=principal,
        claims=dict(claims or {}),
    )
    bind_tenancy(tenancy, ctx, headers=headers)
    return ctx
