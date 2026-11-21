"""data/places/names-zh.json: Chinese names shown beside English place names in the Chinese interface."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from curate_place_names_zh import DROP, OVERRIDE, curate  # noqa: E402

DOC = json.loads((ROOT / 'data/places/names-zh.json').read_text(encoding='utf-8'))
NAMES = DOC['names']


def test_file_says_where_the_names_come_from():
    assert 'Wikidata' in DOC['source'] and DOC['license'].startswith('CC0') and DOC['retrieved']
    assert DOC['count'] == len(NAMES) > 500


def test_every_name_is_a_clean_chinese_name():
    for en, zh in NAMES.items():
        assert re.search(r'[一-鿿]', zh), en
        assert not re.search(r'[()（）]', zh), (en, zh)
        assert not zh.startswith('·'), (en, zh)
        if re.search(r'[车車]站', zh):
            assert re.search(r'station|terminal', en, re.I), (en, zh)


def test_simplified_characters():
    # a few traditional characters that appear in Wikidata's zh labels and must not reach the interface
    assert not any(re.search(r'[國園門館際廣場樂劇區圖書館會灣橋舊東]', zh) for zh in NAMES.values())


def test_wrong_labels_are_dropped_or_corrected():
    assert not set(NAMES) & DROP
    for en, zh in OVERRIDE.items():
        assert NAMES.get(en) == zh, en
    assert NAMES['Flatiron Building'] == '熨斗大厦' and NAMES['Central Park'] == '中央公园'
    assert 'Fulton Street' not in NAMES  # Wikidata's label is the subway station


def test_curation_rules():
    raw = {'Fulton Street': '福爾頓街車站 (BMT第五大道線)', 'Reid Avenue Station': '萊德大道車站', 'Vessel': 'Vessel (建築物)',
           'Alma Mater': '智慧女神 (紐約雕塑)', 'Fred F. French Building': '·弗雷德·F.·法兰奇大厦', 'Weeksville': '布魯克林',
           'Times Square': '时报广场'}
    assert curate(raw) == {'Alma Mater': '智慧女神', 'Fred F. French Building': '弗雷德·F.·法兰奇大厦',
                           'Reid Avenue Station': '萊德大道車站', 'Times Square': '时代广场'}
