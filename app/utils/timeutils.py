"""Time helpers.

The database stores every timestamp in UTC (naive datetimes). People think in
LOCAL time, so for "today", "this month" and per-day charts we convert:

    local date  ->  [start, end) in UTC   (to FILTER rows in the database)
    UTC value   ->  local date            (to GROUP rows into days/months)

Example (Asia/Kolkata = UTC+5:30): local day 2026-10-10 is
    2026-10-09 18:30:00 UTC  ->  2026-10-10 18:30:00 UTC
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def tz():
    return ZoneInfo(current_app.config["HOSPITAL_TIMEZONE"])


def local_now():
    return datetime.now(tz())


def local_today():
    return local_now().date()


def utc_now_naive():
    """Same format the database uses (UTC, no tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_local_date(value):
    """UTC datetime from the database -> local calendar date."""
    return value.replace(tzinfo=timezone.utc).astimezone(tz()).date()


def start_of_day_utc(day):
    """Local midnight at the start of `day`, as naive UTC."""
    return datetime.combine(day, time.min, tzinfo=tz()).astimezone(timezone.utc).replace(tzinfo=None)


def day_bounds_utc(day):
    """(start, end) of a local day in naive UTC. Use as: start <= value < end."""
    return start_of_day_utc(day), start_of_day_utc(day + timedelta(days=1))


def range_bounds_utc(first_day, last_day):
    """Bounds covering local days first_day..last_day INCLUSIVE."""
    return start_of_day_utc(first_day), start_of_day_utc(last_day + timedelta(days=1))


def date_range(first_day, last_day):
    """Every date from first_day to last_day inclusive."""
    return [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]


def month_start(day):
    return day.replace(day=1)


def month_end(day):
    nxt = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt - timedelta(days=1)


def add_months(day, delta):
    """First day of the month `delta` months away from day's month."""
    idx = day.year * 12 + (day.month - 1) + delta
    return date(idx // 12, idx % 12 + 1, 1)
