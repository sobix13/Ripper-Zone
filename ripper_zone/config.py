"""Validated settings. All RC amounts are integer credits."""
import copy
import hashlib
import json
import re


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
    "active": False, "member_role": 0, "manager_roles": [], "primary_users": [],
    "panel_channel": 0, "tasks_channel": 0, "leaderboard_channel": 0,
    "raffle_channel": 0, "log_channel": 0, "panel_message": 0, "leaderboard_message": 0,
    "panel_state": "new", "spin_enabled": True, "spin_role": 0,
    "roles_enabled": False, "tiers": [],
    "reactions": {"✅": {"kind": "base", "amount": 0}, "🏅": {"kind": "quality", "amount": 5}},
}


def settings(data=None):
    result = copy.deepcopy(DEFAULTS)
    if data:
        unknown = set(data) - set(result)
        if unknown:
            raise ValueError("Unknown settings: " + ", ".join(sorted(unknown)))
        result.update(copy.deepcopy(data))
    for key in ("active", "spin_enabled", "roles_enabled"):
        if type(result[key]) is not bool:
            raise ValueError(f"{key} must be true or false.")
    for key in ("member_role", "spin_role", "panel_channel", "tasks_channel", "leaderboard_channel",
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
    for emoji, rule in result["reactions"].items():
        clean(emoji, 100)
        if set(rule) != {"kind", "amount"} or rule["kind"] not in ("base", "quality"):
            raise ValueError("Reaction kind must be base or quality.")
        integer(rule["amount"], 0, 1000)
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
