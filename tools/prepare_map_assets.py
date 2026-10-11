"""Build AURA's offline Natural Earth GeoJSON from official SHP archives.

Build-time tool only. Runtime has no shapefile dependency or network access.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import zipfile
from pathlib import Path

REGION = (-14.0, 30.0, 38.0, 72.0)  # west, south, east, north
TOLERANCE = {'50m': 0.02, '10m': 0.005}  # degrees; build-time only


def simplify(points, tolerance, closed=False):
    """Douglas-Peucker with preserved endpoints and polygon closure."""
    values = points[:-1] if closed and points[0] == points[-1] else points
    if len(values) <= (3 if closed else 2): return points
    # For a ring, use an approximately opposite vertex as a stable second
    # endpoint so the closure seam cannot collapse into a straight chord.
    if closed:
        opposite = max(range(1, len(values)), key=lambda i: (values[i][0]-values[0][0])**2 + (values[i][1]-values[0][1])**2)
        left = simplify(values[:opposite+1], tolerance)
        right = simplify(values[opposite:] + values[:1], tolerance)
        result = left[:-1] + right[:-1]
        return result + [result[0]] if len(result) >= 3 else points
    keep = {0, len(values)-1}; stack = [(0, len(values)-1)]; squared = tolerance*tolerance
    while stack:
        a, b = stack.pop(); x1, y1 = values[a]; x2, y2 = values[b]
        dx, dy = x2-x1, y2-y1; length = dx*dx+dy*dy
        best_index, best_distance = -1, squared
        for i in range(a+1, b):
            x, y = values[i]
            t = max(0.0, min(1.0, ((x-x1)*dx+(y-y1)*dy)/length)) if length else 0.0
            distance = (x-(x1+t*dx))**2 + (y-(y1+t*dy))**2
            if distance > best_distance: best_index, best_distance = i, distance
        if best_index >= 0:
            keep.add(best_index); stack.extend(((a,best_index),(best_index,b)))
    return [values[i] for i in sorted(keep)]


def shapes(shp: bytes):
    if shp[:4] != b"\0\0'\n" or struct.unpack_from('<i', shp, 32)[0] not in (3, 5):
        raise ValueError('unsupported Natural Earth SHP')
    offset = 100
    while offset + 8 <= len(shp):
        size = struct.unpack_from('>i', shp, offset + 4)[0] * 2
        record = memoryview(shp)[offset + 8:offset + 8 + size]
        offset += 8 + size
        if len(record) < 44: continue
        kind = struct.unpack_from('<i', record, 0)[0]
        if kind == 0: continue
        if kind not in (3, 5): raise ValueError(f'unsupported shape type {kind}')
        part_count, point_count = struct.unpack_from('<2i', record, 36)
        starts = list(struct.unpack_from(f'<{part_count}i', record, 44)) + [point_count]
        points_offset = 44 + part_count * 4
        if points_offset + point_count * 16 > len(record): raise ValueError('truncated SHP record')
        points = [list(struct.unpack_from('<2d', record, points_offset + i * 16)) for i in range(point_count)]
        for point in points:
            if not all(math.isfinite(v) for v in point) or abs(point[0]) > 180 or abs(point[1]) > 90:
                raise ValueError('invalid coordinate')
        for a, b in zip(starts, starts[1:]):
            if b - a >= 2: yield kind, points[a:b]


def _clip_segment(a, b, box):
    west, south, east, north = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - west), (dx, east - a[0]), (-dy, a[1] - south), (dy, north - a[1])):
        if p == 0:
            if q < 0: return None
        else:
            t = q / p
            if p < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
            if t0 > t1: return None
    return ([a[0] + t0 * dx, a[1] + t0 * dy], [a[0] + t1 * dx, a[1] + t1 * dy])


def clip_line(points, box):
    chunks, current = [], []
    for a, b in zip(points, points[1:]):
        segment = _clip_segment(a, b, box)
        if segment:
            x, y = segment
            if current and current[-1] != x:
                if len(current) > 1: chunks.append(current)
                current = []
            if not current: current = [x]
            current.append(y)
        elif current:
            if len(current) > 1: chunks.append(current)
            current = []
    if len(current) > 1: chunks.append(current)
    return chunks


def clip_ring(points, box):
    west, south, east, north = box
    ring = points[:-1] if points and points[0] == points[-1] else points[:]
    for axis, edge, inside in ((0, west, lambda v: v >= west), (0, east, lambda v: v <= east),
                               (1, south, lambda v: v >= south), (1, north, lambda v: v <= north)):
        if not ring: return []
        output = []
        prev = ring[-1]
        for cur in ring:
            pv, cv = inside(prev[axis]), inside(cur[axis])
            if pv != cv:
                ratio = (edge - prev[axis]) / (cur[axis] - prev[axis])
                output.append([prev[0] + ratio * (cur[0] - prev[0]), prev[1] + ratio * (cur[1] - prev[1])])
            if cv: output.append(cur)
            prev = cur
        ring = output
    return ring + [ring[0]] if len(ring) >= 3 else []


def convert(archive: Path, output: Path, region=None, tolerance=0.0):
    with zipfile.ZipFile(archive) as source:
        names = [name for name in source.namelist() if name.lower().endswith('.shp')]
        if len(names) != 1: raise ValueError(f'expected one SHP in {archive.name}')
        raw = source.read(names[0])
    features = []
    for kind, points in shapes(raw):
        if kind == 5:
            ring = clip_ring(points, region) if region else points
            if len(ring) < 4: continue
            if tolerance: ring = simplify(ring, tolerance, closed=True)
            geometry = {'type': 'Polygon', 'coordinates': [ring]}
        else:
            lines = clip_line(points, region) if region else [points]
            for line in lines:
                if tolerance: line = simplify(line, tolerance)
                features.append({'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': line}})
            continue
        features.append({'type': 'Feature', 'properties': {}, 'geometry': geometry})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return len(features)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    for scale, kind, output in (('50m', 'land', 'world_50m_land.geojson'), ('50m', 'coastline', 'world_50m_coastline.geojson'),
                                ('10m', 'land', 'europe_10m_land.geojson'), ('10m', 'coastline', 'europe_10m_coastline.geojson')):
        count = convert(args.source_dir / f'ne_{scale}_{kind}.zip', args.output_dir / output, REGION if scale == '10m' else None, TOLERANCE[scale])
        print(f'{output}: {count} features', flush=True)


if __name__ == '__main__': main()
