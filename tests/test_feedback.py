"""Walker feedback (routing/feedback.py): validation, the aggregation rules, the store protocol and the routing overlay."""
import base64
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from routing import feedback as fb  # noqa: E402

NOW = datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc)   # 15:00 in New York: 'midday'


def rep(seg='QN-1', dim='architecture', direction='worse', days_ago=0, hour=20):
    at = (NOW - timedelta(days=days_ago)).replace(hour=hour)
    return {'v': 1, 'id': 'x', 'at': at.isoformat(), 'segment_id': seg, 'dimension': dim, 'direction': direction,
            'rated': 70, 'bucket': fb.ny_bucket(at), 'score_version': None}


class Validation(unittest.TestCase):
    def test_report_keeps_nothing_personal(self):
        r = fb.make_report({'segment_id': 'QN-1', 'dimension': 'quiet', 'direction': 'worse', 'rated': 81.4,
                            'lat': 40.7, 'lon': -73.9, 'name': 'someone', 'note': 'free text'}, lambda s: True, NOW)
        self.assertEqual(set(r), {'v', 'id', 'at', 'segment_id', 'dimension', 'direction', 'rated', 'bucket', 'score_version'})
        self.assertEqual((r['rated'], r['bucket'], r['at']), (81, 'midday', '2026-11-19T20:00:00+00:00'))

    def test_rejects_unknown_values(self):
        known = lambda s: s == 'QN-1'
        for bad in ({'segment_id': 'QN-2', 'dimension': 'quiet', 'direction': 'worse'},
                    {'segment_id': 'QN-1', 'dimension': 'loudness', 'direction': 'worse'},
                    {'segment_id': 'QN-1', 'dimension': 'quiet', 'direction': 'awful'},
                    {'segment_id': 'QN-1', 'dimension': 'quiet', 'direction': 'worse', 'rated': 140}, 'text'):
            with self.assertRaises(ValueError):
                fb.make_report(bad, known, NOW)

    def test_new_york_buckets(self):
        self.assertEqual(fb.ny_bucket(datetime(2026, 7, 1, 12, tzinfo=timezone.utc)), 'morning')   # 08:00 EDT
        self.assertEqual(fb.ny_bucket(datetime(2026, 1, 15, 2, tzinfo=timezone.utc)), 'evening')   # 21:00 EST
        self.assertEqual(fb.ny_bucket(datetime(2026, 1, 15, 4, tzinfo=timezone.utc)), 'night')


class Aggregation(unittest.TestCase):
    def test_one_report_changes_nothing(self):
        s = fb.aggregate([rep()], NOW)['QN-1']['architecture']
        self.assertEqual((s['status'], s['delta'], fb.delta_for(s, 'midday')), ('pending', 0.0, 0.0))

    def test_needs_different_days(self):
        same_day = [rep(hour=h) for h in (14, 15, 16)]
        self.assertEqual(fb.aggregate(same_day, NOW)['QN-1']['architecture']['status'], 'pending')

    def test_agreeing_reports_move_a_score_within_the_cap(self):
        three = fb.aggregate([rep(days_ago=d) for d in (0, 1, 2)], NOW)['QN-1']['architecture']
        many = fb.aggregate([rep(days_ago=d) for d in range(40)], NOW)['QN-1']['architecture']
        self.assertEqual(three['status'], 'applied')
        self.assertTrue(-fb.MAX_DELTA < three['delta'] < -5)
        self.assertTrue(-fb.MAX_DELTA <= many['delta'] < three['delta'])
        better = fb.aggregate([rep(direction='better', days_ago=d) for d in (0, 1, 2)], NOW)['QN-1']['architecture']
        self.assertEqual(better['delta'], -three['delta'])

    def test_disagreement_and_age(self):
        mixed = [rep(days_ago=0), rep(days_ago=1), rep(direction='better', days_ago=2), rep(direction='better', days_ago=3)]
        self.assertEqual(fb.aggregate(mixed, NOW)['QN-1']['architecture']['status'], 'mixed')
        old = fb.aggregate([rep(days_ago=d) for d in (200, 201, 202)], NOW)['QN-1']['architecture']
        new = fb.aggregate([rep(days_ago=d) for d in (0, 1, 2)], NOW)['QN-1']['architecture']
        self.assertTrue(abs(old['delta']) < abs(new['delta']))
        self.assertNotIn('QN-1', fb.aggregate([rep(days_ago=d) for d in (400, 401, 402)], NOW))

    def test_noise_reports_only_apply_at_their_time_of_day(self):
        s = fb.aggregate([rep(dim='quiet', days_ago=d, hour=3) for d in (0, 1, 2)], NOW)['QN-1']['quiet']   # 22:00/23:00 New York
        self.assertEqual(s['status'], 'applied')
        self.assertLess(fb.delta_for(s, 'night'), 0)
        self.assertEqual(fb.delta_for(s, 'midday'), 0.0)


class Store(unittest.TestCase):
    def test_append_then_load_round_trip(self):
        files = {}

        def call(method, path, body=None):
            if path.startswith('branches/'):
                return {}
            name = path.split('?')[0].replace('contents/', '')
            if method == 'GET' and name == 'feedback':
                if not files:
                    raise fb.urllib.error.HTTPError(path, 404, 'nf', None, None)
                return [{'name': n.split('/')[-1]} for n in files]
            if method == 'GET':
                if name not in files:
                    raise fb.urllib.error.HTTPError(path, 404, 'nf', None, None)
                return {'content': base64.b64encode(files[name].encode()).decode(), 'sha': 's'}
            files[name] = base64.b64decode(body['content']).decode()
            return {}

        store = fb.GitHubStore('o/r', 't')
        with mock.patch.object(store, '_call', side_effect=call):
            self.assertEqual(store.load(), [])
            a, b = rep(), rep(days_ago=1)
            store.append(a); store.append(b)
            self.assertEqual(store.load(), [a, b])
        self.assertEqual(list(files), ['feedback/reports-2026-11.jsonl'])

    def test_rate_limit(self):
        book = fb.FeedbackBook()
        self.assertTrue(book.allow('1.2.3.4', ('QN-1', 'quiet')))
        self.assertFalse(book.allow('1.2.3.4', ('QN-1', 'quiet')))
        self.assertTrue(book.allow('1.2.3.5', ('QN-1', 'quiet')))
        self.assertFalse(fb.FeedbackBook().enabled)


class Routing(unittest.TestCase):
    def test_overlay_moves_route_scores_but_keeps_the_data_scores(self):
        from routing.engine import get_planner
        p = get_planner()
        args = ({'lon': -73.9535, 'lat': 40.7425}, {'lon': -73.9370, 'lat': 40.7480}, {'architecture': 90}, {'max_minutes': 60})
        before = p.plan(*args)['routes'][0]
        seg = next(m for e in before['edges'] for m in e.get('matched_segments', []) if m['segment_id'])['segment_id']
        book = fb.FeedbackBook()
        book.summary = fb.aggregate([rep(seg=seg, days_ago=d) for d in range(10)], datetime.now(timezone.utc))
        with mock.patch.object(p, 'feedback', book):
            after = p.plan(*args)['routes']
        hit = [r for r in after if r['walker_feedback']['applied']]
        self.assertTrue(hit)
        r = hit[0]
        self.assertEqual(r['walker_feedback']['applied'][0]['segment_id'], seg)
        self.assertLess(r['walker_feedback']['applied'][0]['delta'], 0)
        self.assertLessEqual(r['dimension_scores']['Architecture'], r['walker_feedback']['dimension_scores_from_data']['Architecture'])
        self.assertEqual(before['walker_feedback']['applied'], [])


if __name__ == '__main__':
    unittest.main()
