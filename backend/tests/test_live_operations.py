import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('verify_live_operations', Path(__file__).parents[1] / 'scripts/verify_live_operations.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LiveOperationsTests(unittest.TestCase):
    def events(self, table='table', other='id', stream='s'):
        return [{'timestamp':10,'logStreamName':'s','eventId':'a','message':'{"event":"intent_put_started","intentId":"id","table":"'+table+'"}'},
                {'timestamp':11,'logStreamName':stream,'eventId':'b','message':'{"event":"intent_put_succeeded","intentId":"'+other+'"}'}]
    def check(self, events):
        return module.correlate({'Item':{'intentId':{'S':'id'}}}, events, 'id', 'table', 0, 20)
    def test_exact_pair(self):
        self.assertEqual(self.check(self.events())['verdict'], 'CONFIRMED_SPECIFIC_APP_WRITE')
    def test_unrelated_table_id_stream_or_window_rejected(self):
        for events in [self.events(table='other'),self.events(other='other'),self.events(stream='other'),self.events()[:1], self.events()[1:]]:
            with self.subTest(events=events), self.assertRaises(ValueError): self.check(events)
        with self.assertRaises(ValueError): module.correlate({'Item':{'intentId':{'S':'id'}}}, self.events(), 'id', 'table', 12, 20)
    def test_arbitrary_text_rejected(self):
        with self.assertRaises(ValueError): self.check([{'timestamp':10,'message':'intent_put_succeeded id'}])

    def test_missing_source_identity_cannot_corroborate_a_write(self):
        for field in ['logStreamName', 'eventId']:
            events = self.events()
            for event in events:
                event.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(events)
