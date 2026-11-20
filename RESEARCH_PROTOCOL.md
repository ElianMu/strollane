# STROLLANE · NYC — user validation protocol (ready to run, not yet run)

**Status: a plan with the tools to run it. No participant has been recruited and no answer collected. Nothing in
this repository simulates user feedback.** The three user types (`AUDIENCE.md`) are hypotheses to test, not findings.

## 1. Why

The route scores are ranks of proxies computed from public records (`METHODOLOGY.md`). The route benchmarks show that
the engine raises its own score for a requested dimension; they cannot show that a walker perceives a greener, quieter
or more interesting walk, or trusts the recommendation. That is the critique's question ("Why do you think that's
nice?", "survey people as they use this"), and the one this study answers, separately for each user type.

## 2. Questions

1. **Understanding**: after reading *Why this route?*, can a participant say what the recommendation is based on?
2. **Trust before walking**: would they take the recommended walk over the shortest one, and why or why not?
3. **Match after walking**: did the walk give them what their entry promised (landmarks, a new neighbourhood, a quiet
   green walk), and which stretches did or did not?
4. **Proxy validity**: does the perceived difference between two walks go in the same direction as the score
   difference, for the dimensions each entry switches on?
5. **Type fit**: does each type find its entry useful? Do the types differ in how much they value the walk and whether
   the extra distance was worth it?

## 3. Participants

12 people for a first round, **4 per user type**:

| Type | Who | Entry they use | Dimensions behind it |
|---|---|---|---|
| Tourist | Visitors in NYC for under two weeks, or residents taking a visiting friend round | **Tourist** | Architecture, Culture (+ stops at historic buildings and culture venues) |
| Curious Local | Residents of 1+ years, in a neighbourhood they say they have not walked | **Curious Local** | Urban Vibrancy, Food & Retail, Architecture (a loop) |
| Leisure Walker | Residents who walk for leisure at least weekly, after work (17:00–21:00) | **Leisure Walker** | Quiet & Relax, Nature (a loop) |

Record only: type, years in NYC (banded: <1, 1–3, 3+), leisure walks per week (banded: 0, 1–2, 3+). Give each person a
study code (P01–P12). It is the only identifier, and it is what joins their app answers to the interview notes.

## 4. Walks

- **Comparison, within each person**: two walks of the same trip. One is the walk their entry gives. The other is the
  shortest route between the same start and end (for a loop, the shortest loop through the same stops). Walk them in
  counterbalanced order (P01 recommended first, P02 shortest first, …) and **do not say which is which until the end**.
  Walking only the recommended one cannot separate "the walk is green" from "I was told it is green".
- **Trips**: 1.5–3 km, where the benchmarks show a priority changes the route (`benchmarks/ROUTE_BENCHMARK_AREAS.md`
  by length). Tourist and Leisure Walker trips come from `benchmarks/od_pairs.json` and `od_pairs_areas.json`. Curious
  Local loops start at a point the participant picks in a neighbourhood they have not walked.
- **Time**: Leisure Walkers after work (the "evening" bucket of `routing/feedback.py`), the others in daylight.
- **Record conditions**: date, start time, weather, leaf state. They change perceived greenery and quiet.

## 5. Instruments

Five-point scales (1 = not at all, 5 = very) unless noted. Keep each part under three minutes.

**Before walking** (interview, after they tap their entry and see the walk)

| # | Question | 中文 |
|---|---|---|
| B1 | In your own words, why does the app recommend this walk? (free text) | 用你自己的话说，应用为什么推荐这段路？ |
| B2 | How clear is the reason? | 推荐理由有多清楚？ |
| B3 | How much do you trust that it gives you what you asked for (landmarks / a new neighbourhood / quiet and green)? | 你有多相信它能给你想要的（地标 / 新街区 / 安静有绿意）？ |

**After each walk** (interview, asked twice)

| # | Question | 中文 |
|---|---|---|
| A1 | Tourist: how much historic architecture and culture did you notice? · Curious Local: how much did you learn about the neighbourhood? · Leisure Walker: how quiet and green did it feel? | 游客：注意到多少历史建筑和文化？· 好奇的本地人：对这个街区了解了多少？· 休闲散步者：感觉有多安静、多绿？ |
| A2 | How pleasant was it overall? | 整体有多愉快？ |
| A3 | Which stretch matched what you wanted, and which did not? (free text, street names or landmarks) | 哪一段符合期待？哪一段不符合？ |

**After both walks, in the app**: the participant opens *Why this route* on the recommended walk and answers the
**post-walk check** ("After your walk: did it match what you asked for?"), entering their study code:

| Field | Question | Stored as |
|---|---|---|
| match | How well did it match what you asked for? (1 not at all – 5 exactly) | `match` |
| worth | Was the extra distance worth it? (yes / no; not asked without a detour) | `worth_detour` |
| compared | Of your two walks, which fitted your request better? (this one / the other one / no difference; shown once a study code is entered) | `compared_with_shortest` |

The app adds the user type (from the entry used), the priorities that were on, and the route's signature, score and
network versions, length and detour. The participant can also report single streets that felt different from their
score ("Walked here? Did it match?", `routing/feedback.py`); those reports feed the walker-feedback loop, not this
study's tables.

**Debrief** (interview, after the reveal)

| # | Question | 中文 |
|---|---|---|
| D1 | Does the app's recommendation match your experience? | 推荐与你的感受一致吗？ |
| D2 | Would you use this entry again? For what kind of walk? | 你还会用这个入口吗？用在什么样的步行上？ |
| D3 | What made you doubt the recommendation, if anything? (free text) | 有什么让你怀疑过推荐？ |

## 6. Analysis

- **Per type** (`python3 scripts/summarize_walk_checks.py --study-only`, after `git fetch origin feedback-data`):
  number of checks, mean match and its 1–5 spread, detour worth it (yes / no), and which walk fitted better (this /
  shortest / same). With 4 people per type this is descriptive, not a significance test.
- **Direction agreement**: `compared_with_shortest` against the sign of the score gap on the entry's dimensions
  between the two walks, as a count out of 4 per type, with the score gap beside each case.
- **Perceived gap vs score gap**: the A1 difference between the two walks against the score difference, to find the
  smallest gap people notice. Compare it with the 5-point wording threshold in `route-story.js`.
- **Understanding**: B1 coded as correct / partly / wrong against the indicators actually used.
- Report null and negative results as they are. If a type cannot tell its walks apart, that is the finding for that type.

## 7. Privacy and ethics

- No names, emails, device identifiers, GPS traces or precise locations, in the app or the notes. The app stores the
  study code, answers, walk type, priorities and route versions (`routing/walkcheck.py`). Free text stays in the
  interviewer's notes.
- Participation is voluntary, walks are on public streets, and participants can stop at any time. Leisure Walker walks
  after dark use lit streets only, with the interviewer present.
- Before recruiting, confirm with the course instructor whether this needs IRB review or falls under class-project
  practice. Do not publish results beyond the course until that is settled.

## 8. Tools in the app

| What | Where | Stored |
|---|---|---|
| Post-walk check (all users; study code optional) | *Why this route* → "After your walk"; prompted on arrival in navigation | `POST /api/walk-checks` → `walk-checks/checks-YYYY-MM.jsonl` on the `feedback-data` branch |
| Per-type summary (counts and means only) | `GET /api/walk-checks/summary`, `scripts/summarize_walk_checks.py` | read only |
| Street-level reports | Explore street inspector, *Why this route* | `POST /api/feedback` (`routing/feedback.py`) |

Both stores need `FEEDBACK_GITHUB_TOKEN` on the API host (`DEPLOYMENT.md`). Without it the forms say answers are not
switched on, and nothing is kept.
