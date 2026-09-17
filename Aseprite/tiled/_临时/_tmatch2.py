# -*- coding: utf-8 -*-
"""numpy 模板匹配：stone_06/stone_05 在官方图与工具图中的真实位置"""
import numpy as np
from PIL import Image
import os

BASE = r"E:\My_work\PixelsProject\Aseprite\tiled"
TMP = os.path.join(BASE, "_临时")

def load_rgba(p):
    im = Image.open(p).convert("RGBA")
    return np.array(im)

ref = load_rgba(os.path.join(TMP, "_ref01_f0.png"))
tool = load_rgba(os.path.join(TMP, "_tool_f0_1x.png"))

def find_template(img_rgba, tmpl_path, area=None):
    t = load_rgba(tmpl_path)
    th, tw = t.shape[:2]
    a = t[:, :, 3] > 200
    tr = t[:, :, 0].astype(np.int16); tg = t[:, :, 1].astype(np.int16); tb = t[:, :, 2].astype(np.int16)
    H, W = img_rgba.shape[:2]
    if area:
        x0, y0, x1, y1 = area
    else:
        x0, y0, x1, y1 = 0, 0, W - tw + 1, H - th + 1
    best = (1e9, None)
    ta = t[:, :, 3]
    for y in range(y0, y1):
        win = img_rgba[y:y+th, x0:x0+tw]
        sa = win[:, :, 3] > 200
        # 只比较模板不透明像素
        mask = a & sa
        n = mask.sum()
        if n < 300:
            continue
        diff = (np.abs(win[:, :, 0].astype(np.int16) - tr) + np.abs(win[:, :, 1].astype(np.int16) - tg) + np.abs(win[:, :, 2].astype(np.int16) - tb))
        d = diff[mask].sum() / n
        if d < best[0]:
            best = (d, (x0, y))
    return best

stone6 = os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_06.png")
stone5 = os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_05.png")

for name, path in [("stone_06", stone6), ("stone_05", stone5)]:
    print(f"--- {name} ---")
    for tag, img in [("官方", ref), ("工具", tool)]:
        score, pos = find_template(img, path)
        print(f"  {tag}: 最佳匹配 mean_diff={score:.2f} 左上角=({pos[0]},{pos[1]})" if pos else f"  {tag}: 未找到")

# 官方图中 stone_06 是否在 (40,225)？直接比较该位置的匹配质量
t6 = load_rgba(stone6)
for tag, img in [("官方", ref), ("工具", tool)]:
    x0, y0 = 40, 225
    win = img[y0:y0+32, x0:x0+32]
    mask = (t6[:, :, 3] > 200) & (win[:, :, 3] > 200)
    diff = (np.abs(win[:, :, 0].astype(np.int16) - t6[:, :, 0].astype(np.int16)) + np.abs(win[:, :, 1].astype(np.int16) - t6[:, :, 1].astype(np.int16)) + np.abs(win[:, :, 2].astype(np.int16) - t6[:, :, 2].astype(np.int16)))
    print(f"{tag} (40,225) 位置: 模板不透明像素 {mask.sum()}, mean_diff {diff[mask].mean():.2f}")
