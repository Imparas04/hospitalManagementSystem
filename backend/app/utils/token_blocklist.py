"""Logout support: remember the ID (jti) of every token that was logged out, until it would have expired.

Limitation: kept in memory, so a server restart forgets it (old tokens then work until they expire,
which is at most JWT_EXPIRES_HOURS). For a bigger deployment store it in Redis or a database table.
"""
import time

_revoked = {}   # jti -> unix time when the token expires anyway


def revoke(jti, expires_at):
    now = time.time()
    for old in [j for j, exp in _revoked.items() if exp < now]:   # forget tokens that expired by themselves
        del _revoked[old]
    _revoked[jti] = expires_at


def is_revoked(jti):
    return jti in _revoked


def clear():
    """Used by tests so one test never affects another."""
    _revoked.clear()
