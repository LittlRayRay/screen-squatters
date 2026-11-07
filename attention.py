"""Quiet screen-change context. Never generates status-log dialogue."""
from collections import deque
import time

EVENTS = {'tab-opened','tab-closed','tab-switched','page-changed','window-opened','window-closed','window-switched'}


class Attention:
    def __init__(self):
        self.pending = deque(maxlen=32)
        self.seen = deque(maxlen=2048)
        self.last_spoken = 0
        self.last_considered = 0

    def add(self,event,now=None):
        if event.get('event') not in EVENTS:
            return False
        key = event.get('event_id')
        if key and key in self.seen:
            return False
        if key:
            self.seen.append(key)
        self.pending.append(dict(event,time=time.monotonic() if now is None else now))
        return True

    def clear(self,source=None):
        self.pending = deque((item for item in self.pending if source and item.get('source') != source),maxlen=32)

    def take(self,allowed=lambda event:True,maximum=4):
        events = []
        while self.pending and len(events)<maximum:
            item = self.pending.popleft()
            if allowed(item):
                events.append(item)
        return events

    def occasional(self,now,rng,allowed=lambda event:True):
        recent = [item for item in self.pending if now-item['time']<=20 and allowed(item)]
        self.pending.clear()
        if not recent or now-self.last_considered<90:
            return None
        self.last_considered = now
        if rng.random()>=.25:
            return None
        # Ignore short-lived shell/pop-up windows that both appeared and disappeared.
        opened = {item.get('window') for item in recent if item['event']=='window-opened'}
        closed = {item.get('window') for item in recent if item['event']=='window-closed'}
        transient = (opened & closed)-{None}
        recent = [item for item in recent if item.get('window') not in transient and not item.get('counts')]
        if not recent:
            return None
        item = recent[-1]
        self.last_spoken = now
        return {key:item.get(key,'') for key in ('event','app','title','url')}
