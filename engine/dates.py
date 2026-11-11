"""Turn the dates people say into calendar dates, counted from the day of the call.

"Next Tuesday" said on Tuesday, September 8 is September 15, since "next" means that day in the following week.
"Next Wednesday" on the same Tuesday is September 16. "By Thursday" is the coming Thursday, "the thirtieth" is the
next 30th, and "October second" or "October 2" is that day in the call's year (or the next one, if it's past).
"The week of October nineteenth" resolves to that Monday. Anything vaguer ("soon," "next quarter," "after the audit")
comes back as None, so it's compared as words instead of as a date. Standard library only.
"""
import re
from datetime import date, timedelta

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
            "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
            "twentieth": 20, "thirtieth": 30}
UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
         "ninth": 9}


def _day_number(text):
    """The day of the month in "the 30th," "30," "the thirtieth" or "twenty-second"."""
    t = text.lower().replace("-", " ").strip()
    m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)?", t)
    if m:
        return int(m.group(1))
    if t in ORDINALS:
        return ORDINALS[t]
    parts = t.split()
    if len(parts) == 2 and parts[0] in ("twenty", "thirty") and parts[1] in UNITS:
        return (20 if parts[0] == "twenty" else 30) + UNITS[parts[1]]
    return None


DAYNUM = r"(\d{1,2}(?:st|nd|rd|th)?|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|" \
         r"twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth|" \
         r"(?:twenty|thirty)[- ](?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth))"


def resolve(phrase, call_day):
    """The calendar date a phrase names, as a date, or None when it doesn't name one."""
    if not phrase:
        return None
    if isinstance(call_day, str):
        call_day = date.fromisoformat(call_day)
    t = " " + phrase.lower().replace(",", " ") + " "
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if re.search(r"\btoday\b|\bthis afternoon\b|\bthis morning\b", t):
        return call_day
    if re.search(r"\btomorrow\b", t):
        return call_day + timedelta(days=1)
    m = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(?:the\s+)?" + DAYNUM + r"\b", t)
    if m:
        return _in_year(call_day, MONTHS.index(m.group(1)) + 1, _day_number(m.group(2)))
    m = re.search(r"\bthe\s+" + DAYNUM + r"\s+of\s+(" + "|".join(MONTHS) + r")\b", t)
    if m:
        return _in_year(call_day, MONTHS.index(m.group(2)) + 1, _day_number(m.group(1)))
    m = re.search(r"\bthe\s+" + DAYNUM + r"\b", t)
    if m:
        day = _day_number(m.group(1))
        if day:
            y, mo = call_day.year, call_day.month
            if day < call_day.day:
                mo += 1
                if mo == 13:
                    y, mo = y + 1, 1
            try:
                return date(y, mo, day)
            except ValueError:
                return None
    m = re.search(r"\b(?:next\s+)?(" + "|".join(DAYS) + r")\b", t)
    if m:
        target = DAYS.index(m.group(1))
        if re.search(r"\bnext\s+" + m.group(1), t):
            return call_day + timedelta(days=7 - call_day.weekday() + target)
        return call_day + timedelta(days=(target - call_day.weekday()) % 7 or 7)
    return None


def _in_year(call_day, month, day):
    """That month and day in the call's year, or the next year when it's well past."""
    if not day:
        return None
    try:
        d = date(call_day.year, month, day)
        return d if d >= call_day - timedelta(days=60) else date(call_day.year + 1, month, day)
    except ValueError:
        return None
