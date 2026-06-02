from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media"
FONT_ZH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_EN = "/System/Library/Fonts/HelveticaNeue.ttc"
W, H = 1280, 720


def font(size: int, bold: bool = False):
    path = FONT_ZH if Path(FONT_ZH).exists() else FONT_EN
    try:
        return ImageFont.truetype(path, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()


F = {
    "hero": font(66, True),
    "h1": font(46, True),
    "h2": font(30, True),
    "body": font(22),
    "small": font(16),
    "tiny": font(13),
    "mono": font(18, True),
}


PALETTES = {
    "midnight": {
        "bg": (10, 14, 25),
        "panel": (21, 27, 45),
        "card": (30, 38, 62),
        "line": (102, 126, 234),
        "line2": (109, 212, 193),
        "text": (238, 243, 255),
        "muted": (152, 166, 195),
        "danger": (255, 103, 123),
        "warn": (255, 203, 87),
    },
    "sakura": {
        "bg": (24, 15, 29),
        "panel": (40, 27, 48),
        "card": (55, 36, 65),
        "line": (255, 140, 198),
        "line2": (158, 231, 255),
        "text": (255, 243, 251),
        "muted": (222, 193, 216),
        "danger": (255, 111, 145),
        "warn": (255, 209, 102),
    },
    "aurora": {
        "bg": (13, 16, 32),
        "panel": (24, 29, 55),
        "card": (36, 46, 86),
        "line": (167, 139, 250),
        "line2": (34, 211, 238),
        "text": (238, 242, 255),
        "muted": (190, 200, 239),
        "danger": (251, 113, 133),
        "warn": (251, 191, 36),
    },
}


def blend(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def gradient(size, top, bottom):
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        c = blend(top, bottom, t)
        for x in range(size[0]):
            px[x, y] = c
    return img.convert("RGBA")


def rounded(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def text(draw, xy, value, fill, fnt, anchor=None):
    draw.text(xy, value, fill=fill, font=fnt, anchor=anchor)


def glow_line(draw, points, color, width=3):
    for w, alpha in [(12, 45), (7, 80), (width, 255)]:
        draw.line(points, fill=(*color, alpha), width=w, joint="curve")


def draw_chart(draw, x, y, w, h, p, palette, label="NVDA"):
    rounded(draw, (x, y, x + w, y + h), 18, (*palette["panel"], 235), (*palette["card"], 255))
    text(draw, (x + 24, y + 20), label, palette["text"], F["h2"])
    text(draw, (x + 24, y + 58), "新闻事件 × K线走势", palette["muted"], F["small"])
    for i in range(5):
        yy = y + 100 + i * (h - 140) / 4
        draw.line((x + 20, yy, x + w - 20, yy), fill=(100, 116, 150, 40), width=1)
    pts = []
    n = 38
    for i in range(n):
        t = i / (n - 1)
        wave = math.sin(t * 8.2 + p * 1.6) * 0.12 + math.sin(t * 18.0) * 0.035
        trend = 0.58 - t * 0.26 + max(0, t - 0.62) * 0.35
        yy = y + 105 + (trend + wave) * (h - 150)
        xx = x + 34 + t * (w - 68)
        pts.append((xx, yy))
    glow_line(draw, pts, palette["line2"], 4)
    for i, (xx, yy) in enumerate(pts):
        if i % 5 == 0:
            col = palette["line"] if i % 10 else palette["danger"]
            draw.ellipse((xx - 5, yy - 5, xx + 5, yy + 5), fill=(*col, 220))
    for i in range(12):
        bx = x + 40 + i * (w - 90) / 11
        bh = 20 + (math.sin(i * 1.9 + p * 2) + 1) * 24
        col = palette["line2"] if i % 3 else palette["danger"]
        draw.rounded_rectangle((bx, y + h - 36 - bh, bx + 18, y + h - 36), radius=4, fill=(*col, 120))


def draw_radar(draw, x, y, w, h, p, palette):
    rounded(draw, (x, y, x + w, y + h), 18, (*palette["panel"], 235), (*palette["card"], 255))
    text(draw, (x + 24, y + 22), "风口雷达", palette["text"], F["h2"])
    themes = [
        ("AI应用与新模型发布", "强信号", 86, palette["line"]),
        ("港股打新 / 新经济IPO", "观察", 71, palette["line2"]),
        ("宏观流动性", "观察", 64, palette["warn"]),
    ]
    for i, (name, tag, score, col) in enumerate(themes):
        yy = y + 82 + i * 82
        rounded(draw, (x + 22, yy, x + w - 22, yy + 58), 12, (*palette["card"], 210), (90, 105, 140, 120))
        text(draw, (x + 40, yy + 13), name, palette["text"], F["body"])
        text(draw, (x + 40, yy + 38), tag, col, F["small"])
        draw.arc((x + w - 88, yy + 10, x + w - 40, yy + 58), -90, -90 + int(score * 3.6 * (0.7 + p * 0.3)), fill=(*col, 255), width=5)
        text(draw, (x + w - 64, yy + 26), str(score), palette["text"], F["small"], anchor="mm")


def draw_books(draw, x, y, w, h, palette):
    rounded(draw, (x, y, x + w, y + h), 18, (*palette["panel"], 235), (*palette["card"], 255))
    text(draw, (x + 24, y + 22), "双币种模拟交易", palette["text"], F["h2"])
    cards = [("HKD Paper Book", "HK$1,000,000", "+2.8%"), ("USD Paper Book", "$40,000", "+1.4%")]
    for i, (a, b, c) in enumerate(cards):
        yy = y + 86 + i * 92
        rounded(draw, (x + 24, yy, x + w - 24, yy + 70), 12, (*palette["card"], 225), (90, 105, 140, 130))
        text(draw, (x + 44, yy + 16), a, palette["muted"], F["small"])
        text(draw, (x + 44, yy + 38), b, palette["text"], F["body"])
        text(draw, (x + w - 92, yy + 35), c, palette["line2"], F["body"], anchor="mm")


def base_frame(palette_name="midnight", t=0.0):
    palette = PALETTES[palette_name]
    img = gradient((W, H), palette["bg"], blend(palette["bg"], palette["panel"], 0.45))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(70):
        x = (i * 173 + int(t * 60)) % W
        y = (i * 91 + int(math.sin(t + i) * 24)) % H
        r = 1 + (i % 4)
        col = palette["line"] if i % 2 else palette["line2"]
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, 45))
    img.alpha_composite(overlay)
    return img


def hero_frame(title, subtitle, palette_name="midnight", progress=0.0, scene="radar"):
    palette = PALETTES[palette_name]
    img = base_frame(palette_name, progress * 4)
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (58, 52), "天眼 SkyEye", palette["text"], F["h2"])
    text(d, (58, 105), title, palette["text"], F["hero"])
    text(d, (62, 188), subtitle, palette["muted"], F["body"])
    rounded(d, (62, 242, 262, 286), 22, (*palette["line"], 220))
    text(d, (162, 264), "Research Only", (255, 255, 255), F["small"], anchor="mm")
    if scene == "radar":
        draw_chart(d, 560, 76, 620, 330, progress, palette, "0100.HK")
        draw_radar(d, 680, 430, 500, 230, progress, palette)
    elif scene == "profile":
        draw_radar(d, 590, 78, 560, 300, progress, palette)
        draw_chart(d, 610, 420, 540, 220, progress, palette, "NVDA")
    else:
        draw_chart(d, 540, 80, 600, 310, progress, palette, "0700.HK")
        draw_books(d, 650, 420, 490, 230, palette)
    return img


VIDEO_SPECS = [
    {
        "slug": "01-opportunity-radar",
        "palette": "midnight",
        "scene": "radar",
        "title": "从风口到标的",
        "subtitle": "新闻、IPO、产业链与K线一起看",
        "beats": ["风口雷达聚合市场线索", "证据、风险、相关公司同屏展开", "只做模拟交易，不碰实盘"],
    },
    {
        "slug": "02-company-profile",
        "palette": "sakura",
        "scene": "profile",
        "title": "K线不再空白",
        "subtitle": "公司是谁、做什么、官网与财报一次看懂",
        "beats": ["新搜股票自动补公司档案", "官网、公告、财报链接直接打开", "最近新闻按需抓取，缓存可清理"],
    },
    {
        "slug": "03-paper-trading",
        "palette": "aurora",
        "scene": "books",
        "title": "先模拟，再复盘",
        "subtitle": "港股HKD账本，美股USD账本，互不折算",
        "beats": ["一键加入模拟账本", "仓位、现金、收益曲线持续跟踪", "给学习交易留一条安全路径"],
    },
]


SHOWCASE = [
    ("showcase-01-radar.png", "风口雷达", "把新闻、重大事件、IPO、产业链和价格反应收成一个机会队列。", "midnight", "radar"),
    ("showcase-02-company.png", "公司档案", "打开行情先看公司、主营业务、官网、公告和财报链接。", "sakura", "profile"),
    ("showcase-03-paper.png", "双币种模拟", "HKD 与 USD 账本分开复盘，先学习，再接近真实决策。", "aurora", "books"),
    ("showcase-04-themes.png", "多套配色", "深夜蓝、港股科技、交易终端、樱粉少女、晨光白、紫青灵感。", "sakura", "radar"),
    ("showcase-05-cache.png", "按需新闻缓存", "只保存标题、摘要、链接和分析索引，让资料有用但不无限膨胀。", "midnight", "profile"),
]


def save_cover_and_showcase():
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in VIDEO_SPECS:
        img = hero_frame(spec["title"], spec["subtitle"], spec["palette"], 0.56, spec["scene"])
        d = ImageDraw.Draw(img, "RGBA")
        y = 606
        for i, beat in enumerate(spec["beats"]):
            text(d, (72 + i * 380, y), beat, PALETTES[spec["palette"]]["muted"], F["small"])
        img.save(OUT / f"{spec['slug']}-cover.png")
    for name, title, subtitle, palette_name, scene in SHOWCASE:
        img = hero_frame(title, subtitle, palette_name, 0.72, scene).resize((1600, 900), Image.Resampling.LANCZOS)
        img.save(OUT / name)


def make_video(spec):
    tmp = Path(tempfile.mkdtemp(prefix="skyeye_video_"))
    fps = 30
    seconds = 15
    frames = fps * seconds
    palette = PALETTES[spec["palette"]]
    try:
        for i in range(frames):
            p = i / (frames - 1)
            img = hero_frame(spec["title"], spec["subtitle"], spec["palette"], p, spec["scene"])
            d = ImageDraw.Draw(img, "RGBA")
            beat_idx = min(2, int(p * 3))
            beat = spec["beats"][beat_idx]
            rounded(d, (58, 604, 810, 662), 22, (*palette["panel"], 230), (*palette["line"], 130))
            text(d, (84, 622), f"{beat_idx + 1}/3  {beat}", palette["text"], F["body"])
            bar_w = int(694 * p)
            rounded(d, (84, 650, 84 + bar_w, 655), 3, (*palette["line2"], 240))
            img.save(tmp / f"frame_{i:04d}.png")
        out = OUT / f"{spec['slug']}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmp / "frame_%04d.png"),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(seconds),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-c:a", "aac", "-shortest", str(out),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_index():
    lines = [
        "# SkyEye Release Media",
        "",
        "Generated product-launch visuals for README, GitHub social preview, and Codex developer-program application materials.",
        "",
        "## 15-second videos",
        "",
    ]
    for spec in VIDEO_SPECS:
        lines.append(f"- `{spec['slug']}.mp4`")
        lines.append(f"- `{spec['slug']}-cover.png`")
    lines += ["", "## Product showcase images", ""]
    for name, *_ in SHOWCASE:
        lines.append(f"- `{name}`")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    save_cover_and_showcase()
    for spec in VIDEO_SPECS:
        make_video(spec)
    write_index()
    print(f"generated media in {OUT}")


if __name__ == "__main__":
    main()
