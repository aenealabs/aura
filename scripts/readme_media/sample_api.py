"""Browser setup shared by the README screenshot and video scripts.

Sets the theme, skips the first-run onboarding, hides the dev-mode toolbar, and answers the
frontend's API calls without a backend: calls listed in SAMPLES get that sample data, and every
other call fails the way it does with no backend running, so each page shows the same
development fallbacks it shows on a laptop.
"""

import json
import subprocess
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def app_sample(module: str, name: str):
    """A sample object the frontend itself ships (e.g. in services/*MockData.js), read with Node
    so the screenshots stay in step with the app's own sample data."""
    path = FRONTEND / "src" / module
    script = f"const m = await import({json.dumps(str(path))}); console.log(JSON.stringify(m.{name}))"
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True,
                         text=True, check=True)
    return json.loads(out.stdout)

ONBOARDING_DONE = {
    "welcome_modal_dismissed": True, "tour_completed": True, "tour_skipped": True,
    "checklist_dismissed": True, "checklist_steps": {}, "dismissed_tooltips": [],
    "video_progress": {},
}

# The dashboard's headline cards have no development fallback, so they need a summary.
# The numbers agree with the rest of the sample platform (7 approvals, 156 open findings).
SAMPLES: dict[str, object] = {
    "/dashboard/summary": {
        "agents": {"active": 14, "trend": 8},
        "approvals": {"pending": 7, "trend": -12},
        "vulnerabilities": {"open": 156, "trend": -14},
        "patches": {"deployed": 892, "trend": 15},
        "sandbox": {"running": 12, "status": "healthy"},
        "anomalies": {"count": 3},
    },
    # Guardrail activity cards (the service's built-in fallback has a different shape)
    "/guardrails/metrics": {
        "threatDetection": {"blocked": 47, "breakdown": [
            {"label": "Prompt injection", "value": 31},
            {"label": "Jailbreak attempts", "value": 9},
            {"label": "Data exfiltration", "value": 7}]},
        "contextTrust": {"verified": 12480, "breakdown": [
            {"label": "Verified sources", "value": 12466},
            {"label": "Quarantined", "value": 14}]},
        "agentOperations": {"total": 1247, "breakdown": [
            {"label": "Auto-approved", "value": 1189},
            {"label": "Sent for human review", "value": 58}]},
        "explanations": {"averageConfidence": 91, "alternativesDisclosed": 87,
                         "consistency": 96},
    },
    # No saved policies: the Autonomy tab shows its default policy
    "/autonomy/policies": [],
    # The scanner page's default scan, from the app's scanner sample data
    "/scanner/scans/scan-a1b2c3d4": app_sample("services/vulnScannerMockData.js",
                                                "MOCK_SCAN_DETAIL"),
}

# Dev-mode toolbar (bottom left) is a developer tool, not part of the product
HIDE_DEV = 'div.fixed.bottom-4.left-4[class*="z-[9999]"] { display: none !important; }'


def _answer(route) -> None:
    path = route.request.url.split("?", 1)[0].split("/api/v1", 1)[1]
    while path.startswith("/api/v1/"):  # some services repeat the prefix
        path = path[len("/api/v1"):]
    if path in SAMPLES:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(SAMPLES[path]))
    else:
        route.fulfill(status=502, body="no backend")


def prepare_context(context, theme: str = "light") -> None:
    state = json.dumps(json.dumps(ONBOARDING_DONE))
    context.add_init_script(
        f"localStorage.setItem('aura-theme', {json.dumps(theme)});"
        f"localStorage.setItem('aura_onboarding_state', {state});"
        "document.addEventListener('DOMContentLoaded', () => {"
        "  const s = document.createElement('style');"
        f"  s.textContent = {json.dumps(HIDE_DEV)};"
        "  document.head.appendChild(s);"
        "});"
    )
    context.route("**/api/v1/**", _answer)
