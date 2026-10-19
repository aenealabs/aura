"""Cut a square (1080x1080) social clip and thumbnail from the feature clip, for LinkedIn.

Each shot sits between a headline band (readable on a phone, where the app's own captions are
small) and a band with the repository link; shots crossfade. Shots are found by their caption
in assets/media/aura-demo.vtt, so re-recording the clip needs no edits here. Writes
~/aura-media/aura-social.mp4 and ~/aura-media/aura-social-thumbnail.png (outside the repo).

    python scripts/readme_media/make_social_clip.py
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "assets" / "media" / "aura-demo.mp4"
CAPTIONS = VIDEO.with_suffix(".vtt")
OUT_DIR = Path.home() / "aura-media"
SIZE, VIDEO_H = 1080, 675  # the 1440x900 clip scaled to the square's width
TOP = (SIZE - VIDEO_H) // 2
FADE = 0.5
LINK = "github.com/aenealabs/aura"
BAND = "#374151"

# (caption the shot starts at, seconds into it, length, headline)
SHOTS = [
    ("The security dashboard", 0.4, 5.5, "Autonomous security remediation, refreshed"),
    ("The reviewer sees the exact change", 0.6, 6.5, "Every patch waits for a person"),
    ("Guardrails set how much", 0.6, 6.0, "Guardrails decide what agents do alone"),
    (
        "Guardrail activity is measured",
        0.6,
        6.0,
        "Every block and agent action is measured",
    ),
    ("Mission Control shows", 0.6, 6.0, "Agents show their reasoning before they act"),
    ("Red-team campaigns", 0.6, 6.0, "The agents get red-teamed too"),
    (
        "Human-in-the-loop by design",
        0.2,
        3.5,
        "Built for AWS. People approve every change.",
    ),
]
THUMB = (
    "The reviewer sees the exact change",
    4.0,
    "Autonomous AI security, with people in charge",
)

BAND_HTML = """<!doctype html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap"
      rel="stylesheet">
<style>
  html, body {{ margin: 0; width: {size}px; height: {size}px; background: {band};
               font-family: 'Inter', sans-serif; color: #fff; }}
  .top {{ height: {top}px; display: flex; flex-direction: column; justify-content: center;
          padding: 0 56px; box-sizing: border-box; }}
  .over {{ font-size: 22px; letter-spacing: 4px; font-weight: 600; opacity: .8; }}
  .head {{ font-size: {head_px}px; font-weight: 600; line-height: 1.15; margin-top: 10px;
           letter-spacing: -.01em; }}
  .bottom {{ position: absolute; top: {bottom_top}px; left: 0; right: 0; bottom: 0;
             display: flex; align-items: center; justify-content: center; font-size: 30px; }}
</style></head><body>
  <div class="top"><div class="over">PROJECT AURA</div><div class="head">{head}</div></div>
  <div class="bottom">{link}</div>
</body></html>"""


def ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def caption_starts() -> list[tuple[float, str]]:
    cues = []
    for h, m, sec, text in re.findall(
        r"(\d+):(\d+):([\d.]+) --> [^\n]+\n([^\n]+)", CAPTIONS.read_text()
    ):
        cues.append((int(h) * 3600 + int(m) * 60 + float(sec), text))
    return cues


def start_of(caption: str, cues: list[tuple[float, str]]) -> float:
    for at, text in cues:
        if caption in text:
            return at
    raise SystemExit(
        f"No caption containing {caption!r} in {CAPTIONS}; re-record the clip"
    )


def render_bands(work: Path, headlines: list[str]) -> list[Path]:
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE})
        for i, head in enumerate(headlines):
            page.set_content(
                BAND_HTML.format(
                    size=SIZE,
                    top=TOP,
                    bottom_top=TOP + VIDEO_H,
                    band=BAND,
                    link=LINK,
                    head=head,
                    head_px=46 if len(head) < 36 else 40,
                )
            )
            page.wait_for_load_state("networkidle")
            path = work / f"band{i}.png"
            page.screenshot(path=path)
            paths.append(path)
        browser.close()
    return paths


def make_clip(work: Path, cues: list[tuple[float, str]]) -> tuple[Path, float]:
    bands = render_bands(work, [head for *_, head in SHOTS])
    inputs, graph = ["-i", str(VIDEO)], []
    for band in bands:
        inputs += ["-loop", "1", "-i", str(band)]
    for i, (caption, into, length, _) in enumerate(SHOTS):
        start = start_of(caption, cues) + into
        graph.append(
            f"[0:v]trim=start={start:.2f}:duration={length},setpts=PTS-STARTPTS,fps=30,"
            f"scale={SIZE}:{VIDEO_H}:flags=lanczos[v{i}]"
        )
        graph.append(
            f"[{i + 1}:v]trim=duration={length},setpts=PTS-STARTPTS,fps=30[b{i}]"
        )
        graph.append(f"[b{i}][v{i}]overlay=0:{TOP},format=yuv420p[s{i}]")
    last, offset = "s0", SHOTS[0][2]
    for i in range(1, len(SHOTS)):
        offset -= FADE
        graph.append(
            f"[{last}][s{i}]xfade=transition=fade:duration={FADE}:offset={offset:.2f}[x{i}]"
        )
        last, offset = f"x{i}", offset + SHOTS[i][2]
    out = OUT_DIR / "aura-social.mp4"
    subprocess.run(
        [
            ffmpeg(),
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(graph),
            "-map",
            f"[{last}]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )
    return out, offset


def make_thumbnail(work: Path, cues: list[tuple[float, str]]) -> Path:
    caption, into, head = THUMB
    band = render_bands(work, [head])[0]
    frame = work / "thumb-frame.png"
    subprocess.run(
        [
            ffmpeg(),
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_of(caption, cues) + into:.2f}",
            "-i",
            str(VIDEO),
            "-frames:v",
            "1",
            "-vf",
            f"scale={SIZE}:{VIDEO_H}:flags=lanczos",
            str(frame),
        ],
        check=True,
    )
    out = OUT_DIR / "aura-social-thumbnail.png"
    subprocess.run(
        [
            ffmpeg(),
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(band),
            "-i",
            str(frame),
            "-filter_complex",
            f"[0:v][1:v]overlay=0:{TOP}",
            "-frames:v",
            "1",
            str(out),
        ],
        check=True,
    )
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="aura-social-"))
    cues = caption_starts()
    clip, seconds = make_clip(work, cues)
    thumb = make_thumbnail(work, cues)
    print(f"Wrote {clip} ({clip.stat().st_size / 1e6:.1f} MB, about {seconds:.0f} s)")
    print(f"Wrote {thumb}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
