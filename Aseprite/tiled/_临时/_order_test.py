# -*- coding: utf-8 -*-
"""实验：对象层绘制顺序（列表序 vs y升序）哪个与官方一致"""
from PIL import Image
import os

TMP = r"E:\My_work\PixelsProject\Aseprite\tiled\_临时"
BASE = r"E:\My_work\PixelsProject\Aseprite\tiled"
ref = Image.open(os.path.join(TMP, "_ref01_f0.png")).convert("RGBA")
W, H = ref.size
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

# 只画两个石头对象（id71 gid614 stone_06, id72 gid615 stone_05）
stone6 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_06.png")).convert("RGBA")
stone5 = Image.open(os.path.join(BASE, r"..\project_end\Cozy Lands - Asset Pack\Objects\Mineral\stone_05.png")).convert("RGBA")
# 位置（工具规则：bottom 对齐 + half-up）
objs = [
    (stone6, 40, 256.5, 32, 32, "614"),
    (stone5, 27.75, 242.75, 32, 32, "615"),
]

def paint(cv, order, mode):
    for idx in order:
        img, ox, oy, ow, oh, tag = objs[idx]
        px = int(ox + 0.5)
        py = int(oy + 0.5) - oh
        x0, y0 = px, py
        tile = img
        # 直接覆盖（SourceOver 简化：石头不透明，用 paste 观察叠加）
        cv.alpha_composite(tile, (x0, y0))

def diff_area(a, b, box):
    x0, y0, x1, y1 = box
    pa, pb = a.load(), b.load()
    d = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            ca, cb = pa[x, y], pb[x, y]
            if ca != cb and (max(abs(ca[i]-cb[i]) for i in range(3)) > 10 or abs(ca[3]-cb[3]) > 30):
                d += 1
    return d

box = (22, 204, 82, 266)

# 方案A：列表顺序 614先 615后
cvA = canvas.copy(); paint(cvA, [0, 1], "list")
# 方案B：y升序（615 y=242.75 先，614 y=256.5 后）
cvB = canvas.copy(); paint(cvB, [1, 0], "topdown")

dA = diff_area(ref, cvA, box)
dB = diff_area(ref, cvB, box)
print(f"列表序差异: {dA}")
print(f"y升序差异:  {dB}")

# 保存两张对比图
for tag, cv in [("list", cvA), ("topdown", cvB)]:
    sub = cv.crop(box); subr = ref.crop(box)
    out = Image.new("RGBA", (sub.width * 2 + 6, sub.height), (255,255,255,255))
    out.paste(subr, (0,0)); out.paste(sub, (sub.width+6,0))
    out = out.resize((out.width*6, out.height*6), Image.NEAREST)
    out.convert("RGB").save(os.path.join(TMP, f"_order_{tag}.png"))
print("保存 _order_list.png / _order_topdown.png")
