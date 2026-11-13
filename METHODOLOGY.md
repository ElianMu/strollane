# Spatial evidence methodology / 空间证据方法

> **Read this first (updated 2026-11-13).** Everything below "Scope and truthfulness" describes the original **Midtown
> pilot "Street evidence" layer** (`experience-core.js`, `data/pilot.json`): two raw proxies, 75 m buffers, scores NULL.
> That layer still exists in Navigate → *Street evidence*, and the text is accurate **for that layer only**. It is no
> longer how routes are ranked or how the Explore map is coloured. Current scoring is described in the next three
> sections, in `README.md`, `ARCHITECTURE.md` and `DIMENSIONS_MAP_MODE_REPORT.md`.

## Two score builds (known inconsistency)

The 12 dimensions have the same names and order everywhere, but two builds of their street scores are in use:

| | Routes (ranking, Why this route, route cards) | Explore Urban Data map |
|---|---|---|
| Build | `sw-score-46f39c1c97`, data 2026-10-23 | `strollane-12x24-v1`, built 2026-11-10 |
| Code | `scripts/streetwise_indicators.py` → `data/manhattan-streets.json` → `data/pedestrian/edge-scores.json.gz` | `scripts/dimensions/` → `data/dimensions/manhattan/` |
| Scored indicators | 15 | 20 computed (24 specified; canopy and impervious rasters not connected) |

The map build adds five indicators: seat access and ramp coverage (Spatial Comfort), waterfront access (Scenic & Visual),
route directness (Walkability) and crime-report proximity (Access & Safety). Compared segment by segment over the same
10,533 LION segments (2026-11-13), the two builds agree closely on eight dimensions and differ on four:

| Dimension | Spearman ρ between builds | Segments differing by more than 20 points |
|---|---|---|
| Spatial Comfort | 0.71 | 40 % (routes build: N/A on 1,145 segments) |
| Scenic & Visual | 0.74 | 36 % |
| Walkability | 0.79 | 26 % |
| Access & Safety | 0.90 | 14 % |
| Nature | 0.95 | 2 % |
| Architecture | 0.99 | 3 % |
| Culture, Quiet & Relax, Urban Vibrancy, Food & Retail, Environment, Transit Connectivity | 1.00 | 0 % |

Consequence: a street's score on the Explore map can differ from the score the router used for it. Route explanations
therefore always quote the routes build (`data/pedestrian/score-indicators.json`, shown only when its `score_version`
equals the route's). Unifying the two builds changes route results and is a pending decision; it has not been done.

## What the route scores are, and are not

Each scored indicator is a 0–100 percentile rank among Manhattan street segments ("lower is better" indicators
reversed); a dimension score is the equal-weight mean of its available indicators; a route score is the length-weighted
mean over the OSM edges the route uses. These are **relative ranks of proxies computed from public records**. They are
not calibrated measurements and have not been validated against how people experience a walk.

All 12 dimensions are offered as walk priorities on the first screen (`walk-presets.js`), ordered by their effect in
the route benchmark. Proxy limits a reader should know for each name:

- **Nature**: density of inventory tree points within 30 m and share of samples beside NYC Parks land. Not canopy
  cover and not shade.
- **Quiet & Relax**: 311 noise-complaint intensity over the last 12 months and roadway width. Complaints depend on who
  calls 311; neither indicator is a sound level.
- **Scenic & Visual**: proximity to OSM viewpoints, public art, fountains, memorials and monuments. It does not measure
  whether a street looks nice.
- **Urban Vibrancy**: POI diversity × quantity. At the 36 Manhattan DOT pedestrian-count locations its rank correlation
  with observed people per hour is −0.022 (`data/dimensions/manhattan/manifest.json`; the locations are mostly busy
  retail corridors, so the range is restricted). It is not evidence of how lively a street is.
- **Access & Safety**: in the routes build, injury-crash density only. It is not a measure of personal safety.
- **Spatial Comfort**: in the routes build, sidewalk-area share only, available on 72.9 % of routable length.

*Why this route?* states the indicators behind every priority the visitor picked, so these limits are visible in use.

## Benchmark and validation status

- **Route benchmark** (`benchmarks/route_benchmark.py`, results in `benchmarks/ROUTE_BENCHMARK.md`): shortest route vs
  the preference route vs the next candidate for 19 fixed trips × 12 single-dimension preferences. It reports gains,
  detours, overlap and "same as shortest" as they come out, and asserts nothing about which route is better. It shows
  whether the engine moves its own metric, not whether a walker notices.
- **User validation**: not done. `RESEARCH_PROTOCOL.md` describes the planned before/after-walk study. No user
  feedback has been collected and none is simulated anywhere in this repository.

## Scope and truthfulness

Two calculated raw proxies; zero research-calibrated 0–100 experience scores. The 12 `*_score` properties are always NULL in this release. Candidate match (0–100) is a separate relative comparison among requested routes; it is not an urban quality score. User sliders are importance, never environmental measurements.

## Source screening

- Nature: official NYC Open Data 2015 Tree Census, `https://data.cityofnewyork.us/resource/uvpi-gqnh.json`. Numeric latitude/longitude box and Manhattan `borocode='1'`; stable `tree_id` pagination, count verification and duplicate rejection. Only `status='Alive'` enters exposure counts. Original Alive/Dead/Stump records remain available in the raw layer. No canopy or shade inference.
- Architecture: original project's ArcGIS LPC individual-landmark parcel service retained. Bounded query, object-ID-sorted paging, expected-count verification and deduplication. All 186 pilot records are Designated. It excludes historic districts, non-landmark architecture, building visibility and subjective aesthetic quality. Source observation year unspecified.
- Street geometry: original project's NYC Street Centerline ArcGIS service, Manhattan borough filter. A road centerline is a research display geometry, not proof of pedestrian access. Source observation year unspecified.
- Routes: returned Valhalla pedestrian shapes based on OSM. Never join arbitrary centerline edges into fabricated walkable paths. Weather: Open-Meteo forecast context only. POIs: existing backend's named OSM nodes near the selected route.

The original tree mirror had malformed status fields. This release deliberately uses the authoritative Socrata records instead. The 3,177-record pilot contains 3,025 Alive, 102 Dead and 50 Stump records.

## Geometry and units

Pure computations are in `experience-core.js`. Coordinates remain WGS84 in GeoJSON. Distance uses a local equirectangular metric approximation at latitude 40.76° (x = longitude × 111320 × cos(latitude), y = latitude × 111320). This is explicitly an exploratory local approximation, not survey-grade distance or a formal projected CRS analysis. Full-Manhattan production processing should use an appropriate projected CRS and spatial index.

For a line section of length L km:

- Nature raw exposure = number of unique living tree records within 75 m / L.
- Architecture raw exposure = number of unique LPC parcels within 75 m / L.
- Polygon proximity checks line–polygon intersections, edge distances, interiors, holes and MultiPolygons; not merely proximity to polygon vertices.
- A complete evidence query must cover the **entire 75 m buffer**. Sections within the 75 m query-box margin are excluded or NULL, never silently assigned zero.
- Empty, successfully completed observations yield a legitimate raw zero. Failed or unavailable observations yield NULL.

The 75 m buffer is retained as an **exploratory pilot parameter**, not a literature-validated field-of-view distance or a claim that all dimensions should use the same radius. Other dimensions require their own influence models. No fabricated normalization or percentiles are emitted as calibrated scores.

## Two geometry populations

1. **Explore:** 477 fully covered NYC centerline parts within the real Midtown snapshot. MultiLineString parts are analyzed separately, with IDs `nyc-{sourceID}-{part}`. Centerline parts can include representations with different physical meaning; no citywide reference distribution or 0–100 calibration is derived from these parts.
2. **Navigate:** returned pedestrian route geometry split into sections of at most approximately 80 m while retaining all turns. Stable geometry-derived `walk-{hash}` section IDs and `route_id` link to the returned route. These are **not OSM graph edge IDs**. No claim of exact graph-edge matching or edge-cost optimization is made.

Route exposure = Σ(section exposure × section length) / Σ(section length). Every section must have complete observations for a dimension, or its route aggregate is NULL. Overlapping buffers intentionally repeat environmental exposure across sections; aggregate exposure is not a unique-record total. Whole-route deduplicated counts are displayed separately for continuity with the original UI.

The map uses local terciles of raw records/km solely to color available section evidence. Exact numeric breakpoints are in the legend and change with the analyzed section collection. Colors do not imply cross-neighborhood absolute quality. No-data sections are gray.

## Ranking and replanning

The existing Valhalla waypoint candidate strategy is retained. Manual weight changes and conversational refinements request real pedestrian paths again; they do not just relabel lines. Only expressed Nature / Architecture dimensions with complete route-section aggregates enter candidate ranking. Each is min–max normalized across the candidates; direction is applied separately (`high` or `low`). Importance zero excludes the dimension. All-equal evidence is excluded as nondiscriminating.

Time and detour limits filter feasible candidates first. Step-free/stair avoidance remains blocked without accessibility proof. The existing walking-time tie penalty is retained. This is constrained **candidate reranking**, not a guaranteed global optimum, not 12D edge-cost routing and not a certified accessible route.

The same `route.sections` collection feeds the map, route aggregate and right-panel shared section evidence. Source errors cannot be converted into score zero. Replanning preserves the current view on follow-ups. Identical best geometry receives an explicit unchanged explanation.

## Exact dimension registry

| # | Dimension | This release |
|---|---|---|
| 01 | Architecture | Computed LPC proximity proxy; score NULL |
| 02 | Nature | Computed living-tree proximity proxy; score NULL |
| 03 | Culture | Venue inventory/access model missing; NULL |
| 04 | Quiet & Relax | Noise/time model and inverse conversion missing; NULL |
| 05 | Spatial Comfort | Width, obstruction and crowding data missing; NULL |
| 06 | Urban Vibrancy | Activity model missing; NULL. Higher activity is not universally better; user direction is separate |
| 07 | Food & Retail | Business/opening-hours model missing; NULL |
| 08 | Scenic & Visual | Visibility/perception model missing; NULL |
| 09 | Walkability | Grade, crossing and connectivity model missing; NULL |
| 10 | Access & Safety | Barrier/hazard evidence missing; NULL |
| 11 | Environment | Street-level air/heat exposure model missing; NULL. Weather is context only |
| 12 | Transit Connectivity | Entrances/service-frequency model missing; NULL |

## Validation boundary

Automated spatial checks cover NULL vs zero, duplicate trees, dead trees, polygon crossings and holes, complete buffers, turn-preserving splitting, length conservation, unique IDs and weighted aggregation. Real pilot data and real recorded Valhalla responses are used in separate reproducible checks. DOM/state tests cover preferences, direction, mode, shared data, errors and replanning calls.

These checks establish computational consistency; they do not validate human experience, 75 m perception distance, source positional accuracy, OSM access quality, production browser rendering or real GPS navigation. No consent, itinerary or GPS records are stored by this implementation; external routing/weather/POI services receive the coordinates needed for their requests.
