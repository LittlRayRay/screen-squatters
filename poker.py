"""Friendly fixed-limit Texas hold'em. Hidden cards never enter another player's view."""
from collections import Counter
from itertools import combinations
import random


def hand_rank(cards):
    """Comparable five-card rank, including ace-low straights and all kickers."""
    values = sorted(('23456789TJQKA'.index(card[0])+2 for card in cards), reverse=True)
    counts = Counter(values)
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    unique = sorted(counts, reverse=True)
    straight = 5 if unique == [14, 5, 4, 3, 2] else unique[0] if len(unique) == 5 and unique[0]-unique[-1] == 4 else 0
    flush = len({card[1] for card in cards}) == 1
    if straight and flush:
        return (8, straight)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if [g[0] for g in groups] == [3, 2]:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *values)
    if straight:
        return (4, straight)
    if groups[0][0] == 3:
        return (3, groups[0][1], *sorted((v for v in values if v != groups[0][1]), reverse=True))
    if [g[0] for g in groups[:2]] == [2, 2]:
        return (2, *sorted((groups[0][1], groups[1][1]), reverse=True), groups[2][1])
    if groups[0][0] == 2:
        return (1, groups[0][1], *sorted((v for v in values if v != groups[0][1]), reverse=True))
    return (0, *values)


def best_hand(cards):
    return max(hand_rank(hand) for hand in combinations(cards, 5))


class Poker:
    kind = 'Poker'

    def __init__(self, players, rng=None, dealer=0):
        if len(players) != 4 or len(set(players)) != 4:
            raise ValueError('Poker needs you and all three housemates')
        self.players = list(players)
        self.dealer = dealer % 4
        self.deck = [rank+suit for rank in '23456789TJQKA' for suit in 'CDHS']
        (rng or random.SystemRandom()).shuffle(self.deck)
        self.hands = {p: [] for p in players}
        for _ in range(2):
            for p in self.clockwise(self.dealer):
                self.hands[p].append(self.deck.pop())
        self.board = []
        self.active = list(players)
        self.revealed = set()
        self.stacks = {p: 1000 for p in players}
        self.bets = {p: 0 for p in players}
        self.pot = 0
        self.awarded_pot = 0
        self.phase = 'preflop'
        self.result = ''
        self.raises = 0
        self.current_bet = 10
        small, big = self.clockwise(self.dealer)[:2]
        self.pay(small, 5)
        self.pay(big, 10)
        self.events = [f'{small} posts 5; {big} posts 10.']
        self.pending = self.clockwise(self.players.index(big))

    def clockwise(self, after):
        return [self.players[(after+i) % 4] for i in range(1, 5)]

    @property
    def actor(self):
        return self.pending[0] if self.pending and not self.result else None

    @property
    def increment(self):
        return 20 if self.phase in ('turn', 'river') else 10

    def pay(self, player, amount):
        if amount > self.stacks[player]:
            raise ValueError('Insufficient chips')
        self.stacks[player] -= amount
        self.bets[player] += amount
        self.pot += amount

    def legal_actions(self, player):
        if player != self.actor:
            return []
        due = self.current_bet-self.bets[player]
        actions = ['fold', 'call' if due else 'check']
        if self.raises < 3 and self.stacks[player] >= due+self.increment:
            actions.append('raise')
        return actions

    def reveal(self, player):
        if player not in self.players:
            raise ValueError('Unknown player')
        if player not in self.revealed:
            self.revealed.add(player)
            self.events.append(player+' shows '+', '.join(self.hands[player])+'.')

    def act(self, player, action, reveal=False):
        if action not in self.legal_actions(player):
            raise ValueError('Not a legal poker action')
        self.pending.pop(0)
        due = self.current_bet-self.bets[player]
        if action == 'fold':
            self.active.remove(player)
            self.events.append(player+' folds.')
        elif action == 'check':
            self.events.append(player+' checks.')
        elif action == 'call':
            self.pay(player, due)
            self.events.append(f'{player} calls {due}.')
        else:
            self.pay(player, due+self.increment)
            if self.current_bet:
                self.raises += 1
            self.current_bet += self.increment
            self.events.append(f'{player} bets to {self.current_bet}.')
            self.pending = [p for p in self.clockwise(self.players.index(player)) if p in self.active and p != player]
        if reveal:
            self.reveal(player)
        if len(self.active) == 1:
            self.finish(self.active)
        elif not self.pending:
            self.next_street()

    def next_street(self):
        if self.phase == 'river':
            ranks = {p: best_hand(self.hands[p]+self.board) for p in self.active}
            top = max(ranks.values())
            self.finish([p for p, rank in ranks.items() if rank == top])
            return
        self.deck.pop()  # Burn a card before each community-card deal.
        count = 3 if self.phase == 'preflop' else 1
        self.board.extend(self.deck.pop() for _ in range(count))
        self.phase = {'preflop':'flop', 'flop':'turn', 'turn':'river'}[self.phase]
        self.bets = {p: 0 for p in self.players}
        self.current_bet = self.raises = 0
        self.pending = [p for p in self.clockwise(self.dealer) if p in self.active]
        self.events.append(self.phase.title()+': '+', '.join(self.board)+'.')

    def finish(self, winners):
        self.awarded_pot = self.pot
        share, odd = divmod(self.pot, len(winners))
        ordered = [p for p in self.clockwise(self.dealer) if p in winners]
        for i, player in enumerate(ordered):
            self.stacks[player] += share + (i < odd)
        self.pot = 0
        self.result = ', '.join(ordered)+(' splits' if len(ordered) > 1 else ' wins')+f' the {self.awarded_pot}-chip pot!'
        self.phase = 'finished'
        self.pending = []
        self.events.append(self.result)

    def view(self, player):
        if player not in self.players:
            raise ValueError('Unknown player')
        return {'game': self.kind, 'variant': 'Fixed-limit Texas hold\'em', 'players': list(self.players),
                'phase': self.phase, 'turn': self.actor, 'your_cards': list(self.hands[player]),
                'shown_cards': {p: list(self.hands[p]) for p in self.players if p in self.revealed},
                'board': list(self.board), 'folded': [p for p in self.players if p not in self.active],
                'chips': dict(self.stacks), 'street_bets': dict(self.bets), 'pot': self.pot,
                'to_call': max(0, self.current_bet-self.bets[player]), 'bet_increment': self.increment,
                'legal_actions': self.legal_actions(player), 'events': self.events[-10:], 'result': self.result,
                'rule': 'Choose poker_action from legal_actions. raise is a bet if nobody has bet. '
                        'Set reveal_cards true to voluntarily show your two cards after this action, or false to keep them private. '
                        'Never name your private cards in speech unless you choose to reveal them. '
                        'Other unrevealed hands are unknown, including after the winner is computed. '
                        'No real money. Fresh 1,000 chips each hand, blinds 5/10, bets 10 preflop/flop and 20 turn/river, three raises per street. '
                        'The app evaluates winners automatically; voluntary disclosure stays optional even at the end.'}
