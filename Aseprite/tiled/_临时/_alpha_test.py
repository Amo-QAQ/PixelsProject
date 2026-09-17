# -*- coding: utf-8 -*-
"""stone_06/05 原图重叠区 alpha 分布 + 官方重叠区半透明验证"""
from PIL import Image
import os
from collections import Counter

BASE = r"E:\My_work\PixelsProject\Aseprite\tiled"
TMP = os.path.join(BASE, "_临时")
stone6 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_06.png")).convert("RGBA")
stone5 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_05.png")).convert("RGBA")

# 原图整体 alpha 分布
for name, im in [("stone_06", stone6), ("stone_05", stone5)]:
    p = im.load()
    cnt = Counter()
    for y in range(im.height):
        for x in range(im.width):
            cnt[p[x, y][3]] += 1
    semi = sum(v for k, v in cnt.items() if 0 < k < 255)
    print(f"{name}: {im.width}x{im.height} alpha分布 {sorted(cnt.items())[:3]}... 半透明像素={semi}")

# 重叠区：stone6 绘制 (40,225), stone5 绘制 (28,211)；重叠 (40,225)-(60,243)
# 重叠区在 stone6 内的局部坐标 (0,0)-(20,18)；在 stone5 内的局部坐标 (12,14)-(32,32)
print("\n重叠区 alpha 检查:")
semi6 = semi5 = 0
p6, p5 = stone6.load(), stone5.load()
for y in range(225, 243):
    for x in range(40, 60):
        a6 = p6[x - 40, y - 225][3]
        a5 = p5[x - 28, y - 211][3]
        if 0 < a6 < 255: semi6 += 1
        if 0 < a5 < 255: semi5 += 1
print(f"重叠区 stone_06 半透明像素: {semi6} (18x18={18*18})")
print(f"重叠区 stone_05 半透明像素: {semi5}")

# 官方重叠区与"stone6半透明混合stone5"比较
ref = Image.open(os.path.join(TMP, "_ref01_f0.png")).convert("RGBA")
pr = ref.load()
mix = 0
for y in range(225, 243):
    for x in range(40, 60):
        c6 = p6[x - 40, y - 225]
        c5 = p5[x - 28, y - 211]
        a = c6[3] / 255.0
        mr = c6[0]*a + c5[0]*(1-a); mg = c6[1]*a + c5[1]*(1-a); mb = c6[2]*a + c5[2]*(1-a)
        c_ref = pr[x, y]
        if max(abs(c_ref[0]-mr), abs(c_ref[1]-mg), abs(c_ref[2]-mb)) > 25:
            mix += 1
print(f"官方重叠区 vs [stone6半透明混合stone5] 不匹配: {mix} (若小=>官方=stone6盖在stone5上)")
