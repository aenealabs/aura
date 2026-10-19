"""Capture the README's platform screenshots (assets/logo/*.png) from the running frontend.

Start the frontend in dev mode first (VITE_DEV_MODE=true in frontend/.env.local):

    cd frontend && npx vite --port 5199

then, with any Python that has Playwright installed:

    python scripts/readme_media/capture_screenshots.py [--base http://localhost:5199] [--theme light]

No backend is needed. API calls the pages make are answered with the sample data in
sample_api.py, so the screenshots show a populated platform without any mock data living in
the app itself.
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_api import prepare_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "logo"

# 1440 x 1281 CSS pixels at 1.34x gives the 1929 x 1717 images the README was laid out for
VIEWPORT = {"width": 1440, "height": 1281}
SCALE = 1.34

# file name: (route, optional tab or row to click before the shot)
SHOTS = {
    "Main Dashboard": ("/", None),
    "Vulnerability Scanner": ("/security/scanner", None),
    "HITL Approvals": ("/approvals", "approval"),
    "Mission Control": ("/agents/mission-control", None),
    "AI Trust Center": ("/trust-center", None),
    "Explainability Dashboard": ("/explainability", None),
    "Red Team Dashboard": ("/security/red-team", "text:API Security Assessment"),
    "Agent Registry": ("/agents/registry", "text:Orchestrator Prime"),
    "Guardrails Settings": ("/guardrails", None),
    "Platform Settings": ("/settings", None),
    "Autonomous Policies": ("/settings", "Autonomy Policies"),
}

STILL = "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}"


def settle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # long-polling pages never go fully idle
        pass
    page.add_style_tag(content=STILL)
    page.wait_for_timeout(700)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:5199")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--only", nargs="*", help="capture just these names")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        prepare_context(context, args.theme)
        page = context.new_page()
        for name, (route, action) in SHOTS.items():
            if args.only and name not in args.only:
                continue
            page.goto(args.base + route)
            settle(page)
            if action == "approval":
                page.get_by_text("SQL Injection Fix in Authentication Handler").first.click()
                settle(page)
            elif action and action.startswith("text:"):
                page.get_by_text(action[5:]).first.click()
                settle(page)
            elif action:
                page.get_by_role("button", name=action).first.click()
                settle(page)
            page.mouse.move(0, VIEWPORT["height"] - 1)  # no hover states in the shot
            page.screenshot(path=out / f"{name}.png")
            print("wrote", name)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
