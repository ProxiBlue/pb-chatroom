"""Pydantic v2 models and JSON loader for responders.json config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Trigger sub-model (responder)
# ---------------------------------------------------------------------------


class TriggerConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    from_pattern: str = ''
    subject_keywords: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ClaudeInvocation sub-model (responder)
# ---------------------------------------------------------------------------


class ClaudeInvocationConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    cwd: str = ''
    model: str = ''
    extra_args: list[str] = Field(default_factory=list)
    system_prompt_addendum: str = ''


# ---------------------------------------------------------------------------
# Budget sub-model (responder)
# ---------------------------------------------------------------------------


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    max_invocations_per_hour: int = Field(ge=0, default=0)
    max_invocations_per_day: int = Field(ge=0, default=0)


# ---------------------------------------------------------------------------
# GhPolling sub-model (responder)
# ---------------------------------------------------------------------------


class GhPollingConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    repos: list[str] = Field(default_factory=list)
    poll_interval_minutes: int = 5
    eligible_label_filter: list[str] = Field(default_factory=list)
    min_age_minutes: int = 10


# ---------------------------------------------------------------------------
# Responder record
# ---------------------------------------------------------------------------


class ResponderConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    claude_invocation: ClaudeInvocationConfig = Field(default_factory=ClaudeInvocationConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    archive_on_ack: bool = False
    gh_polling: GhPollingConfig | None = None


# ---------------------------------------------------------------------------
# ActiveWindow sub-model (broadcaster)
# ---------------------------------------------------------------------------


class ActiveWindowConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    start_hour_local: int = Field(ge=0, le=23)
    end_hour_local: int = Field(ge=0, le=23)


# ---------------------------------------------------------------------------
# Broadcaster record
# ---------------------------------------------------------------------------


class BroadcasterConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    idle_threshold_minutes: int = 0
    max_per_day: int = 0
    min_hours_between: int = 0
    active_window: ActiveWindowConfig | None = None
    broadcast_to: list[str] = Field(default_factory=list)
    prompt_subject: str = ''
    prompt_body: str = ''
    schedule_cron: str = ''


# ---------------------------------------------------------------------------
# Archiver record
# ---------------------------------------------------------------------------


class ArchiverConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    enabled: bool = False
    graphiti_group_id_resolution: str = ''
    group_id_map: dict[str, str] = Field(default_factory=dict)
    max_thread_chars: int = 0
    exclude_test_subjects: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------


class RespondersConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    responders: dict[str, ResponderConfig] = Field(default_factory=dict)
    broadcasters: dict[str, BroadcasterConfig] = Field(default_factory=dict)
    archivers: dict[str, ArchiverConfig] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNDERSCORE_PREFIX = '_'


def _strip_comment_keys(data: Any) -> Any:
    """Recursively remove keys prefixed with '_' from dicts."""
    if isinstance(data, dict):
        return {
            k: _strip_comment_keys(v)
            for k, v in data.items()
            if not k.startswith(_UNDERSCORE_PREFIX)
        }
    if isinstance(data, list):
        return [_strip_comment_keys(item) for item in data]
    return data


def _extract_archiver_group_id_map(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Pull _group_id_map from each archiver record before stripping underscore keys."""
    archivers_raw = raw_data.get('archivers', {})
    for _key, value in archivers_raw.items():
        if isinstance(value, dict) and '_group_id_map' in value:
            value['group_id_map'] = value['_group_id_map']
    return raw_data


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_responders_config(path: Path) -> RespondersConfig:
    """Load and validate *responders.json* from *path*, returning a typed config."""
    raw: Any = json.loads(path.read_text())
    # Lift _group_id_map → group_id_map BEFORE stripping underscored keys
    raw = _extract_archiver_group_id_map(raw)
    cleaned = _strip_comment_keys(raw)
    return RespondersConfig.model_validate(cleaned)
