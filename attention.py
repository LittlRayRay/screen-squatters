"""Reliable, inexpensive acknowledgements of permitted screen changes."""
from collections import Counter, deque
import random
import time

EVENTS = {'tab-opened','tab-closed','tab-switched','page-changed','window-opened','window-closed','window-switched'}


class Attention:
    def __init__(self):
        self.pending = deque()
        self.seen = deque(maxlen=2048)
        self.serial = 0
        self.last_spoken = 0

    def add(self,event,now=None):
        if event.get('event') not in EVENTS:
            return False
        key = event.get('event_id')
        if key and key in self.seen:
            return False
        if key:
            self.seen.append(key)
        item = dict(event,time=time.monotonic() if now is None else now)
        if item.get('count',1)>1:
            item['counts'] = {item['event']:item['count']}
        self.pending.append(item)
        # Preserve coverage during bursts without an unbounded queue of stale titles.
        if len(self.pending)>256:
            oldest = [self.pending.popleft() for _ in range(128)]
            counts = Counter()
            for item in oldest:
                counts.update(item.get('counts',{item['event']:1}))
            self.pending.appendleft({'event':'tab-opened','counts':dict(counts),'source':'summary','time':time.monotonic()})
        return True

    def clear(self,source=None):
        self.pending = deque(item for item in self.pending if source and item.get('source') != source) if source else deque()

    def take(self,allowed=lambda event:True,maximum=4):
        events = []
        while self.pending and len(events)<maximum:
            item = self.pending.popleft()
            if allowed(item):
                events.append(item)
        return events


SINGLE = {
    'Burt': {
        'tab-opened':['Umm, another tab? Okay, I am following.','Oh, a new tab. Wait, we still have the other one, right?'],
        'tab-closed':['Uhh, that tab went away. Were we finished with it?','Wait, one less tab. I think I noticed that.'],
        'tab-switched':['Umm, different tab. Give me a second to catch up.'],
        'page-changed':['Oh, the page changed. Uhh, what are we looking at now?'],
        'window-opened':['Umm, a new window! Is this part of what we were doing?'],
        'window-closed':['Wait, that window is gone. Okay, uhh, I am still here.'],
        'window-switched':['Umm, over to {app}. I think I am keeping up.']},
    'Cody': {
        'tab-opened':['Ooh, another tab! What have we found?','New tab! I always want to know what is in those.'],
        'tab-closed':['Oh! That tab is gone. One less thing to get distracted by.'],
        'tab-switched':['Ooh, different tab. I am looking too!'],
        'page-changed':['Hey, the page changed! What is this bit?'],
        'window-opened':['Oh, a new window! I was not expecting that.'],
        'window-closed':['Bye, window! Okay, what are we doing next?'],
        'window-switched':['Oh! {app}. I am coming with you.']},
    'Victoria': {
        'tab-opened':['Another tab, darling? Very ambitious.','A fresh tab. Let us hope this one meets my standards.'],
        'tab-closed':['One fewer tab. A little restraint, at last.'],
        'tab-switched':['A different tab. Very well, you have my attention.'],
        'page-changed':['A change of page. Do keep me informed, darling.'],
        'window-opened':['A new window. I shall reserve judgement.'],
        'window-closed':['That window has made its exit. Quite decisive.'],
        'window-switched':['Over to {app}, then. Do keep up, everyone.']},
    'Mika': {
        'tab-opened':['A new tab. Shall we have a look together?'],
        'tab-closed':['That tab is finished with, then. That is alright.'],
        'tab-switched':['A different tab. I am still following.'],
        'page-changed':['The page has changed. Let us see where you are going with it.'],
        'window-opened':['A new window. Shall we make room for it?'],
        'window-closed':['That window is closed. We can move on together.'],
        'window-switched':['Over to {app}. I am right here.']},
}


def screen_remark(name,events,rng=None):
    rng = rng or random
    if len(events)==1 and 'counts' not in events[0]:
        item = events[0]
        app = item.get('app','another window').removesuffix('.exe')[:35]
        choices = SINGLE.get(name,SINGLE['Mika'])[item['event']]
        return rng.choice(choices).format(app=app)
    counts = Counter()
    for item in events:
        counts.update(item.get('counts',{item['event']:1}))
    labels = {'tab-opened':'tabs opened','tab-closed':'tabs closed','tab-switched':'tab switches',
              'page-changed':'page changes','window-opened':'windows opened','window-closed':'windows closed','window-switched':'window switches'}
    changes = ', '.join(f'{count} {labels[kind]}' for kind,count in counts.items())
    return {'Burt':f'Umm, {changes}. Wait, I am catching up.',
            'Cody':f'Whoa, {changes}! Lots happening over there.',
            'Victoria':f'{changes}. Quite the rearrangement, darling.',
            'Mika':f'{changes}. I am following; take your time.'}[name]
