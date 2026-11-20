# Deployment note: the Agent Runtime's dependencies

This is the **first** `requirements.txt` this repository has had. `server.py`/`routing/*` remain intentionally
stdlib-only and need nothing from it — if `AGENT_ENABLED` is never set to `1`, these packages are never
imported and the server runs exactly as it did before this change.

If you want the real Agent Runtime live in production (`AGENT_ENABLED=1` + a real `OPENAI_API_KEY` in
Render's environment settings, alongside the existing `GOOGLE_PLACES_API_KEY` etc. per `PROVIDER_ACCESS.md`),
Render's build command needs to install `requirements.txt`:

```
pip install -r requirements.txt
```

No Dockerfile, no container runtime, no new infrastructure — this is one extra `pip install` line, consistent
with the rest of this app's zero-framework deployment. Not adding CI/CD changes beyond this note: no new
GitHub Actions workflow was added, since the 4 existing ones (`production-acceptance.yml`,
`indexed-urban-refresh.yml`, `tourism-data-audit.yml`, `urban-intelligence.yml`) don't exercise this new,
flag-gated endpoint and nothing in the request asked for a new pipeline to be built for it.

## Street photos (Mapillary)

Optional. To show street-level photos along a walk, set one environment variable on the API host (Render → the
service → Environment → Add Environment Variable), then redeploy:

    MAPILLARY_TOKEN = <the "Access Token" shown for the app in the Mapillary developer dashboard, starting with MLY|>

- Use the **Access Token**, not the **Client secret**. The client secret is only for OAuth sign-in, is not used by this
  project, and should never be pasted into code, a commit, or the environment.
- The token stays on the API host: the browser calls `POST /api/street-photos` and never sees it.
- Check: `POST /api/street-photos` with a route's coordinates answers `"configured": true` once the variable is set.
  `"failed_points"` above 0 means Mapillary did not answer (bad token, rate limit or outage).
- Without the variable the endpoint answers `"configured": false` and the page shows no street photos.


## Router memory (compiled network pack)

The router reads `data/pedestrian/<area>-network.bin.gz`, a compact binary copy of `<area>-walk-graph.json.gz` and the
area's edge scores (`routing/netpack.py`), when the SHA-256 of both JSON files matches the one recorded in the pack.
Otherwise it falls back to the JSON, which gives the same routes but costs much more memory. After anything rewrites
the walk graph or the edge scores, run:

    python3 scripts/compile_network.py            # Manhattan; --area brooklyn / --area lic for the others

`tests/test_netpack.py` fails while the committed pack is stale. Measured on 2026-11-17 with
`scripts/check_capacity.py` (fresh process, real data, concurrent route requests), Manhattan's peak was 408 MB from
the JSON and 182 MB from the pack. Loading the Brooklyn and Long Island City networks as well added about 173 MB
(measured with placeholder scores, since those areas had no edge scores yet), which keeps all three under the
448 MB ceiling the capacity check reserves inside a 512 MB instance.

With western Queens (2026-11-18: Long Island City to Jackson Heights, 416,268 edges) and the Brooklyn / western Queens place
index, the capacity check peak is 407 MB, still under the 448 MB ceiling. The router costs about 0.6 MB per 1,000 edges, so
a larger area needs a larger instance; widen `scripts/areas.py` only after measuring.

## Rebuilding the joined network (Manhattan, Brooklyn, western Queens)

After a new download or a scoring change, in this order (all standard library except steps marked *):

    python3 scripts/download_area_sources.py                       # Brooklyn, western Queens ('lic') sources (needs open internet)
    python3 scripts/build_pedestrian_network.py --area brooklyn     # * osmnx; same for --area lic (retries busy Overpass servers)
    python3 -m scripts.dimensions.area_build --area brooklyn        # * numpy, shapely, pyproj; same for lic
    python3 -m scripts.dimensions.combine_areas                     # * one scale for the three areas
    python3 scripts/transfer_dimension_scores.py                    # Manhattan edges
    python3 scripts/match_area.py --area brooklyn                   # same for lic
    python3 scripts/measure_direct_edges.py --area brooklyn         # * same for lic
    python3 scripts/transfer_dimension_scores.py --area brooklyn    # same for lic
    python3 scripts/merge_networks.py
    python3 scripts/compile_network.py --area nyc
    python3 scripts/build_waterfront_features.py                    # * numpy, shapely
    python3 scripts/build_score_indicators.py

`tests/test_joined_network.py` and `tests/test_netpack.py` fail if a step is skipped.

After changing an area's box in `scripts/areas.py`, download that area again with `--refresh` (kept Overpass tiles are
per box) and remove `data/dimensions/work/<area>/` before `area_build`: its stage files belong to the old segment set.

Place recommendations for Brooklyn and western Queens (after the joined network, so places are snapped to it):

    python3 scripts/download_area_sources.py --places             # OSM places, landmarks, restrooms, hotel lots, Wikidata (needs open internet)
    python3 scripts/build_area_places.py                          # adds both areas to data/places; Manhattan records unchanged
    python3 scripts/build_registry.py                             # then keep only its places:* rows if the rest should not change

A place is kept when it is in its area's box, its nearest LION street segment belongs to that area (the boxes reach into
Manhattan) and it is within 150 m of the walk network. `tests/test_area_places.py` checks the result.

Map layers for Brooklyn and western Queens (data/layers; 53 of the 58 tilesets):

    python3 scripts/download_area_sources.py --layers             # 19 sources per area (needs open internet)
    python3 scripts/build_area_layers.py                          # merges each area into the tiles; Manhattan's features unchanged
    python3 scripts/build_layer_overviews.py                      # one city-wide file per sparse layer, for zoomed-out views

Building footprints (and the height / age views), tax lots, activity places, 311 noise complaints and sidewalk surface
stay Manhattan only, to keep the published site well under GitHub Pages' 1 GB (it is about 790 MB with all three
areas). `tests/test_urban_layers.py` checks every feature against its own area.

## Website deploy (GitHub Pages, from a workflow)

With all of Queens the repository is larger than GitHub Pages' 1 GB site limit, so `.github/workflows/pages.yml`
publishes a copy without the API server's own data (`data/urban`, `data/pedestrian` except `score-indicators.json`,
`data/cache`, `tests`, `scripts`, `routing`, `*.py`): about 815 MB on 2026-11-19. The workflow stops if the copy is
over 990 MB. Settings → Pages → Build and deployment → Source must be **GitHub Actions**. Render still deploys the
API from the whole repository.

## Walker feedback (routing/feedback.py)

Reports are stored as JSON lines on the `feedback-data` branch (`feedback/reports-YYYY-MM.jsonl`) because the Render
Free disk is wiped on every restart. The API host needs one environment variable:

    FEEDBACK_GITHUB_TOKEN   fine-grained GitHub token, repository ElianMu/strollane only, permission Contents: read and write
    FEEDBACK_REPO           optional, default ElianMu/strollane

Without the token `/api/feedback` answers 503 `feedback_disabled` and routing ignores feedback. A report holds a
segment ID, a dimension, a direction (worse / better than the score shown), that score, the UTC hour and the New York
time-of-day bucket: no location, account, free text or IP address. Rules (MIN_REPORTS, MIN_DAYS, MIN_AGREEMENT,
MAX_DELTA, SHRINK, HALF_LIFE_DAYS, TIME_SENSITIVE) are at the top of `routing/feedback.py`; `tests/test_feedback.py`
checks them.
