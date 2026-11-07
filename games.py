"""Authoritative local game rules. Model output never bypasses them."""
import random

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


class TicTacToe:
    kind = "Tic-tac-toe"

    def __init__(self, first, second):
        if first == second:
            raise ValueError("Choose two different players")
        self.players = [first, second]
        self.board = [""] * 9
        self.turn = first
        self.result = ""

    @property
    def actor(self):
        return None if self.result else self.turn

    def move(self, actor, cell):
        if self.result or actor != self.turn or type(cell) is not int or cell not in range(9) or self.board[cell]:
            raise ValueError("Not a legal move")
        mark = "X" if actor == self.players[0] else "O"
        self.board[cell] = mark
        if any(all(self.board[cell] == mark for cell in line) for line in LINES):
            self.result = actor + " wins!"
        elif all(self.board):
            self.result = "It's a draw!"
        else:
            self.turn = self.players[1] if actor == self.players[0] else self.players[0]

    def view(self, _actor):
        return {"game": self.kind, "players": self.players, "board": self.board,
                "turn": self.actor, "legal_cells": [i for i, cell in enumerate(self.board) if not cell],
                "result": self.result, "rule": "Cells 0-8, row-major. Your response move must be a legal cell on your turn."}


class Mafia:
    kind = "Mafia"

    def __init__(self, players, rng=None):
        if len(players) != 4 or len(set(players)) != 4:
            raise ValueError("Mafia needs you and all three housemates")
        self.players = list(players)
        self.alive = list(players)
        self.mafia = (rng or random).choice(players)
        self.phase = "discussion"
        self.spoken = []
        self.votes = {}
        self.events = ["Day 1: one secret mafia, three townsfolk. Discuss, then everyone votes. Ties spare everyone. At night the mafia eliminates one player."]
        self.result = ""
        self.day = 1

    @property
    def actor(self):
        if self.result:
            return None
        if self.phase == "night":
            return self.mafia
        completed = self.spoken if self.phase == "discussion" else self.votes
        return next((player for player in self.alive if player not in completed), None)

    def _winner(self):
        if self.mafia not in self.alive:
            self.result = "The town wins! The mafia was " + self.mafia + "."
        elif len(self.alive) <= 2:
            self.result = "The mafia wins! It was " + self.mafia + "."
        if self.result:
            self.events.append(self.result)

    def act(self, actor, target=""):
        if self.result or actor != self.actor:
            raise ValueError("It's someone else's turn")
        if self.phase == "discussion":
            self.spoken.append(actor)
            if len(self.spoken) == len(self.alive):
                self.phase = "voting"
                self.events.append("Discussion finished. Vote for someone other than yourself.")
            return
        if target not in self.alive or target == actor:
            raise ValueError("Choose another living player")
        if self.phase == "voting":
            self.votes[actor] = target
            if len(self.votes) == len(self.alive):
                counts = {p: list(self.votes.values()).count(p) for p in self.alive}
                leaders = [p for p, votes in counts.items() if votes == max(counts.values())]
                if len(leaders) == 1:
                    self.alive.remove(leaders[0])
                    self.events.append(leaders[0] + " was voted out.")
                else:
                    self.events.append("A tied vote. Nobody was voted out.")
                self._winner()
                if not self.result:
                    self.phase = "night"
                    self.events.append("Night falls. The mafia chooses in secret.")
        else:
            self.alive.remove(target)
            self.events.append(target + " was eliminated during the night.")
            self._winner()
            if not self.result:
                self.day += 1
                self.phase = "discussion"
                self.spoken = []
                self.votes = {}
                self.events.append(f"Day {self.day}. Time to discuss.")

    def view(self, actor):
        return {"game": self.kind, "alive": list(self.alive), "phase": self.phase,
                "turn": self.actor if self.phase != "night" or actor == self.mafia else "secret night action",
                "your_role": "mafia" if actor == self.mafia else "town",
                "events": self.events[-6:], "votes": dict(self.votes) if self.phase != "night" else {},
                "targets": [p for p in self.alive if p != actor], "result": self.result,
                "rule": "Don't reveal your secret role. In discussion, just speak. When voting/night, put the chosen target in vote. Night speech is private and will not be shown."}
