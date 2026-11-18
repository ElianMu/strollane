# Route benchmark — shortest vs preference route

Generated 2026-11-18T03:20:46Z by `benchmarks/route_benchmark.py` · network `nyc3-1efe6705` · scores `strollane-12x24-v1+nyc3-8829299a21` · 19 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks within Manhattan). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 19 | +6.0 | +4.0 | 9/19 | 6/19 | 3.0% | 0.46 |
| Nature | 19 | +13.2 | +11.0 | 12/19 | 1/19 | 5.6% | 0.39 |
| Culture | 19 | +4.9 | +4.0 | 9/19 | 5/19 | 3.5% | 0.39 |
| Quiet & Relax | 19 | +11.7 | +9.0 | 15/19 | 2/19 | 4.9% | 0.33 |
| Spatial Comfort | 19 | +9.0 | +8.0 | 15/19 | 3/19 | 5.3% | 0.36 |
| Urban Vibrancy | 19 | +2.6 | +1.0 | 4/19 | 7/19 | 1.4% | 0.60 |
| Food & Retail | 19 | +6.6 | +5.0 | 11/19 | 3/19 | 4.0% | 0.38 |
| Scenic & Visual | 19 | +1.6 | +0.0 | 3/19 | 10/19 | 0.8% | 0.66 |
| Walkability | 19 | +5.6 | +5.0 | 10/19 | 2/19 | 2.7% | 0.38 |
| Access & Safety | 19 | +7.0 | +7.0 | 12/19 | 4/19 | 3.8% | 0.43 |
| Environment | 19 | +4.8 | +3.0 | 8/19 | 7/19 | 3.6% | 0.41 |
| Transit Connectivity | 19 | +8.9 | +8.0 | 12/19 | 7/19 | 4.2% | 0.45 |
| **All** | 228 | +6.8 | +5.0 | 120/228 | 57/228 | 3.6% | 0.44 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 72 | +3.5 | +0.0 | 20/72 | 36/72 | 2.1% | 0.67 |
| medium (1.5–3 km) | 120 | +8.1 | +6.0 | 71/120 | 20/120 | 4.2% | 0.38 |
| long (≥ 3 km) | 36 | +9.6 | +7.5 | 29/36 | 1/36 | 4.5% | 0.17 |

## Nature (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +2.8 | +1.5 | 1/6 | 1/6 | 0.5% | 0.63 |
| medium (1.5–3 km) | 10 | +15.3 | +13.0 | 8/10 | 0/10 | 6.5% | 0.34 |
| long (≥ 3 km) | 3 | +27.0 | +26.0 | 3/3 | 0/3 | 12.8% | 0.11 |

## Quiet & Relax (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 6 | +8.3 | +8.5 | 5/6 | 1/6 | 4.1% | 0.47 |
| medium (1.5–3 km) | 10 | +12.9 | +12.0 | 7/10 | 1/10 | 5.8% | 0.27 |
| long (≥ 3 km) | 3 | +14.7 | +14.0 | 3/3 | 0/3 | 3.5% | 0.24 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 0.
