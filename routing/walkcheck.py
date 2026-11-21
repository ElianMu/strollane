"""Walk feedback and evaluation: after a walk, the walker rates it; the evaluation compares those ratings with the
scores the system predicted for the same route.

The loop: route recommendation → real walk → walk feedback (this module) → evaluation (evaluate(), shown on
evaluation.html). Approved by the project owner on 2026-11-20; RESEARCH_PROTOCOL.md uses the same form for walk-alongs.

A walk feedback record holds
  * ratings 1–5: overall satisfaction (required), match with the request, quiet, greenery, and optionally any of the
    other 12 experience dimensions (dimension_ratings);
  * an optional comment (at most 500 characters; e-mail addresses, phone numbers and links are removed before storage);
  * the walk: user type, the priorities that were on (dimension, weight, direction), route ID and signature, score and
    network versions, length, detour;
  * the prediction: the route's 12 dimension scores **recomputed by the server** from its own network (Planner.data_scores)
    for that route, never taken from the client; None when the route cannot be verified;
  * the UTC hour and the New York time-of-day bucket; an optional study code for walk-along participants.
No location, account, name or IP address. Feedback is voluntary and never changes scores or routes.

Storage: the API host's disk is wiped on restart (Render Free) and the project's only database files are read-only
snapshots, so records go to the same store as walker street reports (routing/feedback.py GitHubStore), folder
walk-checks/ on the feedback-data branch. The branch is public: the form says so, which is why comments are cleaned.

Scales: a rating is 1–5; a predicted score is a 0–100 percentile rank among the street segments of the three boroughs.
They are not the same unit. evaluate() reports both, rank agreement (Spearman) and, as one simple common scale, the
rating mapped linearly to 0–100 ((r − 1) × 25) minus the predicted score. That mapping is an assumption, stated as such.
"""

import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from . import feedback as fb

USER_TYPES = ('tourist', 'curious-local', 'leisure', 'custom')   # walk-presets.js WALK_ACTIVITIES keys, or own priorities
WORTH = ('yes', 'no', 'no-detour')
COMPARED = ('this', 'shortest', 'same')
DIMENSION_LABELS = ('Architecture', 'Nature', 'Culture', 'Quiet & Relax', 'Spatial Comfort', 'Urban Vibrancy',
                    'Food & Retail', 'Scenic & Visual', 'Walkability', 'Access & Safety', 'Environment',
                    'Transit Connectivity')
RATINGS = ('overall', 'match', 'quiet', 'green')
RATING_DIMENSION = {'quiet': 'Quiet & Relax', 'green': 'Nature'}   # the two ratings that name one dimension each
STUDY_CODE = re.compile(r'^[A-Z]{1,3}[0-9]{1,3}$')
ROUTE_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+')
_URL = re.compile(r'(https?://|www\.)\S+', re.I)
_PHONE = re.compile(r'(\+?\d[\d\s().-]{7,}\d)')
TEXT_MAX = 500
SCHEMA = 2


def clean_text(text):
    """Trim, cap and remove e-mail addresses, links and phone numbers (the store is public)."""
    if not isinstance(text, str) or not text.strip():
        return None
    t = _URL.sub('[link removed]', _EMAIL.sub('[e-mail removed]', text.strip()[:TEXT_MAX]))
    return _PHONE.sub('[number removed]', t)


def _rating(v, name):
    if v is None:
        return None
    if type(v) is not int or not 1 <= v <= 5:
        raise ValueError(f'{name} must be a whole number from 1 to 5')
    return v


def make_check(payload, predicted=None, now=None):
    """A validated record from a request body, or ValueError. `predicted` is the server's own prediction for the route
    (Planner.data_scores), or None."""
    if not isinstance(payload, dict):
        raise ValueError('the feedback must be a JSON object')
    ut = payload.get('user_type')
    if ut not in USER_TYPES:
        raise ValueError('user_type must be one of: ' + ', '.join(USER_TYPES))
    raw = payload.get('ratings')
    if not isinstance(raw, dict):
        raise ValueError('ratings must be an object with at least overall (1–5)')
    ratings = {k: _rating(raw.get(k), k) for k in RATINGS}
    if ratings['overall'] is None:
        raise ValueError('ratings.overall (overall satisfaction, 1–5) is required')
    dr = payload.get('dimension_ratings') or {}
    if not isinstance(dr, dict) or any(k not in DIMENSION_LABELS for k in dr):
        raise ValueError('dimension_ratings keys must be the 12 dimension names')
    dr = {k: _rating(v, k) for k, v in dr.items() if v is not None}
    worth = payload.get('worth_detour')
    if worth is not None and worth not in WORTH:
        raise ValueError('worth_detour must be yes, no or no-detour')
    compared = payload.get('compared_with_shortest')
    if compared is not None and compared not in COMPARED:
        raise ValueError('compared_with_shortest must be this, shortest or same')
    code = payload.get('study_code')
    code = str(code).strip().upper() if code not in (None, '') else None
    if code and not STUDY_CODE.match(code):
        raise ValueError('study_code is letters then digits, for example P07')
    pri = payload.get('priorities') or {}
    if not isinstance(pri, dict) or any(k not in DIMENSION_LABELS for k in pri):
        raise ValueError('priorities must map dimension names to {weight, direction}')
    priorities = {}
    for k, v in pri.items():
        w = v.get('weight') if isinstance(v, dict) else None
        d = v.get('direction', 'high') if isinstance(v, dict) else None
        if type(w) not in (int, float) or not 0 <= w <= 100 or d not in ('high', 'low'):
            raise ValueError(f'priority {k} needs a weight 0–100 and direction high or low')
        priorities[k] = {'weight': round(w), 'direction': d}
    rid = payload.get('route_id')
    rid = rid if isinstance(rid, str) and ROUTE_ID.match(rid) else None

    def text(k, n):
        v = payload.get(k)
        return v[:n] if isinstance(v, str) else None

    def num(k, lo, hi):
        v = payload.get(k)
        return round(float(v), 1) if type(v) in (int, float) and lo <= v <= hi else None
    now = now or datetime.now(timezone.utc)
    return {'v': SCHEMA, 'id': uuid.uuid4().hex[:12], 'at': now.replace(minute=0, second=0, microsecond=0).isoformat(),
            'bucket': fb.ny_bucket(now), 'user_type': ut, 'priorities': priorities, 'ratings': ratings,
            'dimension_ratings': dr, 'comment': clean_text(payload.get('comment')), 'worth_detour': worth,
            'compared_with_shortest': compared, 'study_code': code, 'route_id': rid,
            'route_signature': text('route_signature', 64), 'score_version': text('score_version', 80),
            'network_version': text('network_version', 40), 'distance_m': num('distance_m', 0, 50000),
            'detour_pct': num('detour_pct', -5, 400),
            'predicted': predicted if isinstance(predicted, dict) else None}


# ---------------------------------------------------------------------------------------------------- evaluation
def _mean(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(xs, ys):
    """Spearman rank correlation with ties averaged; None below 5 pairs or with no spread."""
    if len(xs) < 5:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if not sx or not sy:
        return None
    return round(sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy), 2)


def _match_prediction(c):
    """What the system predicted for 'match': the mean predicted score of the dimensions the walker raised (direction
    high, weight above 55); a lowered dimension counts as 100 − score. None without priorities or prediction."""
    p = c.get('predicted') or {}
    vals = [(p.get(k) if v['direction'] == 'high' else (None if p.get(k) is None else 100 - p[k]))
            for k, v in (c.get('priorities') or {}).items() if v['weight'] > 55 or v['direction'] == 'low']
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def _pairs(checks):
    """(label, predicted 0–100, rating 1–5) for every rating that has a prediction to compare with."""
    out = []
    for c in checks:
        p = c.get('predicted') or {}
        r = c.get('ratings') or {}
        if r.get('match') is not None and _match_prediction(c) is not None:
            out.append(('Match with request', _match_prediction(c), r['match']))
        for k, dim in RATING_DIMENSION.items():
            if r.get(k) is not None and p.get(dim) is not None:
                out.append((dim, p[dim], r[k]))
        for dim, v in (c.get('dimension_ratings') or {}).items():
            if dim not in RATING_DIMENSION.values() and p.get(dim) is not None:
                out.append((dim, p[dim], v))
    return out


LIMITATIONS = [
    'Self-selected: only walkers who chose to answer are counted; they are not a random sample of users.',
    'Ratings (1–5) and predicted scores (0–100 percentile ranks) are different scales. "Perceived on 0–100" maps a '
    'rating linearly, (rating − 1) × 25; that mapping is an assumption, so read deviations as direction, not size.',
    'A predicted score is relative to all street segments of Manhattan, Brooklyn and Queens; a rating is relative to '
    'what the walker expected. A 50 is an average street, not a "3 out of 5".',
    'Spearman correlation is shown only from 5 pairs up; with fewer than about 30 pairs any figure is descriptive.',
    'Conditions (time of day, weather, season) change perceived quiet and greenery; the record keeps the time-of-day '
    'bucket only.',
    'Predicted scores come from the server\'s own network for the route that was walked; when the route could not be '
    'verified (another network version, or a route this process never planned and no snapshot) no prediction is stored '
    'and that record is left out of the comparison.',
]
SOURCES = [
    'Walk feedback: voluntary answers on the STROLLANE site after a walk (POST /api/walk-checks), stored on the '
    'feedback-data branch of the project repository.',
    'Predicted scores: the 12 dimension scores of the walked route, recomputed by the routing server from its network '
    'and score build (score_version in each record).',
]


COMMENTS_SHOWN, COMMENT_SHOWN_CHARS = 30, 280


def evaluate(checks):
    """Everything evaluation.html shows, from the stored records alone. With no records: {'n': 0}."""
    n = len(checks)
    out = {'n': n, 'sources': SOURCES, 'limitations': LIMITATIONS}
    if not n:
        return out
    out['first_at'] = min(c['at'] for c in checks)
    out['last_at'] = max(c['at'] for c in checks)
    out['score_versions'] = sorted({c.get('score_version') for c in checks if c.get('score_version')})
    out['ratings'] = {}
    for k in RATINGS:
        vals = [c['ratings'][k] for c in checks if (c.get('ratings') or {}).get(k) is not None]
        out['ratings'][k] = {'n': len(vals), 'missing': n - len(vals), 'mean': _mean(vals),
                             'counts': {str(i): vals.count(i) for i in range(1, 6)}}
    out['by_user_type'] = {}
    for t in USER_TYPES:
        rows = [c for c in checks if c.get('user_type') == t]
        if rows:
            out['by_user_type'][t] = {'n': len(rows), **{f'mean_{k}': _mean([c['ratings'][k] for c in rows if c['ratings'].get(k) is not None]) for k in RATINGS}}
    dims = {}
    for c in checks:
        for k, v in (c.get('dimension_ratings') or {}).items():
            dims.setdefault(k, []).append(v)
    for k, dim in RATING_DIMENSION.items():
        dims.setdefault(dim, []).extend(c['ratings'][k] for c in checks if c['ratings'].get(k) is not None)
    out['dimension_ratings'] = {k: {'n': len(v), 'mean': _mean(v)} for k, v in sorted(dims.items())}
    comparison = {}
    for label, pred, rating in _pairs(checks):
        comparison.setdefault(label, []).append((pred, rating))
    out['comparison'] = {}
    for label, pts in sorted(comparison.items()):
        dev = [(r - 1) * 25 - p for p, r in pts]
        out['comparison'][label] = {
            'n': len(pts), 'mean_predicted': _mean([p for p, _ in pts]), 'mean_rating': _mean([r for _, r in pts]),
            'mean_perceived_0_100': _mean([(r - 1) * 25 for _, r in pts]), 'mean_deviation': _mean(dev),
            'mean_abs_deviation': _mean([abs(x) for x in dev]), 'spearman': spearman([p for p, _ in pts], [r for _, r in pts]),
            'points': [[p, r] for p, r in pts]}
    out['missing'] = {'prediction_unavailable': sum(1 for c in checks if not c.get('predicted')),
                      'no_priorities': sum(1 for c in checks if not c.get('priorities')),
                      **{f'rating_{k}': out['ratings'][k]['missing'] for k in RATINGS}}
    out['worth_detour'] = {w: sum(c.get('worth_detour') == w for c in checks) for w in WORTH}
    out['compared_with_shortest'] = {w: sum(c.get('compared_with_shortest') == w for c in checks) for w in COMPARED}
    out['comments'] = sum(1 for c in checks if c.get('comment'))
    # What walkers wrote, newest first, for other walkers to read (the form says comments are public; they were
    # cleaned of e-mail addresses, links and phone numbers when stored). Day only, no time, no route.
    said = sorted((c for c in checks if c.get('comment')), key=lambda c: c['at'], reverse=True)[:COMMENTS_SHOWN]
    out['recent_comments'] = [{'date': str(c['at'])[:10], 'user_type': c.get('user_type'), 'overall': (c.get('ratings') or {}).get('overall'),
                               'comment': c['comment'][:COMMENT_SHOWN_CHARS]} for c in said]
    out['study_participants'] = len({c['study_code'] for c in checks if c.get('study_code')})
    return out


class WalkCheckBook:
    """Records in memory, loaded from the store at most every REFRESH_S, plus the in-memory rate limit."""

    REFRESH_S = 300

    def __init__(self, store=None):
        self.store, self.checks, self.loaded_at, self.error = store, [], 0.0, None
        self.lock, self._limits = threading.Lock(), {}

    @classmethod
    def from_env(cls):
        token = os.environ.get('FEEDBACK_GITHUB_TOKEN')
        return cls(fb.GitHubStore(os.environ.get('FEEDBACK_REPO', 'ElianMu/strollane'), token,
                                  folder='walk-checks', name='checks') if token else None)

    @property
    def enabled(self):
        return self.store is not None

    def refresh(self):
        if not self.store or time.time() - self.loaded_at < self.REFRESH_S:
            return
        self.loaded_at = time.time()
        try:
            checks = self.store.load()
            with self.lock:
                self.checks, self.error = [c for c in checks if c.get('v') == SCHEMA], None
        except Exception as e:
            self.error = str(e)[:200]

    def allow(self, client, route_key):
        """At most 10 records an hour from one client, and one per route a day (client only hashed, in memory)."""
        now, h = time.time(), hash(client)
        recent = [x for x in self._limits.get(h, []) if now - x[0] < 86400]
        if sum(now - t < 3600 for t, _ in recent) >= 10 or (route_key and any(r == route_key for _, r in recent)):
            return False
        recent.append((now, route_key))
        self._limits[h] = recent
        return True

    def add(self, check):
        self.store.append(check)
        with self.lock:
            self.checks = self.checks + [check]

    def evaluate(self):
        return evaluate(self.checks)
