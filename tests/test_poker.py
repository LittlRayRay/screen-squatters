import json
import random
import unittest
from unittest.mock import patch

from ai import DEFAULT_MODEL, companion_turn
from poker import Poker, best_hand, hand_rank
from speech import SpeechLine, conversational_speech

PLAYERS = ['You','Burt','Cody','Victoria']


class PokerTests(unittest.TestCase):
    def test_every_hand_category_and_kickers(self):
        examples = ['2C 4D 7H 9S JC','2C 2D 7H 9S JC','2C 2D 7H 7S JC',
                    '2C 2D 2H 9S JC','2C 3D 4H 5S 6C','2C 4C 7C 9C JC',
                    '2C 2D 2H 9S 9C','2C 2D 2H 2S JC','2C 3C 4C 5C 6C']
        ranks = [hand_rank(cards.split()) for cards in examples]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual([rank[0] for rank in ranks], list(range(9)))
        self.assertLess(hand_rank('AC 2D 3S 4H 5C'.split()),hand_rank('2C 3D 4S 5H 6C'.split()))
        self.assertLess(hand_rank('AC AD 3S 4H JC'.split()),hand_rank('AS AH 3D 4C QC'.split()))
        self.assertEqual(best_hand('AC AD AH 2C 2D 2H KS'.split()),(6,14,2))
        self.assertEqual(best_hand('AC KC QC JC TC 9C 8C'.split()),(8,14))

    def test_blinds_turn_order_and_illegal_action_is_atomic(self):
        game = Poker(PLAYERS,rng=random.Random(1))
        self.assertEqual(game.pot,15)
        self.assertEqual(game.actor,'Victoria')
        before = json.dumps(game.view('You'))
        with self.assertRaises(ValueError):
            game.act('You','raise')
        self.assertEqual(before,json.dumps(game.view('You')))
        with self.assertRaises(ValueError):
            game.act('Victoria','check')
        game.act('Victoria','call')
        game.act('You','call')
        game.act('Burt','call')
        self.assertEqual(game.actor,'Cody','Big blind retains the option to raise')
        game.act('Cody','check')
        self.assertEqual(game.phase,'flop')
        self.assertEqual(len(game.board),3)
        self.assertEqual(game.actor,'Burt')
        self.assertEqual(game.pot,40)

    def test_raise_cap_and_players_must_respond_again(self):
        game = Poker(PLAYERS)
        game.act('Victoria','raise')
        game.act('You','raise')
        game.act('Burt','raise')
        self.assertNotIn('raise',game.legal_actions('Cody'))
        for player in ['Cody','Victoria','You']:
            self.assertEqual(game.actor,player)
            game.act(player,'call')
        self.assertEqual(game.phase,'flop')
        self.assertEqual(game.pot,160)
        self.assertIn('raise',game.legal_actions('Burt'))

    def test_fold_win_and_optional_reveal_including_after_finish(self):
        game = Poker(PLAYERS)
        for player in ['Victoria','You','Burt']:
            game.act(player,'fold')
        self.assertIn('Cody wins',game.result)
        self.assertEqual(game.stacks['Cody'],1005)
        self.assertIsNone(game.actor)
        self.assertEqual(game.view('You')['shown_cards'],{})
        game.reveal('Victoria')
        self.assertEqual(game.view('You')['shown_cards']['Victoria'],game.hands['Victoria'])
        with self.assertRaises(ValueError):
            game.act('Cody','check')

    def test_private_views_and_reveal_after_action(self):
        game = Poker(PLAYERS,rng=random.Random(8))
        for player in PLAYERS:
            view = game.view(player)
            self.assertEqual(view['your_cards'],game.hands[player])
            self.assertEqual(view['shown_cards'],{})
            raw = json.dumps(view)
            for other in PLAYERS:
                if other != player:
                    for card in game.hands[other]:
                        self.assertNotIn('"'+card+'"',raw)
        game.act('Victoria','call',reveal=True)
        self.assertEqual(game.view('Burt')['shown_cards'],{'Victoria':game.hands['Victoria']})
        game.view('You')['your_cards'].clear()
        self.assertEqual(len(game.hands['You']),2)

    def test_split_pot_and_no_compulsory_disclosure(self):
        game = Poker(PLAYERS)
        while game.phase != 'river':
            game.act(game.actor,'check' if 'check' in game.legal_actions(game.actor) else 'call')
        game.board = ['TS','JS','QS','KS','AS']
        game.hands = dict(zip(PLAYERS,[['2C','3C'],['4C','5C'],['6C','7C'],['8C','9C']]))
        while not game.result:
            game.act(game.actor,'check')
        self.assertTrue(all(stack == 1000 for stack in game.stacks.values()))
        self.assertIn('splits',game.result)
        self.assertEqual(game.view('You')['shown_cards'],{})

    def test_many_random_hands_terminate_and_conserve_chips(self):
        rng = random.Random(42)
        for n in range(300):
            game = Poker(PLAYERS,rng=rng,dealer=n)
            cards = game.deck + [card for hand in game.hands.values() for card in hand]
            self.assertEqual(len(set(cards)),52)
            turns = 0
            while not game.result:
                legal = game.legal_actions(game.actor)
                game.act(game.actor,rng.choice(legal),reveal=rng.random()<.1)
                self.assertEqual(sum(game.stacks.values())+game.pot,4000)
                self.assertTrue(all(stack >= 0 for stack in game.stacks.values()))
                turns += 1
                self.assertLess(turns,100)
            self.assertEqual(sum(game.stacks.values()),4000)

    def test_ai_poker_action_and_strict_reveal_boolean(self):
        for reveal, expected in [(True,True),('false',False),(False,False)]:
            reply = {'usageMetadata':{'totalTokenCount':180},'candidates':[{'content':{'parts':[{'text':json.dumps(
                {'speech':'I am calling.','poker_action':'call','reveal_cards':reveal})}]}}]}
            with patch('ai.post',side_effect=[{'totalTokens':100},reply]):
                result = companion_turn('test',DEFAULT_MODEL,'Victoria',[],[],PLAYERS,'Play',1000,game=Poker(PLAYERS).view('Victoria'))
            self.assertEqual(result.poker_action,'call')
            self.assertEqual(result.reveal_cards,expected)


class SpeechTests(unittest.TestCase):
    def test_typing_then_incremental_delivery_with_punctuation_pause(self):
        line = SpeechLine('Wait, what? Okay.',10)
        self.assertTrue(line.typing(10.3))
        self.assertEqual(line.visible(10.3),'')
        partial = line.visible(11)
        self.assertTrue(0 < len(partial) < len(line.text))
        self.assertEqual(line.visible(line.end),line.text)
        self.assertFalse(line.speaking(line.end))
        comma = line.text.index(',')
        self.assertGreater(line.times[comma+1]-line.times[comma],.13)

    def test_long_lines_paginate_without_disappearing_or_losing_final_text(self):
        line = SpeechLine(('Here are some ordinary words. '*20)+'Finished.',0)
        for now in [1,3,6,10,line.end]:
            page = line.page(now)
            self.assertLessEqual(len(page),96)
            self.assertIn(page,line.text)
        self.assertTrue(line.page(line.end).endswith('Finished.'))

    def test_filler_is_silent_but_real_hesitant_speech_is_kept(self):
        for text in ['hmm','Hmm…','umm, uhh...','Ahh!']:
            self.assertEqual(conversational_speech(text),'')
        text = 'Umm, wait, are we starting?'
        self.assertEqual(conversational_speech(text),text)


if __name__ == '__main__':
    unittest.main()
