from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
SHOTS = MEDIA / "screenshots"
FONT_ZH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
W, H = 1600, 900


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(FONT_ZH, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()


F = {
    "hero": font(62, True),
    "h1": font(44, True),
    "h2": font(30, True),
    "body": font(24),
    "small": font(17),
    "tiny": font(14),
}


def wrap(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt) -> list[str]:
    lines, current = [], ""
    for ch in text:
        test = current + ch
        if draw.textlength(test, font=fnt) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def gradient(top=(9, 13, 25), bottom=(23, 18, 38)):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img.convert("RGBA")


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def paste_screen(canvas, path, box, radius=34):
    shot = Image.open(path).convert("RGBA")
    target_w, target_h = box[2] - box[0], box[3] - box[1]
    shot_ratio = shot.width / shot.height
    target_ratio = target_w / target_h
    if shot_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * shot_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / shot_ratio)
    shot = shot.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    shot = shot.crop((left, top, left + target_w, top + target_h))
    shadow = Image.new("RGBA", (target_w + 80, target_h + 80), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((40, 40, target_w + 40, target_h + 40), radius=radius, fill=(0, 0, 0, 155))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas.alpha_composite(shadow, (box[0] - 40, box[1] - 30))
    mask = rounded_mask((target_w, target_h), radius)
    clipped = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    clipped.paste(shot, (0, 0), mask)
    canvas.alpha_composite(clipped, (box[0], box[1]))
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(box, radius=radius, outline=(125, 153, 255, 120), width=2)


def label(draw, xy, text, color=(132, 225, 255)):
    draw.rounded_rectangle((xy[0], xy[1], xy[0] + 188, xy[1] + 38), radius=19, fill=(*color, 34), outline=(*color, 135), width=1)
    draw.text((xy[0] + 94, xy[1] + 19), text, font=F["tiny"], fill=(248, 250, 255), anchor="mm")


def make_card(filename, shot, title, subtitle, bullets, accent=(132, 225, 255), layout="right"):
    img = gradient()
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(54):
        x = (i * 229) % W
        y = (i * 113) % H
        r = 2 + (i % 5)
        col = accent if i % 2 else (255, 140, 198)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, 38))
    label(d, (72, 64), "SkyEye 实机界面", accent)
    d.text((72, 128), title, font=F["hero"], fill=(248, 250, 255))
    y = 220
    for line in wrap(d, subtitle, 600, F["body"])[:3]:
        d.text((76, y), line, font=F["body"], fill=(193, 204, 232))
        y += 36
    y += 28
    for item in bullets:
        d.ellipse((78, y + 12, 90, y + 24), fill=accent)
        for line in wrap(d, item, 540, F["small"])[:2]:
            d.text((108, y), line, font=F["small"], fill=(223, 231, 250))
            y += 28
        y += 14
    if layout == "right":
        paste_screen(img, SHOTS / shot, (690, 92, 1518, 802))
    else:
        paste_screen(img, SHOTS / shot, (560, 280, 1518, 828))
    img.save(MEDIA / filename)


def main():
    make_card(
        "real-showcase-01-news-kline.png",
        "real-nvda-deep-ready.png",
        "新闻舆情解释K线",
        "把公司新闻、舆情分类、价格反应、风险价位放在同一个研究现场。",
        [
            "新闻不是孤立列表，而是贴近K线和交易日期",
            "公司档案、最近新闻、支撑/止损/目标价同步呈现",
            "适合从“为什么涨跌”开始训练主观交易判断",
        ],
        (132, 225, 255),
    )
    make_card(
        "real-showcase-02-radar-dashboard.png",
        "real-overview-ready.png",
        "综合新闻分析看板",
        "从宏观、产业链、IPO、政策、财报和地缘事件里筛出真正值得看的风口。",
        [
            "风口雷达把新闻、事件、产业链和催化信号合并",
            "过滤噪音，只保留强信号和观察信号",
            "从微观公司事件放大到宏观趋势与资产配置线索",
        ],
        (167, 139, 250),
    )
    make_card(
        "real-showcase-03-company-to-macro.png",
        "real-minimax-deep.png",
        "从公司决策到产业趋势",
        "新搜一家公司，先看到它是谁、做什么、官网、公告、财报和最近关键新闻。",
        [
            "公司档案让新股或冷门标的不再是一张空K线",
            "按需抓取新闻索引，减少本地空间膨胀",
            "从产品发布、融资、管理层变动追踪产业链扩散",
        ],
        (255, 140, 198),
    )
    print("generated real showcase images")


if __name__ == "__main__":
    main()
