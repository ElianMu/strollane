"""Study areas beyond Manhattan: what each public source calls them, and their bounding boxes.

Manhattan's own build (scripts/streetwise_indicators.py and the scripts that read it) is unchanged and does not read
this file. It is the single place where a new area is described for scripts/download_area_sources.py and
scripts/build_pedestrian_network.py --area.

Queens is the whole borough (Queens County; LION borocode 4), as Brooklyn is. It was first a box around Long Island City,
then western Queens (to Jackson Heights), while the router cost about 0.6 MB per 1,000 edges; with the router's columns
(routing/compact.py, 2026-11-18: about 0.32 MB per 1,000 edges) the whole borough fits the 512 MB server. Its id stays
'lic', so file names and segment IDs do not change. The box is the borough's bounding box (Rockaway Point to Little
Neck, Long Island City to Glen Oaks); it reaches into Brooklyn, the Bronx and Nassau County, so records are kept by
borough (borocode / borough fields) or by the OSM boundary of Queens County (data/pedestrian/lic-boundary.json, written
by scripts/build_pedestrian_network.py), never by the box alone.
"""

AREAS = {
    'brooklyn': {
        'label': 'Brooklyn (Kings County, LION borocode 3)',
        'short': 'Brooklyn',
        'box': (-74.0420, 40.5700, -73.8330, 40.7395),  # west, south, east, north (WGS84)
        'clip_to_box': False,
        'borocode': '3', 'lpc_boro': 'Brooklyn', 'parks_borough': 'B', 'borough_upper': 'BROOKLYN',
        'osm_place': 'Brooklyn, Kings County, New York, United States',
    },
    'lic': {  # Queens; the id is historical (see above)
        'label': 'Queens (Queens County, LION borocode 4)',
        'short': 'Queens',
        'box': (-73.9630, 40.5410, -73.7000, 40.8010),
        'clip_to_box': False,
        'borocode': '4', 'lpc_boro': 'Queens', 'parks_borough': 'Q', 'borough_upper': 'QUEENS',
        'osm_place': 'Queens County, New York, United States',
    },
}


def in_box(lon, lat, box):
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def coords_of(geometry):
    """Every [lon, lat] of a GeoJSON geometry, whatever its nesting."""
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c or []:
                yield from walk(x)
    return walk((geometry or {}).get('coordinates') or [])


def touches_box(geometry, box):
    return any(in_box(c[0], c[1], box) for c in coords_of(geometry))
