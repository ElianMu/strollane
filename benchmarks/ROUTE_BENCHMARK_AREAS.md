# Route benchmark — shortest vs preference route (Brooklyn, Queens and East River crossings)

Generated 2026-11-20T02:38:54Z by `benchmarks/route_benchmark.py` · network `nyc3-9ad51815` · scores `strollane-12x24-v1+nyc3-80d4e2f969` · 19 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks over Manhattan, Brooklyn and Queens together). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 19 | +11.2 | +5.0 | 10/19 | 4/19 | 5.3% | 0.50 |
| Nature | 19 | +9.9 | +11.0 | 13/19 | 6/19 | 5.4% | 0.48 |
| Culture | 19 | +2.8 | +0.0 | 3/19 | 9/19 | 2.9% | 0.68 |
| Quiet & Relax | 19 | +11.0 | +11.0 | 14/19 | 3/19 | 7.6% | 0.43 |
| Spatial Comfort | 19 | +4.2 | +4.0 | 6/19 | 5/19 | 1.8% | 0.58 |
| Urban Vibrancy | 19 | +3.9 | +1.0 | 5/19 | 4/19 | 3.7% | 0.51 |
| Food & Retail | 19 | +10.5 | +4.0 | 8/19 | 4/19 | 5.9% | 0.51 |
| Scenic & Visual | 19 | +4.4 | +1.0 | 7/19 | 8/19 | 2.9% | 0.59 |
| Walkability | 19 | +5.7 | +5.0 | 10/19 | 5/19 | 4.3% | 0.50 |
| Access & Safety | 19 | +11.3 | +12.0 | 14/19 | 4/19 | 6.6% | 0.40 |
| Environment | 19 | +1.9 | +1.0 | 3/19 | 8/19 | 1.6% | 0.63 |
| Transit Connectivity | 19 | +4.1 | +1.0 | 5/19 | 5/19 | 2.9% | 0.59 |
| **All** | 228 | +6.7 | +3.0 | 98/228 | 65/228 | 4.2% | 0.53 |

## By area

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Brooklyn | 96 | +8.2 | +4.0 | 47/96 | 28/96 | 4.9% | 0.53 |
| Western Queens | 60 | +5.5 | +2.0 | 21/60 | 22/60 | 4.3% | 0.52 |
| Eastern Queens | 36 | +8.7 | +7.0 | 22/36 | 1/36 | 5.5% | 0.32 |
| Across the river | 36 | +2.8 | +1.5 | 8/36 | 14/36 | 1.2% | 0.79 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 72 | +6.7 | +2.0 | 26/72 | 24/72 | 4.1% | 0.53 |
| medium (1.5–3 km) | 108 | +5.8 | +3.0 | 44/108 | 38/108 | 4.5% | 0.59 |
| long (≥ 3 km) | 48 | +8.9 | +7.0 | 28/48 | 3/48 | 3.9% | 0.41 |

## Nature (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +9.2 | +6.5 | 3/6 | 3/6 | 5.7% | 0.58 |
| medium (1.5–3 km) | 9 | +8.8 | +10.0 | 6/9 | 3/9 | 6.2% | 0.48 |
| long (≥ 3 km) | 4 | +13.8 | +12.0 | 4/4 | 0/4 | 3.3% | 0.30 |

## Quiet & Relax (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +11.7 | +12.5 | 5/6 | 0/6 | 9.5% | 0.25 |
| medium (1.5–3 km) | 9 | +10.0 | +8.0 | 5/9 | 3/9 | 7.0% | 0.56 |
| long (≥ 3 km) | 4 | +12.2 | +10.5 | 4/4 | 0/4 | 6.1% | 0.39 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 0.
