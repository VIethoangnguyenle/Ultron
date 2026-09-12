#!/usr/bin/env python3
"""Dung avatar cho app Chat Ultron — 512x512 PNG, nen trong suot (Chat tu cat tron).

Chay: python3 make_avatar.py   -> ~/.hermes/reports/avatar/*.png
"""
import math
import os
import pathlib

from PIL import Image, ImageDraw, ImageFilter

OUT = pathlib.Path.home() / ".hermes/reports/avatar"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024          # ve o 1024 roi thu nho -> vien muot
FINAL = 512       # kich thuoc cuoi
NAVY = (11, 30, 58)
BLUE = (20, 96, 210)
CYAN = (34, 211, 238)
SILVER = (232, 238, 245)
GREY = (176, 190, 205)
RED = (255, 74, 62)


def grad_circle(size, top, bottom):
    """Hinh tron nen gradient doc."""
    g = Image.new("RGBA", (1, size))
    for y in range(size):
        t = y / (size - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    canvas.paste(g.resize((size, size)), (0, 0), mask)
    return canvas


def glow(img, xy, r, color, blur=28):
    """Ve vet sang (glow) cho mat."""
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse((xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r), fill=color + (210,))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)))


def rounded_head(d, x0, y0, x1, y1, fill):
    d.rounded_rectangle((x0, y0, x1, y1), radius=int((y1 - y0) * 0.34), fill=fill)


def robot_head(img, d, cx, cy, w, h, eye_col, mouth=True, antenna=True):
    """Dau robot: vien ngoai + mat + mieng + ang ten."""
    rounded_head(d, cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2, (120, 140, 165, 255))
    rounded_head(d, cx - w // 2 + 14, cy - h // 2 + 14, cx + w // 2 - 14, cy + h // 2 - 14, SILVER + (255,))
    ey = cy - int(h * 0.08)
    er = int(w * 0.115)
    for sx in (-1, 1):
        ex = cx + sx * int(w * 0.22)
        glow(img, (ex, ey), int(er * 2.6), eye_col)
        d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=eye_col + (255,))
        d.ellipse((ex - er + 4, ey - er + 4, ex - er + 12, ey - er + 12), fill=(255, 255, 255, 235))
    if antenna:
        ax, ay = cx, cy - h // 2 - int(h * 0.20)
        d.line((cx, cy - h // 2, ax, ay), fill=(120, 140, 165, 255), width=int(w * 0.035))
        d.ellipse((ax - 22, ay - 22, ax + 22, ay + 22), fill=CYAN + (255,))
    if mouth:
        mw = int(w * 0.30)
        my = cy + int(h * 0.24)
        d.arc((cx - mw, my - 34, cx + mw, my + 34), start=20, end=160, fill=(90, 110, 135, 255), width=int(w * 0.045))


def v1_robot():
    """Robot mat do, nen xanh dam — kieu Ultron co dien."""
    img = grad_circle(S, NAVY, (16, 62, 128))
    d = ImageDraw.Draw(img)
    robot_head(img, d, S // 2, int(S * 0.54), int(S * 0.56), int(S * 0.46), RED)
    return img


def v2_monogram():
    """Chu U + 2 mat robot + duoi bong chat."""
    img = grad_circle(S, (9, 24, 48), (24, 110, 220))
    d = ImageDraw.Draw(img)
    bub = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bub)
    x0, y0, x1, y1 = int(S * 0.20), int(S * 0.20), int(S * 0.80), int(S * 0.68)
    bd.rounded_rectangle((x0, y0, x1, y1), radius=int(S * 0.09), fill=SILVER + (255,))
    bd.polygon([(int(S * 0.32), y1 - 8), (int(S * 0.34), int(S * 0.80)), (int(S * 0.46), y1 - 8)], fill=SILVER + (255,))
    img.alpha_composite(bub)
    ey = int(S * 0.40)
    er = int(S * 0.055)
    for sx in (-1, 1):
        ex = S // 2 + sx * int(S * 0.155)
        glow(img, (ex, ey), int(er * 3.2), BLUE)
        d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=BLUE + (255,))
    d.arc((int(S * 0.36), int(S * 0.44), int(S * 0.64), int(S * 0.62)), start=25, end=155,
          fill=BLUE + (255,), width=int(S * 0.028))
    return img


def v3_bot_chat():
    """Dau robot xanh + bong chat nho, nen tim thanh sang."""
    img = grad_circle(S, (12, 40, 90), CYAN)
    d = ImageDraw.Draw(img)
    robot_head(img, d, S // 2, int(S * 0.50), int(S * 0.50), int(S * 0.40), BLUE, antenna=False)
    b = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    bx0, by0 = int(S * 0.60), int(S * 0.70)
    bd.rounded_rectangle((bx0, by0, bx0 + int(S * 0.26), by0 + int(S * 0.17)), radius=int(S * 0.05),
                         fill=(255, 255, 255, 245))
    bd.polygon([(bx0 + 10, by0 + int(S * 0.17) - 6), (bx0 + 22, by0 + int(S * 0.23)),
                (bx0 + int(S * 0.06), by0 + int(S * 0.17) - 6)], fill=(255, 255, 255, 245))
    img.alpha_composite(b)
    return img


def save(img, name):
    out = img.resize((FINAL, FINAL), Image.LANCZOS)
    p = OUT / name
    out.save(p, "PNG")
    print(f"{p}  {out.size[0]}x{out.size[1]}  {os.path.getsize(p)//1024} KB")


if __name__ == "__main__":
    save(v1_robot(), "avatar1_robot_red.png")
    save(v2_monogram(), "avatar2_monogram_chat.png")
    save(v3_bot_chat(), "avatar3_robot_cyan.png")
