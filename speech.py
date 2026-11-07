"""Local, clock-driven text delivery. Animation does not spend AI tokens."""
from bisect import bisect_right
import re


def conversational_speech(text,suppress_events=False):
    """A filler-only response is silence, rather than a spoken thinking placeholder."""
    if suppress_events and re.search(r'\b\d+\s+(?:windows?|tabs?)\s+(?:open(?:ed)?|clos(?:ed|e)|switch(?:es)?)\b',text,re.I):
        return ''
    return '' if re.fullmatch(r'[\s.,!?…]*(?:(?:h+m+|um+|uh+|ah+|erm+)[\s.,!?…]*)+', text, re.I) else text


class SpeechLine:
    def __init__(self, text, start, fast=False):
        self.text = text
        self.start = start
        self.times = []
        cursor = start+(.12 if fast else .55)
        for i, char in enumerate(text):
            cursor += (.014 if fast else .038) + (i % 4)*(.001 if fast else .004)
            if i and text[i-1] in '.!?':
                cursor += .06 if fast else .29
            elif i and text[i-1] in ',;:':
                cursor += .025 if fast else .13
            self.times.append(cursor)
        self.end = cursor

    def visible(self, now):
        return self.text[:bisect_right(self.times, now)]

    def typing(self, now):
        return now < (self.times[0] if self.times else self.start)

    def speaking(self, now):
        return not self.typing(now) and now < self.end

    def page(self, now, width=96):
        visible = self.visible(now)
        if not visible:
            return ''
        # Keep each page anchored while it types; long replies continue on new pages.
        start = 0
        while len(visible)-start > width:
            boundary = self.text.rfind(' ', start+width//2, start+width)
            start = boundary+1 if boundary >= 0 else start+width
        return visible[start:]
