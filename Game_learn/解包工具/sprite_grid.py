# -*- coding: utf-8 -*-
"""springobjects.png 生成带 SpriteIndex 编号的网格图"""
from PIL import Image, ImageDraw, ImageFont

src = r'E:\My_work\PixelsProject\Game_learn\素材解包\Maps\springobjects.png'
out = r'E:\My_work\PixelsProject\Game_learn\素材解包\Maps\springobjects_编号网格.png'

sprite = Image.open(src).convert('RGBA')
W, H = sprite.size
cols = W // 16
rows = H // 16

scale = 3  # 放大倍数
cell = 16 * scale
canvas = Image.new('RGBA', (cols * cell, rows * cell), (30, 30, 34, 255))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 11)
except:
    font = ImageFont.load_default()

for r in range(rows):
    for c in range(cols):
        idx = r * cols + c
        tile = sprite.crop((c * 16, r * 16, c * 16 + 16, r * 16 + 16)).resize((cell, cell), Image.NEAREST)
        x = c * cell
        y = r * cell
        canvas.paste(tile, (x, y), tile)
        draw.text((x + 2, y + 2), str(idx), fill=(255, 255, 255, 220), font=font)

canvas.convert('RGB').save(out)
print('OK', out, canvas.size)
