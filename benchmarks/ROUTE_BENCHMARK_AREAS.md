# Route benchmark — shortest vs preference route (Brooklyn, western Queens and East River crossings)

Generated 2026-11-18T16:53:41Z by `benchmarks/route_benchmark.py` · network `nyc3-1efe6705` · scores `strollane-12x24-v1+nyc3-8829299a21` · 16 trips × 12 single-dimension preferences (weight 80) · limits: 100 min, 25% detour.

"Gain" = the preference route's score on the requested dimension minus the shortest route's score (0–100 ranks over Manhattan, Brooklyn and western Queens together). 5 points is the smallest difference the app describes in words (`route-story.js`). These are the router's own scores: a gain shows the engine moved its metric, **not** that a walker perceives the difference. The trip set is hand-picked, not a random sample.

## By dimension

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Architecture | 16 | +10.0 | +3.5 | 8/16 | 5/16 | 4.8% | 0.54 |
| Nature | 16 | +8.5 | +9.0 | 11/16 | 5/16 | 4.8% | 0.53 |
| Culture | 16 | +2.2 | +1.0 | 3/16 | 6/16 | 2.1% | 0.66 |
| Quiet & Relax | 16 | +12.2 | +12.5 | 12/16 | 4/16 | 7.8% | 0.45 |
| Spatial Comfort | 16 | +3.6 | +3.5 | 4/16 | 5/16 | 1.2% | 0.62 |
| Urban Vibrancy | 16 | +4.9 | +1.0 | 5/16 | 6/16 | 3.6% | 0.64 |
| Food & Retail | 16 | +11.8 | +5.5 | 9/16 | 3/16 | 6.7% | 0.55 |
| Scenic & Visual | 16 | +3.4 | +1.5 | 3/16 | 7/16 | 1.9% | 0.70 |
| Walkability | 16 | +4.1 | +1.5 | 6/16 | 5/16 | 2.9% | 0.60 |
| Access & Safety | 16 | +11.0 | +11.0 | 11/16 | 4/16 | 5.3% | 0.44 |
| Environment | 16 | +1.4 | +0.0 | 2/16 | 9/16 | 1.6% | 0.71 |
| Transit Connectivity | 16 | +4.9 | +2.0 | 4/16 | 4/16 | 3.6% | 0.60 |
| **All** | 192 | +6.5 | +2.0 | 78/192 | 63/192 | 3.9% | 0.59 |

## By area

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| Brooklyn | 96 | +8.5 | +4.5 | 48/96 | 29/96 | 4.8% | 0.53 |
| Western Queens | 60 | +5.2 | +1.0 | 20/60 | 26/60 | 3.6% | 0.59 |
| Across the river | 36 | +3.4 | +2.0 | 10/36 | 8/36 | 1.8% | 0.74 |

## By trip length (shortest-path distance)

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 60 | +6.8 | +1.0 | 21/60 | 28/60 | 3.8% | 0.62 |
| medium (1.5–3 km) | 96 | +5.5 | +2.0 | 36/96 | 33/96 | 4.2% | 0.61 |
| long (≥ 3 km) | 36 | +8.8 | +5.0 | 21/36 | 2/36 | 3.2% | 0.47 |

## Nature (Nature) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 5 | +6.4 | +0.0 | 2/5 | 3/5 | 3.2% | 0.70 |
| medium (1.5–3 km) | 8 | +9.2 | +9.0 | 6/8 | 2/8 | 7.0% | 0.49 |
| long (≥ 3 km) | 3 | +10.0 | +11.0 | 3/3 | 0/3 | 1.8% | 0.39 |

## Quiet & Relax (Quiet & Relax) by trip length

| | Runs | Mean gain (pts) | Median gain | Gain ≥ 5 pts | Same as shortest | Mean detour | Mean overlap with shortest |
|---|---|---|---|---|---|---|---|
| short (< 1.5 km) | 5 | +14.0 | +16.0 | 4/5 | 1/5 | 9.5% | 0.34 |
| medium (1.5–3 km) | 8 | +11.1 | +10.0 | 5/8 | 3/8 | 7.6% | 0.54 |
| long (≥ 3 km) | 3 | +12.0 | +9.0 | 3/3 | 0/3 | 5.8% | 0.40 |

Routing errors: 0. Blocking QA issues on preference routes: 0. Preference routes scoring below the shortest route on the requested dimension: 0.
