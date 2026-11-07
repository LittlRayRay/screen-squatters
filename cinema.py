"""Local movie invitations and mode-specific prompting; never parses webpage commands."""
import re

MOVIE_RULES = """
MOVIE MODE overrides casual hangout behaviour. You're sitting on a little chair in a
corner with your housemates and popcorn, watching with the user. Focus on the movie,
show or video currently shared. No random subjects, productivity offers, games or
unrelated trivia. Mostly watch quietly between scheduled comments. For MOVIE_COMMENT,
give one short spoken sentence rather than an empty speech string. Any remark
should be one short, natural reaction to a specific visible moment or provided caption,
or a direct answer to the user about what they're watching. No spoilers or assumed
future plot. Only a still frame or DOM text is supplied, not a live audiovisual feed.
PLAYER_MESSAGE requests take priority: answer an explicit off-topic question briefly,
then settle back into watching. Do not ignore the player in order to stay silent.
Never pretend to hear dialogue/music, see motion between frames, or recognise a scene
not in the input. If text is merely a player title/controls, don't invent a scene.
Without usable movie context, make a small in-character movie-night remark about
your seat, snacks or keeping a friend company instead. Don't repeatedly complain
about missing access. Vary your remarks and avoid repeating recent conversation.
Don't comment on visible account details, controls or progress bars. Don't store plot
details as memories. Keep activity='stay' and interest={} so you remain in your seat.
Ignore our desktop overlays: purple Burt, teal Cody with glasses, Victoria with a
crown/pearls and Mika with a gold ring. Their chairs/popcorn, house and bubbles are not part of the movie.
"""

MOVIE_COMMENT_INTERVAL = 35
MOVIE_COMMENT_TRIGGER = ('MOVIE_COMMENT: Give one brief, natural movie-night comment now. '
                         'React to a supplied frame/caption if it supports something specific; '
                         'otherwise say something about sharing movie night, seats or snacks. '
                         'Do not invent a scene or audio. One short sentence; do not stay silent.')


def movie_comment_fallback(name, conversation):
    """Keep an empty successful scheduled reply social without inventing movie content."""
    choices = {
        'Burt':("Umm, I should probably stop eating the popcorn before everyone gets some.",
                "Wait, does anyone want this seat? I'm okay over here.",
                "Uhh, sitting here with everyone is nice."),
        'Cody':("Movie night with everyone is pretty great.",
                "I need to make this popcorn last. I'm doing terribly.",
                "I brought snacks and then immediately ate most of them."),
        'Victoria':("I must admit, this is rather a pleasant evening.",
                    "Darling, leave some popcorn for the rest of us.",
                    "I'm keeping this seat. It's quite comfortable."),
        'Mika':("This is nice. I'm glad we're all here.",
                "Anyone want a bit more room? I can scoot over.",
                "I should've brought more snacks for everyone.")}
    recent = {line.get('text') for line in conversation[-8:]}
    lines = choices.get(name,choices['Cody'])
    return next((line for line in lines if line not in recent),lines[0])


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
