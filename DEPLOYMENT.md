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

## Rebuilding the joined network (Manhattan, Brooklyn, Long Island City)

After a new download or a scoring change, in this order (all standard library except steps marked *):

    python3 scripts/download_area_sources.py                       # Brooklyn, LIC sources (needs open internet)
    python3 scripts/build_pedestrian_network.py --area brooklyn     # * osmnx; same for --area lic
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

Place recommendations for Brooklyn and Long Island City (after the joined network, so places are snapped to it):

    python3 scripts/download_area_sources.py --places             # OSM places, landmarks, restrooms, hotel lots, Wikidata (needs open internet)
    python3 scripts/build_area_places.py                          # adds both areas to data/places; Manhattan records unchanged
    python3 scripts/build_registry.py                             # then keep only its places:* rows if the rest should not change

A place is kept when it is in its area's box, its nearest LION street segment belongs to that area (the boxes reach into
Manhattan) and it is within 150 m of the walk network. `tests/test_area_places.py` checks the result.
