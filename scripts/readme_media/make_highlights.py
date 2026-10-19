"""Cut the README's animated highlight reel (assets/media/aura-highlights.webp) from the clip.

Takes a few seconds from each captioned moment in assets/media/aura-demo.vtt (the title and
closing cards are left out), so re-recording the clip needs no edits here:

    python scripts/readme_media/make_highlights.py
"""

import re
import shutil
import subprocess
from pathlib import Path

MEDIA = Path(__file__).resolve().parents[2] / "assets" / "media"
SECONDS_EACH = 5.0  # of each caption, starting just after it appears


def cue_starts(vtt: Path) -> list[float]:
    starts = []
    for h, m, s, text in re.findall(r"(\d+):(\d+):([\d.]+) --> [^\n]+\n([^\n]+)", vtt.read_text()):
        if "·" in text:  # a title card
            continue
        starts.append(int(h) * 3600 + int(m) * 60 + float(s))
    return starts


def main() -> None:
    clips = [(start + 0.6, SECONDS_EACH) for start in cue_starts(MEDIA / "aura-demo.vtt")]
    parts = [f"[0:v]trim=start={s:.2f}:duration={d},setpts=PTS-STARTPTS,fps=8,"
             f"scale=960:-1:flags=lanczos[c{i}]" for i, (s, d) in enumerate(clips)]
    graph = (";".join(parts) + ";" + "".join(f"[c{i}]" for i in range(len(clips)))
             + f"concat=n={len(clips)}:v=1:a=0[out]")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = MEDIA / "aura-highlights.webp"
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", str(MEDIA / "aura-demo.mp4"),
                    "-filter_complex", graph, "-map", "[out]", "-c:v", "libwebp_anim",
                    "-quality", "60", "-compression_level", "6", "-loop", "0", str(out)],
                   check=True)
    print(f"Wrote {out} ({len(clips)} moments, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
