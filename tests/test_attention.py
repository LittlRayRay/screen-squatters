from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from ai import DEFAULT_MODEL, companion_turn
from attention import Attention, screen_remark, EVENTS
from behaviour import World
from game_social import occasional_refusal
from house import House, CHARACTERS
from poker import Poker
from speech import SpeechLine
from test_desktop_world import Backend, record
from window_world import WindowWorld, clean_options, clean_rule


class AttentionTests(unittest.TestCase):
    def test_every_event_is_covered_and_duplicate_delivery_is_not_repeated(self):
        attention = Attention()
        for kind in EVENTS:
            self.assertTrue(attention.add({'event':kind,'event_id':kind,'source':'browser'}))
            self.assertFalse(attention.add({'event':kind,'event_id':kind,'source':'browser'}))
        heard = []
        while attention.pending:
            events = attention.take()
            for name in CHARACTERS:
                self.assertTrue(screen_remark(name,events,random.Random(2)))
            heard.extend(item['event'] for item in events)
        self.assertEqual(set(heard),EVENTS)

    def test_large_bursts_preserve_counts_without_unbounded_title_storage(self):
        attention = Attention()
        for i in range(1000):
            attention.add({'event':'tab-opened','event_id':str(i),'source':'browser'})
        self.assertLessEqual(len(attention.pending),256)
        count = 0
        while attention.pending:
            for item in attention.take():
                count += sum(item.get('counts',{'tab-opened':1}).values())
        self.assertEqual(count,1000)

    def test_pause_and_permission_revocation_remove_pending_private_reactions(self):
        attention = Attention()
        attention.add({'event':'tab-closed','source':'browser'})
        attention.add({'event':'window-opened','source':'native','title':'PRIVATE'})
        attention.clear('browser')
        self.assertFalse(attention.take(lambda event:event['source']!='native'))

    def test_native_burst_does_not_lose_events_at_the_ai_context_limit(self):
        world = WindowWorld(clean_options({}),Backend())
        world.update([])
        world.update([record(i,i+100) for i in range(60)])
        self.assertEqual(len(world.changes),60)
        self.assertEqual(len(world.events),16)
        self.assertEqual(len({event['event_id'] for event in world.changes}),60)

    def test_hidden_then_shown_windows_keep_their_session_privacy_policy(self):
        backend = Backend()
        world = WindowWorld(clean_options({}),backend)
        world.update([backend.record])
        key = next(iter(world.windows))
        world.overrides[key] = clean_rule({'observe':'ignore'})
        closed = world.native_change('closed',backend.record,10)
        self.assertIsNotNone(closed)
        self.assertIsNone(world.native_change('closed',backend.record,11))
        opened = world.native_change('opened',backend.record,12)
        self.assertEqual(opened['window'],key)
        self.assertIsNone(world.public(key,backend.record))

    def test_direct_player_reply_cannot_be_silently_empty(self):
        response = {'usageMetadata':{'totalTokenCount':150},'candidates':[{'content':{'parts':[{'text':'{"speech":"hmm"}'}]}}]}
        with patch('ai.post',side_effect=[{'totalTokens':100},response]):
            result = companion_turn('fixture',DEFAULT_MODEL,'Cody',[],[],['Cody'],'PLAYER_MESSAGE: Hello?',1000)
        self.assertTrue(result.speech)
        self.assertNotEqual(result.speech,'hmm')

    def test_poker_delivery_is_short_and_fast_without_changing_normal_typing(self):
        text = 'Fine, I call.'
        self.assertLess(SpeechLine(text,0,fast=True).end,SpeechLine(text,0).end/2)


class CharacterTests(unittest.TestCase):
    def test_old_names_and_memory_references_migrate_without_resetting_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'house.json'
            path.write_text(json.dumps({'agents':{
                'Byte':{'used':400,'game_used':900,'memories':[{'from':'Rex','text':'Byte and Rex played with Pip.'}]},
                'Rex':{'used':700,'reserved':100},
                'Burt':{'memories':[{'from':'Byte','text':'Rex helped Byte.'}]}}}),encoding='utf-8')
            house = House(path)
            self.assertEqual(set(house.agents),{'Burt','Cody','Victoria','Mika'})
            self.assertEqual(house.agents['Cody']['used'],400)
            self.assertEqual(house.agents['Cody']['game_used'],900)
            self.assertEqual(house.agents['Victoria']['used'],800)
            note = house.agents['Cody']['memories'][0]
            self.assertEqual(note['from'],'Victoria')
            self.assertEqual(note['text'],'Cody and Victoria played with Burt.')
            house.save()
            self.assertNotIn('Rex',json.loads(path.read_text())['agents'])

    def test_canonical_save_takes_precedence_over_old_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'house.json'
            path.write_text(json.dumps({'agents':{'Cody':{'used':5},'Byte':{'used':99},'Victoria':{'used':9},'Rex':{'used':88}}}))
            house = House(path)
            self.assertEqual(house.agents['Cody']['used'],5)
            self.assertEqual(house.agents['Victoria']['used'],9)

    def test_rotation_returns_upright_after_throw_and_freeze(self):
        world = World(['Burt'],(0,0,1200,800),(100,100),rng=random.Random(3))
        resident = world.residents['Burt']
        resident.mode,resident.x,resident.y = 'idle',300,100
        world.throw('Burt',800,-300,0)
        for i in range(2000):
            world.step(.02,i*.02,False)
        self.assertEqual(resident.mode,'idle')
        self.assertEqual(resident.spin,0)

    def test_wandering_and_natural_rest_do_not_interrupt_a_throw_or_pickup(self):
        world = World(['Burt'],(0,0,1200,800),(100,100))
        resident = world.residents['Burt']
        resident.mode = 'idle'
        world.throw('Burt',500,-200,0)
        world.inspect('Burt',(400,300,'window'),1)
        self.assertEqual(resident.mode,'airborne')
        self.assertFalse(world.due(1000,['Burt'],['Burt']))
        resident.mode,resident.picked_up = 'idle',True
        self.assertFalse(world.due(1000,['Burt'],['Burt']))
        resident.spin = 123
        world.freeze(True)
        self.assertEqual(resident.spin,0)

    def test_eager_local_window_play_still_requires_permission_and_limits(self):
        options = clean_options({})
        backend = Backend()
        world = WindowWorld(options,backend)
        world.update([backend.record])
        self.assertIsNone(world.play('Cody',random.Random(1),100))
        options['window_control'] = True
        key = next(iter(world.windows))
        world.overrides[key] = clean_rule({'control':'nudge'})
        self.assertEqual(world.play('Victoria',random.Random(1),100),key)
        self.assertLessEqual(abs(backend.record['rect'][0]-100),24)
        self.assertIsNone(world.play('Cody',random.Random(2),101))

    def test_spectator_poker_view_contains_only_explicitly_shown_cards(self):
        game = Poker(list(CHARACTERS),rng=random.Random(8))
        view = game.public_view()
        self.assertNotIn('your_cards',view)
        self.assertEqual(view['shown_cards'],{})
        game.reveal('Victoria')
        self.assertEqual(game.public_view()['shown_cards'],{'Victoria':game.hands['Victoria']})

    def test_deliberation_is_rare_and_can_be_disabled(self):
        rng = random.Random(12)
        decisions = [occasional_refusal(['You',*CHARACTERS],'Poker',rng) for _ in range(1000)]
        self.assertTrue(70 < sum(item is not None for item in decisions) < 180)
        self.assertIsNone(occasional_refusal(['You',*CHARACTERS],'Poker',rng,False))


if __name__ == '__main__':
    unittest.main()
