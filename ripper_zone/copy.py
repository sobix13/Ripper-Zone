"""Editable copy with bounded, named placeholders. No expressions or attributes."""
from string import Formatter

COPY={
 'task_received':'Your contribution is recorded for moderator review. Recording a post does not award RC by itself.',
 'cooldown':'Please wait {remaining} before posting in this task again.',
 'award_success':'Your RC award is recorded. Check the receipt below.',
 'already_awarded':'This operation was already recorded. No duplicate reward was issued.',
 'snapshot_preview':'Review the source, recipients and total before confirming.',
 'snapshot_success':'Participation rewards have been recorded.',
 'spin_ready':'Your free daily spin is ready. Press Spin · Free to claim it.',
 'spin_claimed':'Your daily spin is already recorded for {day}.',
 'spin_result':'You received {amount} Ripper Credits.',
 'program_paused':'The community program is currently paused.',
 'spin_paused':'Daily spin is currently paused.',
 'leaderboard_intro':'Earned RC determine your ranking. Spending does not lower it.',
 'progress_intro':'All requirements apply. Only your highest eligible achievement role remains.',
 'raffle_howto':'Choose Buy Tickets, review the total and confirm. Ticket costs are reserved until closing.',
 'purchase_receipt':'Your ticket purchase has been recorded. Keep the receipt below.',
 'prize_claim':'Your prize claim is recorded. Follow the support instructions below.',
 'help_intro':'Choose a guide for the activity you want to complete.',
 'task_closed':'This task is closed. Previously accepted contributions remain reviewable.',
 'raffle_result':'The saved draw is final. Open Verify Draw to inspect its proof.',
 'operation_unknown':'The display failed. A saved operation may already have succeeded. Check History or its receipt before starting another award.',
}
FIELDS={'cooldown':{'remaining'},'spin_claimed':{'day'},'spin_result':{'amount'}}

def validate_copy(key,text):
    if key not in COPY or not isinstance(text,str) or not text.strip() or len(text)>300:raise ValueError('Message text must contain 1–300 characters.')
    try:
        for _,field,format_spec,conversion in Formatter().parse(text):
            if field is not None and (field not in FIELDS.get(key,set()) or format_spec or conversion):raise ValueError('Use only the listed named placeholders, without formatting expressions.')
    except (ValueError,KeyError) as exc:raise ValueError('Invalid message placeholder. Use only the listed names.') from exc
    return text.strip()

def phrase(cfg,key,**values):
    template=cfg.get('messages',COPY).get(key,COPY[key])
    if key=='cooldown':template=template.replace('{remaining} seconds','{remaining}')
    return template.format_map(values)


def receipt_text(entry):
    if not (entry['da']>0 and entry['da']==entry['de'] and entry['dr']==0):return None
    source=entry['source'];ref=entry['ref']
    if source=='spin':context='from the daily spin'
    elif source=='reaction':
        from .config import display_emoji
        context='for receiving '+display_emoji(entry['reason'].removeprefix('Reaction '))
    elif source in ('rumble','raffle'):context=f"from the {'Rumble' if source=='rumble' else 'raffle'} #{ref} snapshot"
    elif source=='voice':context=f"from voice snapshot #{ref.split(':')[-1]} in <#{ref.split(':')[0]}>"
    elif source=='task':context=f"for task #{ref.split(':')[0]}"
    elif source=='manual':context='from a moderator award'
    else:return None
    return f"<@{entry['user']}> received {entry['da']} RC {context}."
