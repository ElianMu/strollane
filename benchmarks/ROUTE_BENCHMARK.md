# Route benchmark — shortest vs preference route

Generated 2026-11-13T05:57:21Z by `benchmarks/route_benchmark.py` · network `osm-walk-20261023-99602011` · scores `sw-score-46f39c1c97` · 19 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks within Manhattan). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 19 | +10.1 | +9.0 | 12/19 | 7/19 | 5.3% | 0.45 |
| Nature | 19 | +13.4 | +11.0 | 13/19 | 1/19 | 6.1% | 0.37 |
| Culture | 19 | +7.7 | +2.0 | 9/19 | 6/19 | 3.4% | 0.44 |
| Quiet & Relax | 19 | +10.8 | +12.0 | 15/19 | 2/19 | 4.2% | 0.35 |
| Spatial Comfort | 19 | +14.2 | +16.0 | 15/19 | 2/19 | 5.0% | 0.34 |
| Urban Vibrancy | 19 | +5.8 | +3.0 | 7/19 | 4/19 | 2.7% | 0.48 |
| Food & Retail | 19 | +8.1 | +7.0 | 14/19 | 2/19 | 5.3% | 0.32 |
| Scenic & Visual | 19 | +5.0 | +6.0 | 10/19 | 6/19 | 3.4% | 0.46 |
| Walkability | 19 | +8.9 | +3.0 | 8/19 | 1/19 | 4.1% | 0.37 |
| Access & Safety | 19 | +13.7 | +13.0 | 17/19 | 2/19 | 5.3% | 0.34 |
| Environment | 19 | +6.4 | +3.0 | 9/19 | 4/19 | 2.9% | 0.39 |
| Transit Connectivity | 19 | +10.5 | +13.0 | 12/19 | 7/19 | 4.2% | 0.43 |
| **All** | 228 | +9.5 | +8.0 | 141/228 | 44/228 | 4.3% | 0.39 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 72 | +4.8 | +1.0 | 28/72 | 24/72 | 2.9% | 0.58 |
| medium (1.5–3 km) | 120 | +10.8 | +9.5 | 80/120 | 20/120 | 4.7% | 0.36 |
| long (≥ 3 km) | 36 | +14.8 | +14.0 | 33/36 | 0/36 | 5.9% | 0.13 |

## Green Walk (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +4.3 | +1.5 | 2/6 | 1/6 | 0.6% | 0.59 |
| medium (1.5–3 km) | 10 | +15.1 | +14.0 | 8/10 | 0/10 | 7.4% | 0.31 |
| long (≥ 3 km) | 3 | +25.7 | +25.0 | 3/3 | 0/3 | 12.7% | 0.10 |

## Quiet Walk (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +7.5 | +7.5 | 5/6 | 1/6 | 4.1% | 0.46 |
| medium (1.5–3 km) | 10 | +11.4 | +12.0 | 7/10 | 1/10 | 4.1% | 0.32 |
| long (≥ 3 km) | 3 | +15.3 | +14.0 | 3/3 | 0/3 | 5.2% | 0.21 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 1.
