"""Walker feedback: reports that a street did not feel the way its score says, kept apart from the data scores.

The loop the reports close (approved by the project owner on 2026-11-19, phases 1 and 2):
  1. a route is recommended from the data scores;
  2. someone walks it;
  3. they report a street segment that felt worse (or better) than rated on one dimension ("louder than rated");
  4. reports are checked here: a segment's dimension is adjusted only when several reports, on different days, agree;
  5. routing uses the adjusted value, and every route says which streets it changed and by how much.

What is never done:
  * a report never replaces a score. The data score stays in the score files; the adjustment is a separate number,
    capped at ±MAX_DELTA percentile points, shrunk toward 0 when reports are few, and it fades with age (HALF_LIFE_DAYS);
  * one report never moves anything (MIN_REPORTS on MIN_DAYS distinct days, and MIN_AGREEMENT of the weight in one
    direction);
  * no location, account, name, free text or IP address is stored. A report is a segment ID, a dimension, a direction,
    the score that was shown, the hour (UTC, rounded) and the time-of-day bucket in New York.

Time: a street's noise or activity changes over the day, so Quiet and Urban Vibrancy reports only adjust routes planned
in the same time-of-day bucket as the reports (TIME_SENSITIVE). The other dimensions describe the built street and are
adjusted at any time.

Storage: the API host's disk is wiped on every restart (Render Free), so reports are kept as JSON lines on a branch of
the project's GitHub repository (GitHubStore; FEEDBACK_GITHUB_TOKEN with contents:write on that repository only). They
are public there, which is why nothing personal is in them. Without a token the feedback endpoints say so and change
nothing.
"""

import base64
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

DIMENSION_KEYS = ['architecture', 'nature', 'culture', 'quiet', 'spatial_comfort', 'urban_vibrancy', 'food_retail',
                  'scenic_visual', 'walkability', 'access_safety', 'environment', 'transit_connectivity']
DIRECTIONS = ('worse', 'better')
TIME_SENSITIVE = {'quiet', 'urban_vibrancy'}
BUCKETS = ('morning', 'midday', 'evening', 'night')   # 6–11, 11–17, 17–22, 22–6 New York time

MAX_DELTA = 15.0        # percentile points, either way
SHRINK = 3.0            # pseudo-reports at "no change": 3 agreeing reports move a score by 7.5 points, 10 by 11.5
HALF_LIFE_DAYS = 90.0
WINDOW_DAYS = 365
MIN_REPORTS = 3
MIN_DAYS = 2
MIN_AGREEMENT = 2 / 3

SCHEMA = 1


def ny_bucket(when):
    """Time-of-day bucket in New York (UTC−5 / UTC−4), from an aware UTC datetime."""
    try:
        from zoneinfo import ZoneInfo
        local = when.astimezone(ZoneInfo('America/New_York'))
    except Exception:  # no tz database on the host: US Eastern daylight time from the second Sunday of March to the first of November
        y = when.year
        march = datetime(y, 3, 8, 7, tzinfo=timezone.utc); march += timedelta(days=(6 - march.weekday()) % 7)
        nov = datetime(y, 11, 1, 6, tzinfo=timezone.utc); nov += timedelta(days=(6 - nov.weekday()) % 7)
        local = when + timedelta(hours=-4 if march <= when < nov else -5)
    h = local.hour
    return 'morning' if 6 <= h < 11 else 'midday' if 11 <= h < 17 else 'evening' if 17 <= h < 22 else 'night'


def make_report(payload, known_segment, now=None):
    """A validated report from a request body, or ValueError. known_segment(id) → bool."""
    if not isinstance(payload, dict):
        raise ValueError('feedback must be a JSON object')
    seg, dim, direction = payload.get('segment_id'), payload.get('dimension'), payload.get('direction')
    if not isinstance(seg, str) or len(seg) > 40 or not known_segment(seg):
        raise ValueError('segment_id must be a street segment of the routing network (for example QN-31730)')
    if dim not in DIMENSION_KEYS:
        raise ValueError('dimension must be one of: ' + ', '.join(DIMENSION_KEYS))
    if direction not in DIRECTIONS:
        raise ValueError("direction must be 'worse' or 'better' (than the score shown)")
    rated = payload.get('rated')
    if rated is not None and (type(rated) not in (int, float) or not 0 <= rated <= 100):
        raise ValueError('rated must be the 0–100 score that was shown, or omitted')
    sv = payload.get('score_version')
    now = now or datetime.now(timezone.utc)
    return {'v': SCHEMA, 'id': uuid.uuid4().hex[:12], 'at': now.replace(minute=0, second=0, microsecond=0).isoformat(),
            'segment_id': seg, 'dimension': dim, 'direction': direction,
            'rated': None if rated is None else round(float(rated)), 'bucket': ny_bucket(now),
            'score_version': sv[:80] if isinstance(sv, str) else None}


def aggregate(reports, now=None):
    """{segment_id: {dimension: summary}} where summary = {n, worse, better, days, status, delta, by_bucket}.

    status: 'applied' (delta used in routing), 'pending' (too few reports or days), 'mixed' (reports disagree).
    For TIME_SENSITIVE dimensions the check runs per time bucket and by_bucket holds each bucket's delta; delta is then
    the delta of the bucket with most weight, for display only."""
    now = now or datetime.now(timezone.utc)
    groups = {}
    for r in reports:
        try:
            at = datetime.fromisoformat(r['at'])
        except (KeyError, TypeError, ValueError):
            continue
        age = (now - at).total_seconds() / 86400
        if age < 0 or age > WINDOW_DAYS or r.get('dimension') not in DIMENSION_KEYS or r.get('direction') not in DIRECTIONS:
            continue
        groups.setdefault((r['segment_id'], r['dimension']), []).append((r, age))
    out = {}
    for (seg, dim), rows in groups.items():
        def judge(rows):
            w_worse = sum(0.5 ** (age / HALF_LIFE_DAYS) for r, age in rows if r['direction'] == 'worse')
            w_better = sum(0.5 ** (age / HALF_LIFE_DAYS) for r, age in rows if r['direction'] == 'better')
            total = w_worse + w_better
            days = len({r['at'][:10] for r, _ in rows})
            if len(rows) < MIN_REPORTS or days < MIN_DAYS:
                return 'pending', 0.0
            if max(w_worse, w_better) < MIN_AGREEMENT * total:
                return 'mixed', 0.0
            return 'applied', round(max(-MAX_DELTA, min(MAX_DELTA, MAX_DELTA * (w_better - w_worse) / (total + SHRINK))), 1)
        summary = {'n': len(rows), 'worse': sum(r['direction'] == 'worse' for r, _ in rows),
                   'better': sum(r['direction'] == 'better' for r, _ in rows), 'days': len({r['at'][:10] for r, _ in rows}),
                   'time_sensitive': dim in TIME_SENSITIVE}
        if dim in TIME_SENSITIVE:
            by = {}
            for b in BUCKETS:
                sub = [x for x in rows if x[0].get('bucket') == b]
                if sub:
                    status, delta = judge(sub)
                    by[b] = {'n': len(sub), 'status': status, 'delta': delta}
            applied = [v for v in by.values() if v['status'] == 'applied']
            status = 'applied' if applied else 'mixed' if any(v['status'] == 'mixed' for v in by.values()) else 'pending'
            summary.update(by_bucket=by, status=status, delta=max(applied, key=lambda x: x['n'])['delta'] if applied else 0.0)
        else:
            summary['status'], summary['delta'] = judge(rows)
        out.setdefault(seg, {})[dim] = summary
    return out


def delta_for(summary, bucket):
    """The adjustment this summary makes to a route planned in `bucket` (0.0 when none)."""
    if summary.get('time_sensitive'):
        b = summary.get('by_bucket', {}).get(bucket)
        return b['delta'] if b and b['status'] == 'applied' else 0.0
    return summary['delta'] if summary['status'] == 'applied' else 0.0


class GitHubStore:
    """Reports as JSON lines in feedback/reports-YYYY-MM.jsonl on one branch of a GitHub repository (contents API)."""

    def __init__(self, repo, token, branch='feedback-data', api='https://api.github.com', folder='feedback', name='reports'):
        self.repo, self.token, self.branch, self.api = repo, token, branch, api
        self.folder, self.name = folder, name  # walk checks (routing/walkcheck.py) use folder 'walk-checks'

    def _call(self, method, path, body=None):
        req = urllib.request.Request(f'{self.api}/repos/{self.repo}/{path}', method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
                                              'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'strollane-feedback'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    def _ensure_branch(self):
        try:
            self._call('GET', f'branches/{self.branch}')
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            main = self._call('GET', 'git/ref/heads/main')['object']['sha']
            self._call('POST', 'git/refs', {'ref': f'refs/heads/{self.branch}', 'sha': main})

    def load(self):
        try:
            listing = self._call('GET', f'contents/{self.folder}?ref={self.branch}')
        except urllib.error.HTTPError as e:
            if e.code == 404:  # no branch or no reports yet
                return []
            raise
        reports = []
        for item in sorted(listing, key=lambda x: x['name']):
            if not item['name'].endswith('.jsonl'):
                continue
            f = self._call('GET', f"contents/{self.folder}/{item['name']}?ref={self.branch}")
            for line in base64.b64decode(f['content']).decode().splitlines():
                if line.strip():
                    reports.append(json.loads(line))
        return reports

    def append(self, report):
        self._ensure_branch()
        path = f"{self.folder}/{self.name}-{report['at'][:7]}.jsonl"
        for attempt in range(4):  # another report may land between read and write (409): read again
            try:
                try:
                    cur = self._call('GET', f'contents/{path}?ref={self.branch}')
                    text, sha = base64.b64decode(cur['content']).decode(), cur['sha']
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise
                    text, sha = '', None
                body = {'message': f"{self.folder}: " + ' '.join(str(report.get(k)) for k in ('segment_id', 'dimension', 'direction', 'user_type', 'match', 'type', 'target') if k in report),
                        'content': base64.b64encode((text + json.dumps(report, separators=(',', ':')) + '\n').encode()).decode(),
                        'branch': self.branch}
                if sha:
                    body['sha'] = sha
                self._call('PUT', f'contents/{path}', body)
                return
            except urllib.error.HTTPError as e:
                if e.code not in (409, 422) or attempt == 3:
                    raise
                time.sleep(0.5 * (attempt + 1))


class FeedbackBook:
    """Reports in memory (loaded from the store, refreshed at most every REFRESH_S) and their aggregate."""

    REFRESH_S = 600

    def __init__(self, store=None):
        self.store = store
        self.reports, self.summary, self.loaded_at, self.error = [], {}, 0.0, None
        self.lock = threading.Lock()
        self._limits = {}

    @classmethod
    def from_env(cls):
        token = os.environ.get('FEEDBACK_GITHUB_TOKEN')
        return cls(GitHubStore(os.environ.get('FEEDBACK_REPO', 'ElianMu/strollane'), token) if token else None)

    @property
    def enabled(self):
        return self.store is not None

    def refresh(self, force=False):
        if not self.store or (not force and time.time() - self.loaded_at < self.REFRESH_S):
            return
        try:
            reports = self.store.load()
            with self.lock:
                self.reports, self.summary = reports, aggregate(reports)
                self.loaded_at, self.error = time.time(), None
        except Exception as e:  # keep the last good copy; routing never waits on GitHub
            self.loaded_at, self.error = time.time(), str(e)[:200]

    def refresh_in_background(self):
        if self.store and time.time() - self.loaded_at >= self.REFRESH_S:
            self.loaded_at = time.time()  # one refresh at a time
            threading.Thread(target=self.refresh, kwargs={'force': True}, daemon=True).start()

    def allow(self, client, key):
        """At most 20 reports an hour from one client, and one per segment and dimension a day. `client` is only held
        in memory, as a hash, for this check."""
        now, h = time.time(), hash(client)
        recent = [t for t in self._limits.get(h, []) if now - t[0] < 86400]
        if sum(now - t < 3600 for t, _ in recent) >= 20 or any(k == key for _, k in recent):
            return False
        recent.append((now, key))
        self._limits[h] = recent
        if len(self._limits) > 5000:
            self._limits = {k: v for k, v in self._limits.items() if v and now - v[-1][0] < 86400}
        return True

    def add(self, report):
        self.store.append(report)
        with self.lock:
            self.reports = self.reports + [report]
            self.summary = aggregate(self.reports)

    def for_segment(self, segment_id):
        return self.summary.get(segment_id, {})

RULE = (f'A street dimension is adjusted only after {MIN_REPORTS}+ walker reports on {MIN_DAYS}+ different days, '
        f'at least {round(MIN_AGREEMENT * 100)}% of them agreeing; the change is capped at ±{MAX_DELTA:g} points, smaller with '
        f'fewer reports, and fades with a {HALF_LIFE_DAYS:g}-day half-life. Quiet and Urban Vibrancy use only reports '
        'from the same time of day. The data score itself is never replaced.')
