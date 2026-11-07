"""Canvas speech cards shared by desktop companions and the poker table."""
import math


def rounded(canvas, x1, y1, x2, y2, radius=14, **options):
    points = [x1+radius,y1,x2-radius,y1,x2,y1,x2,y1+radius,
              x2,y2-radius,x2,y2,x2-radius,y2,x1+radius,y2,
              x1,y2,x1,y2-radius,x1,y1+radius,x1,y1]
    return canvas.create_polygon(points, smooth=True, splinesteps=16, **options)


def speech_bubble(canvas, name, text, x=5, y=3, width=180, color='#c5b0ff', typing=False, phase=0):
    text_id = None
    height = 59
    if not typing:
        text_id = canvas.create_text(x+13,y+30,text=text,width=width-26,anchor='nw',
                                     fill='#f6f2ff',font=('Segoe UI',10),justify='left')
        bounds = canvas.bbox(text_id)
        height = max(58, (bounds[3]-y+12) if bounds else 58)
    rounded(canvas,x+3,y+4,x+width+3,y+height+4,fill='#10121b',outline='')
    rounded(canvas,x,y,x+width,y+height,fill='#2b2c40',outline='#62617d',width=1)
    canvas.create_polygon(x+width*.43,y+height-1,x+width*.52,y+height+10,
                          x+width*.59,y+height-1,fill='#2b2c40',outline='')
    canvas.create_oval(x+12,y+13,x+17,y+18,fill=color,outline='')
    canvas.create_text(x+23,y+9,text=name+(' is typing' if typing else ''),anchor='nw',
                       fill=color,font=('Segoe UI',8,'bold'))
    if typing:
        for i in range(3):
            lift = max(0,math.sin(phase/4-i*.9))*3
            cx, cy = x+width/2+(i-1)*14, y+39-lift
            canvas.create_oval(cx-3,cy-3,cx+3,cy+3,fill=color,outline='')
    elif text_id:
        canvas.tag_raise(text_id)
