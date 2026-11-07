"""Round housemates: expressive faces and accessories, no limbs."""
import math
from house import CHARACTERS


def draw_friend(canvas,name,x,y,scale=1,asleep=False,phase=0,gaze=(0,0),pointing=False,
                walking=False,seated=False,talking=False,popcorn=True,roll=0,emotion='calm',scuffling=False,motion='idle',impact=0):
    color = CHARACTERS[name]['color']
    bounce = abs(math.sin(phase/3))*5 if walking else math.sin(phase/12)*1.4
    squash = abs(math.sin(phase/3))*2 if walking else math.sin(phase/17)*.5
    if motion == 'impact':
        squash += 3+impact*5
    elif motion == 'airborne':
        squash -= 2
    angle = math.radians(roll%360)+(math.sin(phase/5)*.08 if talking else 0)
    if motion == 'held':
        angle += {'Burt':-.16,'Cody':.16,'Victoria':-.09,'Mika':.05}.get(name,0)
    def point(a,b):
        return x+(a*math.cos(angle)-b*math.sin(angle))*scale,y+(a*math.sin(angle)+b*math.cos(angle)-bounce)*scale
    def oval(a,b,c,d,**kwargs):
        return canvas.create_oval(x+a*scale,y+(b-bounce)*scale,x+c*scale,y+(d-bounce)*scale,**kwargs)
    def circle(a,b,r,**kwargs):
        px,py = point(a,b)
        return canvas.create_oval(px-r*scale,py-r*scale,px+r*scale,py+r*scale,**kwargs)
    canvas.create_oval(x-30*scale,y+30*scale,x+30*scale,y+39*scale,fill='#29273b',outline='')
    if seated:
        canvas.create_rectangle(x-39*scale,y-10*scale,x+39*scale,y+35*scale,fill='#675b79',outline='#9d87ad',width=2)
        canvas.create_oval(x-44*scale,y+18*scale,x+44*scale,y+42*scale,fill='#827290',outline='#ae95bd')
    oval(-31-squash,-31+squash,31+squash,31-squash,fill=color,outline='#65576e',width=2)
    circle(-13,-21,7,fill='#fff5e5',outline='')
    for eye in (-11,11):
        if asleep or phase%113<3 or (motion=='impact' and name in ('Mika','Victoria')):
            canvas.create_line(*point(eye-4,-5),*point(eye+4,-5),fill='#262233',width=2)
        else:
            size = 6.5 if motion in ('held','airborne') and name in ('Burt','Cody') else 5
            circle(eye,-7,size,fill='#fffaf4',outline='')
            circle(eye+gaze[0]*2,-7+gaze[1]*2,2.5,fill='#262233',outline='')
            if name == 'Victoria' and motion != 'airborne':
                canvas.create_line(*point(eye-5,-10),*point(eye+5,-10),fill=color,width=max(2,int(4*scale)))
    if name == 'Cody':
        for eye in (-12,12):
            circle(eye,-7,10,outline='#28444c',width=2)
        canvas.create_line(*point(-2,-7),*point(2,-7),fill='#28444c',width=2)
    elif name == 'Victoria':
        crown = [(-23,-27),(-27,-48),(-12,-38),(0,-55),(12,-38),(27,-48),(23,-27)]
        canvas.create_polygon(*[v for p in crown for v in point(*p)],fill='#f7d977',outline='#92733c',width=2)
        canvas.create_line(*point(3,-19),*point(14,-24),*point(20,-20),smooth=True,fill='#654453',width=2)
        for pearl in (-15,-5,5,15):
            circle(pearl,25,2,fill='#fff6e8',outline='')
    elif name == 'Mika':
        circle(23,15,7,outline='#9e742b',width=max(2,int(4*scale)))
        circle(23,15,7,outline='#ffe49a',width=max(1,int(2*scale)))
        canvas.create_line(*point(-4,-30),*point(0,-40),*point(9,-37),smooth=True,fill='#9e8448',width=3)
        canvas.create_polygon(*[v for p in [(0,-38),(10,-46),(13,-38),(4,-35)] for v in point(*p)],fill='#83a278',outline='')
    else:
        canvas.create_line(*point(-1,-30),*point(3,-42),*point(11,-43),smooth=True,fill='#78618f',width=3)
    if emotion in ('angry','annoyed') and not asleep:
        for sign in (-1,1):
            canvas.create_line(*point(sign*5,-17),*point(sign*18,-22),fill='#483448',width=2)
    if asleep:
        canvas.create_text(x+28*scale,y-35*scale,text='z Z',fill='#abaec7',font=('Segoe UI',max(8,int(10*scale))))
    elif talking or (motion=='airborne' and name in ('Burt','Victoria','Mika')):
        opening = 3+abs(math.sin(phase/1.7))*5
        px,py = point(0,10)
        canvas.create_oval(px-6*scale,py-opening*scale/2,px+6*scale,py+opening*scale/2,fill='#58374e',outline='#35263e')
    else:
        mouth = [(-8,9),(0,11),(11,4)] if name=='Victoria' else [(-10,6),(0,18),(10,6)] if name=='Cody' else [(-7,9),(0,11),(7,8)] if name=='Burt' else [(-7,8),(0,13),(8,8)]
        if motion == 'held' and name == 'Burt':
            mouth = [(-6,10),(0,7),(7,11)]
        points = [point(*position) for position in mouth]
        canvas.create_line(*[v for p in points for v in p],smooth=True,fill='#35263e',width=2)
    if pointing:
        direction = 1 if gaze[0]>=0 else -1
        canvas.create_polygon(x+direction*40*scale,y-4*scale,x+direction*53*scale,y,
                              x+direction*40*scale,y+4*scale,fill=color,outline='')
    if seated and popcorn:
        canvas.create_polygon(x+16*scale,y+15*scale,x+38*scale,y+15*scale,x+34*scale,y+39*scale,x+20*scale,y+39*scale,fill='#ce6769',outline='#ffd9b3')
        for px,py in [(18,14),(25,10),(31,13),(36,10)]:
            circle(px,py,4,fill='#ffe3a0',outline='#cbaa6d')
    if scuffling:
        for i in range(3):
            a = phase/7+i*2.1
            canvas.create_text(x+math.cos(a)*44*scale,y+math.sin(a)*26*scale-26*scale,text='✦',fill='#ffe199',font=('Segoe UI',max(8,int(15*scale))))
