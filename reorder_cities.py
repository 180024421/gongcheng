# -*- encoding=utf8 -*-
"""将单字或空名城池排在 CITIES 和 NEIGHBORS 末尾，并修复语法错误"""
import re
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
city_path = os.path.join(_script_dir, 'city_data.py')

with open(city_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 解析 CITIES（兼容含 "touch" 的畸形行，用正则只取前4个字段）
cities = {}
for m in re.finditer(r'(\d+):\s*\((\d+),\s*(\d+),\s*"([^"]*)",\s*"([^"]*)"', content):
    cid = int(m.group(1))
    if 0 <= cid <= 231:  # 合理 id 范围
        x, y, k, name = int(m.group(2)), int(m.group(3)), m.group(4), m.group(5)
        cities[cid] = (x, y, k, name)

# 解析 NEIGHBORS
parts = content.split('NEIGHBORS = {')
neighbors = {}
if len(parts) >= 2:
    nb_block = parts[1].split('}\n')[0] + '\n'
    for m in re.finditer(r'(\d+):\s*\[([^\]]*)\]', nb_block):
        cid = int(m.group(1))
        raw = m.group(2)
        nb_list = [int(x.strip()) for x in raw.split(',') if x.strip()]
        neighbors[cid] = nb_list

# 单字或空名 -> 排到末尾
def to_end(cid):
    t = cities.get(cid, (0,0,'',''))
    n = t[3] if len(t) > 3 else ''
    return not n or len(n) == 1

keep_ids = sorted(c for c in cities if not to_end(c))
end_ids = sorted(c for c in cities if to_end(c))
all_ids = keep_ids + end_ids

def fmt_city(cid):
    t = cities[cid]
    x, y, k = t[0], t[1], t[2]
    n = t[3] if len(t) > 3 else ''
    return f'    {cid}: ({x}, {y}, "{k}", "{n}"),'

def fmt_neighbor(cid):
    nbs = neighbors.get(cid, [])
    return f'    {cid}: {nbs},'

lines = [
    '# -*- encoding=utf8 -*-',
    '"""',
    '城池地图数据 (1280x720 分辨率)',
    'CITIES[id] = (screen_x, screen_y, kingdom, name)',
    'NEIGHBORS[id] = [相邻城池id, ...]',
    '单字或空名城池已排至末尾',
    '"""',
    '',
    'CITIES = {',
]
for cid in all_ids:
    lines.append(fmt_city(cid))
lines.extend(['}', '', 'NEIGHBORS = {'])

for cid in all_ids:
    if cid in neighbors:
        lines.append(fmt_neighbor(cid))
lines.extend([
    '}',
    '',
    '',
    "def get_border_targets(my_kingdom='wei'):",
    '    """获取可攻击的交界敌方城池列表"""',
    "    my_ids = {cid for cid, v in CITIES.items() if v[2] == my_kingdom}",
    "    targets = []",
    "    seen = set()",
    "    for cid in my_ids:",
    "        for nb in NEIGHBORS.get(cid, []):",
    "            if nb not in my_ids and nb not in seen:",
    "                seen.add(nb)",
    "                info = CITIES[nb]",
    "                targets.append({'id': nb, 'pos': (info[0], info[1]),",
    "                    'kingdom': info[2], 'name': info[3],",
    "                    'from_ally': cid,",
    "                    'ally_pos': (CITIES[cid][0], CITIES[cid][1])})",
    "    return targets",
])

with open(city_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('单字/空名排至末尾:', len(end_ids), '个')
print('已修复语法并保存')
