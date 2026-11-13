"""English duration inputs; stored task times remain integer seconds."""
import re

MAX_TASK_TIME=90*86400
UNITS=(('d',86400,'day'),('h',3600,'hour'),('m',60,'minute'),('s',1,'second'))


def parse_duration(value,*,allow_none=False,maximum=MAX_TASK_TIME):
    value=str(value).strip().lower()
    if value=='none' and allow_none:return 0
    match=re.fullmatch(r'([0-9]{1,8})\s*([smhd])',value)
    if not match:raise ValueError('Use a duration such as 12s, 12m, 12h or 12d'+(', or none.' if allow_none else '.'))
    seconds=int(match[1])*dict((unit,size) for unit,size,_ in UNITS)[match[2]]
    if not 1<=seconds<=maximum:raise ValueError(f'Duration must be between 1 second and {format_duration(maximum)}.')
    return seconds


def duration_input(seconds):
    if not seconds:return 'none'
    return next(f'{seconds//size}{unit}' for unit,size,_ in UNITS if seconds%size==0)


def format_duration(seconds):
    if not seconds:return 'None'
    parts=[]
    for _,size,name in UNITS:
        count,seconds=divmod(int(seconds),size)
        if count:parts.append(f'{count} {name}'+('s' if count!=1 else ''))
    return ' '.join(parts)
