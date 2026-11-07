from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import DEFAULT_MODEL, payload
from behaviour import World
from cinema import movie_command
from house import House


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.house = House(Path(self.temporary.name)/'house.json')
        self.house.agents['Pip']['used'] = 1000

    def test_sleep_reduces_used_tokens_without_changing_limit(self):
        self.house.sleep_recovery_rate = 600
        self.assertEqual(self.house.recover_sleep(10, {'Pip'}), {'Pip': 100})
        self.assertEqual(self.house.agents['Pip']['used'], 900)
        self.assertEqual(self.house.agents['Pip']['limit'], 20000)

    def test_fractional_ticks_accumulate_smoothly(self):
        self.house.sleep_recovery_rate = 3
        self.house.recover_sleep(10, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 1000)
        self.house.recover_sleep(10, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 999)

    def test_recovery_never_affects_awake_or_pending_agents(self):
        self.house.wake('Pip')
        self.house.recover_sleep(60, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 1000)
        self.house.sleep('Pip')
        self.house.reserve('Pip')
        self.house.recover_sleep(60, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 1000)
        self.assertEqual(self.house.remaining('Pip'), 0)

    def test_zero_rate_pauses_and_large_rate_stops_at_zero(self):
        self.house.sleep_recovery_rate = 0
        self.house.recover_sleep(600, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 1000)
        self.house.sleep_recovery_rate = 6000
        self.house.recover_sleep(60, {'Pip'})
        self.assertEqual(self.house.agents['Pip']['used'], 0)
        self.assertEqual(self.house.remaining('Pip'), 20000)

    def test_recovery_rate_motion_and_corner_preferences_persist(self):
        self.house.sleep_recovery_rate = 250
        self.house.stand_still = True
        self.house.movie_corner = 'top-right'
        self.house.save()
        restored = House(self.house.path)
        self.assertEqual(restored.sleep_recovery_rate, 250)
        self.assertTrue(restored.stand_still)
        self.assertEqual(restored.movie_corner, 'top-right')
        restored.reset()
        self.assertEqual(restored.sleep_recovery_rate, 1000)
        self.assertFalse(restored.stand_still)


class MovieTests(unittest.TestCase):
    def setUp(self):
        self.world = World(['Pip','Byte','Rex'], (0,0,1600,900), (1200,600), rng=random.Random(1))

    def test_normal_invites_and_menu_style_commands(self):
        for text in ("Everybody watch something with me", "Let's watch a movie", 'Can we watch this?', 'Movie mode', 'Start movie mode'):
            self.assertEqual(movie_command(text), 'start', text)
        for text in ('Stop movie mode', "We're done watching", 'Turn movie mode off', 'End the watch party'):
            self.assertEqual(movie_command(text), 'stop', text)
        for text in ('What is movie mode?', "I don't want to watch a movie", "Let's not watch anything", "Don't stop movie mode", "Let's watch out for that", 'Tell me about the movie'):
            self.assertIsNone(movie_command(text), text)

    def test_frozen_characters_do_not_translate_and_still_go_home(self):
        self.world.wake('Pip', 0)
        self.world.step(.1, .1)
        self.world.freeze(True)
        resident = self.world.residents['Pip']
        at = resident.x, resident.y
        for tick in range(100):
            self.world.step(.1, tick)
        self.assertEqual((resident.x,resident.y), at)
        self.world.inspect('Pip', (500,500,'test'), 100)
        self.assertEqual(resident.mode, 'idle')
        self.world.rest('Pip', 101)
        self.assertEqual(resident.mode, 'home')

    def test_movie_seats_are_distinct_and_reached_without_wandering(self):
        self.world.movie_enabled = True
        for name in self.world.residents:
            self.world.wake(name, 0)
        for tick in range(180):
            self.world.step(.1, tick*.1)
        self.assertTrue(all(r.mode == 'seated' for r in self.world.residents.values()))
        positions = [(r.x,r.y) for r in self.world.residents.values()]
        self.assertEqual(len(set(positions)), 3)
        for tick in range(500):
            self.world.step(.1, 100+tick*.1)
        self.assertEqual(positions, [(r.x,r.y) for r in self.world.residents.values()])
        self.assertEqual(self.world.due(10000, list(self.world.residents), list(self.world.residents)), [])

    def test_movie_seating_is_an_explicit_rearrangement_even_when_frozen(self):
        self.world.freeze(True)
        self.world.movie_enabled = True
        self.world.wake('Pip', 0)
        self.assertEqual(self.world.residents['Pip'].mode, 'seated')
        for corner in ('bottom-left','bottom-right','top-left','top-right'):
            self.world.movie_corner = corner
            self.world.seat('Pip', 0, immediate=True)
            resident = self.world.residents['Pip']
            self.assertTrue(0 <= resident.x <= 1410)
            self.assertTrue(0 <= resident.y <= 670)

    def test_ending_movie_restores_normal_body_state(self):
        self.world.movie_enabled = True
        self.world.wake('Pip', 0)
        self.world.seat('Pip', 0, immediate=True)
        self.world.end_movie(10)
        self.assertFalse(self.world.movie_enabled)
        self.assertEqual(self.world.residents['Pip'].mode, 'idle')

    def test_movie_prompts_focus_on_movie_without_claiming_audio(self):
        body = payload(DEFAULT_MODEL, 'Pip', [], [], ['Pip'], 'Watch', movie=True)
        instructions = body['systemInstruction']['parts'][0]['text']
        self.assertIn('MOVIE MODE overrides', instructions)
        self.assertIn('Never pretend to hear', instructions)
        self.assertIn('empty speech string', instructions)
        self.assertIn('"mode": "movie"', body['contents'][0]['parts'][0]['text'])
        normal = payload(DEFAULT_MODEL, 'Pip', [], [], ['Pip'], 'Hi')
        self.assertNotIn('MOVIE MODE overrides', normal['systemInstruction']['parts'][0]['text'])


if __name__ == '__main__':
    unittest.main()
