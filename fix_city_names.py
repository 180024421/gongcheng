# -*- encoding=utf8 -*-
"""将重名和单字城池名置空，并把这些城池移到 CITIES 末尾"""
import sys
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from city_data import CITIES, NEIGHBORS

# 1. 重名
name_to_cids = {}
for cid, tup in CITIES.items():
    name = tup[3] if len(tup) > 3 else ""
    if name:
        name_to_cids.setdefault(name, []).append(cid)
dup_cids = {c for cids in name_to_cids.values() if len(cids) > 1 for c in cids}

# 2. 单字
single_cids = {cid for cid, tup in CITIES.items() 
               if (tup[3] if len(tup) > 3 else "") and len(tup[3]) == 1}

to_clear = dup_cids | single_cids

# 3. 分两类并置空
keep = [(cid, CITIES[cid]) for cid in sorted(CITIES) if cid not in to_clear]
clear = []
for cid in sorted(CITIES):
    if cid in to_clear:
        t = list(CITIES[cid])
        while len(t) < 4:
            t.append("")
        t[3] = ""
        clear.append((cid, tuple(t)))

# 4. 生成新 CITIES 文本
def fmt(cid, tup):
    x, y, k = tup[0], tup[1], tup[2]
    n = tup[3] if len(tup) > 3 else ""
    return f'    {cid}: ({x}, {y}, "{k}", {repr(n)}),'

lines = []
lines.append('# -*- encoding=utf8 -*-')
lines.append('"""')
lines.append('城池地图数据 (1280x720 分辨率)')
lines.append('CITIES[id] = (screen_x, screen_y, kingdom, name)')
lines.append('NEIGHBORS[id] = [相邻城池id, ...]')
lines.append('重名及单字城池名已置空，置于末尾')
lines.append('"""')
lines.append('')
lines.append('CITIES = {')
for cid, tup in keep + clear:
    lines.append(fmt(cid, tup))
lines.append('}')
lines.append('')
lines.append('NEIGHBORS = {')
for cid in sorted(NEIGHBORS):
    lines.append(f'    {cid}: {NEIGHBORS[cid]},')
lines.append('}')
lines.append('')
lines.append('')
lines.append('def get_border_targets(my_kingdom=\'wei\'):')
lines.append('    """获取可攻击的交界敌方城池列表"""')
lines.append('    my_ids = {cid for cid, v in CITIES.items() if v[2] == my_kingdom}')
lines.append('    targets = []')
lines.append('    seen = set()')
lines.append('    for cid in my_ids:')
lines.append('        for nb in NEIGHBORS.get(cid, []):')
lines.append('            if nb not in my_ids and nb not in seen:')
lines.append('                seen.add(nb)')
lines.append('                info = CITIES[nb]')
lines.append("                targets.append({'id': nb, 'pos': (info[0], info[1]),")
lines.append("                    'kingdom': info[2], 'name': info[3],")
lines.append("                    'from_ally': cid,")
lines.append("                    'ally_pos': (CITIES[cid][0], CITIES[cid][1])})")
lines.append('    return targets')

# 5. 写入
out_path = os.path.join(_script_dir, 'city_data.py')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('重名置空:', sorted(dup_cids))
print('单字置空:', sorted(single_cids))
print('已置空并移至末尾，共', len(to_clear), '个')
