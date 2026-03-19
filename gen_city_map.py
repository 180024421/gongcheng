"""
从地图截图检测所有城池位置和连接关系，生成完整数据。
使用 Delaunay 三角剖分构建平面图（无交叉边），再过滤长边和穿山边。
"""
import cv2
import numpy as np
from scipy.spatial import Delaunay

SCREEN_W, SCREEN_H = 1280, 720
MAP_REGION = (123, 45, 1175, 670)

# 颜色检测参数
MIN_CITY_AREA = 25
MAX_CITY_AREA = 280
MIN_CIRCULARITY = 0.45
MIN_SOLIDITY = 0.72
MERGE_DIST = 14

# 连接检测参数
MAX_ROAD_DIST = 68          # Delaunay 边的最大保留长度
MOUNTAIN_BRIGHT_THRESH = 195  # 路径采样亮度超此值视为山脉
MOUNTAIN_RATIO_THRESH = 0.25  # 路径上山脉像素占比超此值则断开

HSV_RANGES = {
    'wei': {
        'lower': [np.array([90, 135, 95])],
        'upper': [np.array([128, 255, 255])],
        'bgr': (255, 150, 0), 'label': '魏',
    },
    'wu': {
        'lower': [np.array([36, 155, 110])],
        'upper': [np.array([82, 255, 255])],
        'bgr': (0, 220, 0), 'label': '吴',
    },
    'shu': {
        'lower': [np.array([0, 145, 115]), np.array([165, 145, 115])],
        'upper': [np.array([12, 255, 255]), np.array([180, 255, 255])],
        'bgr': (0, 0, 255), 'label': '蜀',
    },
}


# ========== 检测城池 ==========

def _find_centers(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MIN_CITY_AREA < area < MAX_CITY_AREA):
            continue
        peri = cv2.arcLength(cnt, True)
        if peri == 0:
            continue
        circ = 4 * np.pi * area / (peri * peri)
        if circ < MIN_CIRCULARITY:
            continue
        hull = cv2.convexHull(cnt)
        ha = cv2.contourArea(hull)
        if ha > 0 and (area / ha) < MIN_SOLIDITY:
            continue
        M = cv2.moments(cnt)
        if M["m00"] <= 0:
            continue
        centers.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
    return centers


def _merge(points, min_d=MERGE_DIST):
    if not points:
        return []
    pts = list(points)
    used = [False] * len(pts)
    out = []
    for i in range(len(pts)):
        if used[i]:
            continue
        gx, gy, gc = pts[i][0], pts[i][1], 1
        used[i] = True
        for j in range(i + 1, len(pts)):
            if used[j]:
                continue
            if abs(pts[i][0] - pts[j][0]) + abs(pts[i][1] - pts[j][1]) < min_d * 1.5:
                d = np.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                if d < min_d:
                    gx += pts[j][0]
                    gy += pts[j][1]
                    gc += 1
                    used[j] = True
        out.append((int(gx / gc), int(gy / gc)))
    return out


def detect_all_cities(map_img):
    hsv = cv2.cvtColor(map_img, cv2.COLOR_BGR2HSV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    all_cities = []

    for kingdom, cfg in HSV_RANGES.items():
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in zip(cfg['lower'], cfg['upper']):
            mask |= cv2.inRange(hsv, lo, hi)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        pts = _merge(_find_centers(mask))
        for p in pts:
            sx = p[0] + MAP_REGION[0]
            sy = p[1] + MAP_REGION[1]
            all_cities.append({'map_pos': p, 'screen_pos': (sx, sy), 'kingdom': kingdom})

    all_cities.sort(key=lambda c: (c['screen_pos'][1], c['screen_pos'][0]))
    for i, c in enumerate(all_cities):
        c['id'] = i
    return all_cities


# ========== 连接关系（Delaunay + 过滤） ==========

def _is_mountain_path(gray, p1, p2, n_samples=25):
    """沿路径采样，检测是否穿过高亮度的山脉区域"""
    h, w = gray.shape
    bright_count = 0
    for t in np.linspace(0.15, 0.85, n_samples):
        x = int(p1[0] + t * (p2[0] - p1[0]))
        y = int(p1[1] + t * (p2[1] - p1[1]))
        if 0 <= x < w and 0 <= y < h:
            if gray[y, x] > MOUNTAIN_BRIGHT_THRESH:
                bright_count += 1
    ratio = bright_count / n_samples if n_samples > 0 else 0
    return ratio > MOUNTAIN_RATIO_THRESH


def build_adjacency_delaunay(cities, map_img):
    """用 Delaunay 三角剖分建立连接，过滤长边和穿山边"""
    if len(cities) < 3:
        return {c['id']: [] for c in cities}, []

    pts = np.array([c['map_pos'] for c in cities], dtype=np.float64)
    tri = Delaunay(pts)

    gray = cv2.cvtColor(map_img, cv2.COLOR_BGR2GRAY)

    edge_set = set()
    for simplex in tri.simplices:
        for k in range(3):
            i, j = int(simplex[k]), int(simplex[(k + 1) % 3])
            edge_set.add((min(i, j), max(i, j)))

    neighbors = {c['id']: [] for c in cities}
    roads = []

    for i, j in edge_set:
        d = np.linalg.norm(pts[i] - pts[j])
        if d > MAX_ROAD_DIST:
            continue
        p1 = (int(pts[i][0]), int(pts[i][1]))
        p2 = (int(pts[j][0]), int(pts[j][1]))
        if _is_mountain_path(gray, p1, p2):
            continue
        ci, cj = cities[i]['id'], cities[j]['id']
        neighbors[ci].append(cj)
        neighbors[cj].append(ci)
        roads.append((ci, cj, round(d, 1)))

    for k in neighbors:
        neighbors[k].sort()
    return neighbors, roads


# ========== 可视化 ==========

def draw_debug(full_img, cities, neighbors, path="debug_city_map.png"):
    canvas = full_img.copy()
    pos_map = {c['id']: c['screen_pos'] for c in cities}
    kcolors = {'wei': (255, 150, 0), 'wu': (0, 220, 0), 'shu': (0, 0, 255)}

    drawn = set()
    for cid, nbs in neighbors.items():
        for nb in nbs:
            e = (min(cid, nb), max(cid, nb))
            if e not in drawn:
                drawn.add(e)
                cv2.line(canvas, pos_map[cid], pos_map[nb], (120, 120, 120), 1, cv2.LINE_AA)

    for c in cities:
        sp = c['screen_pos']
        cv2.circle(canvas, sp, 5, kcolors[c['kingdom']], -1)
        cv2.circle(canvas, sp, 5, (255, 255, 255), 1)
        cv2.putText(canvas, str(c['id']), (sp[0] + 6, sp[1] - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, (255, 255, 255), 1)

    cv2.imwrite(path, canvas)
    print(f"[OK] 验证图: {path}")


# ========== 生成数据文件 ==========

def write_data(cities, neighbors, path="city_data.py"):
    lines = [
        "# -*- encoding=utf8 -*-",
        '"""',
        "城池地图数据 (1280x720 分辨率)",
        "CITIES[id] = (screen_x, screen_y, kingdom)",
        "NEIGHBORS[id] = [相邻城池id, ...]",
        '"""',
        "",
        "CITIES = {",
    ]
    for c in cities:
        sx, sy = c['screen_pos']
        lines.append(f"    {c['id']}: ({sx}, {sy}, \"{c['kingdom']}\"),")
    lines.append("}")
    lines.append("")
    lines.append("NEIGHBORS = {")
    for c in cities:
        nbs = neighbors.get(c['id'], [])
        lines.append(f"    {c['id']}: {nbs},")
    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def get_border_targets(my_kingdom='wei'):")
    lines.append('    """获取可攻击的交界敌方城池列表"""')
    lines.append("    my_ids = {cid for cid, v in CITIES.items() if v[2] == my_kingdom}")
    lines.append("    targets = []")
    lines.append("    seen = set()")
    lines.append("    for cid in my_ids:")
    lines.append("        for nb in NEIGHBORS.get(cid, []):")
    lines.append("            if nb not in my_ids and nb not in seen:")
    lines.append("                seen.add(nb)")
    lines.append("                info = CITIES[nb]")
    lines.append("                targets.append({'id': nb, 'pos': (info[0], info[1]),")
    lines.append("                    'kingdom': info[2], 'from_ally': cid,")
    lines.append("                    'ally_pos': (CITIES[cid][0], CITIES[cid][1])})")
    lines.append("    return targets")
    lines.append("")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"[OK] 数据: {path}")


# ========== 主流程 ==========

def main():
    print("=" * 60)
    print("  城池地图完整数据生成")
    print("=" * 60)

    full = cv2.imread("tpl1773477536988.png")
    h, w = full.shape[:2]
    if (w, h) != (SCREEN_W, SCREEN_H):
        full = cv2.resize(full, (SCREEN_W, SCREEN_H))

    l, t, r, b = MAP_REGION
    map_img = full[t:b, l:r].copy()

    print("[1/4] 检测城池...")
    cities = detect_all_cities(map_img)
    for k in ('wei', 'wu', 'shu'):
        n = sum(1 for c in cities if c['kingdom'] == k)
        print(f"  {HSV_RANGES[k]['label']}国: {n}")
    print(f"  合计: {len(cities)}")

    print("[2/4] Delaunay 三角剖分 + 连接过滤...")
    neighbors, roads = build_adjacency_delaunay(cities, map_img)
    print(f"  连接数: {len(roads)}")

    deg = [len(neighbors[c['id']]) for c in cities]
    print(f"  每城连接数: min={min(deg)} max={max(deg)} avg={np.mean(deg):.1f}")
    iso = [c['id'] for c in cities if not neighbors[c['id']]]
    if iso:
        print(f"  [WARN] 孤立城池: {iso}")

    print("[3/4] 写数据...")
    write_data(cities, neighbors)

    print("[4/4] 画验证图...")
    draw_debug(full, cities, neighbors)

    wei_ids = {c['id'] for c in cities if c['kingdom'] == 'wei'}
    border_e = set()
    border_a = set()
    for wid in wei_ids:
        for nb in neighbors[wid]:
            if nb not in wei_ids:
                border_e.add(nb)
                border_a.add(wid)
    print(f"\n--- 魏国交界 ---")
    print(f"  我方交界: {len(border_a)}")
    print(f"  可攻击敌方: {len(border_e)}")
    print("[完成]")


if __name__ == '__main__':
    main()
