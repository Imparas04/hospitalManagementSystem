"""Brute-force protection for the login endpoint.

Idea (easy to explain in a viva): remember the time of every FAILED login per (username, IP address).
If there are LOGIN_MAX_ATTEMPTS failures inside the last LOGIN_LOCKOUT_MINUTES, refuse further tries
until the oldest failure is old enough. A successful login clears the counter.

Limitation: the counters live in this process's memory, so they reset when the server restarts and are
not shared between several server workers. For a bigger deployment, move them to Redis or the database.
"""
import time


class LoginGuard:
    def __init__(self, max_attempts=5, lockout_minutes=15):
        self.max_attempts = max_attempts
        self.window = lockout_minutes * 60
        self._failures = {}   # key -> list of failure timestamps

    def _recent(self, key):
        now = time.monotonic()
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def seconds_until_allowed(self, key):
        """0 if the user may try to log in, otherwise how many seconds they must wait."""
        if self.max_attempts <= 0:          # 0 = protection switched off
            return 0
        recent = self._recent(key)
        if len(recent) < self.max_attempts:
            return 0
        return int(recent[0] + self.window - time.monotonic()) + 1

    def record_failure(self, key):
        self._failures.setdefault(key, []).append(time.monotonic())

    def reset(self, key):
        self._failures.pop(key, None)
