"""Small local moods and cartoon scuffles, with cooldowns and no external actions."""
import math


class Social:
    def __init__(self,names,options):
        self.options = options
        self.moods = {name:'calm' for name in names}
        self.until = {name:0 for name in names}
        self.scuffles = {}
        self.last_scuffle = -1e9

    def context(self):
        return {'moods':dict(self.moods),'scuffles_allowed':self.options.get('scuffles',True),
                'rule':'React to your friends by name, include quieter friends, and do not repeat their answers.'}

    def react(self,name,result,world,awake,now,allowed=True):
        self.moods[name] = result.emotion
        self.until[name] = now+45
        action = result.social_action
        target = action.get('target')
        kind = action.get('kind')
        if result.emotion == 'angry' and not kind:
            target = next((friend for friend in awake if friend != name and self.moods[friend] in ('angry','annoyed')),None)
            kind = 'scuffle' if target else None
        if not allowed or not self.options.get('scuffles') or not world.movement_enabled or not world.physics_enabled:
            return None
        if kind != 'scuffle' or result.emotion not in ('angry','annoyed') or target == name or target not in awake:
            return None
        if now-self.last_scuffle < self.options.get('scuffle_cooldown',90):
            return None
        a,b = world.residents[name],world.residents[target]
        if a.mode in ('home','returning','seated') or b.mode in ('home','returning','seated'):
            return None
        midpoint = ((a.x+b.x)/2,(a.y+b.y)/2)
        for index,resident in enumerate((a,b)):
            resident.goal = world.constrain(midpoint[0]+(-25 if index == 0 else 25),midpoint[1])
            resident.mode = 'sparring'
            resident.next_wander = now+15
            resident.interest = resident.gaze = None
        self.scuffles[name] = self.scuffles[target] = now+6
        self.last_scuffle = now
        return name+' and '+target+' have a tiny cartoon squabble.'

    def tick(self,world,now):
        for name in self.moods:
            if now >= self.until[name]:
                self.moods[name] = 'calm'
            if name in self.scuffles and (now >= self.scuffles[name] or not self.options.get('scuffles')):
                self.scuffles.pop(name,None)
                resident = world.residents[name]
                if resident.mode == 'sparring':
                    resident.mode,resident.goal = 'idle',None


def throw_velocity(samples,now):
    recent = [sample for sample in samples if now-sample[0] <= .16]
    if len(recent) < 2 or recent[-1][0]-recent[0][0] < .01:
        return 0,0
    dt = recent[-1][0]-recent[0][0]
    vx,vy = (recent[-1][1]-recent[0][1])/dt,(recent[-1][2]-recent[0][2])/dt
    speed = math.hypot(vx,vy)
    if speed > 1400:
        vx,vy = vx*1400/speed,vy*1400/speed
    return vx,vy
