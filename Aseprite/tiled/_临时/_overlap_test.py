# -*- coding: utf-8 -*-
"""判断官方 stone_06/stone_05 重叠区：后画的谁？"""
from PIL import Image
import os

TMP = r"E:\My_work\PixelsProject\Aseprite\tiled\_临时"
BASE = r"E:\My_work\PixelsProject\Aseprite\tiled"
ref = Image.open(os.path.join(TMP, "_ref01_f0.png")).convert("RGBA")
tool = Image.open(os.path.join(TMP, "_tool_f0_1x.png")).convert("RGBA")

stone6 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_06.png")).convert("RGBA")
stone5 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_05.png")).convert("RGBA")

# 石头绘制区域
s6 = (40, 225, 72, 257)   # 614
s5 = (28, 211, 60, 243)   # 615
# 重叠区
ox0, oy0 = max(s6[0], s5[0]), max(s6[1], s5[1])
ox1, oy1 = min(s6[2], s5[2]), min(s6[3], s5[3])
print(f"重叠区: ({ox0},{oy0})-({ox1},{oy1})")

pr = ref.load()
# 官方重叠区 vs stone_06 对应位置 / stone_05 对应位置
d6 = d5 = 0
for y in range(oy0, oy1):
    for x in range(ox0, ox1):
        c_ref = pr[x, y]
        c6 = stone6.load()[x - s6[0], y - s6[1]]
        c5 = stone5.load()[x - s5[0], y - s5[1]]
        if max(abs(c_ref[i]-c6[i]) for i in range(3)) > 25:
            d6 += 1
        if max(abs(c_ref[i]-c5[i]) for i in range(3)) > 25:
            d5 += 1

print(f"官方重叠区 与 stone_06 不匹配像素: {d6}")
print(f"官方重叠区 与 stone_05 不匹配像素: {d5}")
print("=> 官方重叠区更像:", "stone_06(614后画=topdown)" if d6 < d5 else "stone_05(615后画=列表序)")

# 工具当前重叠区 vs 两个石头
pt = tool.load()
d6t = d5t = 0
for y in range(oy0, oy1):
    for x in range(ox0, ox1):
        c_tool = pt[x, y]
        c6 = stone6.load()[x - s6[0], y - s6[1]]
        c5 = stone5.load()[x - s5[0], y - s5[1]]
        if max(abs(c_tool[i]-c6[i]) for i in range(3)) > 25:
            d6t += 1
        if max(abs(c_tool[i]-c5[i]) for i in range(3)) > 25:
            d5t += 1
print(f"工具重叠区 与 stone_06 不匹配: {d6t} | 与 stone_05 不匹配: {d5t}")
print("=> 工具当前重叠区显示:", "stone_06" if d6t < d5t else "stone_05")
