# Route benchmark — shortest vs preference route

Generated 2026-11-17T21:33:40Z by `benchmarks/route_benchmark.py` · network `osm-walk-20261023-99602011` · scores `strollane-12x24-v1+nyc3-2c5f8e8350` · 19 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks within Manhattan). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 19 | +6.3 | +4.0 | 9/19 | 6/19 | 3.1% | 0.46 |
| Nature | 19 | +13.2 | +10.0 | 12/19 | 1/19 | 6.1% | 0.38 |
| Culture | 19 | +5.2 | +4.0 | 9/19 | 5/19 | 3.4% | 0.38 |
| Quiet & Relax | 19 | +11.9 | +10.0 | 16/19 | 2/19 | 5.0% | 0.31 |
| Spatial Comfort | 19 | +9.6 | +8.0 | 15/19 | 2/19 | 5.3% | 0.35 |
| Urban Vibrancy | 19 | +2.8 | +1.0 | 5/19 | 8/19 | 1.4% | 0.64 |
| Food & Retail | 19 | +6.3 | +5.0 | 10/19 | 4/19 | 4.0% | 0.39 |
| Scenic & Visual | 19 | +1.6 | +0.0 | 3/19 | 10/19 | 0.8% | 0.67 |
| Walkability | 19 | +5.8 | +4.0 | 9/19 | 2/19 | 2.6% | 0.39 |
| Access & Safety | 19 | +7.2 | +7.0 | 12/19 | 3/19 | 3.8% | 0.42 |
| Environment | 19 | +3.7 | +0.0 | 6/19 | 10/19 | 1.6% | 0.59 |
| Transit Connectivity | 19 | +8.9 | +8.0 | 12/19 | 7/19 | 4.2% | 0.45 |
| **All** | 228 | +6.9 | +5.0 | 118/228 | 60/228 | 3.4% | 0.45 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 72 | +3.5 | +0.0 | 20/72 | 37/72 | 1.9% | 0.68 |
| medium (1.5–3 km) | 120 | +8.1 | +6.0 | 68/120 | 22/120 | 4.1% | 0.40 |
| long (≥ 3 km) | 36 | +9.6 | +7.5 | 30/36 | 1/36 | 4.4% | 0.18 |

## Nature (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +2.7 | +1.0 | 1/6 | 1/6 | 0.5% | 0.63 |
| medium (1.5–3 km) | 10 | +15.4 | +14.0 | 8/10 | 0/10 | 7.5% | 0.31 |
| long (≥ 3 km) | 3 | +27.0 | +26.0 | 3/3 | 0/3 | 12.8% | 0.11 |

## Quiet & Relax (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +8.3 | +8.5 | 5/6 | 1/6 | 4.1% | 0.46 |
| medium (1.5–3 km) | 10 | +13.2 | +12.0 | 8/10 | 1/10 | 6.0% | 0.24 |
| long (≥ 3 km) | 3 | +15.0 | +14.0 | 3/3 | 0/3 | 3.5% | 0.24 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 0.
