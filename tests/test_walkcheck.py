"""Walk feedback and evaluation (routing/walkcheck.py; server /api/walk-checks and /api/evaluation)."""
import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from routing import walkcheck as wc  # noqa: E402

NOW = datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)   # 18:30 in New York: 'evening'
PRED = {d: 50 for d in wc.DIMENSION_LABELS}


def check(ratings, predicted=PRED, **kw):
    return wc.make_check({'user_type': kw.pop('user_type', 'leisure'), 'ratings': ratings, **kw}, predicted, NOW)


class Records(unittest.TestCase):
    def test_a_record_holds_nothing_personal(self):
        c = wc.make_check({'user_type': 'leisure', 'ratings': {'overall': 4, 'quiet': 5}, 'study_code': 'p07',
                           'priorities': {'Nature': {'weight': 80, 'direction': 'high'}}, 'route_id': 'rt-abc123',
                           'comment': 'Lovely. Mail me at a.b@example.com or call +1 (212) 555-0199, see https://x.y/z',
                           'lat': 40.7, 'lon': -73.9, 'name': 'someone', 'predicted': {'Nature': 100}}, PRED, NOW)
        self.assertEqual(set(c), {'v', 'id', 'at', 'bucket', 'user_type', 'priorities', 'ratings', 'dimension_ratings',
                                  'comment', 'worth_detour', 'compared_with_shortest', 'study_code', 'route_id',
                                  'route_signature', 'score_version', 'network_version', 'distance_m', 'detour_pct',
                                  'predicted', 'photos'})
        self.assertEqual(c['photos'], [], 'no photos sent: an empty list, not missing')
        self.assertEqual(c['ratings'], {'overall': 4, 'match': None, 'quiet': 5, 'green': None})
        self.assertEqual((c['study_code'], c['bucket'], c['at']), ('P07', 'evening', '2026-11-20T23:00:00+00:00'))
        self.assertEqual(c['predicted'], PRED, 'the prediction is the server\'s, never the client\'s')
        self.assertNotIn('@', c['comment']); self.assertNotIn('555', c['comment']); self.assertNotIn('https', c['comment'])
        self.assertTrue(c['comment'].startswith('Lovely.'))
        self.assertEqual(len(wc.clean_text('x' * 900)), wc.TEXT_MAX)

    def test_rejects_bad_answers(self):
        for bad in ({'user_type': 'tourist', 'ratings': {}}, {'user_type': 'tourist', 'ratings': {'overall': 6}},
                    {'user_type': 'tourist', 'ratings': {'overall': 3.5}}, {'user_type': 'robot', 'ratings': {'overall': 3}},
                    {'user_type': 'tourist', 'ratings': {'overall': 3}, 'dimension_ratings': {'Hidden gems': 4}},
                    {'user_type': 'tourist', 'ratings': {'overall': 3}, 'priorities': {'Nature': {'weight': 300}}},
                    {'user_type': 'tourist', 'ratings': {'overall': 3}, 'study_code': 'Jane Doe'}, []):
            with self.assertRaises(ValueError):
                wc.make_check(bad, None, NOW)

    def test_photos(self):
        jpeg = 'data:image/jpeg;base64,' + 'AB01+/' * 20 + '=='
        ok = check({'overall': 4}, photos=[jpeg, jpeg])
        self.assertEqual(ok['photos'], [jpeg, jpeg])
        self.assertEqual(check({'overall': 4})['photos'], [])
        with self.assertRaises(ValueError):
            check({'overall': 4}, photos=[jpeg] * (wc.PHOTOS_MAX + 1))
        with self.assertRaises(ValueError):
            check({'overall': 4}, photos='not-a-list')
        with self.assertRaises(ValueError):
            check({'overall': 4}, photos=['not-a-data-url'])
        with self.assertRaises(ValueError):
            check({'overall': 4}, photos=['data:image/gif;base64,' + 'A' * 20])  # not an accepted image type
        with self.assertRaises(ValueError):
            check({'overall': 4}, photos=['data:image/jpeg;base64,' + 'A' * (wc.PHOTO_MAX_CHARS + 1)])


class Evaluation(unittest.TestCase):
    def test_no_data(self):
        e = wc.evaluate([])
        self.assertEqual(e['n'], 0)
        self.assertTrue(e['limitations'] and e['sources'])
        self.assertNotIn('ratings', e)

    def test_ratings_missing_values_and_types(self):
        rows = [check({'overall': 4, 'quiet': 5}), check({'overall': 2}, user_type='tourist'), check({'overall': 5, 'green': 3}, predicted=None)]
        e = wc.evaluate(rows)
        self.assertEqual(e['n'], 3)
        self.assertEqual(e['ratings']['overall'], {'n': 3, 'missing': 0, 'mean': 3.67, 'counts': {'1': 0, '2': 1, '3': 0, '4': 1, '5': 1}})
        self.assertEqual((e['ratings']['quiet']['n'], e['ratings']['quiet']['missing']), (1, 2))
        self.assertEqual(e['missing']['prediction_unavailable'], 1)
        self.assertEqual(e['by_user_type']['tourist']['n'], 1)
        self.assertEqual(set(e['comparison']), {'Quiet & Relax'}, 'the greenery answer has no prediction, so it is not compared')

    def test_comments_for_other_walkers(self):
        rows = [check({'overall': 4}, comment='Quiet side streets, lovely.'), check({'overall': 2}, user_type='tourist'),
                check({'overall': 5}, user_type='tourist', comment='Call me at 212 555 0199 ' + 'x' * 400)]
        rows[0]['at'], rows[2]['at'] = '2026-11-18T15:00:00+00:00', '2026-11-20T23:00:00+00:00'
        said = wc.evaluate(rows)['recent_comments']
        self.assertEqual([c['date'] for c in said], ['2026-11-20', '2026-11-18'], 'newest first, day only')
        self.assertEqual(set(said[0]), {'date', 'user_type', 'overall', 'comment', 'photos'}, 'no route, time, code or prediction')
        self.assertEqual(said[0]['photos'], [])
        self.assertEqual((said[1]['comment'], said[1]['overall'], said[1]['user_type']), ('Quiet side streets, lovely.', 4, 'leisure'))
        self.assertNotIn('555', said[0]['comment']); self.assertLessEqual(len(said[0]['comment']), wc.COMMENT_SHOWN_CHARS)
        self.assertEqual(wc.evaluate([check({'overall': 3})])['recent_comments'], [])

    def test_photo_only_comment_shows_up_and_feed_is_budgeted(self):
        jpeg = 'data:image/jpeg;base64,' + 'AB01+/' * 20 + '=='
        photo_only = check({'overall': 5}, photos=[jpeg])
        self.assertIsNone(photo_only['comment'])
        e = wc.evaluate([photo_only, check({'overall': 3})])
        self.assertEqual(len(e['recent_comments']), 1, 'a photo with no text still counts as something to show')
        self.assertEqual(e['recent_comments'][0]['photos'], [jpeg])
        self.assertEqual(e['recent_comments'][0]['comment'], '')
        self.assertEqual(e['photos'], 1)
        # more photo-bearing rows than PHOTOS_IN_FEED: only the first that many carry their photo in this response
        rows = [check({'overall': 5}, photos=[jpeg]) for _ in range(wc.PHOTOS_IN_FEED + 2)]
        for i, r in enumerate(rows):
            r['at'] = f'2026-11-{10 + i:02d}T20:00:00+00:00'   # distinct, increasing timestamps: stable newest-first order
        said = wc.evaluate(rows)['recent_comments']
        self.assertEqual(sum(1 for c in said if c['photos']), wc.PHOTOS_IN_FEED)
        self.assertTrue(all(c['photos'] for c in said[:wc.PHOTOS_IN_FEED]), 'the newest ones get the budget')

    def test_predicted_vs_perceived(self):
        # five walks: predicted Quiet 20, 40, 60, 80, 100 and ratings that rise with it
        rows = [check({'overall': 3, 'quiet': q}, predicted={**PRED, 'Quiet & Relax': p}) for p, q in ((20, 1), (40, 2), (60, 3), (80, 4), (100, 5))]
        c = wc.evaluate(rows)['comparison']['Quiet & Relax']
        self.assertEqual(c['n'], 5)
        self.assertEqual(c['spearman'], 1.0)
        self.assertEqual(c['mean_predicted'], 60)
        self.assertEqual(c['mean_perceived_0_100'], 50)
        self.assertEqual(c['mean_deviation'], -10)          # (0−20, 25−40, 50−60, 75−80, 100−100) / 5
        self.assertEqual(len(c['points']), 5)
        self.assertIsNone(wc.evaluate(rows[:4])['comparison']['Quiet & Relax']['spearman'], 'no correlation below 5 pairs')

    def test_match_compares_with_the_requested_dimensions(self):
        c = check({'overall': 4, 'match': 5}, predicted={**PRED, 'Nature': 80, 'Architecture': 40},
                  priorities={'Nature': {'weight': 80, 'direction': 'high'}, 'Architecture': {'weight': 80, 'direction': 'high'}})
        m = wc.evaluate([c])['comparison']['Match with request']
        self.assertEqual((m['mean_predicted'], m['mean_rating']), (60, 5))

    def test_spearman_handles_ties(self):
        self.assertEqual(wc.spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), -1.0)
        self.assertIsNone(wc.spearman([1, 1, 1, 1, 1], [1, 2, 3, 4, 5]))


class Server(unittest.TestCase):
    def test_prediction_is_recomputed_by_the_server(self):
        from routing.engine import get_planner
        p = get_planner()
        r = p.plan({'lon': -73.8303, 'lat': 40.7596}, {'lon': -73.8448, 'lat': 40.7461}, {'Nature': 80}, {})['routes'][0]
        self.assertEqual(p.data_scores(r['route_id']), r['dimension_scores'])
        snap = {k: r[k] for k in ('route_id', 'network_version', 'route_signature', 'ordered_edge_ids')}
        from_snapshot = p.data_scores(None, snap)
        self.assertTrue(all(abs((from_snapshot[k] or 0) - (r['dimension_scores'][k] or 0)) <= 3 for k in from_snapshot),
                        'a snapshot counts whole end edges, so it can differ by a point or two')
        self.assertIsNone(p.data_scores(None, {**snap, 'route_signature': 'forged'}))
        self.assertIsNone(p.data_scores('rt-never-planned'))

    def test_api_without_a_store(self):
        import server
        os.environ.pop('FEEDBACK_GITHUB_TOKEN', None)
        server._WALK_CHECKS = None
        self.assertFalse(server.walk_checks().enabled)
        self.assertEqual(server.walk_checks().evaluate()['n'], 0)


if __name__ == '__main__':
    unittest.main()


class Lookup(unittest.TestCase):
    def test_street_reports_for_a_route_before_walking(self):
        import json, threading, urllib.request
        from http.server import ThreadingHTTPServer
        import server
        from routing import feedback as fb
        p = server.get_planner()
        book = fb.FeedbackBook()
        rows = [{'v': 1, 'id': str(d), 'at': f'2026-11-{10 + d}T20:00:00+00:00', 'segment_id': 'QN-1', 'dimension': 'quiet',
                 'direction': 'worse', 'rated': 70, 'bucket': 'midday'} for d in range(3)]
        book.summary = fb.aggregate(rows, datetime(2026, 11, 20, tzinfo=timezone.utc))
        old = p.feedback
        p.feedback = book
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            def post(body):
                req = urllib.request.Request(f'http://127.0.0.1:{httpd.server_port}/api/feedback/lookup', data=json.dumps(body).encode(),
                                             headers={'Content-Type': 'application/json'}, method='POST')
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, json.load(r)
                except urllib.error.HTTPError as e:
                    return e.code, json.load(e)
            st, j = post({'segment_ids': ['QN-1', 'QN-2']})
            self.assertEqual(st, 200)
            self.assertEqual(list(j['segments']), ['QN-1'], 'only streets with reports come back')
            self.assertEqual(j['segments']['QN-1']['quiet']['n'], 3)
            self.assertEqual(post({'segment_ids': 'QN-1'})[0], 400)
            self.assertEqual(post({'segment_ids': ['x'] * 601})[0], 400)
        finally:
            httpd.shutdown(); p.feedback = old
