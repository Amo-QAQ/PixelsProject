# -*- coding: utf-8 -*-
"""极简 TMX 渲染器：验证星露谷地图 = 数字矩阵 + 图集裁剪"""
import xml.etree.ElementTree as ET
import sys
from PIL import Image

tmx_path = sys.argv[1]
out_path = sys.argv[2]
maps_dir = sys.argv[3]  # 图集 PNG 所在目录（Maps）

ns = ''  # tmx 无命名空间
root = ET.parse(tmx_path).getroot()
W, H = int(root.get('width')), int(root.get('height'))
tile_w = int(root.get('tilewidth'))

# 1) 收集图块集：firstgid -> (图片文件, columns)
tilesets = []
for ts in root.findall('tileset'):
    firstgid = int(ts.get('firstgid'))
    img = ts.find('image')
    src = img.get('source')  # ../Maps/xxx.png
    cols = int(ts.get('columns'))
    tilesets.append((firstgid, src, cols))
tilesets.sort()

def find_tileset(gid):
    for i in range(len(tilesets)):
        if gid >= tilesets[i][0] and (i + 1 == len(tilesets) or gid < tilesets[i + 1][0]):
            return tilesets[i]
    return None

# 2) 加载图集
cache = {}
def get_img(src):
    if src not in cache:
        p = src.replace('../Maps/', maps_dir + '/')
        cache[src] = Image.open(p).convert('RGBA')
    return cache[src]

# 3) 按图层顺序绘制（文件内顺序 = 从底层到顶层）
canvas = Image.new('RGBA', (W * tile_w, H * tile_w), (0, 0, 0, 0))
for layer in root.findall('layer'):
    data = layer.find('data')
    if data.get('encoding') != 'csv':
        continue
    nums = [int(x) for x in data.text.strip().replace('\n', '').split(',')]
    for idx, gid in enumerate(nums):
        if gid == 0:
            continue
        ts = find_tileset(gid)
        if not ts:
            continue
        _, src, cols = ts
        img = get_img(src)
        local = gid - ts[0]
        sx = (local % cols) * tile_w
        sy = (local // cols) * tile_w
        tx = (idx % W) * tile_w
        ty = (idx // W) * tile_w
        canvas.paste(img.crop((sx, sy, sx + tile_w, sy + tile_w)), (tx, ty))

canvas.convert('RGB').save(out_path)
print('OK 渲染完成:', out_path, canvas.size)
