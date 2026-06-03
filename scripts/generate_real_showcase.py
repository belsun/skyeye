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
    "hero": font(56, True),
    "hero_safe": font(50, True),
    "h1": font(42, True),
    "h2": font(30, True),
    "body": font(23),
    "small": font(17),
    "tiny": font(13),
    "mono": font(16, True),
}


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    return int(draw.textlength(text, font=fnt))


def wrap(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt) -> list[str]:
    lines: list[str] = []
    current = ""
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


def gradient(top=(6, 12, 22), bottom=(23, 16, 35)):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img.convert("RGBA")


def add_texture(draw: ImageDraw.ImageDraw, accent=(122, 224, 255)):
    for i in range(70):
        x = (i * 197 + 37) % W
        y = (i * 109 + 19) % H
        r = 2 + (i % 5)
        col = accent if i % 3 else (255, 132, 196)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(*col, 32))
    for x in range(0, W, 80):
        draw.line((x, 0, x - 240, H), fill=(95, 125, 190, 10), width=1)


def round_mask(size: tuple[int, int], radius: int):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def crop_cover(img: Image.Image, crop_box: tuple[int, int, int, int], target: tuple[int, int]):
    src = img.crop(crop_box)
    tw, th = target
    sr = src.width / src.height
    tr = tw / th
    if sr > tr:
        nh = th
        nw = int(nh * sr)
    else:
        nw = tw
        nh = int(nw / sr)
    src = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - tw) // 2)
    top = max(0, (nh - th) // 2)
    return src.crop((left, top, left + tw, top + th)).convert("RGBA")


def paste_panel(canvas: Image.Image, img: Image.Image, box: tuple[int, int, int, int], radius=28, outline=(105, 135, 255, 130)):
    x1, y1, x2, y2 = box
    tw, th = x2 - x1, y2 - y1
    shadow = Image.new("RGBA", (tw + 92, th + 92), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((46, 46, tw + 46, th + 46), radius=radius, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas.alpha_composite(shadow, (x1 - 46, y1 - 34))

    mask = round_mask((tw, th), radius)
    clipped = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    clipped.paste(img.resize((tw, th), Image.Resampling.LANCZOS), (0, 0), mask)
    canvas.alpha_composite(clipped, (x1, y1))
    ImageDraw.Draw(canvas, "RGBA").rounded_rectangle(box, radius=radius, outline=outline, width=2)


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill, outline=None, fnt=None, pad=12):
    fnt = fnt or F["tiny"]
    x, y = xy
    w = text_width(draw, text, fnt) + pad * 2
    h = 30
    draw.rounded_rectangle((x, y, x + w, y + h), radius=15, fill=fill, outline=outline or fill, width=1)
    draw.text((x + pad, y + 8), text, font=fnt, fill=(244, 249, 255))
    return x + w + 8


def label(draw: ImageDraw.ImageDraw, xy, text, accent):
    x, y = xy
    w = text_width(draw, text, F["tiny"]) + 34
    draw.rounded_rectangle((x, y, x + w, y + 36), radius=18, fill=(*accent, 34), outline=(*accent, 130), width=1)
    draw.text((x + w / 2, y + 18), text, font=F["tiny"], fill=(247, 250, 255), anchor="mm")


def draw_headline(draw: ImageDraw.ImageDraw, title: str, subtitle: str, accent, x=70, y=54, max_width=650):
    label(draw, (x, y), "SkyEye 实机界面", accent)
    ty = y + 70
    for line in title.split("\n"):
        draw.text((x, ty), line, font=F["hero_safe"], fill=(248, 250, 255))
        ty += 60
    ty += 12
    for line in wrap(draw, subtitle, max_width, F["body"])[:3]:
        draw.text((x, ty), line, font=F["body"], fill=(194, 205, 234))
        ty += 35
    return ty


def make_kline_news():
    accent = (90, 218, 255)
    img = gradient((4, 10, 20), (18, 15, 32))
    d = ImageDraw.Draw(img, "RGBA")
    add_texture(d, accent)

    shot = Image.open(SHOTS / "real-nvda-company-loaded.png").convert("RGBA")
    chart = crop_cover(shot, (0, 420, 1360, 980), (1130, 630))
    paste_panel(img, chart, (46, 184, 1196, 828), radius=26, outline=(89, 148, 255, 155))

    d.rounded_rectangle((54, 38, 720, 182), radius=24, fill=(4, 10, 20, 232), outline=(90, 218, 255, 80), width=1)
    d.text((78, 56), "点一下 K 线", font=F["hero_safe"], fill=(250, 252, 255))
    d.text((78, 112), "新闻解释走势", font=F["hero_safe"], fill=(250, 252, 255))
    d.text((80, 166), "价格、新闻节点、趋势解释和一键分析在同一张图里。", font=F["tiny"], fill=(195, 207, 236))

    node = (856, 604)
    lens_center = (824, 394)
    r = 118
    d.line((node[0], node[1], lens_center[0] + 76, lens_center[1] + 76), fill=(*accent, 180), width=3)
    d.ellipse((node[0] - 10, node[1] - 10, node[0] + 10, node[1] + 10), fill=(255, 82, 105), outline=(255, 255, 255, 220), width=2)

    zoom_src = chart.crop((850, 270, 1030, 450)).resize((r * 2, r * 2), Image.Resampling.LANCZOS)
    lens_mask = Image.new("L", (r * 2, r * 2), 0)
    ImageDraw.Draw(lens_mask).ellipse((0, 0, r * 2 - 1, r * 2 - 1), fill=255)
    lens_shadow = Image.new("RGBA", (r * 2 + 40, r * 2 + 40), (0, 0, 0, 0))
    ImageDraw.Draw(lens_shadow).ellipse((20, 20, r * 2 + 20, r * 2 + 20), fill=(0, 0, 0, 180))
    img.alpha_composite(lens_shadow.filter(ImageFilter.GaussianBlur(16)), (lens_center[0] - r - 20, lens_center[1] - r - 12))
    lens = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
    lens.paste(zoom_src, (0, 0), lens_mask)
    img.alpha_composite(lens, (lens_center[0] - r, lens_center[1] - r))
    d.ellipse((lens_center[0] - r, lens_center[1] - r, lens_center[0] + r, lens_center[1] + r), outline=(155, 233, 255, 230), width=5)
    d.line((lens_center[0] + 84, lens_center[1] + 84, lens_center[0] + 158, lens_center[1] + 158), fill=(155, 233, 255, 220), width=9)

    panel = (1222, 184, 1548, 828)
    d.rounded_rectangle(panel, radius=24, fill=(11, 18, 34, 235), outline=(90, 160, 255, 120), width=2)
    d.text((1248, 216), "节点新闻证据", font=F["h2"], fill=(250, 252, 255))
    d.text((1248, 258), "NVDA · 2026-06-02 · 价格 +4.8%", font=F["tiny"], fill=(124, 234, 204))

    y = 298
    news_items = [
        ("AI 需求", "Jensen Huang 称 AI 需求仍然强劲，数据中心收入继续超预期。", "+ 舆情强度 82"),
        ("产业链", "云厂商资本开支上修，HBM 与 GPU 供应链关注度同步升温。", "+ 产业链相关 76"),
        ("风险", "估值已经拥挤，若财报指引低于预期，波动可能放大。", "- 拥挤度扣分 18"),
    ]
    for tag, body, score in news_items:
        d.rounded_rectangle((1248, y, 1522, y + 92), radius=14, fill=(21, 29, 50, 220), outline=(63, 87, 135, 130), width=1)
        d.text((1266, y + 13), tag, font=F["small"], fill=(134, 226, 255))
        line_y = y + 40
        for line in wrap(d, body, 198, F["tiny"])[:2]:
            d.text((1266, line_y), line, font=F["tiny"], fill=(222, 231, 248))
            line_y += 18
        d.text((1266, y + 72), score, font=F["tiny"], fill=(100, 245, 202))
        y += 102

    d.rounded_rectangle((1248, 650, 1522, 744), radius=16, fill=(8, 28, 36, 235), outline=(93, 236, 200, 150), width=1)
    d.text((1266, 670), "一键分析输出", font=F["small"], fill=(111, 244, 210))
    analysis = "短线价格反应与 AI/HBM 新闻同向；适合放入观察池，等待回踩支撑或新财报确认。"
    ay = 698
    for line in wrap(d, analysis, 228, F["tiny"])[:2]:
        d.text((1266, ay), line, font=F["tiny"], fill=(236, 246, 255))
        ay += 20
    d.rounded_rectangle((1288, 772, 1522, 808), radius=18, fill=(115, 88, 255, 255))
    d.text((1405, 790), "生成分析报告", font=F["small"], fill=(255, 255, 255), anchor="mm")

    img.save(MEDIA / "real-showcase-01-news-kline.png")


def make_news_dashboard():
    accent = (168, 132, 255)
    img = gradient((7, 12, 24), (21, 16, 36))
    d = ImageDraw.Draw(img, "RGBA")
    add_texture(d, accent)

    shot = Image.open(SHOTS / "real-overview-ready.png").convert("RGBA")
    screen = crop_cover(shot, (0, 0, shot.width, shot.height), (1020, 690))
    paste_panel(img, screen, (500, 74, 1530, 774), radius=28, outline=(141, 128, 255, 135))
    d.rounded_rectangle((48, 48, 468, 304), radius=24, fill=(6, 10, 22, 205))

    draw_headline(
        d,
        "风口雷达\n抓住热点",
        "热点、风险和资产线索，先排序再模拟。",
        accent,
        x=70,
        y=58,
        max_width=390,
    )

    d.rounded_rectangle((70, 340, 458, 790), radius=24, fill=(12, 18, 34, 225), outline=(120, 105, 255, 110), width=1)
    d.text((98, 368), "今天该看什么", font=F["h2"], fill=(250, 252, 255))
    ranks = [
        ("AI算力 / HBM", 93, (99, 240, 213)),
        ("宏观流动性", 83, (125, 190, 255)),
        ("港股打新", 70, (255, 202, 88)),
        ("机器人/自动驾驶", 70, (255, 142, 198)),
        ("加密基础设施", 63, (169, 139, 250)),
    ]
    y = 420
    for name, score, col in ranks:
        d.text((98, y), name, font=F["small"], fill=(232, 240, 255))
        d.rounded_rectangle((98, y + 28, 374, y + 40), radius=6, fill=(28, 36, 62, 255))
        d.rounded_rectangle((98, y + 28, 98 + int(276 * score / 100), y + 40), radius=6, fill=col)
        d.text((392, y + 12), str(score), font=F["h2"], fill=col, anchor="mm")
        y += 66

    d.text((98, 732), "词云", font=F["small"], fill=(177, 188, 218))
    x = 150
    y = 722
    words = [
        ("AI", 24, (98, 239, 215)),
        ("IPO", 18, (255, 202, 88)),
        ("监管政策", 14, (125, 190, 255)),
        ("流动性", 13, (169, 139, 250)),
        ("HBM", 16, (255, 142, 198)),
        ("地缘风险", 12, (255, 100, 130)),
    ]
    for word, size, col in words:
        fnt = font(size, True)
        w = text_width(d, word, fnt) + 24
        if x + w > 438:
            x = 98
            y += 36
        d.rounded_rectangle((x, y, x + w, y + 30), radius=15, fill=(*col, 45), outline=(*col, 125), width=1)
        d.text((x + 12, y + 5), word, font=fnt, fill=(245, 248, 255))
        x += w + 8

    d.rounded_rectangle((592, 794, 1438, 844), radius=24, fill=(9, 17, 31, 230), outline=(115, 224, 255, 120), width=1)
    d.text((624, 809), "强信号：AI算力、宏观流动性、港股打新", font=F["small"], fill=(115, 238, 218))
    d.text((968, 809), "观察信号：机器人、加密基础设施、地缘冲突", font=F["small"], fill=(213, 222, 248))

    img.save(MEDIA / "real-showcase-02-radar-dashboard.png")


def make_company_loaded():
    accent = (255, 134, 198)
    img = gradient((8, 10, 20), (28, 15, 31))
    d = ImageDraw.Draw(img, "RGBA")
    add_texture(d, accent)
    d.rounded_rectangle((48, 48, 530, 314), radius=26, fill=(6, 10, 22, 210))

    draw_headline(
        d,
        "先懂公司\n再看 K 线",
        "新搜一家公司，先看它是谁、做什么、官网、公告、财报和新闻，再回到行情。",
        accent,
        x=70,
        y=62,
        max_width=460,
    )

    loaded = [
        ("公司档案", "NVIDIA Corporation / Semiconductors"),
        ("最近新闻", "4 条已加载，按相关度与日期排序"),
        ("行情区", "日 K 与新闻节点已同步显示"),
        ("研究入口", "官网、投资者关系、公告/监管文件、财报"),
    ]
    y = 330
    for title, body in loaded:
        d.rounded_rectangle((74, y, 506, y + 72), radius=16, fill=(18, 24, 42, 218), outline=(*accent, 95), width=1)
        d.ellipse((96, y + 24, 120, y + 48), fill=(96, 242, 206))
        d.text((134, y + 13), title, font=F["small"], fill=(255, 210, 232))
        d.text((134, y + 40), body, font=F["tiny"], fill=(224, 232, 250))
        y += 88

    d.rounded_rectangle((74, 720, 506, 792), radius=18, fill=(35, 15, 31, 225), outline=(255, 140, 198, 130), width=1)
    d.text((100, 738), "没有加载态入镜", font=F["small"], fill=(255, 220, 238))
    d.text((100, 764), "截图前等待公司、新闻、K线全部完成。", font=F["tiny"], fill=(230, 238, 252))

    shot = Image.open(SHOTS / "real-nvda-company-loaded.png").convert("RGBA")
    screen = crop_cover(shot, (0, 70, 1800, 1320), (955, 735))
    paste_panel(img, screen, (560, 74, 1532, 824), radius=30, outline=(255, 136, 198, 135))

    img.save(MEDIA / "real-showcase-03-company-to-macro.png")


def main():
    make_kline_news()
    make_news_dashboard()
    make_company_loaded()
    print("generated upgraded real showcase images")


if __name__ == "__main__":
    main()
