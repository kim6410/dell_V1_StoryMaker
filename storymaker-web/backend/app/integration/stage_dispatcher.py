# -*- coding: utf-8 -*-
"""Disconnected GenerationDispatcher for StoryMaker Gate 4.

This module is an integration seam only. It must not call the one-click API,
the staged API, a Worker, the production database, or any network endpoint.
Actual execution is deliberately deferred to Gate 5 approval.
"""
from __future__ import annotations

from app.integration.feature_flags import FLAGS, IntegrationFeatureFlags
from app.integration.generation_selector import GenerationSelector
from app.integration.integration_models import (
    DispatcherRequest,
    DispatcherResponse,
    DispatchStatus,
)


class GenerationDispatcher:
    def __init__(self, flags: IntegrationFeatureFlags | None = None) -> None:
        self._flags = FLAGS if flags is None else flags

    def preview(self, request: DispatcherRequest) -> DispatcherResponse:
        """Return the routing decision without executing generation."""
        decision = GenerationSelector.determine_mode(
            request.generation_mode,
            self._flags,
        )

        if not decision.allowed:
            return DispatcherResponse(
                ok=False,
                requested_mode=decision.requested_mode,
                selected_mode=None,
                status=DispatchStatus.BLOCKED_BY_FLAG,
                dispatch_executed=False,
                job_id=None,
                reason=decision.reason,
            )

        return DispatcherResponse(
            ok=True,
            requested_mode=decision.requested_mode,
            selected_mode=decision.selected_mode,
            status=DispatchStatus.READY_FOR_FUTURE_WIRING,
            dispatch_executed=False,
            job_id=None,
            reason=f"{decision.reason}; Gate 4 does not execute generation",
        )

    def dispatch(self, request: DispatcherRequest) -> DispatcherResponse:
        """Compatibility entry point that remains non-executing in Gate 4."""
        result = self.preview(request)
        if not result.ok:
            return result

        return DispatcherResponse(
            ok=True,
            requested_mode=result.requested_mode,
            selected_mode=result.selected_mode,
            status=DispatchStatus.PREVIEW_ONLY,
            dispatch_executed=False,
            job_id=None,
            reason=(
                "Gate 4 dispatcher is disconnected; no API, Worker, database, "
                "or job queue was called"
            ),
        )
