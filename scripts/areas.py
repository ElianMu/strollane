"""Study areas beyond Manhattan: what each public source calls them, and their bounding boxes.

Manhattan's own build (scripts/streetwise_indicators.py and the scripts that read it) is unchanged and does not read
this file. It is the single place where a new area is described for scripts/download_area_sources.py and
scripts/build_pedestrian_network.py --area.

Long Island City is not an administrative unit in any of these sources, so it is a box inside Queens. The box is a
working definition: Newtown Creek to the south, the East River to the west, about 36th Avenue / Queensbridge to the
north and the Sunnyside rail yards to the east. Sources are downloaded for Queens (or for the box, where a source can
filter by geometry) and cut to the box afterwards; the box can be tightened later without downloading again.
"""

AREAS = {
    'brooklyn': {
        'label': 'Brooklyn (Kings County, LION borocode 3)',
        'box': (-74.0420, 40.5700, -73.8330, 40.7395),  # west, south, east, north (WGS84)
        'clip_to_box': False,
        'borocode': '3', 'lpc_boro': 'Brooklyn', 'parks_borough': 'B', 'borough_upper': 'BROOKLYN',
        'osm_place': 'Brooklyn, Kings County, New York, United States',
    },
    'lic': {
        'label': 'Long Island City (working box inside Queens, LION borocode 4)',
        'box': (-73.9650, 40.7280, -73.9150, 40.7750),
        'clip_to_box': True,
        'borocode': '4', 'lpc_boro': 'Queens', 'parks_borough': 'Q', 'borough_upper': 'QUEENS',
        'osm_place': None,  # no OSM boundary to geocode: the walk network is cut by the box
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
