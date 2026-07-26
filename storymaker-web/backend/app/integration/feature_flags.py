# -*- coding: utf-8 -*-
"""StoryMaker Gate 4 integration feature flags.

This module is intentionally side-effect free. It does not register routers,
start workers, access databases, or call generation APIs.
All Gate 4 flags default to OFF until an explicit production approval.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _read_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class IntegrationFeatureFlags:
    enable_stage_generation: bool = False
    enable_oneclick_generation: bool = False
    enable_stage_ui: bool = False
    enable_stage_worker: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "IntegrationFeatureFlags":
        source = os.environ if env is None else env
        return cls(
            enable_stage_generation=_read_bool(
                source, "STORYMAKER_ENABLE_STAGE_GENERATION"
            ),
            enable_oneclick_generation=_read_bool(
                source, "STORYMAKER_ENABLE_ONECLICK_GENERATION"
            ),
            enable_stage_ui=_read_bool(source, "STORYMAKER_ENABLE_STAGE_UI"),
            enable_stage_worker=_read_bool(
                source, "STORYMAKER_ENABLE_STAGE_WORKER"
            ),
        )

    def as_dict(self) -> dict[str, bool]:
        return {
            "ENABLE_STAGE_GENERATION": self.enable_stage_generation,
            "ENABLE_ONECLICK_GENERATION": self.enable_oneclick_generation,
            "ENABLE_STAGE_UI": self.enable_stage_ui,
            "ENABLE_STAGE_WORKER": self.enable_stage_worker,
        }


# Snapshot used only by code that explicitly imports it. No runtime wiring exists.
FLAGS = IntegrationFeatureFlags.from_env()


def get_flags_status() -> dict[str, bool]:
    return FLAGS.as_dict()
