#!/usr/bin/env python3
"""Chinese names for places, for the Chinese interface: data/places/names-zh.json.

Input: a JSON object {English name: Chinese label} collected from Wikidata. The names are those of the place
index (data/places/*.json) whose records carry a Wikidata ID (`wd`); the labels are Wikidata's own, read with
wbgetentities (props=labels, languages zh-hans|zh-cn|zh-sg|zh-my|zh, first one that is present). Wikidata is not
reachable from the build machines, so the collection ran in a browser; the object it produced is this script's input.

What is kept: Wikidata labels are written for an encyclopedia, so some do not name the place a walker sees.
 * A label for a subway station given to a street (Fulton Street → 福尔顿街车站) is dropped: a street name in a
   route card is the street, not the station.
 * A disambiguator in brackets is removed (圣伊纳爵堂 (纽约市) → 圣伊纳爵堂).
 * Labels that name something else (the 9/11 attacks for the memorial, a whole borough for Weeksville, an earlier name
   of a renamed theatre) are dropped or corrected by hand below.
 * Traditional characters become simplified (OpenCC t2s), since the interface is simplified Chinese.

Usage: python3 scripts/curate_place_names_zh.py RAW.json [RAW2.json …] [-o data/places/names-zh.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    from opencc import OpenCC  # pip install opencc-python-reimplemented
except ImportError:  # pragma: no cover - the build needs it, the tests do not
    OpenCC = None

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'places' / 'names-zh.json'

# A Wikidata label that names something other than the place, or a former name: dropped.
DROP = {
    'Amsterdam Avenue',  # merged with Tenth Avenue in Wikidata
    'Basilica of Saint Patrick\'s Old Cathedral - Most Precious Blood Catholic Church',
    'Bloody Angle',  # the label is Doyers Street
    'Burlington',  # the company, not the store
    'Carrere Memorial',  # the architects' firm
    'City Center', 'Mecca Temple', 'New York City Center',  # 纽约市中心 reads as "the centre of New York"
    'Cooper–Hewitt, Smithsonian Design Museum',  # the label is the Carnegie mansion it is housed in
    'East Village Hotel',  # the neighbourhood
    'Fire Engine Company No. 54',  # a theatre nearby
    'First Church of Christ, Scientist',  # the label is the Second Church
    'Fort Washington Park',
    'Fuentidueña Chapel',  # the label is just "apse"
    'Gay Street',
    'Gerald Schoenfeld Theatre', 'James Earl Jones Theatre', 'Lena Horne Theatre',  # former names of the theatres
    'Grand Hotel',
    'Iglesia ACM de Queens',  # the denomination
    'Long Island College Hospital Park',  # the hospital
    'Park Lane New York',
    'Pier 76',  # the whole Hudson River Park
    'Pratt Row Houses',  # the institute
    'Public Baths',
    'The Standard', 'The Washington New York City',
    'Theatre Row',  # one theatre in the row
    'Universalist Church of New York',
    'Vessel',  # the label is the English name with a note in brackets
    'Weeksville',  # the label is Brooklyn
    'West 155th Street',  # the bridge at its end
}
# A better-known or correct Chinese name.
OVERRIDE = {
    '9/11 Memorial & Museum': '九一一国家纪念博物馆',  # the label was the attacks themselves
    'Brooklyn Public Library': '布鲁克林公共图书馆',
    'Brooklyn Public Library, Central Building': '布鲁克林公共图书馆中央馆',
    'Battery Park': '炮台公园',
    'Bryant Park': '布莱恩特公园',
    'Carnegie Hall': '卡内基音乐厅',
    'Cathedral of St. Sava': '塞尔维亚东正教圣萨瓦大教堂',  # the label lost its first two characters
    'Trinity Chapel Complex': '塞尔维亚东正教圣萨瓦大教堂',
    'City Hall': '纽约市政厅',  # the label was the subway station
    'Grand Central Terminal': '纽约中央车站',
    'David Geffen Hall': '大卫·格芬音乐厅',  # the label was the hall's former name
    'John Golden Theatre': '约翰·戈尔登剧院',  # the label translated "Golden"
    'National Museum of the American Indian': '美国印第安人国家博物馆',
    'New York Central Building': '赫尔姆斯利大厦',  # not a hotel
    'Parachute Jump': '跳伞塔',
    'Perelman Performing Arts Center': '佩雷尔曼表演艺术中心',
    'Times Square': '时代广场', 'Times Square Ball': '时代广场水晶球',
}
STATION = re.compile(r'[车車]站')
BRACKETS = re.compile(r'\s*[(（][^)）]*[)）]\s*')
HAN = re.compile(r'[一-鿿]')


def curate(raw, convert=None):
    """{English: Chinese} → the kept, cleaned {English: Chinese}; `convert` turns traditional into simplified."""
    out = {}
    for en, zh in raw.items():
        if en in DROP:
            continue
        if en in OVERRIDE:
            out[en] = OVERRIDE[en]
            continue
        if STATION.search(zh) and not re.search(r'station|terminal', en, re.I):
            continue
        zh = BRACKETS.sub('', zh).strip(' ·・')
        if not HAN.search(zh):
            continue
        if convert:
            zh = convert(zh)
        if zh and zh != en:
            out[en] = zh
    return dict(sorted(out.items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('raw', nargs='+', type=Path)
    ap.add_argument('-o', '--out', type=Path, default=OUT)
    ap.add_argument('--retrieved', default='2026-11-21')
    a = ap.parse_args(argv)
    if OpenCC is None:
        sys.exit('needs OpenCC: pip install opencc-python-reimplemented')
    raw = {}
    for p in a.raw:
        raw.update(json.loads(p.read_text(encoding='utf-8')))
    names = curate(raw, OpenCC('t2s').convert)
    doc = {
        'source': 'Wikidata labels (zh-hans, zh-cn, zh-sg, zh-my, zh) of the places in data/places/*.json that carry a '
                  'Wikidata ID; checked by scripts/curate_place_names_zh.py',
        'license': 'CC0 1.0 (Wikidata)',
        'retrieved': a.retrieved,
        'count': len(names),
        'names': names,
    }
    a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=0, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{len(raw)} labels → {len(names)} names → {a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out}')


if __name__ == '__main__':
    main()
