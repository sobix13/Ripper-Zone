"""HMAC weighted selection adapted from sobix13/Ripcars-Raffle drawing.py.

Reference: 7727fc67d448f677f1d16b54c86cf71bee960013. No repeat winners.
"""
import hashlib
import hmac
import re
from .config import digest, ident, integer, raffle_spec

ALGORITHM = "ripcars-weighted-hmac-sha256-v1"


def seed_bytes(seed):
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("Invalid seed.")
    return bytes.fromhex(seed)


def commitment(seed):
    return hashlib.sha256(seed_bytes(seed)).hexdigest()


def select(seed, context, pool, count):
    key = seed_bytes(seed)
    integer(count, 0, 25)
    if not isinstance(pool, list):
        raise ValueError("Invalid weighted pool.")
    for row in pool:
        if not isinstance(row, dict) or set(row) != {"user", "weight"}:
            raise ValueError("Invalid weighted entry.")
        ident(row["user"])
        integer(row["weight"], 1, 2000)
    if len({x["user"] for x in pool}) != len(pool):
        raise ValueError("Duplicate weighted entry.")
    remaining = sorted((dict(x) for x in pool), key=lambda x: x["user"])
    winners, counter = [], 0
    for _ in range(min(count, len(remaining))):
        total = sum(x["weight"] for x in remaining)
        bound = 2**256 - 2**256 % total
        while True:
            number = int.from_bytes(hmac.new(key, f"{context}:{counter}".encode(), hashlib.sha256).digest(), "big")
            counter += 1
            if number < bound:
                ticket = number % total
                break
        for i, entry in enumerate(remaining):
            if ticket < entry["weight"]:
                winners.append(entry["user"])
                remaining.pop(i)
                break
            ticket -= entry["weight"]
    return winners


def result(seed, context, pool, winners, round_number=0):
    pool = sorted(pool, key=lambda x: x["user"])
    pool_hash = digest(pool)
    return {"algorithm": ALGORITHM, "round": round_number, "context": context,
            "pool": pool, "pool_hash": pool_hash, "requested": winners,
            "winners": select(seed, f"{context}:{round_number}:{pool_hash}", pool, winners)}


def verify(bundle):
    try:
        if commitment(bundle["seed"]) != bundle["commitment"] or digest(bundle["contract"]) != bundle["contract_hash"]:
            return False
        spec=raffle_spec(bundle['contract']['spec'])
        frozen={x['user']:x['weight'] for x in bundle['frozen']}
        if len(frozen)!=len(bundle['frozen']):return False
        checks=bundle['checks']
        if len(checks)!=len(frozen) or {x['user'] for x in checks}!=set(frozen) or any(type(x['eligible']) is not bool for x in checks):return False
        eligible={x['user']:frozen[x['user']] for x in checks if x['eligible']}
        seen = set()
        initial = None
        for n, rnd in enumerate(bundle["rounds"]):
            pool = rnd["pool"]
            if n == 0:
                initial = {x["user"]: x["weight"] for x in pool}
                expected_count=spec['winners'] if len(eligible)>=spec['minimum'] else 0
                if initial!=eligible or rnd['requested']!=expected_count:return False
            elif not 1<=rnd['requested']<=spec['winners']:return False
            if any(x["user"] in seen or initial.get(x["user"]) != x["weight"] for x in pool):
                return False
            expected = result(bundle["seed"], bundle["contract_hash"], pool, rnd['requested'], n)
            if rnd != expected:
                return False
            seen.update(rnd["winners"])
        return bool(bundle["rounds"])
    except (ValueError, KeyError, TypeError):
        return False
