from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from ai import DEFAULT_MODEL, Turn, companion_turn, payload
from behaviour import World
from games import Debate, Mafia
from house import House, CHARACTERS
from poker import Poker
from social import Social, throw_velocity
from window_world import WindowWorld, clean_options, clean_rule


def record(hwnd=1,pid=20,title='A document'):
    return {'hwnd':hwnd,'pid':pid,'started':100,'path':'c:\\apps\\editor.exe','app':'editor.exe',
            'title':title,'class':'Fixture','rect':[100,100,600,500],'work':[0,0,1600,900],
            'state':'normal','foreground':False,'movable':True,'resizable':True}


class Backend:
    def __init__(self):
        self.record = record()
        self.idle = 10
        self.calls = []

    def inspect(self,_hwnd):
        return deepcopy(self.record)

    def idle_seconds(self):
        return self.idle

    def position(self,live,rect):
        self.calls.append(rect)
        self.record['rect'] = list(rect)
        return True


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.options = clean_options({})
        self.backend = Backend()
        self.world = WindowWorld(self.options,self.backend)
        self.world.update([self.backend.record])
        self.key = next(iter(self.world.windows))

    def permit(self,control='nudge'):
        self.options['window_control'] = True
        self.world.overrides[self.key] = clean_rule({'control':control,'distance':48,'size':40,'cooldown':5})
        self.options['window_cooldown'] = 5

    def test_observation_is_separate_from_control_and_contains_no_native_handles(self):
        data = self.world.context()
        raw = json.dumps(data)
        self.assertIn('A document',raw)
        for private in ('hwnd','pid','started','c:\\apps','allowed'):
            self.assertNotIn(private,raw)
        self.assertFalse(self.world.apply({'target':self.key,'dx':10},100))
        self.assertFalse(self.backend.calls)
        self.options['window_awareness'] = False
        self.assertIsNone(self.world.context())

    def test_per_app_policy_and_window_override_privacy_including_closed_events(self):
        self.options['window_rules'][self.backend.record['path']] = clean_rule({'observe':'app'})
        self.assertNotIn('A document',json.dumps(self.world.context()))
        self.world.overrides[self.key] = clean_rule({'observe':'ignore','control':'resize'})
        self.world.update([])
        self.assertNotIn('A document',json.dumps(self.world.context()))
        self.assertFalse(self.world.context()['events'])

    def test_open_focus_close_events_and_handle_reuse_get_new_ids(self):
        second = record(2,21)
        opened = self.world.update([self.backend.record,second])
        self.assertEqual(len(opened),1)
        self.assertEqual(self.world.context()['events'][-1]['event'],'opened')
        second['foreground'] = True
        self.world.update([second])
        self.assertEqual([event['event'] for event in self.world.context()['events']][-2:],['focused','closed'])
        previous = next(iter(self.world.windows))
        second['started'] += 1
        self.world.update([second])
        self.assertNotEqual(next(iter(self.world.windows)),previous)

    def test_nudge_is_bounded_and_rate_limited_and_undo_restores(self):
        self.permit()
        self.assertTrue(self.world.apply({'target':self.key,'dx':9999},100))
        self.assertEqual(self.backend.record['rect'],[124,100,624,500])
        self.assertFalse(self.world.apply({'target':self.key,'dx':-20},101))
        self.assertTrue(self.world.apply({'target':self.key,'dx':-9999},106))
        self.assertEqual(self.backend.record['rect'][0],100)
        self.assertTrue(self.world.undo())
        self.assertEqual(self.backend.record['rect'][0],124)
        self.assertTrue(self.world.undo())
        self.assertEqual(self.backend.record['rect'],[100,100,600,500])

    def test_idle_identity_state_revocation_and_invalid_numbers_block_actions(self):
        self.permit()
        action = {'target':self.key,'dx':12}
        self.backend.idle = 0
        self.assertFalse(self.world.apply(action,100))
        self.backend.idle = 10
        self.backend.record['pid'] = 99
        self.assertFalse(self.world.apply(action,100))
        self.backend.record['pid'] = 20
        self.backend.record['movable'] = False
        self.assertFalse(self.world.apply(action,100))
        self.backend.record['movable'] = True
        for value in (True,float('nan'),float('inf'),'20'):
            self.assertFalse(self.world.apply(dict(action,dx=value),100))
        self.options['window_control'] = False
        self.assertFalse(self.world.apply(action,100))

    def test_resize_requires_permission_and_total_travel_and_size_are_capped(self):
        self.permit('move')
        self.assertFalse(self.world.apply({'target':self.key,'dw':30},100))
        self.permit('resize')
        self.assertTrue(self.world.apply({'target':self.key,'dx':1000,'dw':1000},100))
        self.assertEqual(self.backend.record['rect'],[148,100,688,500])
        self.assertFalse(self.world.apply({'target':self.key,'dx':1000,'dw':1000},106),'Repeated play cannot accumulate beyond the anchor limits')
        self.backend.record['rect'] = [700,100,1240,500]
        self.assertTrue(self.world.apply({'target':self.key,'dx':10},112))
        self.assertEqual(self.backend.record['rect'][0],710,'A user-moved window must not jump back to its old anchor')

    def test_global_rate_limit_applies_across_windows(self):
        self.permit()
        self.options['window_actions_per_minute'] = 1
        self.assertTrue(self.world.apply({'target':self.key,'dx':10},100))
        self.assertFalse(self.world.apply({'target':self.key,'dx':10},110))
        self.assertTrue(self.world.apply({'target':self.key,'dx':-10},161))

    def test_small_window_resize_never_exceeds_zero_size_permission(self):
        self.backend.record['rect'] = [100,100,280,220]
        self.world.update([self.backend.record])
        self.permit('resize')
        self.world.overrides[self.key]['size'] = 0
        self.assertFalse(self.world.apply({'target':self.key,'dw':1,'dh':1},100))
        self.assertFalse(self.backend.calls)

    def test_stale_metadata_is_not_sent_to_models(self):
        self.world.last_update -= 11
        self.assertIsNone(self.world.context())

    def test_context_is_bounded_and_excluded_from_games_and_movies(self):
        self.world.update([record(i,i+20) for i in range(1,51)])
        context = self.world.context()
        self.assertEqual(len(context['windows']),20)
        self.assertEqual(context['total_visible'],50)
        for game,movie in [(None,False),({'game':'Poker'},False),(None,True)]:
            body = payload(DEFAULT_MODEL,'Mika',[],[],[],'Hello',game=game,movie=movie,windows=context)
            sent = json.loads(body['contents'][0]['parts'][0]['text'])
            self.assertEqual('desktop_windows' in sent,not game and not movie)


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.world = World(['Burt','Mika'],(0,0,1200,800),(100,100),rng=random.Random(3))
        for i,name in enumerate(self.world.residents):
            resident = self.world.residents[name]
            resident.x,resident.y,resident.mode = 200+i*300,100,'idle'

    def test_throw_gravity_bounce_and_eventual_rest_stay_in_bounds(self):
        self.world.throw('Burt',1300,-600,0)
        resident = self.world.residents['Burt']
        initial_y = resident.y
        self.world.step(.02,.02,False)
        self.assertLess(resident.y,initial_y)
        for n in range(1,1500):
            self.world.step(.02,n*.02,False)
            self.assertEqual((resident.x,resident.y),self.world.constrain(resident.x,resident.y))
        self.assertEqual(resident.mode,'idle')
        self.assertEqual((resident.vx,resident.vy),(0,0))

    def test_collision_transfers_momentum_and_separates_balls(self):
        a,b = self.world.residents.values()
        a.x,b.x = 200,250
        a.vx,b.vx = 400,0
        self.world.collide(1)
        self.assertGreater(b.vx,0)
        self.assertAlmostEqual(a.vx+b.vx,400)
        self.assertAlmostEqual(b.x-a.x,59)

    def test_fast_opposing_throws_do_not_tunnel_through_each_other(self):
        a,b = self.world.residents.values()
        a.x,b.x = 200,300
        self.world.throw('Burt',1400,0,0)
        self.world.throw('Mika',-1400,0,0)
        self.world.step(.1,.1,False)
        self.assertLess(a.x,b.x)
        self.assertLess(a.vx,0)
        self.assertGreater(b.vx,0)

    def test_frozen_or_disabled_physics_do_not_throw(self):
        self.world.freeze(True)
        self.world.throw('Burt',300,-500,0)
        self.assertEqual(self.world.residents['Burt'].mode,'idle')
        self.world.freeze(False)
        self.world.physics_enabled = False
        self.world.throw('Burt',300,-500,0)
        self.assertEqual(self.world.residents['Burt'].mode,'idle')

    def test_drag_velocity_uses_recent_motion_and_caps_speed(self):
        self.assertEqual(throw_velocity([(0,0,0),(.1,200,0)],1),(0,0))
        vx,vy = throw_velocity([(0,0,0),(.1,300,-400)],.1)
        self.assertAlmostEqual((vx*vx+vy*vy)**.5,1400)

    def test_scuffle_cooldown_and_mode_controls(self):
        options = clean_options({})
        social = Social(['Burt','Mika'],options)
        turn = Turn(emotion='angry',social_action={'kind':'scuffle','target':'Mika'})
        self.assertIsNone(social.react('Burt',turn,self.world,['Burt','Mika'],1,allowed=False))
        self.assertIsNotNone(social.react('Burt',turn,self.world,['Burt','Mika'],2))
        self.assertEqual(set(social.scuffles),{'Burt','Mika'})
        self.assertIsNone(social.react('Burt',turn,self.world,['Burt','Mika'],3))
        social.tick(self.world,9)
        self.assertFalse(social.scuffles)


class ActivityTests(unittest.TestCase):
    def test_game_usage_bypasses_spent_chat_allowance_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            house = House(Path(directory)/'house.json')
            house.agents['Burt']['used'] = 20000
            self.assertTrue(house.wake('Burt',ignore_limit=True))
            self.assertIsNone(house.reserve('Burt',unlimited=True))
            interrupted = House(house.path)
            self.assertTrue(interrupted.warning)
            self.assertEqual(interrupted.agents['Burt']['used'],20000)
            house.settle('Burt',50000,unlimited=True)
            self.assertTrue(house.agents['Burt']['awake'])
            self.assertEqual(house.agents['Burt']['used'],20000)
            house.save()
            self.assertEqual(House(house.path).agents['Burt']['game_used'],50000)

    def test_unlimited_model_turn_can_exceed_normal_local_allowance(self):
        response = {'usageMetadata':{'totalTokenCount':50100},'candidates':[{'content':{'parts':[{'text':'{"speech":"I call.","poker_action":"call"}'}]}}]}
        with patch('ai.post',side_effect=[{'totalTokens':50000},response]):
            turn = companion_turn('fixture',DEFAULT_MODEL,'Burt',[],[],[],'Play',None)
        self.assertEqual(turn.used,50100)
        self.assertFalse(turn.exhausted)
        self.assertFalse(turn.error)

    def test_four_housemates_play_five_seat_games_and_debate(self):
        players = ['You',*CHARACTERS]
        self.assertEqual(len(players),5)
        poker = Poker(players,rng=random.Random(4))
        while not poker.result:
            poker.act(poker.actor,'check' if 'check' in poker.legal_actions(poker.actor) else 'call')
        self.assertEqual(sum(poker.stacks.values()),5000)
        mafia = Mafia(players,random.Random(4))
        self.assertEqual(len(mafia.alive),5)
        debate = Debate(players,'Should the house have a garden?',rounds=2)
        with self.assertRaises(ValueError):
            debate.act('Mika','Out of turn')
        for _ in range(10):
            debate.act(debate.actor,'One reason.')
        self.assertTrue(debate.result)
        self.assertIsNone(debate.actor)

    def test_preferences_validation_and_factory_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            house = House(Path(directory)/'house.json')
            house.options.update(clean_options({'window_control':True,'gravity':float('nan'),'bounce':20}))
            house.save()
            loaded = House(house.path)
            self.assertEqual(loaded.options['gravity'],900)
            self.assertEqual(loaded.options['bounce'],.9)
            self.assertTrue(loaded.options['window_control'])
            loaded.reset()
            self.assertFalse(loaded.options['window_control'])


if __name__ == '__main__':
    unittest.main()
