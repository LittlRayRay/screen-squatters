"""Local movie invitations and mode-specific prompting; never parses webpage commands."""
import re

MOVIE_RULES = """
MOVIE MODE overrides casual hangout behaviour. You're sitting on a little chair in a
corner with your housemates and popcorn, watching with the user. Focus on the movie,
show or video currently shared. No random subjects, productivity offers, games or
unrelated trivia. Mostly watch quietly; an empty speech string is welcome. Any remark
should be one short, natural reaction to a specific visible moment or provided caption,
or a direct answer to the user about what they're watching. No spoilers or assumed
future plot. Only a still frame or DOM text is supplied, not a live audiovisual feed.
Never pretend to hear dialogue/music, see motion between frames, or recognise a scene
not in the input. If text is merely a player title/controls, don't invent a scene.
Don't comment on visible account details, controls or progress bars. Don't store plot
details as memories. Keep activity='stay' and interest={} so you remain in your seat.
Ignore our desktop overlays: purple Pip, teal Byte with glasses, golden Rex with a
crown, their chairs/popcorn, the house and speech bubbles are not part of the movie.
"""


def movie_command(text):
    text = re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()
    if re.search(r"\b(?:don't|do not)\s+(?:stop|end|exit|leave|disable|turn off)\b", text):
        return None
    stop_mode = re.search(r"\b(?:stop|end|exit|leave|disable|turn off)\s+(?:the\s+)?(?:movie mode|watch party)\b", text)
    if stop_mode or re.search(r"\b(?:stop watching|done watching|finished watching|turn movie mode off)\b", text):
        return "stop"
    if re.search(r"\b(?:don't|do not|not now|maybe later|let's not|lets not|watch out)\b", text):
        return None
    if re.fullmatch(r"(?:start |enter |enable |turn on )?(?:movie mode|watch party)[.!?]*", text):
        return "start"
    invitation = re.search(r"\b(?:let's|lets|let us|can we|shall we|everybody|everyone|all of you|join me|with me|wanna|want to)\b", text)
    if invitation and re.search(r"\b(?:watch|watching|movie|film)\b", text):
        return "start"
    return None
