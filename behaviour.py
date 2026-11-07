"""Local movement and daily rhythms. AI may choose interests, never execute input."""
from dataclasses import dataclass
import math
import random


def clamp(value, low, high):
    return max(low, min(high, value))


def unit(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def interest_point(observation, interest):
    """Map a validated viewport target or image point into desktop coordinates."""
    if not isinstance(observation, dict) or not isinstance(interest, dict):
        return None
    bounds = observation.get("bounds")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return None
    if not all(type(n) in (int, float) and math.isfinite(n) for n in bounds):
        return None
    left, top, right, bottom = bounds
    if right <= left or bottom <= top:
        return None
    if observation.get("kind") == "page":
        index = interest.get("target")
        targets = observation.get("targets", [])
        if type(index) is not int or not 0 <= index < len(targets):
            return None
        target = targets[index]
        x, y = target.get("x"), target.get("y")
        if not unit(x) or not unit(y):
            return None
        viewport = observation.get("viewport", {})
        width = viewport.get("width", 1)
        height = viewport.get("height", 1)
        outer_w = viewport.get("outerWidth", width)
        outer_h = viewport.get("outerHeight", height)
        if not all(type(n) in (int, float) and math.isfinite(n) and n > 0 for n in (width, height, outer_w, outer_h)):
            return None
        # Use ratios to account for browser chrome without mixing CSS and desktop DPI.
        x = clamp(((max(0, outer_w-width)/2) + x*width)/outer_w, 0, 1)
        y = clamp((max(0, outer_h-height) + y*height)/outer_h, 0, 1)
        label = str(target.get("label", "something on this page"))[:80]
    else:
        x, y = interest.get("x"), interest.get("y")
        if not unit(x) or not unit(y):
            return None
        label = str(interest.get("label", "something on screen"))[:80]
    return (left+x*(right-left), top+y*(bottom-top), label)


@dataclass
class Resident:
    x: float
    y: float
    mode: str = "home"
    goal: tuple = None
    gaze: tuple = None
    interest: tuple = None
    interest_until: float = 0
    next_wander: float = 0
    rest_at: float = 0
    wake_at: float = 0
    blocked: bool = False
    held_until: float = 0
    pending_speech: str = ""
    wake_threshold: int = 1000


class World:
    width, height = 190, 230

    def __init__(self, names, bounds, home, now=0, rng=None):
        self.rng = rng or random.Random()
        self.bounds = bounds
        self.home = home
        self.paused = False
        self.movement_enabled = True
        self.movie_enabled = False
        self.movie_corner = "bottom-left"
        self.residents = {name: Resident(*self.home, wake_at=now+self.rng.uniform(45, 120)) for name in names}

    def constrain(self, x, y):
        left, top, right, bottom = self.bounds
        return clamp(x, left, max(left, right-self.width)), clamp(y, top, max(top, bottom-self.height))

    def destination(self):
        left, top, right, bottom = self.bounds
        return self.constrain(self.rng.uniform(left, max(left, right-self.width)),
                              self.rng.uniform(top+50, max(top+50, bottom-self.height)))

    def wake(self, name, now):
        resident = self.residents[name]
        if resident.mode == "home":
            resident.x, resident.y = self.constrain(*self.home)
        resident.mode = "walking"
        resident.goal = self.destination()
        resident.rest_at = now+self.rng.uniform(240, 480)
        resident.next_wander = now+self.rng.uniform(10, 25)
        resident.pending_speech = ""
        resident.gaze = resident.interest = None
        if self.movie_enabled:
            self.seat(name, now, immediate=not self.movement_enabled)
        elif not self.movement_enabled:
            resident.mode, resident.goal = "idle", None

    def rest(self, name, now, immediate=False):
        resident = self.residents[name]
        resident.mode = "home" if immediate or not self.movement_enabled or resident.mode == "home" else "returning"
        resident.goal = self.constrain(*self.home)
        resident.wake_at = now+self.rng.uniform(90, 210)
        resident.gaze = resident.interest = None
        resident.pending_speech = ""
        resident.held_until = 0

    def freeze(self, enabled):
        self.movement_enabled = not enabled
        if not enabled:
            return
        for resident in self.residents.values():
            resident.gaze = resident.interest = None
            resident.goal = None
            if resident.mode == "returning":
                resident.mode = "home"
            elif resident.mode == "settling":
                resident.mode = "seated"
            elif resident.mode not in {"home", "seated"}:
                resident.mode = "idle"

    def seat_goal(self, name):
        names = list(self.residents)
        left, top, right, bottom = self.bounds
        span = self.width + (len(names)-1)*125
        start = left+16 if self.movie_corner.endswith("left") else right-span-16
        y = top+16 if self.movie_corner.startswith("top") else bottom-self.height-16
        return self.constrain(start+names.index(name)*125, y)

    def seat(self, name, now, immediate=False):
        resident = self.residents[name]
        resident.goal = self.seat_goal(name)
        resident.mode = "seated" if immediate else "settling"
        if immediate:
            resident.x, resident.y = resident.goal
        resident.gaze = ((self.bounds[0]+self.bounds[2])/2, (self.bounds[1]+self.bounds[3])/2)
        resident.interest = None
        resident.held_until = 0
        resident.next_wander = now+60

    def end_movie(self, now):
        self.movie_enabled = False
        for resident in self.residents.values():
            if resident.mode in {"seated", "settling"}:
                resident.mode, resident.goal, resident.gaze = "idle", None, None
                resident.pending_speech = ""
                resident.next_wander = now+15
                resident.rest_at = now+self.rng.uniform(240, 480)

    def inspect(self, name, point, now, speech=""):
        resident = self.residents[name]
        if not self.movement_enabled or self.movie_enabled or resident.mode in {"home", "returning"}:
            return
        x, y, label = point
        # Stand beside a target, leaving the object itself uncovered.
        stand_x = x+42 if x < (self.bounds[0]+self.bounds[2])/2 else x-self.width-42
        resident.goal = self.constrain(stand_x, y-165)
        resident.mode = "approaching"
        resident.gaze = (x, y)
        resident.interest = (x, y, label)
        resident.interest_until = now+25
        resident.pending_speech = speech
        resident.next_wander = now+35

    def due(self, now, awake, eligible, busy=(), playing=False):
        if self.paused or playing or self.movie_enabled:
            return []
        events = []
        for name, resident in self.residents.items():
            if name in awake and name not in busy and now >= resident.rest_at:
                events.append(("sleep", name))
            elif name not in awake and resident.mode == "home" and name in eligible and not resident.blocked and now >= resident.wake_at:
                events.append(("wake", name))
        return events

    def step(self, dt, now, autonomous=True):
        arrived = []
        dt = clamp(dt, 0, .15)
        for name, resident in self.residents.items():
            if resident.mode == "home" or now < resident.held_until:
                continue
            if resident.mode == "idle" and self.movement_enabled and autonomous and not self.paused and not self.movie_enabled and now >= resident.next_wander:
                resident.goal, resident.mode = self.destination(), "walking"
                resident.next_wander = now+self.rng.uniform(20, 45)
            if resident.mode == "interested" and now >= resident.interest_until:
                resident.mode, resident.interest, resident.gaze = "idle", None, None
            if not self.movement_enabled or resident.mode not in {"walking", "returning", "approaching", "settling"} or not resident.goal:
                continue
            if not autonomous and resident.mode not in {"returning", "settling"}:
                continue
            dx, dy = resident.goal[0]-resident.x, resident.goal[1]-resident.y
            distance = math.hypot(dx, dy)
            speed = 240 if resident.mode in {"returning", "settling"} else 180 if resident.mode == "approaching" else 65
            if distance <= max(2, speed*dt):
                resident.x, resident.y = resident.goal
                resident.mode = {"returning": "home", "approaching": "interested", "settling": "seated"}.get(resident.mode, "idle")
                if resident.mode == "interested":
                    resident.interest_until = now+18
                arrived.append(name)
            else:
                resident.x, resident.y = self.constrain(resident.x+dx/distance*speed*dt, resident.y+dy/distance*speed*dt)
        return arrived
