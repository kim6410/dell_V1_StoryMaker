# -*- coding: utf-8 -*-
"""Pure mode selection for Gate 4.

The selector only decides whether a requested mode is eligible. It never calls
an API, Worker, database, or production module.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.integration.feature_flags import IntegrationFeatureFlags
from app.integration.integration_models import GenerationMode


@dataclass(frozen=True)
class SelectionDecision:
    allowed: bool
    requested_mode: GenerationMode
    selected_mode: GenerationMode | None
    reason: str


class GenerationSelector:
    @staticmethod
    def determine_mode(
        requested_mode: GenerationMode,
        flags: IntegrationFeatureFlags,
    ) -> SelectionDecision:
        if requested_mode is GenerationMode.STAGED:
            if not flags.enable_stage_generation:
                return SelectionDecision(
                    allowed=False,
                    requested_mode=requested_mode,
                    selected_mode=None,
                    reason="ENABLE_STAGE_GENERATION is OFF",
                )
            if not flags.enable_stage_worker:
                return SelectionDecision(
                    allowed=False,
                    requested_mode=requested_mode,
                    selected_mode=None,
                    reason="ENABLE_STAGE_WORKER is OFF",
                )
            return SelectionDecision(
                allowed=True,
                requested_mode=requested_mode,
                selected_mode=GenerationMode.STAGED,
                reason="staged mode is eligible for future wiring",
            )

        if not flags.enable_oneclick_generation:
            return SelectionDecision(
                allowed=False,
                requested_mode=requested_mode,
                selected_mode=None,
                reason="ENABLE_ONECLICK_GENERATION is OFF",
            )

        return SelectionDecision(
            allowed=True,
            requested_mode=requested_mode,
            selected_mode=GenerationMode.ONECLICK,
            reason="oneclick mode is eligible for future wiring",
        )
