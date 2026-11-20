# Route benchmark — shortest vs preference route (Brooklyn, Queens and East River crossings)

Generated 2026-11-20T17:05:54Z by `benchmarks/route_benchmark.py` · network `nyc3-eeafb331` · scores `strollane-12x24-v1+nyc3-80d4e2f969` · 19 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks over Manhattan, Brooklyn and Queens together). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 19 | +12.6 | +5.0 | 10/19 | 4/19 | 5.5% | 0.47 |
| Nature | 19 | +10.1 | +13.0 | 13/19 | 6/19 | 5.1% | 0.48 |
| Culture | 19 | +2.9 | +0.0 | 4/19 | 7/19 | 3.4% | 0.59 |
| Quiet & Relax | 19 | +10.9 | +8.0 | 14/19 | 2/19 | 7.4% | 0.35 |
| Spatial Comfort | 19 | +4.2 | +3.0 | 6/19 | 5/19 | 1.5% | 0.55 |
| Urban Vibrancy | 19 | +3.9 | +1.0 | 5/19 | 5/19 | 3.6% | 0.53 |
| Food & Retail | 19 | +10.7 | +3.0 | 9/19 | 4/19 | 5.8% | 0.48 |
| Scenic & Visual | 19 | +6.2 | +1.0 | 8/19 | 8/19 | 2.7% | 0.57 |
| Walkability | 19 | +5.8 | +5.0 | 10/19 | 2/19 | 4.6% | 0.40 |
| Access & Safety | 19 | +11.6 | +12.0 | 14/19 | 4/19 | 6.6% | 0.38 |
| Environment | 19 | +2.5 | +1.0 | 5/19 | 7/19 | 2.8% | 0.56 |
| Transit Connectivity | 19 | +5.1 | +1.0 | 5/19 | 5/19 | 3.0% | 0.57 |
| **All** | 228 | +7.2 | +3.0 | 103/228 | 59/228 | 4.3% | 0.49 |

## By area

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Brooklyn | 96 | +8.8 | +5.0 | 49/96 | 27/96 | 4.8% | 0.49 |
| Western Queens | 60 | +6.0 | +2.0 | 23/60 | 19/60 | 4.9% | 0.46 |
| Eastern Queens | 36 | +9.3 | +8.0 | 22/36 | 1/36 | 5.2% | 0.28 |
| Across the river | 36 | +3.0 | +2.0 | 9/36 | 12/36 | 1.3% | 0.78 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 72 | +6.8 | +2.0 | 26/72 | 23/72 | 4.2% | 0.51 |
| medium (1.5–3 km) | 108 | +6.3 | +3.0 | 48/108 | 33/108 | 4.8% | 0.53 |
| long (≥ 3 km) | 48 | +10.0 | +8.0 | 29/48 | 3/48 | 3.4% | 0.38 |

## Nature (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +9.2 | +6.5 | 3/6 | 3/6 | 5.7% | 0.58 |
| medium (1.5–3 km) | 9 | +8.7 | +10.0 | 6/9 | 3/9 | 5.4% | 0.52 |
| long (≥ 3 km) | 4 | +14.5 | +13.0 | 4/4 | 0/4 | 3.6% | 0.24 |

## Quiet & Relax (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +11.7 | +12.5 | 5/6 | 0/6 | 9.5% | 0.25 |
| medium (1.5–3 km) | 9 | +10.2 | +8.0 | 5/9 | 2/9 | 7.1% | 0.45 |
| long (≥ 3 km) | 4 | +11.2 | +8.0 | 4/4 | 0/4 | 5.2% | 0.29 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 0.
