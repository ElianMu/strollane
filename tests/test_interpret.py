"""/api/interpret failure reporting with the OpenAI call mocked (no network, no real key): every failure returns a safe
`reason` (stage, HTTP status, provider error type/code, our validator's message) and the key never appears in the response
or the log. Run: python3 -m unittest tests.test_interpret
"""
import contextlib, io, json, pathlib, sys, unittest
from unittest import mock
from urllib import error

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402

FAKE_KEY = 'sk-test-SECRET1234567890abcdef'
DOC = {'message': 'I want a greener walk'}


class Resp:
    def __init__(self, body):
        self.body = json.dumps(body).encode() if not isinstance(body, bytes) else body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, body):
    return error.HTTPError('https://api.openai.com/v1/chat/completions', code, 'err', {}, io.BytesIO(json.dumps(body).encode()))


def wire(doc):
    """Test fixture encoder: mocks the new provider wire format, not production AI."""
    from interpretation_contract import WIRE_SCHEMA
    def fill(value, schema):
        if 'anyOf' in schema:
            return None if value is None else fill(value, schema['anyOf'][0])
        if schema['type'] == 'object' and isinstance(value, dict):
            out = dict(value)
            for k, spec in schema['properties'].items():
                default = None if 'anyOf' in spec else [] if spec['type'] == 'array' else {} if spec['type'] == 'object' else True
                out[k] = fill(out.get(k, default), spec)
            return out
        if schema['type'] == 'array' and isinstance(value, list):
            return [fill(x, schema['items']) for x in value]
        return value
    out = {k: v for k, v in doc.items() if k not in ('weights', 'directions')}
    out['preferences'] = []
    for d in dict.fromkeys([*doc.get('weights', {}), *doc.get('directions', {})]):
        record = {'dimension': d, 'direction': doc.get('directions', {}).get(d, 'high')}
        if d in doc.get('weights', {}):
            record['weight'] = doc['weights'][d]
        out['preferences'].append(record)
    # Do not fill missing weight: the orphan-direction fixtures must stay invalid.
    saved = out['preferences']
    result = fill(out, WIRE_SCHEMA)
    result['preferences'] = saved
    return result


def completion(content):
    if isinstance(content, dict):
        content = wire(content)
    return Resp({'choices': [{'message': {'content': content if isinstance(content, str) else json.dumps(content)}}]})


class InterpretFailures(unittest.TestCase):
    def run_with(self, effect, message=None):
        log = io.StringIO()
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(server.request, 'urlopen', **({'side_effect': effect} if isinstance(effect, BaseException) else {'return_value': effect})), contextlib.redirect_stdout(log):
            status, body = server.interpret({'message':message} if message is not None else dict(DOC))
        text = json.dumps(body) + log.getvalue()
        self.assertNotIn(FAKE_KEY, text, 'the key never leaks')
        self.assertNotIn('SECRET', text)
        return status, body, log.getvalue()

    def test_key_environment_whitespace_is_trimmed(self):
        key = server.normalize_openai_api_key('  \r\nsk-test-clean-token \t\n')
        self.assertEqual(key, 'sk-test-clean-token')
        self.assertIsNone(server.openai_key_problem(key))
        with mock.patch.object(server, 'KEY', key), mock.patch.object(server.request, 'urlopen', return_value=completion({'weights': {}, 'constraints': {}})) as opener:
            status, body = server.interpret(dict(DOC))
        self.assertEqual(status, 200)
        self.assertEqual(body['weights'], {})
        self.assertEqual(opener.call_args.args[0].get_header('Authorization'), 'Bearer sk-test-clean-token')

    def test_key_format_problem_stops_before_http(self):
        for key in ('sk-test-middle\nnewline', 'sk-test-middle space', 'sk-test-middle\x00nul', 'sk-test-middle\u200bnonascii'):
            with self.subTest(key=repr(key)), mock.patch.object(server, 'KEY', key), mock.patch.object(server.request, 'urlopen') as opener:
                log = io.StringIO()
                with contextlib.redirect_stdout(log):
                    status, body = server.interpret(dict(DOC))
                self.assertEqual(status, 503)
                self.assertEqual(body['reason']['stage'], 'invalid_key_format')
                self.assertNotIn(key, json.dumps(body) + log.getvalue())
                opener.assert_not_called()

    def test_blank_environment_value_is_not_configured(self):
        self.assertEqual(server.normalize_openai_api_key(' \r\n '), '')
        self.assertEqual(server.openai_key_problem(''), 'not_configured')

    def test_not_configured(self):
        with mock.patch.object(server, 'KEY', ''):
            status, body = server.interpret(dict(DOC))
        self.assertEqual(status, 503); self.assertEqual(body['reason']['stage'], 'not_configured')

    def test_invalid_key(self):
        status, body, log = self.run_with(http_error(401, {'error': {'message': f'Incorrect API key provided: {FAKE_KEY[:8]}***cdef', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}))
        self.assertEqual(status, 502)
        self.assertEqual(body['reason'], {'stage': 'upstream_http', 'http_status': 401, 'type': 'invalid_request_error', 'code': 'invalid_api_key', 'detail': None})
        self.assertIn('invalid_api_key', log)
        self.assertNotIn('Incorrect API key', json.dumps(body), 'the provider message (which echoes key fragments) is not passed on')

    def test_no_quota(self):
        status, body, _ = self.run_with(http_error(429, {'error': {'message': 'You exceeded your current quota', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}}))
        self.assertEqual((body['reason']['http_status'], body['reason']['code']), (429, 'insufficient_quota'))

    def test_model_not_available(self):
        status, body, _ = self.run_with(http_error(404, {'error': {'type': 'invalid_request_error', 'code': 'model_not_found'}}))
        self.assertEqual(body['reason']['code'], 'model_not_found')

    def test_unreachable(self):
        status, body, _ = self.run_with(error.URLError(TimeoutError('timed out')))
        self.assertEqual(body['reason']['stage'], 'upstream_unreachable'); self.assertEqual(body['reason']['detail'], 'TimeoutError')

    def test_bad_provider_response(self):
        status, body, _ = self.run_with(Resp({'object': 'error'}))
        self.assertEqual(body['reason']['stage'], 'upstream_bad_response')

    def test_model_output_not_json(self):
        status, body, _ = self.run_with(completion('Sure! Here is your plan: greener streets.'))
        self.assertEqual(body['reason']['stage'], 'model_output_invalid_json')

    def test_model_output_rejected_names_the_problem(self):
        status, body, log = self.run_with(completion({'weights': {'Greenery': 90}, 'directions': {}, 'constraints': {}}))
        r = body['reason']
        self.assertEqual(r['stage'], 'model_output_rejected'); self.assertIn('preferences[].dimension', r['detail'])
        self.assertIn('model_output_rejected', log)

    def test_dimension_failure_diagnostics_are_distinct(self):
        cases = [({'weights': {'Scenic': 90}}, 'name in weights'),
                 ({'weights': {'Nature': 90}, 'directions': {'Parks': 'high'}}, 'name in directions'),
                 ({'weights': {}, 'directions': {'Nature': 'high'}}, 'no corresponding weight')]
        for output, detail in cases:
            with self.subTest(detail=detail):
                with self.assertRaisesRegex(ValueError, detail):
                    server.validate_interpretation(output)


    def test_success_unchanged(self):
        status, body, _ = self.run_with(completion({'weights': {'Nature': 90}, 'directions': {'Nature': 'high'}, 'constraints': {}}))
        self.assertEqual(status, 200); self.assertEqual(body['weights'], {'Nature': 90}); self.assertNotIn('reason', body)

    def test_history_must_be_array(self):
        with mock.patch.object(server, 'KEY', FAKE_KEY):
            status, _ = server.interpret({'message': 'walk', 'history': None})
        self.assertEqual(status, 400)

    def test_unexpected_failure_logs_frames_without_message(self):
        status, body, log = self.run_with(ValueError('SECRET header value'))
        self.assertEqual(status, 500)
        self.assertIn('frames', log)
        self.assertIn('call_llm', log)

    def test_coffee_is_preserved_separately_from_weights(self):
        result = {'weights': {'Scenic & Visual': 90, 'Architecture': 85, 'Nature': 85},
                  'journey': {'interests': ['parks'], 'food': [
                      {'category': 'cafes', 'item': 'coffee', 'required': True}]}}
        status, body, _ = self.run_with(completion(result), message='I want a scenic walk with architecture, parks, and good coffee.')
        self.assertEqual(status, 200)
        self.assertEqual(body['journey']['food'][0]['item'], 'coffee')
        self.assertEqual(body['journey']['interests'], ['parks'])
        from routing.engine import get_planner
        routes = get_planner().plan({'lon': -73.9832, 'lat': 40.7536},
                                   {'lon': -73.9787, 'lat': 40.7587}, body,
                                   {'max_minutes': 30, 'max_detour_pct': 25})['routes']
        self.assertTrue(routes)
        self.assertTrue(all(r['distance_m'] > 0 and r['ordered_edge_ids'] for r in routes))
        self.assertEqual(set(routes[0]['dimension_scores']), set(server.DIMENSIONS))
        self.assertIn('food must preserve it', server.SYSTEM)
        self.assertIn('restaurants or cafes without naming a dish', server.SYSTEM)

    def test_orphan_direction_is_corrected_by_model_once(self):
        invalid = {'weights': {'Nature': 85}, 'directions': {'Architecture': 'high'}}
        valid = {'weights': {'Nature': 85, 'Architecture': 90},
                 'directions': {'Nature': 'high', 'Architecture': 'high'},
                 'journey': {'food': [{'category': 'cafes', 'item': 'coffee', 'required': True}]}}
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(
                server.request, 'urlopen', side_effect=[completion(invalid), completion(valid)]) as call:
            status, body = server.interpret({'message': 'Architecture, parks and coffee'})
        self.assertEqual(status, 200)
        self.assertEqual(body['weights'], valid['weights'])
        self.assertEqual(body['journey']['food'][0]['item'], 'coffee')
        self.assertEqual(call.call_count, 2)
        second = json.loads(call.call_args_list[1].args[0].data)
        self.assertIn('missing fields', second['messages'][-1]['content'])
        self.assertEqual(json.loads(second['messages'][-2]['content']), wire(invalid))
        self.assertEqual(second['response_format']['type'], 'json_schema')
        self.assertTrue(second['response_format']['json_schema']['strict'])
        self.assertLessEqual(call.call_args_list[1].kwargs['timeout'], call.call_args_list[0].kwargs['timeout'])

    def test_repeated_invalid_result_still_fails(self):
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(
                server.request, 'urlopen', return_value=completion({'directions': {'Nature': 'high'}})) as call:
            status, body = server.interpret(dict(DOC))
        self.assertEqual(status, 502)
        self.assertEqual(body['reason']['stage'], 'model_output_rejected')
        self.assertEqual(call.call_count, 2)

    def test_no_retry_after_deadline(self):
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(
                server.time, 'monotonic', side_effect=[0, 0, 27]), mock.patch.object(
                server.request, 'urlopen', return_value=completion({'directions': {'Nature': 'high'}})) as call:
            status, body = server.interpret(dict(DOC))
        self.assertEqual(status, 502)
        self.assertEqual(body['reason']['detail'], 'TimeoutError')
        self.assertEqual(call.call_count, 1)

    def test_authentication_error_is_not_retried(self):
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(
                server.request, 'urlopen', side_effect=http_error(401, {'error': {'code': 'invalid_api_key'}})) as call:
            status, body = server.interpret(dict(DOC))
        self.assertEqual(status, 502)
        self.assertEqual(body['reason']['code'], 'invalid_api_key')
        self.assertEqual(call.call_count, 1)

    def test_provider_refusal_and_truncation_are_distinct(self):
        for choice, stage in [({'message': {'refusal': 'refused', 'content': None}}, 'model_refused'),
                              ({'finish_reason': 'length', 'message': {'content': '{'}}, 'model_output_incomplete')]:
            with self.subTest(stage=stage):
                status, body, _ = self.run_with(Resp({'choices': [choice]}))
                self.assertEqual(status, 502)
                self.assertEqual(body['reason']['stage'], stage)

    def test_scrub(self):
        with mock.patch.object(server, 'KEY', FAKE_KEY):
            self.assertEqual(server.scrub(f'value {FAKE_KEY} and sk-proj-abcdEFGH1234 end'), 'value [key] and [key] end')


if __name__ == '__main__':
    unittest.main()


class ReplyLanguage(unittest.TestCase):
    """reply_language 'zh' asks the model for Chinese clarifications / unsupported reasons; nothing else changes."""
    def sent_prompt(self, doc):
        seen = {}
        def fake(req, timeout=None):
            seen['body'] = json.loads(req.data.decode())
            return completion({'weights': {'Nature': 90}, 'directions': {'Nature': 'high'}, 'constraints': {}})
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(server.request, 'urlopen', side_effect=fake):
            status, body = server.interpret(doc)
        self.assertEqual(status, 200)
        return seen['body']['messages'][-1]['content']

    def test_chinese_interface_asks_for_chinese_text(self):
        prompt = self.sent_prompt({**DOC, 'reply_language': 'zh'})
        self.assertIn('Simplified Chinese', prompt)
        # the language note must not push the model towards clarifications or unsupported items (seen live on
        # 2026-11-20: "quieter and greener" came back as unsupported in Chinese mode)
        self.assertIn('changes nothing about WHAT you return', prompt)
        self.assertIn('never unsupported', prompt)

    def test_english_by_default(self):
        self.assertNotIn('Chinese', self.sent_prompt(dict(DOC)))


class GenericNamedStops(unittest.TestCase):
    def test_a_food_word_is_not_a_named_place(self):
        # Live 2026-11-21: "with a coffee stop" came back with named_stops=[coffee]; the map search found "Coffeed".
        j = {'interests': [], 'services': [], 'food': [{'category': 'cafes', 'item': 'coffee', 'cuisine': None, 'required': True}],
             'named_stops': [{'name': n, 'required': True, 'order': None} for n in ('coffee', 'a coffee stop', 'lunch', '咖啡', 'Joe Coffee Company', 'Blue Bottle')],
             'service_scope': None, 'hotel': None, 'origin': None, 'destination': None, 'end_mode': None, 'walking_minutes': None,
             'outing_minutes': None, 'distance_km': None, 'more': {}, 'remove': [], 'requirements': None, 'counts': {}}
        self.assertEqual([x['name'] for x in server.validate_journey(j)['named_stops']], ['Joe Coffee Company', 'Blue Bottle'])


class EndsAndOtherBindings(unittest.TestCase):
    """Bindings the 2026-11-21 eval (eval/interpret_cases.jsonl) found the model getting wrong; each goes back to the
    model once with the reason, like every other rejected binding."""
    def check(self, result, message, history=()):
        server.validate_intent_bindings(result, message, history)

    def test_the_ends_a_request_names(self):
        cases = {
            'From Grand Army Plaza to Brooklyn Bridge Park, a quieter greener walk': ('Grand Army Plaza', 'Brooklyn Bridge Park'),
            'A quiet walk away from busy streets, from Astoria Park to Socrates Sculpture Park': ('Astoria Park', 'Socrates Sculpture Park'),
            'I want to see historic buildings and grab a bagel, start at City Hall': ('City Hall', None),
            'Coffee first, then the Met, and end at the Guggenheim': (None, 'Guggenheim'),
            'Walk from my hotel to the High Line and then end at Chelsea Market': (None, 'Chelsea Market'),
            '从哥伦比亚大学走到中央公园': ('哥伦比亚大学', '中央公园'),
            '晚上走，安全一点，从宾州车站到切尔西市场': ('宾州车站', '切尔西市场'),
            '博物馆加一块披萨，终点随意，从中央车站出发': ('中央车站', None),
            '先喝咖啡，再去大都会博物馆，最后古根海姆': (None, '古根海姆'),
            '杰克逊高地走到法拉盛草原可乐娜公园': ('杰克逊高地', '法拉盛草原可乐娜公园'),
            # no place name: a time, "here", "my hotel", a pronoun, "finally another coffee"
            'A walk from 2 to 4 pm': (None, None), 'from here to Central Park': (None, 'Central Park'),
            'Start from my hotel, visit two landmarks and return to my hotel.': (None, None),
            '我想走到中央公园': (None, None), '最后再喝杯咖啡': (None, None), 'Take me there': (None, None),
            'I want a greener walk': (None, None),
        }
        for text, ends in cases.items():
            self.assertEqual(server.request_endpoints(text), ends, text)

    def test_named_ends_are_not_stops(self):
        stops = {'origin': None, 'destination': None, 'named_stops': [{'name': 'Columbia University', 'required': True, 'order': None}, {'name': 'Central Park', 'required': True, 'order': None}]}
        with self.assertRaisesRegex(ValueError, 'journey.origin'):
            self.check({'journey': stops}, '从哥伦比亚大学走到中央公园')
        with self.assertRaisesRegex(ValueError, 'journey.destination'):
            self.check({'journey': {**stops, 'origin': 'Columbia University'}}, '从哥伦比亚大学走到中央公园')
        with self.assertRaisesRegex(ValueError, 'journey.origin'):
            self.check({'weights': {'Nature': 90}, 'journey': None}, 'Fewer crowds and more trees, from Prospect Park to Park Slope')
        self.check({'journey': {'origin': 'Columbia University', 'destination': 'Central Park', 'named_stops': []}}, '从哥伦比亚大学走到中央公园')
        self.check({'journey': {'origin': 'hotel', 'end_mode': 'hotel', 'interests': ['famous'], 'counts': {'famous': 2}}}, 'Start from my hotel, visit two landmarks and return to my hotel.')

    def test_a_park_on_the_water_is_not_a_waterfront_wish(self):
        ends = {'origin': 'Grand Army Plaza', 'destination': 'Brooklyn Bridge Park'}
        with self.assertRaisesRegex(ValueError, 'waterfront'):
            self.check({'waterfront': {'mode': 'set', 'direction': 'high', 'weight': 90}, 'journey': ends}, 'From Grand Army Plaza to Brooklyn Bridge Park, a quieter greener walk')
        self.check({'waterfront': {'mode': 'set', 'direction': 'high', 'weight': 90}}, 'I would like a walk along the water')
        self.check({'waterfront': {'mode': 'set', 'direction': 'low', 'weight': 90}}, '离河远一点')

    def test_a_safe_walk_never_asks_for_more_crime(self):
        ends = {'origin': 'Penn Station', 'destination': 'Chelsea Market'}
        with self.assertRaisesRegex(ValueError, 'LESS reported crime'):
            self.check({'crime': {'mode': 'set', 'direction': 'high', 'weight': 90}, 'journey': ends}, '晚上走，安全一点，从宾州车站到切尔西市场')
        self.check({'crime': {'mode': 'set', 'direction': 'low', 'weight': 90}, 'journey': ends}, '晚上走，安全一点，从宾州车站到切尔西市场')
        self.check({'crime': {'mode': 'set', 'direction': 'high', 'weight': 90}}, 'I want a route with very high crime rate')

    def test_there_with_nothing_named_is_a_question(self):
        empty = {'weights': {}, 'directions': {}, 'constraints': {}, 'journey': None, 'unsupported': []}
        with self.assertRaisesRegex(ValueError, 'clarification'):
            self.check(empty, 'Take me there')
        self.check({**empty, 'clarification': 'Where would you like to go?'}, 'Take me there')
        self.check(empty, 'Take me there', [{'role': 'user', 'content': 'Is the Frick open today?'}])  # a place named earlier

    def test_the_model_repairs_the_ends_once(self):
        wrong = {'weights': {'Quiet & Relax': 90}, 'directions': {'Quiet & Relax': 'high'},
                 'journey': {'named_stops': [{'name': 'Astoria Park', 'required': True, 'order': None}, {'name': 'Socrates Sculpture Park', 'required': True, 'order': None}]}}
        right = {'weights': {'Quiet & Relax': 90}, 'directions': {'Quiet & Relax': 'high'},
                 'journey': {'origin': 'Astoria Park', 'destination': 'Socrates Sculpture Park'}}
        with mock.patch.object(server, 'KEY', FAKE_KEY), mock.patch.object(
                server.request, 'urlopen', side_effect=[completion(wrong), completion(right)]) as call:
            status, body = server.interpret({'message': '从 Astoria Park 走到 Socrates Sculpture Park，安静一点'})
        self.assertEqual(status, 200)
        self.assertEqual((body['journey']['origin'], body['journey']['destination']), ('Astoria Park', 'Socrates Sculpture Park'))
        second = json.loads(call.call_args_list[1].args[0].data)
        self.assertIn('names its start', second['messages'][-1]['content'])

    def test_prompt_states_the_rules(self):
        for words in ('never in named_stops', '中央车站 Grand Central Terminal', 'Bagels', '贝果 bagel', 'is NOT a waterfront preference', 'safe/safer walk', '车多', 'take me there'):
            self.assertIn(words, server.SYSTEM)

    def test_several_problems_go_back_together(self):
        result = {'waterfront': {'mode': 'set', 'direction': 'high', 'weight': 90}, 'crime': {'mode': 'set', 'direction': 'high', 'weight': 90},
                  'journey': {'named_stops': [{'name': 'Penn Station'}, {'name': 'Chelsea Market'}]}}
        with self.assertRaises(ValueError) as e:
            self.check(result, '晚上走，安全一点，从宾州车站到切尔西市场')
        for words in ('LESS reported crime', 'waterfront', 'journey.origin', 'journey.destination'):
            self.assertIn(words, str(e.exception))
