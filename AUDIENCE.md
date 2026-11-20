# STROLLANE · NYC — who it is for

**Status: a design decision resting on a hypothesis. No user research has confirmed it yet** (see
`RESEARCH_PROTOCOL.md`). It answers the critique's question "What is important and to whom?" with a choice that can
be tested and, if wrong, changed.

## Three user types (since 2026-11-20)

The first screen offers one entry per type of walker, each with the request that walker would make. The project owner
chose these three on 2026-11-20, replacing the single lead audience of people new to New York (the newcomer's
neighbourhood walk now sits under the curious local).

| User type | Their request | Dimensions the entry switches on (weight 80) | What the existing machinery does with it |
|---|---|---|---|
| **Tourist** | "Show me NYC's historic architecture and cultural landmarks." | Architecture, Culture | With no destination, a recommended walk from where they are past historic buildings and culture venues (`journey.js` recommendedInterests: Architecture → historic, Culture → culture venue), ending at the last one; with a destination, a route there along streets ranked by the two. |
| **Curious Local** | "Take me through a neighborhood I've never explored." | Urban Vibrancy, Food & Retail, Architecture | A loop through the neighbourhood they start in (From), past its sights and historic buildings, along its livelier, shop- and food-lined streets. The app asks them to set From to a neighbourhood they have not walked. |
| **Leisure Walker** | "Find me a quiet, green walk after work." | Quiet & Relax, Nature | A loop from where they are along quieter, greener streets and through parks. Quiet takes walker reports from the same time of day into account once there are enough (`routing/feedback.py`), so an evening walk uses evening reports. |

Each entry is a button in the walk-priorities row (`walk-presets.js`, `WALK_ACTIVITIES`). It only switches on the
dimensions in its row at the weight a single pill sets; it adds no dimension, score or route, and moving a pill
afterwards turns it back into plain priorities. Walk length is not a new setting: with no destination the recommender
proposes 60 minutes for a loop and 75 open-ended.

Evidence for each, and what it does not show:

- **The product pays off on longer walks.** In the route benchmark (`benchmarks/ROUTE_BENCHMARK.md`) choosing a priority
  raised that dimension's route score by 3.5 points on average under 1.5 km against 8.1 points for 1.5–3 km and 9.6
  points for 3 km and more. All three entries are leisure walks of 20 minutes or more, not errands.
- **Tourist:** Architecture moves routes a lot in the Brooklyn and Queens set (+11.2 points; +6.0 in Manhattan); Culture is one
  of the weakest (+2.8 points in the Brooklyn and Queens set), because cultural venues are points, not street
  qualities. The tourist walk therefore leans on the recommended stops (historic buildings, culture venues) as much as
  on street scores.
- **Curious Local:** Urban Vibrancy moves routes little (+3.9 points in the Brooklyn and Queens set); Food & Retail and
  Architecture move them more. The value for this type is mostly the loop and the stops in a neighbourhood they do not
  know, which no benchmark measures.
- **Leisure Walker:** Nature and Quiet & Relax are the two dimensions with the largest gains in the Manhattan benchmark
  (+13.2 and +11.7 points) and among the largest in the Brooklyn and Queens set (+9.9 and +11.0).
- No user research has confirmed any of the three yet (`RESEARCH_PROTOCOL.md`); recruiting a few walkers of each type
  for walk-alongs is the next step.

## Before 2026-11-20

The lead audience was people new to New York (first year in the city) getting to know a neighbourhood, with three use
cases: get to know a neighbourhood, take the nicer way, a walk with a point. Visitors were explicitly not the lead.

## What would change this decision

- Walk-along participants of one type do not notice or value the difference between their walk and the shortest one.
- One type turns out to use it mainly for short point-to-point trips, where it adds little.
- The tourist walk is judged by its stops rather than its streets; then the tourist entry belongs in the journey
  planner (named places) more than in street scores.
