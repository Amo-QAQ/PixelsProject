import json, os
TILED_DIR = r"E:\My_work\PixelsProject\Aseprite\tiled"
for f in ['grass_decoration.tsj','stone_01.tsj','girl_idle.tsj','girl_walk.tsj','girl_run.tsj',
          'fence.tsj','soil.tsj','soil_shadow.tsj','soil_texture_01.tsj','grass_02_island.tsj',
          'grass_01_island.tsj','grass_03_island.tsj','soil_island.tsj','grass_01.tsj']:
    p = os.path.join(TILED_DIR, f)
    with open(p, encoding='utf-8') as fh:
        d = json.load(fh)
    off = d.get('tileoffset')
    tw, th = d.get('tilewidth'), d.get('tileheight')
    coll = 'image' not in d
    per_tile = {}
    for t in d.get('tiles', []):
        if 'tileoffset' in t:
            per_tile[t['id']] = t['tileoffset']
    print(f, '| tile=%sx%s' % (tw, th), '| offset=%s' % off, '| collection=%s' % coll,
          '| per_tile_offsets=%s' % (per_tile if per_tile else '-'))
