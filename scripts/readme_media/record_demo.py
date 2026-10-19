"""Record the README's short feature clip (assets/media/aura-demo.mp4, with captions in .vtt).

Start the frontend in dev mode first (see capture_screenshots.py), then:

    python scripts/readme_media/record_demo.py [--base http://localhost:5199] [--pace 1.0]

Moves through the platform the way a user would (the sidebar, a click on an approval), with
captions, a visible pointer, and title cards. API calls are answered as in the screenshots
(sample_api.py). make_highlights.py cuts the README's animated reel from this video.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_api import prepare_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WIDTH, HEIGHT = 1440, 900
NAVY = "#1B3357"

OVERLAY_JS = """
(() => {
  const install = () => {
    if (document.getElementById('demo-caption')) return;
    const style = document.createElement('style');
    style.textContent = `
      #demo-caption { position: fixed; left: 50%; bottom: 32px; transform: translateX(-50%);
        max-width: 1080px; padding: 14px 26px; border-radius: 12px; z-index: 99999;
        background: rgba(15, 23, 42, .9); color: #fff; font: 600 21px/1.4 Inter, sans-serif;
        text-align: center; box-shadow: 0 10px 30px rgba(15, 23, 42, .3);
        transition: opacity .3s; }
      #demo-caption:empty { opacity: 0; }
      #demo-cursor { position: fixed; width: 22px; height: 22px; margin: -11px 0 0 -11px;
        border-radius: 50%; background: rgba(47, 181, 194, .45); border: 2px solid #1A9AA8;
        z-index: 100000; pointer-events: none; left: 50%; top: 50%;
        transition: left .6s ease-in-out, top .6s ease-in-out, transform .15s; }
      #demo-cursor.press { transform: scale(.7); }
      #demo-card { position: fixed; inset: 0; z-index: 100001; display: flex;
        flex-direction: column; align-items: center; justify-content: center;
        background: NAVY; color: #fff; font-family: Inter, sans-serif; text-align: center;
        padding: 40px; animation: demo-in .5s ease both; }
      #demo-card.instant { animation: none; }
      #demo-card h1 { font-size: 56px; font-weight: 600; letter-spacing: -.02em; margin: 0 0 18px; }
      #demo-card p { font-size: 24px; margin: 6px 0; opacity: .88; max-width: 980px; }
      @keyframes demo-in { from { opacity: 0 } to { opacity: 1 } }`.replace('NAVY', 'NAVY_VALUE');
    document.head.appendChild(style);
    const caption = document.createElement('div');
    caption.id = 'demo-caption';
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    document.body.append(caption, cursor);
  };
  window.__demoCaption = (text) => { install(); document.getElementById('demo-caption').textContent = text; };
  window.__demoCursor = (x, y, press) => {
    install();
    const c = document.getElementById('demo-cursor');
    c.style.left = x + 'px'; c.style.top = y + 'px';
    c.classList.toggle('press', !!press);
  };
  window.__demoCard = (title, lines, instant) => {
    install();
    let card = document.getElementById('demo-card');
    if (!card) { card = document.createElement('div'); card.id = 'demo-card'; document.body.appendChild(card); }
    card.classList.toggle('instant', !!instant);
    card.innerHTML = '<h1></h1>' + lines.map(() => '<p></p>').join('');
    card.querySelector('h1').textContent = title;
    card.querySelectorAll('p').forEach((p, i) => p.textContent = lines[i]);
  };
  window.__demoCardOff = () => document.getElementById('demo-card')?.remove();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
""".replace("NAVY_VALUE", NAVY)

STILL = "*{caret-color:transparent!important}"
READ_BASE, READ_CHARS_PER_SEC = 1.2, 15.0  # a caption stays up at least this long


class Demo:
    def __init__(self, page, pace: float):
        self.page, self.pace = page, pace
        self.started = time.monotonic()
        self.cues: list[tuple[float, str]] = []
        self.shown: tuple[str, float] | None = None

    def wait(self, seconds: float) -> None:
        self.page.wait_for_timeout(seconds * 1000 * self.pace)

    def settle(self) -> None:
        """Wait until what is on screen has been up long enough to read."""
        if self.shown:
            text, at = self.shown
            left = READ_BASE + len(text) / READ_CHARS_PER_SEC - (time.monotonic() - at)
            if left > 0:
                self.page.wait_for_timeout(left * 1000)

    def mark(self, text: str) -> None:
        self.cues.append((time.monotonic() - self.started, text))

    def caption(self, text: str, hold: float = 1.0) -> None:
        self.settle()
        self.page.evaluate("t => window.__demoCaption(t)", text)
        self.mark(text)
        self.shown = (text, time.monotonic()) if text else None
        self.wait(hold)

    def card(self, title: str, lines: list[str], hold: float, instant: bool = False) -> None:
        self.settle()
        self.page.evaluate("([t, l, i]) => window.__demoCard(t, l, i)", [title, lines, instant])
        text = " · ".join([title, *lines])
        self.mark(text)
        self.shown = (text, time.monotonic())
        self.wait(hold)

    def card_off(self) -> None:
        self.settle()
        self.page.evaluate("() => window.__demoCardOff()")
        self.shown = None

    def point(self, target, hold: float = 0.6, press: bool = False) -> None:
        target.wait_for(state="visible")
        target.scroll_into_view_if_needed()
        box = target.bounding_box()
        if box:
            self.page.evaluate("([x, y, p]) => window.__demoCursor(x, y, p)",
                               [box["x"] + min(box["width"] / 2, 70),
                                box["y"] + box["height"] / 2, press])
        self.wait(hold)

    def click(self, target, hold: float = 1.0) -> None:
        self.point(target, 0.7)
        self.point(target, 0.15, press=True)
        target.click()
        self.wait(hold)

    def nav(self, label: str, hold: float = 1.2) -> None:
        """Go to a page through the sidebar, clearing the caption first."""
        self.settle()
        self.page.evaluate("() => window.__demoCaption('')")
        self.mark("")
        self.shown = None
        # match the start of the name: some links carry a count badge ("Approvals 7")
        link = self.page.get_by_role("link", name=re.compile(rf"^{re.escape(label)}\b"))
        self.click(link.first, 0.2)
        try:
            self.page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        self.page.mouse.move(0, HEIGHT - 1)
        self.wait(hold)

    def scroll(self, pixels: int, hold: float = 1.2) -> None:
        self.page.mouse.wheel(0, pixels)
        self.wait(hold)


def run_flow(d: Demo, base: str) -> None:
    page = d.page
    page.goto(base + "/")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.add_style_tag(content=STILL)
    d.started = time.monotonic()
    d.cues.clear()
    d.card("Project Aura", ["Autonomous AI security for enterprise codebases",
                            "Find it. Fix it. Prove it. Then a person approves it."], 4.5,
           instant=True)
    d.card_off()

    d.caption("The security dashboard: open findings, agents at work, and patches waiting "
              "on a person.", 2.5)
    d.point(page.get_by_text("Pending Approvals").first, 1.2)

    d.nav("Approvals")
    d.caption("Every patch is generated, tested in a sandbox, then queued for human approval.",
              1.0)
    d.click(page.get_by_text("SQL Injection Fix in Authentication Handler").first, 1.0)
    d.caption("The reviewer sees the exact change: string-built SQL replaced with a "
              "parameterized query.", 1.0)
    d.point(page.get_by_text("VULNERABLE").first, 1.5)
    d.point(page.get_by_text("FIXED").first, 2.0)
    d.point(page.get_by_role("button", name="Approve & Deploy").first, 1.5)

    d.nav("Mission Control")
    d.caption("Mission Control shows each agent's reasoning and the actions it plans, before "
              "they run.", 1.0)
    d.point(page.get_by_text("Agent Thinking Process").first, 2.0)
    d.point(page.get_by_text("Planned Actions").first, 2.0)

    d.nav("Red Team")
    d.caption("Red-team campaigns attack the agents themselves: prompt injection, auth bypass, "
              "data exfiltration.", 1.0)
    d.click(page.get_by_text("LLM Agent Security Test").first, 2.5)

    d.nav("AI Trust Center")
    d.caption("The AI Trust Center tracks constitutional principles and safety metrics "
              "against their targets.", 1.0)
    d.point(page.get_by_text("Key Safety Metrics").first, 3.0)

    d.nav("Explainability")
    d.caption("Every agent decision is explained, and contradictions between agents are "
              "flagged for review.", 1.0)
    d.point(page.get_by_text("Contradiction").nth(1), 3.0)

    d.caption("", 0)
    d.card("Project Aura", ["Human-in-the-loop by design", "github.com/aenealabs/aura"], 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:5199")
    parser.add_argument("--pace", type=float, default=1.0, help=">1 slower, <1 faster")
    parser.add_argument("--out", default=str(ROOT / "assets" / "media" / "aura-demo.mp4"))
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="aura-demo-"))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                record_video_dir=str(work), record_video_size={"width": WIDTH, "height": HEIGHT})
            prepare_context(context, "light")
            context.add_init_script(OVERLAY_JS)
            page = context.new_page()
            opened = time.monotonic()
            demo = Demo(page, args.pace)
            run_flow(demo, args.base)
            lead_in = demo.started - opened
            ended = time.monotonic() - demo.started
            video = page.video.path()
            context.close()
            browser.close()
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{lead_in + 0.15:.3f}",
                        "-i", str(video), "-c:v", "libx264", "-preset", "slow", "-crf", "24",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
        write_captions(demo.cues, ended, out.with_suffix(".vtt"))
        print(f"Wrote {out} ({ended:.0f}s, {out.stat().st_size // 1024} KB)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _stamp(seconds: float) -> str:
    h, rem = divmod(max(seconds, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_captions(cues: list[tuple[float, str]], end: float, vtt: Path) -> None:
    lines = ["WEBVTT", ""]
    for i, (at, text) in enumerate(cues):
        if not text:
            continue
        until = cues[i + 1][0] if i + 1 < len(cues) else end
        lines += [f"{_stamp(at)} --> {_stamp(until)}", text, ""]
    vtt.write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
