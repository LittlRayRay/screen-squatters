"""Occasional game preferences and invitations, independent of model token use."""
MINIMUM = {'Poker':3,'Mafia':4,'Debate':2,'Tic-tac-toe':2}
KINDS = tuple(MINIMUM)
OFFERS = {
    'Burt':'Umm, does anyone want to play {game} with me? I might need help.',
    'Cody':'Hey! {game}? We could all play. Want to join?',
    'Victoria':'I propose {game}. You may join us, darling.',
    'Mika':'Shall we play {game} together? You would be very welcome.',
}
DECLINES = {
    'Burt':'Umm, I think I will watch this one. I am still figuring it out.',
    'Cody':'Can I watch for a bit? I got distracted. I still want to hang out!',
    'Victoria':'I shall observe this round. Someone must maintain standards.',
    'Mika':'I would rather watch for a little while. Do go ahead.',
}


def occasional_refusal(players,kind,rng,enabled=True):
    candidates = [name for name in players if name != 'You']
    if not enabled or not candidates or rng.random()>=.12:
        return None
    return rng.choice(candidates)
