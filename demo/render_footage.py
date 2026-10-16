#!/usr/bin/env python3
"""Render demo/showdown_transcript.json beats to 1280x720 silent MP4s.

One PNG per beat -> ffmpeg concat demuxer with per-beat durations.
Output: video/footage/{act1-unmanaged,act2-managed,close-queries}.mp4
"""
import json
import os
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 30
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPT = os.path.join(REPO, "demo", "showdown_transcript.json")
OUTDIR = os.path.join(REPO, "video", "footage")
TMP = "/tmp/showdown_frames"

FONT_REG = "/usr/share/fonts/Adwaita/AdwaitaMono-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/Adwaita/AdwaitaMono-Bold.ttf"

BG = (11, 14, 20)
RULE = (48, 54, 61)
COLORS = {
    "dim": (139, 148, 158),
    "body": (230, 237, 243),
    "user": (45, 212, 191),
    "wrong": (255, 123, 114),
    "flag": (227, 179, 65),
    "fix": (63, 185, 80),
    "query": (121, 192, 255),
    "row": (230, 237, 243),
}
KICKER = {"a": (255, 107, 107), "b": (45, 212, 191), "c": (121, 192, 255)}

f_reg_20 = ImageFont.truetype(FONT_REG, 20)
f_bold_20 = ImageFont.truetype(FONT_BOLD, 20)
f_bold_34 = ImageFont.truetype(FONT_BOLD, 34)
f_reg_23 = ImageFont.truetype(FONT_REG, 23)
f_bold_23 = ImageFont.truetype(FONT_BOLD, 23)
f_reg_16 = ImageFont.truetype(FONT_REG, 16)


def draw_beat(beat, idx, total, clip_key, png_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    kc = KICKER[clip_key]

    d.text((60, 34), beat["kicker"], font=f_bold_20, fill=kc)
    d.text((60, 66), beat["title"], font=f_bold_34, fill=(230, 237, 243))
    d.line([(60, 122), (W - 60, 122)], fill=RULE, width=2)

    y = 152
    for text, style in beat["lines"]:
        color = COLORS.get(style, COLORS["body"])
        font = f_bold_23 if style in ("wrong", "flag", "fix") else f_reg_23
        for wrapped in textwrap.wrap(text, width=76) or [""]:
            d.text((60, y), wrapped, font=font, fill=color)
            y += 36
        y += 8  # paragraph gap

    # footer
    d.text((60, H - 40), "debias - graph-hacks showdown", font=f_reg_16,
           fill=COLORS["dim"])
    d.text((W - 60 - 120, H - 40), "beat %d / %d" % (idx + 1, total),
           font=f_reg_16, fill=COLORS["dim"])
    # progress bar
    frac = (idx + 1) / total
    d.rectangle([(0, H - 4), (W, H)], fill=(30, 36, 44))
    d.rectangle([(0, H - 4), (int(W * frac), H)], fill=kc)

    img.save(png_path)


def render_clip(clip_key, spec):
    name = os.path.splitext(spec["file"])[0]
    frame_dir = os.path.join(TMP, clip_key)
    os.makedirs(frame_dir, exist_ok=True)
    beats = spec["beats"]
    pngs = []
    for i, b in enumerate(beats):
        png = os.path.join(frame_dir, "beat%03d.png" % i)
        draw_beat(b, i, len(beats), clip_key, png)
        pngs.append((png, b["hold"]))

    lst = os.path.join(frame_dir, "concat.txt")
    with open(lst, "w") as f:
        for png, hold in pngs:
            f.write("file '%s'\n" % png)
            f.write("duration %.2f\n" % hold)
        f.write("file '%s'\n" % pngs[-1][0])  # concat quirk: repeat last

    out = os.path.join(OUTDIR, spec["file"])
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
           "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg FAILED for", name)
        print(r.stderr[-2000:])
        return None

    # verify
    q = ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name,duration",
         "-of", "default=noprint_wrappers=1", out]
    info = subprocess.run(q, capture_output=True, text=True).stdout.strip()
    print("%s -> %s" % (spec["file"], info.replace("\n", " ")))
    return out


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    with open(TRANSCRIPT) as f:
        data = json.load(f)
    for clip_key, spec in data["clips"].items():
        render_clip(clip_key, spec)
    print("done ->", OUTDIR)


if __name__ == "__main__":
    main()
