"""Validated settings. All RC amounts are integer credits."""
import copy
import hashlib
import json
import re
import unicodedata
from .copy import COPY,validate_copy


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def ident(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Use a Discord numeric ID.")
    value = str(value)
    if not re.fullmatch(r"[0-9]+", value) or not 0 < int(value) < 2**63:
        raise ValueError("Use a valid Discord numeric ID.")
    return int(value)


def integer(value, low=1, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Enter an integer from {low} to {high}.")
    return value


def clean(value, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Enter text between 1 and {limit} characters.")
    return value.strip()


DEFAULTS = {
    "messages": COPY, "support_channel": 0, "active": False, "member_role": 0, "manager_roles": [], "primary_users": [],
    "panel_channel": 0, "tasks_channel": 0, "leaderboard_channel": 0,
    "raffle_channel": 0, "log_channel": 0, "panel_message": 0, "leaderboard_message": 0,
    "panel_state": "new", "spin_enabled": True, "spin_role": 0,
    "roles_enabled": False, "tiers": [], "reactions_enabled": True,
    "panel_title": "Ripper Zone",
    "welcome_text": "Your community, your progress.\nEarn Ripper Credits through tasks, events and a free daily spin. Spend RC on public raffles.\nOpen your private panel to get started.",
    "about_text": "Ripper Credits recognize your contributions to the Rip Cars community.",
    "support_text": "For help with a reward or prize, contact the server moderators through a support ticket.",
    "task_footer": "Post your contribution in this thread. Moderators review it and award RC with the configured reactions.",
    "reactions": {"✅": {"kind": "base", "amount": 0}, "🏅": {"kind": "quality", "amount": 5}},
}


LEGACY_KEYS=frozenset({'active','member_role','manager_roles','primary_users','panel_channel','tasks_channel','leaderboard_channel','raffle_channel','log_channel','panel_message','leaderboard_message','panel_state','spin_enabled','spin_role','roles_enabled','tiers','reactions'})


def settings(data=None):
    result = copy.deepcopy(DEFAULTS)
    if data:
        unknown = set(data) - set(result)
        if unknown:
            raise ValueError("Unknown settings: " + ", ".join(sorted(unknown)))
        result.update(copy.deepcopy(data))
    if not isinstance(result['messages'],dict) or set(result['messages'])!=set(COPY):raise ValueError('Incomplete message catalog.')
    result['messages']={k:validate_copy(k,v) for k,v in result['messages'].items()}
    for key in ("active", "spin_enabled", "roles_enabled", "reactions_enabled"):
        if type(result[key]) is not bool:
            raise ValueError(f"{key} must be true or false.")
    for key,limit in (("panel_title",80),("welcome_text",1200),("about_text",1200),("support_text",800),("task_footer",500)):
        result[key]=clean(result[key],limit)
    for key in ("support_channel", "member_role", "spin_role", "panel_channel", "tasks_channel", "leaderboard_channel",
                "raffle_channel", "log_channel", "panel_message", "leaderboard_message"):
        if result[key]:
            result[key] = ident(result[key])
        elif result[key] != 0 or isinstance(result[key], bool):
            raise ValueError(f"Invalid {key}.")
    for key in ("manager_roles", "primary_users"):
        if not isinstance(result[key], list) or len(result[key]) > 25:
            raise ValueError(f"Select at most 25 {key}.")
        result[key] = sorted(set(ident(x) for x in result[key]))
    if not isinstance(result["tiers"], list) or len(result["tiers"]) not in (0, 3):
        raise ValueError("Configure exactly three tiers, or skip them.")
    previous = (-1, -1, -1)
    seen = set()
    for tier in result["tiers"]:
        if not isinstance(tier, dict) or set(tier) != {"role", "earned", "tasks", "events"}:
            raise ValueError("Each tier requires role, earned, tasks and events.")
        role = ident(tier["role"])
        metrics = tuple(integer(tier[k], 0) for k in ("earned", "tasks", "events"))
        if role in seen or role in [result["member_role"], result["spin_role"], *result["manager_roles"]]:
            raise ValueError("Tier roles must be distinct from access and staff roles.")
        if any(a < b for a, b in zip(metrics, previous)) or metrics == previous or not any(metrics):
            raise ValueError("Tier requirements must increase and cannot all be zero.")
        seen.add(role)
        previous = metrics
    if result["roles_enabled"] and len(result["tiers"]) != 3:
        raise ValueError("Complete three tiers before activation.")
    if result["panel_state"] not in ("new", "active", "sending", "review", "missing"):
        raise ValueError("Invalid panel state.")
    if not isinstance(result["reactions"], dict) or not 1 <= len(result["reactions"]) <= 5:
        raise ValueError("Configure one to five reward reactions.")
    keys=[emoji_key(k) for k in result['reactions']]
    if len(keys)!=len(set(keys)):raise ValueError('The same emoji is configured more than once.')
    for emoji, rule in result["reactions"].items():
        validate_emoji(emoji)
        if set(rule) != {"kind", "amount"} or rule["kind"] not in ("base", "quality"):
            raise ValueError("Reaction kind must be base or quality.")
        integer(rule["amount"], 0, 1000)
        if rule['kind']=='base' and rule['amount']!=0:raise ValueError('Base reactions use the task reward; their amount must be 0.')
        if rule['kind']=='quality' and rule['amount']==0:raise ValueError("A quality reaction must award at least 1 RC.")
    if result["active"] and any(not result[k] for k in ("panel_channel", "tasks_channel", "leaderboard_channel", "raffle_channel", "log_channel")):
        raise ValueError("Select all five channels before activation.")
    return result


def emoji_key(emoji):
    eid = getattr(emoji, "id", None)
    if eid:
        return f"custom:{eid}"
    text = str(emoji).strip().replace("\ufe0f", "")
    match = re.fullmatch(r"<a?:[^:>]+:([0-9]+)>", text)
    return "custom:" + match[1] if match else text


def validate_emoji(value):
    value=clean(value,100)
    key=emoji_key(value)
    if key.startswith('custom:'):
        ident(key.split(':',1)[1]);return value
    if re.fullmatch(r'[0-9#*]\ufe0f?\u20e3',value):return value
    bases=[c for c in value if c not in ('\ufe0f','\u200d') and not 0x1F3FB<=ord(c)<=0x1F3FF]
    if not bases or any(unicodedata.category(c) not in ('So','Sk') for c in bases):raise ValueError('Paste one Unicode emoji or a custom server emoji.')
    flag=len(bases)==2 and all(0x1F1E6<=ord(c)<=0x1F1FF for c in bases)
    if len(bases)>1 and '\u200d' not in value and not flag:raise ValueError('Use one emoji per reaction rule.')
    return value


def raffle_spec(spec):
    if set(spec) != {"title", "prize", "price", "max_tickets", "winners", "minimum", "ends"}:
        raise ValueError("Incomplete raffle rules.")
    spec = dict(spec)
    spec["title"] = clean(spec["title"], 100)
    spec["prize"] = clean(spec["prize"], 1500)
    for key, high in (("price", 100000), ("max_tickets", 2000), ("winners", 25), ("minimum", 10000)):
        integer(spec[key], 1, high)
    integer(spec["ends"], 1, 253402300799)
    return spec
