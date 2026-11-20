"""Street-level photos along a walk, from Mapillary.

What this does: for a few points spaced along a route, ask Mapillary for photos taken within 25 m of the point and
return at most one per point — a normal (non-panorama) photo, preferably looking the way the walk goes — with its
capture date, author and a link to its Mapillary page. Photos are CC BY-SA (Mapillary terms); the caller must show
the attribution this module returns.

What it never does: invent, substitute or guess. A point with no photo within 25 m returns nothing. The distance
from the route and the capture date are returned with every photo so the page can say how close and how old it is.

The access token is read from the MAPILLARY_TOKEN environment variable on the API host. It is never sent to the
browser and never stored in the repository. Without it the endpoint answers {"configured": false}.
Only the app's *access token* is needed. The app's *client secret* is for OAuth sign-in and must not be used here.
"""
import json
import math
import os
import threading
import time
from urllib import parse, request

API = 'https://graph.mapillary.com/images'
FIELDS = 'id,computed_geometry,geometry,computed_compass_angle,compass_angle,captured_at,is_pano,thumb_1024_url,creator'
RADIUS_M = 25            # a photo must be taken within this distance of the route point
POINTS = 5               # route points asked about (one request each)
SKIP_END_M = 40          # do not sample right at the start or the end
ALIGN_DEG = 60           # "looking along the walk" = camera heading within this of the walking direction
MAX_COORDS = 6000
CACHE_SECONDS = 20 * 60  # Mapillary thumbnail URLs are signed and expire, so results are kept only briefly
NYC_BOX = (-74.30, 40.45, -73.65, 40.95)   # this proxy only answers for points in the app's area
ATTRIBUTION = 'Images from Mapillary, CC BY-SA'

_cache = {}
_lock = threading.Lock()


def token():
    return (os.environ.get('MAPILLARY_TOKEN') or '').strip()


def configured():
    t = token()
    return t.startswith('MLY|') and t.count('|') == 2


def metres(a, b):
    """Distance between two (lon, lat) points, equirectangular (fine at city scale)."""
    k = math.pi / 180
    x = (b[0] - a[0]) * math.cos((a[1] + b[1]) / 2 * k)
    return math.hypot(x, b[1] - a[1]) * k * 6371008.8


def bearing(a, b):
    k = math.pi / 180
    y = math.sin((b[0] - a[0]) * k) * math.cos(b[1] * k)
    x = math.cos(a[1] * k) * math.sin(b[1] * k) - math.sin(a[1] * k) * math.cos(b[1] * k) * math.cos((b[0] - a[0]) * k)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def validate(coords):
    if not isinstance(coords, list) or not 2 <= len(coords) <= MAX_COORDS:
        raise ValueError(f'coordinates must be a list of 2 to {MAX_COORDS} [lon, lat] pairs')
    out = []
    for c in coords:
        if (not isinstance(c, (list, tuple)) or len(c) < 2 or isinstance(c[0], bool) or isinstance(c[1], bool)
                or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in c[:2])):
            raise ValueError('coordinates must be [lon, lat] number pairs')
        lon, lat = float(c[0]), float(c[1])
        if not (NYC_BOX[0] <= lon <= NYC_BOX[2] and NYC_BOX[1] <= lat <= NYC_BOX[3]):
            raise ValueError('coordinates are outside the area this app covers')
        out.append((lon, lat))
    return out


def sample_points(coords, n=POINTS, skip=SKIP_END_M):
    """Up to n points evenly spaced along the line: [{at_m, lon, lat, bearing}], bearing = walking direction there."""
    cum = [0.0]
    for a, b in zip(coords, coords[1:]):
        cum.append(cum[-1] + metres(a, b))
    total = cum[-1]
    if total <= 2 * skip:
        return []
    n = max(1, min(n, int((total - 2 * skip) // (2 * RADIUS_M)) + 1))   # never two samples whose search circles overlap
    targets = [skip + (total - 2 * skip) * (i + 0.5) / n for i in range(n)]
    out, seg = [], 0
    for t in targets:
        while seg < len(cum) - 2 and cum[seg + 1] < t:
            seg += 1
        a, b, span = coords[seg], coords[seg + 1], cum[seg + 1] - cum[seg]
        f = 0 if span == 0 else (t - cum[seg]) / span
        out.append({'at_m': round(t), 'lon': a[0] + (b[0] - a[0]) * f, 'lat': a[1] + (b[1] - a[1]) * f,
                    'bearing': round(bearing(a, b), 1) if span else None})
    return out


def choose(images, point):
    """The one photo to show for a route point, or None. Never a panorama, never one taken beyond RADIUS_M."""
    best = None
    for im in images if isinstance(images, list) else []:
        if not isinstance(im, dict) or im.get('is_pano') or not im.get('thumb_1024_url') or not im.get('id'):
            continue
        geom = (im.get('computed_geometry') or im.get('geometry') or {}).get('coordinates')
        if not (isinstance(geom, list) and len(geom) >= 2 and all(isinstance(v, (int, float)) for v in geom[:2])):
            continue
        dist = metres((point['lon'], point['lat']), (geom[0], geom[1]))
        captured = im.get('captured_at')
        if dist > RADIUS_M or not isinstance(captured, (int, float)) or isinstance(captured, bool):
            continue
        heading = im.get('computed_compass_angle', im.get('compass_angle'))
        diff = angle_diff(heading, point['bearing']) if isinstance(heading, (int, float)) and point.get('bearing') is not None else None
        along = diff is not None and diff <= ALIGN_DEG
        key = (0 if along else 1, -captured, dist)          # looking along the walk first, then newest, then nearest
        if best is None or key < best[0]:
            creator = im.get('creator') if isinstance(im.get('creator'), dict) else {}
            best = (key, {
                'image_id': str(im['id']), 'thumb': im['thumb_1024_url'], 'at_m': point['at_m'],
                'distance_m': round(dist, 1), 'captured_on': time.strftime('%Y-%m-%d', time.gmtime(captured / 1000)),
                'looks_along_walk': along, 'username': str(creator.get('username') or '') or None,
                'page': 'https://www.mapillary.com/app/?pKey=' + parse.quote(str(im['id']), safe=''),
            })
    return best[1] if best else None


def fetch_images(lon, lat, opener=request.urlopen):
    q = parse.urlencode({'lat': f'{lat:.6f}', 'lng': f'{lon:.6f}', 'radius': RADIUS_M, 'limit': 30, 'fields': FIELDS})
    req = request.Request(f'{API}?{q}', headers={'Authorization': 'OAuth ' + token(), 'User-Agent': 'STROLLANE-NYC/1.0'})
    with opener(req, timeout=6) as resp:
        doc = json.loads(resp.read(2_000_000).decode('utf-8'))
    return doc.get('data') if isinstance(doc, dict) else []


def along_route(coords, opener=request.urlopen, now=time.time):
    """{'configured', 'photos': [...], 'checked_points', 'failed_points', 'attribution', ...} for a route line."""
    base = {'source': 'Mapillary', 'license': 'CC BY-SA 4.0', 'attribution': ATTRIBUTION, 'radius_m': RADIUS_M}
    if not configured():
        return {**base, 'configured': False, 'photos': [], 'checked_points': 0, 'failed_points': 0}
    points, photos, failed = sample_points(validate(coords)), [], 0
    for p in points:
        key = (round(p['lon'], 5), round(p['lat'], 5), round((p['bearing'] or 0) / 30))
        with _lock:
            hit = _cache.get(key)
        if hit and now() - hit[0] < CACHE_SECONDS:
            photo = hit[1]
        else:
            try:
                photo = choose(fetch_images(p['lon'], p['lat'], opener), p)
            except Exception:                 # provider down, bad token, timeout: this point simply has no photo
                failed += 1
                continue
            with _lock:
                if len(_cache) > 4000:
                    _cache.clear()
                _cache[key] = (now(), photo)
        if photo and all(photo['image_id'] != x['image_id'] for x in photos):
            photos.append({**photo, 'at_m': p['at_m']})
    return {**base, 'configured': True, 'photos': photos, 'checked_points': len(points), 'failed_points': failed}


PLACE_RADIUS_M = 30      # a street photo "of a place" must be taken within this distance of it
PLACE_FACING_DEG = 50    # ... and preferably looking at it (camera heading within this of the direction to it)
MAX_PLACES = 8


def validate_places(places):
    if not isinstance(places, list) or not 1 <= len(places) <= MAX_PLACES:
        raise ValueError(f'places must be a list of 1 to {MAX_PLACES} {{id, lon, lat}} objects')
    out = []
    for p in places:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not 0 < len(p['id']) <= 80:
            raise ValueError('each place needs an id (string)')
        lon, lat = p.get('lon'), p.get('lat')
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lon, lat)):
            raise ValueError('each place needs lon and lat numbers')
        if not (NYC_BOX[0] <= lon <= NYC_BOX[2] and NYC_BOX[1] <= lat <= NYC_BOX[3]):
            raise ValueError('places must be inside the area this app covers')
        out.append({'id': p['id'], 'lon': float(lon), 'lat': float(lat)})
    return out


def choose_for_place(images, place):
    """The street-level photo to show for a place, or None: taken within PLACE_RADIUS_M, never a panorama, looking
    at the place first (heading within PLACE_FACING_DEG of the direction from the camera to the place), then nearest,
    then newest. It shows the street at the place, not necessarily the place itself; the caller must say so."""
    best = None
    for im in images if isinstance(images, list) else []:
        if not isinstance(im, dict) or im.get('is_pano') or not im.get('thumb_1024_url') or not im.get('id'):
            continue
        geom = (im.get('computed_geometry') or im.get('geometry') or {}).get('coordinates')
        if not (isinstance(geom, list) and len(geom) >= 2 and all(isinstance(v, (int, float)) for v in geom[:2])):
            continue
        cam, at = (geom[0], geom[1]), (place['lon'], place['lat'])
        dist = metres(cam, at)
        captured = im.get('captured_at')
        if dist > PLACE_RADIUS_M or not isinstance(captured, (int, float)) or isinstance(captured, bool):
            continue
        heading = im.get('computed_compass_angle', im.get('compass_angle'))
        facing = isinstance(heading, (int, float)) and dist >= 3 and angle_diff(heading, bearing(cam, at)) <= PLACE_FACING_DEG
        key = (0 if facing else 1, round(dist / 10), -captured)
        if best is None or key < best[0]:
            creator = im.get('creator') if isinstance(im.get('creator'), dict) else {}
            best = (key, {
                'image_id': str(im['id']), 'thumb': im['thumb_1024_url'], 'distance_m': round(dist, 1),
                'captured_on': time.strftime('%Y-%m-%d', time.gmtime(captured / 1000)), 'faces_place': facing,
                'username': str(creator.get('username') or '') or None,
                'page': 'https://www.mapillary.com/app/?pKey=' + parse.quote(str(im['id']), safe=''),
            })
    return best[1] if best else None


def at_places(places, opener=request.urlopen, now=time.time):
    """{'configured', 'photos': {place_id: photo}, 'failed', 'attribution', ...}: a street-level photo taken at each
    place (for places with no photo of their own). Places with no photo within PLACE_RADIUS_M are left out."""
    base = {'source': 'Mapillary', 'license': 'CC BY-SA 4.0', 'attribution': ATTRIBUTION, 'radius_m': PLACE_RADIUS_M}
    if not configured():
        return {**base, 'configured': False, 'photos': {}, 'failed': 0}
    out, failed = {}, 0
    for p in validate_places(places):
        key = ('place', round(p['lon'], 5), round(p['lat'], 5))
        with _lock:
            hit = _cache.get(key)
        if hit and now() - hit[0] < CACHE_SECONDS:
            photo = hit[1]
        else:
            try:
                q = parse.urlencode({'lat': f"{p['lat']:.6f}", 'lng': f"{p['lon']:.6f}", 'radius': PLACE_RADIUS_M, 'limit': 40, 'fields': FIELDS})
                req = request.Request(f'{API}?{q}', headers={'Authorization': 'OAuth ' + token(), 'User-Agent': 'STROLLANE-NYC/1.0'})
                with opener(req, timeout=6) as resp:
                    doc = json.loads(resp.read(2_000_000).decode('utf-8'))
                photo = choose_for_place(doc.get('data') if isinstance(doc, dict) else [], p)
            except Exception:
                failed += 1
                continue
            with _lock:
                if len(_cache) > 4000:
                    _cache.clear()
                _cache[key] = (now(), photo)
        if photo:
            out[p['id']] = photo
    return {**base, 'configured': True, 'photos': out, 'failed': failed}
