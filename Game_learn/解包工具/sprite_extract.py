# -*- coding: utf-8 -*-
"""从 springobjects.png 裁剪物品图标（鸡蛋/牛奶/奶酪等）"""
import json
from PIL import Image, ImageDraw, ImageFont

json_path = r'E:\My_work\PixelsProject\Game_learn\解包数据\Objects.json'
sprite_path = r'E:\My_work\PixelsProject\Game_learn\素材解包\Maps\springobjects.png'
out_path = r'E:\My_work\PixelsProject\Game_learn\素材解包\Maps\物品图标_鸡蛋牛奶奶酪.png'

data = json.load(open(json_path, encoding='utf-8'))['data']
sprite = Image.open(sprite_path).convert('RGBA')

# 找出鸡蛋/牛奶/奶酪相关物品（按 Name 关键词 + 常见 ID）
targets = {}
for oid, obj in data.items():
    name = obj.get('Name') or ''
    if any(k in name for k in ('Egg', 'Milk', 'Cheese', 'Mayonnaise', 'Yogurt', 'Butter')):
        try:
            sort_key = int(oid)
        except ValueError:
            sort_key = 10**9  # 字符串键排最后
        targets[oid] = (sort_key, obj)

items = sorted(targets.items(), key=lambda kv: kv[1][0])
print('找到物品:', len(items))
for oid, (sk, obj) in items:
    print(f"  ID {oid}: {obj['Name']} SpriteIndex={obj['SpriteIndex']} Texture={obj.get('Texture')}")

# 拼一张展示图：2 列网格，每格放大 8 倍（128x128）
cell = 128
cols = 2
rows = (len(items) + cols - 1) // cols
canvas = Image.new('RGBA', (cols * cell, rows * cell), (245, 243, 238, 255))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
except:
    font = ImageFont.load_default()

for i, (oid, (sk, obj)) in enumerate(items):
    idx = obj['SpriteIndex']
    sx = (idx % 24) * 16
    sy = (idx // 24) * 16
    icon = sprite.crop((sx, sy, sx + 16, sy + 16)).resize((128, 128), Image.NEAREST)
    x = (i % cols) * cell
    y = (i // cols) * cell
    canvas.paste(icon, (x + 0, y), icon)
    draw.text((x + 4, y + 132), f"ID {oid} {obj['Name']}", fill=(60, 60, 60), font=font)

canvas.convert('RGB').save(out_path)
print('OK 已保存:', out_path, canvas.size)
