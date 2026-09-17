# -*- coding: utf-8 -*-
"""特征像素匹配：stone_06/05 在官方/工具图中的位置（无numpy）"""
from PIL import Image
import os, random

BASE = r"E:\My_work\PixelsProject\Aseprite\tiled"
TMP = os.path.join(BASE, "_临时")
ref = Image.open(os.path.join(TMP, "_ref01_f0.png")).convert("RGBA")
tool = Image.open(os.path.join(TMP, "_tool_f0_1x.png")).convert("RGBA")
W, H = ref.size

def find(img, tmpl_path, area=None, sample=40):
    t = Image.open(tmpl_path).convert("RGBA")
    tw, th = t.size
    tp = t.load()
    pts = [(x, y) for y in range(th) for x in range(tw) if tp[x, y][3] > 200]
    random.seed(42)
    pts = random.sample(pts, min(sample, len(pts)))
    feats = [(x, y, tp[x, y]) for x, y in pts]
    pi = img.load()
    x0, y0, x1, y1 = area or (0, 0, W - tw + 1, H - th + 1)
    best = (1e9, None)
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = 0
            for fx, fy, c in feats:
                c2 = pi[x + fx, y + fy]
                d += abs(c[0]-c2[0]) + abs(c[1]-c2[1]) + abs(c[2]-c2[2])
            d /= len(feats)
            if d < best[0]:
                best = (d, (x, y))
    return best

stone6 = os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_06.png")
stone5 = os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_05.png")

for name, path in [("stone_06", stone6), ("stone_05", stone5)]:
    print(f"--- {name} ---")
    for tag, img in [("官方", ref), ("工具", tool)]:
        t = Image.open(path).convert("RGBA")
        tw, th = t.size
        d, pos = find(img, path, area=(0, 0, W - tw + 1, H - th + 1))
        print(f"  {tag}: mean_diff={d:.2f} 左上角=({pos[0]},{pos[1]})")
