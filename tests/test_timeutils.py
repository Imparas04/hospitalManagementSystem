from datetime import date, datetime

from app.utils import timeutils as t


def test_kolkata_day_starts_5h30_before_utc_midnight(app):
    app.config["HOSPITAL_TIMEZONE"] = "Asia/Kolkata"
    start, end = t.day_bounds_utc(date(2026, 10, 11))
    assert start == datetime(2026, 10, 10, 18, 30)
    assert end == datetime(2026, 10, 11, 18, 30)


def test_late_night_ist_payment_belongs_to_the_next_local_day(app):
    """01:30 IST on Oct 11 is stored as 20:00 UTC on Oct 10 - it must count for Oct 11."""
    app.config["HOSPITAL_TIMEZONE"] = "Asia/Kolkata"
    stored = datetime(2026, 10, 10, 20, 0)
    assert t.to_local_date(stored) == date(2026, 10, 11)
    start, end = t.day_bounds_utc(date(2026, 10, 11))
    assert start <= stored < end
    s10, e10 = t.day_bounds_utc(date(2026, 10, 10))
    assert not (s10 <= stored < e10)


def test_range_bounds_are_inclusive_of_the_last_day(app):
    app.config["HOSPITAL_TIMEZONE"] = "UTC"
    start, end = t.range_bounds_utc(date(2026, 10, 1), date(2026, 10, 3))
    assert start == datetime(2026, 10, 1) and end == datetime(2026, 10, 4)


def test_date_range_and_month_helpers():
    assert t.date_range(date(2026, 2, 27), date(2026, 3, 2)) == [date(2026, 2, 27), date(2026, 2, 28), date(2026, 3, 1), date(2026, 3, 2)]
    assert t.month_start(date(2026, 10, 17)) == date(2026, 10, 1)
    assert t.month_end(date(2026, 2, 3)) == date(2026, 2, 28) and t.month_end(date(2028, 2, 3)) == date(2028, 2, 29)
    assert t.add_months(date(2026, 1, 15), -1) == date(2025, 12, 1)
    assert t.add_months(date(2026, 11, 15), 3) == date(2027, 2, 1)
    assert t.add_months(date(2026, 10, 1), -11) == date(2025, 11, 1)
