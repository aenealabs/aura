"""
Bedrock model discovery for the ADR-015 model tiers.

A tier configured as ``auto`` (the default) resolves at service startup to the newest
ACTIVE Claude model of its family that this account can invoke in the deployment region,
so a fresh deployment uses current models rather than a list written into the code that
goes stale as models retire:

    fast      Claude Haiku
    accurate  Claude Sonnet
    maximum   Claude Opus

Models that are not invocable on demand are used through a system-defined inference
profile (the region's geography first, then global). Only models with known pricing are
chosen, because cost tracking and budgets must cover every live model.

Explicitly configured models always win over discovery: operators pin approved models in
the environment's Bedrock secret (ADR-088), and discovery never replaces a pinned model.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

AUTO = "auto"

# Discovery results per region, shared by everything in the process
_DISCOVERY_CACHE: dict[str, dict[str, str]] = {}


def discovered_models(region: str | None = None) -> dict[str, str]:
    """What discovery chose in this process: {tier: model ID} for the region (or any)."""
    if region and region in _DISCOVERY_CACHE:
        return dict(_DISCOVERY_CACHE[region])
    if region is None and len(_DISCOVERY_CACHE) == 1:
        return dict(next(iter(_DISCOVERY_CACHE.values())))
    return {}


# Tier value -> Claude family
TIER_FAMILIES: dict[str, str] = {
    "fast": "haiku",
    "accurate": "sonnet",
    "maximum": "opus",
}

_NEW_STYLE = re.compile(
    r"claude-(haiku|sonnet|opus|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?=-\d{8}|-v\d|:|$)"
    r"(?:-(\d{8}))?"
)
_OLD_STYLE = re.compile(r"claude-(\d+)(?:-(\d{1,2}))?-(haiku|sonnet|opus)(?:-(\d{8}))?")


@dataclass(frozen=True)
class ClaudeModel:
    """A Claude model ID parsed into family and version."""

    family: str
    major: int
    minor: int
    date: str  # YYYYMMDD, or "" for undated IDs

    @property
    def version(self) -> tuple[int, int]:
        return (self.major, self.minor)

    @property
    def key(self) -> str:
        """Family key used for pricing and request rules, e.g. ``claude-sonnet-4-5``."""
        minor = f"-{self.minor}" if self.minor else ""
        return f"claude-{self.family}-{self.major}{minor}"


def parse_claude_model(model_id: str) -> ClaudeModel | None:
    """Parse a Bedrock model or inference profile ID; None if it is not a Claude model.

    Handles current IDs (``anthropic.claude-sonnet-4-5-20250929-v1:0``,
    ``anthropic.claude-sonnet-5-5``, ``us.anthropic.claude-opus-5-5``) and the 3.x style
    (``anthropic.claude-3-5-sonnet-20240620-v1:0``).
    """
    match = _NEW_STYLE.search(model_id)
    if match:
        family, major, minor, date = match.groups()
        return ClaudeModel(family, int(major), int(minor or 0), date or "")
    match = _OLD_STYLE.search(model_id)
    if match:
        major, minor, family, date = match.groups()
        return ClaudeModel(family, int(major), int(minor or 0), date or "")
    return None


def _geo_prefixes(region: str) -> list[str]:
    """Inference profile prefixes to prefer for a region, most specific first."""
    if region.startswith("us-gov-"):
        return ["us-gov.", "global."]
    if region.startswith("us-") or region.startswith("ca-"):
        return ["us.", "global."]
    if region.startswith("eu-"):
        return ["eu.", "global."]
    if region.startswith("ap-"):
        return ["apac.", "global."]
    return ["global."]


def _list_inference_profiles(client: Any) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"typeEquals": "SYSTEM_DEFINED"}
    while True:
        page = client.list_inference_profiles(**kwargs)
        profiles.extend(page.get("inferenceProfileSummaries", []))
        token = page.get("nextToken")
        if not token:
            return profiles
        kwargs["nextToken"] = token


def _profile_for(
    model_id: str, profiles: list[dict[str, Any]], region: str
) -> str | None:
    """The system-defined inference profile that serves model_id, preferring the region's geography."""
    serving = [
        p
        for p in profiles
        if p.get("status", "ACTIVE") == "ACTIVE"
        and any(
            m.get("modelArn", "").endswith(f"foundation-model/{model_id}")
            for m in p.get("models", [])
        )
    ]
    for prefix in _geo_prefixes(region):
        for profile in serving:
            if profile.get("inferenceProfileId", "").startswith(prefix):
                return profile["inferenceProfileId"]
    return serving[0]["inferenceProfileId"] if serving else None


def discover_tier_models(
    client: Any, region: str, is_priced: Callable[[str], bool]
) -> dict[str, str]:
    """
    The newest invocable, priced Claude model for each tier, as {tier value: invoke ID}.

    Tiers with no suitable model are left out (the caller keeps its fallback).
    """
    summaries = client.list_foundation_models(
        byProvider="Anthropic", byOutputModality="TEXT"
    ).get("modelSummaries", [])
    profiles: list[dict[str, Any]] | None = None

    best: dict[str, tuple[tuple[int, int, str], str]] = {}
    for summary in summaries:
        model_id = summary.get("modelId", "")
        status = (summary.get("modelLifecycle") or {}).get("status", "ACTIVE")
        parsed = parse_claude_model(model_id)
        if parsed is None or status != "ACTIVE" or not is_priced(model_id):
            continue
        tiers = [t for t, family in TIER_FAMILIES.items() if family == parsed.family]
        if not tiers:
            continue
        types = summary.get("inferenceTypesSupported") or []
        if "ON_DEMAND" in types:
            invoke_id = model_id
        elif "INFERENCE_PROFILE" in types:
            if profiles is None:
                profiles = _list_inference_profiles(client)
            invoke_id = _profile_for(model_id, profiles, region) or ""
        else:
            invoke_id = ""
        if not invoke_id:
            continue
        rank = (parsed.major, parsed.minor, parsed.date)
        for tier in tiers:
            if tier not in best or rank > best[tier][0]:
                best[tier] = (rank, invoke_id)

    return {tier: invoke_id for tier, (_, invoke_id) in best.items()}
