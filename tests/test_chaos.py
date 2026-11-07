import json
from pathlib import Path
import random
import tempfile
import unittest

from house import House
from speech import conversational_speech
from test_desktop_world import Backend
from window_world import WindowWorld, chaos_options, clean_options, clean_rule


class StateBackend(Backend):
    def __init__(self):
        super().__init__()
        self.record['playable'] = True
        self.normal_rect = list(self.record['rect'])
        self.states = []

    def set_state(self,record,state):
        if state not in ('restore','maximize','minimize'):
            return False
        self.states.append(state)
        if self.record['state']=='normal':
            self.normal_rect = list(self.record['rect'])
        self.record['state'] = {'restore':'normal','maximize':'maximized','minimize':'minimized'}[state]
        self.record['movable'] = state=='restore'
        self.record['rect'] = list(self.normal_rect if state=='restore' else self.record['work'])
        return True


class ChaosTests(unittest.TestCase):
    def setUp(self):
        self.backend = StateBackend()
        self.options = chaos_options({})
        self.world = WindowWorld(self.options,self.backend)
        self.world.update([self.backend.record])
        self.key = next(iter(self.world.windows))

    def test_all_windows_work_without_individual_grants_and_moves_are_visible(self):
        self.assertFalse(self.options['window_rules'])
        before = list(self.backend.record['rect'])
        self.assertTrue(self.world.apply({'target':self.key,'dx':180,'dy':80,'dw':80},100,animated=True,shake=True))
        self.world.animate(100.35)
        self.assertNotEqual(self.backend.record['rect'],before)
        self.world.animate(101.2)
        self.assertEqual(self.backend.record['rect'],[280,180,860,580])
        self.assertFalse(self.world.animations)
        self.assertTrue(self.world.undo())
        self.assertEqual(self.backend.record['rect'],before)

    def test_maximized_windows_restore_and_undo_recovers_state(self):
        self.backend.set_state(self.backend.record,'maximize')
        self.world.update([self.backend.record])
        self.assertTrue(self.world.public(self.key,self.backend.record)['allowed'])
        self.assertTrue(self.world.apply({'target':self.key,'dx':100},100))
        self.assertEqual(self.backend.record['state'],'normal')
        self.assertTrue(self.world.undo())
        self.assertEqual(self.backend.record['state'],'maximized')

    def test_closing_is_unavailable_even_in_chaos(self):
        self.assertFalse(self.world.apply({'target':self.key,'kind':'close'},100))
        self.assertFalse(self.backend.states)
        self.assertFalse(self.backend.calls)

    def test_pause_and_policy_revocation_cancel_an_animation(self):
        self.assertTrue(self.world.apply({'target':self.key,'dx':100},100,animated=True))
        self.options['window_control'] = False
        self.world.animate(100.5)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.world.animations)
        self.options['window_control'] = True
        self.assertTrue(self.world.apply({'target':self.key,'dx':100,'dw':100},106,animated=True))
        self.world.overrides[self.key] = clean_rule({'control':'move','distance':280,'size':160})
        self.world.animate(106.5)
        self.assertFalse(self.backend.calls)

    def test_slightly_offscreen_native_borders_do_not_block_play(self):
        self.backend.record['rect'] = [-8,-8,492,392]
        self.world.update([self.backend.record])
        self.assertTrue(self.world.apply({'target':self.key,'dx':90,'dy':90},100))
        self.assertEqual(self.backend.record['rect'][:2],[82,82])

    def test_explicit_chaos_request_is_applied_and_saved_once_without_changing_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            house = House(Path(directory)/'house.json')
            house.agents['Cody']['used'] = 800
            house.save()
            request = Path(directory)/'window-play-request.json'
            request.write_text(json.dumps({'preset':'chaos'}),encoding='utf-8')
            self.assertTrue(house.apply_window_play_request())
            self.assertFalse(request.exists())
            loaded = House(house.path)
            self.assertEqual(loaded.options['window_scope'],'all')
            self.assertTrue(loaded.options['window_control'])
            self.assertTrue(loaded.options['play_during_activities'])
            self.assertEqual(loaded.options['playfulness'],4)
            self.assertEqual(loaded.agents['Cody']['used'],800)
            self.assertFalse(loaded.apply_window_play_request())

    def test_ambient_numeric_event_logs_are_silent_but_direct_answers_still_work(self):
        line = 'Umm, 1 window switches, 1 windows closed. Wait, I am catching up.'
        self.assertEqual(conversational_speech(line,suppress_events=True),'')
        self.assertEqual(conversational_speech('You have 3 windows open.',suppress_events=False),'You have 3 windows open.')


if __name__=='__main__':
    unittest.main()
