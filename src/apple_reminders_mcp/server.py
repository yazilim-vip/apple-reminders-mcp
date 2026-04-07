"""MCP server for Apple Reminders on macOS via EventKit."""

from __future__ import annotations

import datetime as dt
from typing import Optional

import EventKit  # pyobjc-framework-EventKit
from fastmcp import FastMCP

mcp = FastMCP("apple-reminders")

# Shared EventKit store — reused across tool calls
_store = EventKit.EKEventStore.alloc().init()


def _request_access() -> bool:
    """Request reminder access (blocks until user responds on first run)."""
    import threading

    granted = [False]
    event = threading.Event()

    def callback(ok, error):
        granted[0] = ok
        event.set()

    _store.requestFullAccessToRemindersWithCompletion_(callback)
    event.wait(timeout=30)
    return granted[0]


def _ensure_access():
    """Ensure we have reminder access, request if needed."""
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeReminder)
    if status == EventKit.EKAuthorizationStatusFullAccess:
        return
    if status == EventKit.EKAuthorizationStatusNotDetermined:
        if not _request_access():
            raise PermissionError("Reminders access denied by user.")
    else:
        raise PermissionError("Reminders access not granted. Open System Settings > Privacy & Security > Reminders.")


PRIORITY_MAP = {0: "none", 1: "high", 5: "medium", 9: "low"}
PRIORITY_REVERSE = {"high": 1, "medium": 5, "low": 9, "none": 0}


def _ns_date_to_iso(nsdate) -> Optional[str]:
    """Convert NSDate to ISO 8601 string."""
    if nsdate is None:
        return None
    ts = nsdate.timeIntervalSince1970()
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat()


def _iso_to_ns_date(iso_str: str):
    """Convert ISO 8601 string to NSDate."""
    from Foundation import NSDate

    parsed = dt.datetime.fromisoformat(iso_str)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return NSDate.dateWithTimeIntervalSince1970_(parsed.timestamp())


def _serialize_reminder(reminder) -> dict:
    """Serialize an EKReminder to a dict."""
    due_date = None
    if reminder.dueDateComponents():
        cal = EventKit.NSCalendar.currentCalendar()
        nsdate = cal.dateFromComponents_(reminder.dueDateComponents())
        due_date = _ns_date_to_iso(nsdate)

    return {
        "id": reminder.calendarItemIdentifier(),
        "name": reminder.title() or "",
        "body": reminder.notes() or "",
        "completed": reminder.isCompleted(),
        "dueDate": due_date,
        "completionDate": _ns_date_to_iso(reminder.completionDate()),
        "priority": PRIORITY_MAP.get(reminder.priority(), "none"),
        "list": reminder.calendar().title() if reminder.calendar() else None,
    }


def _fetch_reminders(calendars=None, completed=None) -> list:
    """Fetch reminders synchronously using a predicate."""
    import threading

    predicate = _store.predicateForRemindersInCalendars_(calendars)
    results = [None]
    event = threading.Event()

    def callback(reminders):
        results[0] = reminders
        event.set()

    _store.fetchRemindersMatchingPredicate_completion_(predicate, callback)
    event.wait(timeout=30)

    reminders = list(results[0] or [])
    if completed is not None:
        reminders = [r for r in reminders if r.isCompleted() == completed]
    return reminders


def _find_calendar(name: str):
    """Find a reminder calendar by name (case-insensitive)."""
    lower = name.lower()
    for cal in _store.calendarsForEntityType_(EventKit.EKEntityTypeReminder):
        if cal.title().lower() == lower:
            return cal
    return None


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────


@mcp.tool()
def list_reminder_lists() -> list[dict]:
    """List all reminder lists with counts."""
    _ensure_access()
    results = []
    for cal in _store.calendarsForEntityType_(EventKit.EKEntityTypeReminder):
        reminders = _fetch_reminders(calendars=[cal])
        incomplete = sum(1 for r in reminders if not r.isCompleted())
        results.append(
            {
                "name": cal.title(),
                "count": len(reminders),
                "incomplete": incomplete,
            }
        )
    return results


@mcp.tool()
def create_reminder_list(name: str) -> dict:
    """Create a new reminder list."""
    _ensure_access()
    source = _store.defaultCalendarForNewReminders().source()
    new_cal = EventKit.EKCalendar.calendarForEntityType_eventStore_(EventKit.EKEntityTypeReminder, _store)
    new_cal.setTitle_(name)
    new_cal.setSource_(source)
    ok, error = _store.saveCalendar_commit_error_(new_cal, True, None)
    if not ok:
        return {"error": str(error)}
    return {"created": True, "name": name}


@mcp.tool()
def delete_reminder_list(name: str) -> dict:
    """Delete a reminder list by name. All reminders in the list will be deleted."""
    _ensure_access()
    cal = _find_calendar(name)
    if not cal:
        return {"error": f"List not found: {name}"}
    ok, error = _store.removeCalendar_commit_error_(cal, True, None)
    if not ok:
        return {"error": str(error)}
    return {"deleted": True, "name": name}


@mcp.tool()
def list_reminders(
    list_name: Optional[str] = None,
    include_completed: bool = False,
) -> list[dict]:
    """List reminders. By default shows only incomplete. Optionally filter by list."""
    _ensure_access()
    calendars = None
    if list_name:
        cal = _find_calendar(list_name)
        if not cal:
            return [{"error": f"List not found: {list_name}"}]
        calendars = [cal]

    completed_filter = None if include_completed else False
    reminders = _fetch_reminders(calendars=calendars, completed=completed_filter)
    return [_serialize_reminder(r) for r in reminders]


@mcp.tool()
def search_reminders(
    query: str,
    include_completed: bool = False,
) -> list[dict]:
    """Search reminders by name and notes across all lists."""
    _ensure_access()
    q = query.lower()
    completed_filter = None if include_completed else False
    reminders = _fetch_reminders(completed=completed_filter)
    results = []
    for r in reminders:
        name = (r.title() or "").lower()
        notes = (r.notes() or "").lower()
        if q in name or q in notes:
            results.append(_serialize_reminder(r))
    return results


@mcp.tool()
def add_reminder(
    name: str,
    list_name: Optional[str] = None,
    due: Optional[str] = None,
    notes: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict:
    """Create a new reminder. Due date should be ISO 8601 (e.g. 2026-04-08T10:00:00)."""
    _ensure_access()

    reminder = EventKit.EKReminder.reminderWithEventStore_(_store)
    reminder.setTitle_(name)

    if list_name:
        cal = _find_calendar(list_name)
        if not cal:
            return {"error": f"List not found: {list_name}"}
        reminder.setCalendar_(cal)
    else:
        reminder.setCalendar_(_store.defaultCalendarForNewReminders())

    if notes:
        reminder.setNotes_(notes)

    if due:
        nsdate = _iso_to_ns_date(due)
        cal_obj = EventKit.NSCalendar.currentCalendar()
        components = cal_obj.components_fromDate_(
            EventKit.NSCalendarUnitYear
            | EventKit.NSCalendarUnitMonth
            | EventKit.NSCalendarUnitDay
            | EventKit.NSCalendarUnitHour
            | EventKit.NSCalendarUnitMinute
            | EventKit.NSCalendarUnitSecond,
            nsdate,
        )
        reminder.setDueDateComponents_(components)

        alarm = EventKit.EKAlarm.alarmWithAbsoluteDate_(nsdate)
        reminder.addAlarm_(alarm)

    if priority and priority in PRIORITY_REVERSE:
        reminder.setPriority_(PRIORITY_REVERSE[priority])

    ok, error = _store.saveReminder_commit_error_(reminder, True, None)
    if not ok:
        return {"error": str(error)}

    result = _serialize_reminder(reminder)
    result["created"] = True
    return result


@mcp.tool()
def complete_reminder(query: str, list_name: Optional[str] = None) -> dict:
    """Mark a reminder as complete. Searches incomplete reminders by name."""
    _ensure_access()
    calendars = None
    if list_name:
        cal = _find_calendar(list_name)
        if not cal:
            return {"error": f"List not found: {list_name}"}
        calendars = [cal]

    reminders = _fetch_reminders(calendars=calendars, completed=False)
    q = query.lower()
    matches = [r for r in reminders if q in (r.title() or "").lower()]

    if not matches:
        return {"error": f"No incomplete reminders found matching: {query}"}
    if len(matches) > 1:
        return {
            "error": "Multiple reminders match. Be more specific.",
            "matches": [{"name": r.title(), "list": r.calendar().title()} for r in matches],
        }

    r = matches[0]
    r.setCompleted_(True)
    ok, error = _store.saveReminder_commit_error_(r, True, None)
    if not ok:
        return {"error": str(error)}

    result = _serialize_reminder(r)
    result["updated"] = True
    return result


@mcp.tool()
def delete_reminder(query: str, list_name: Optional[str] = None) -> dict:
    """Delete a reminder by name search. If multiple match, returns the list."""
    _ensure_access()
    calendars = None
    if list_name:
        cal = _find_calendar(list_name)
        if not cal:
            return {"error": f"List not found: {list_name}"}
        calendars = [cal]

    reminders = _fetch_reminders(calendars=calendars)
    q = query.lower()
    matches = [r for r in reminders if q in (r.title() or "").lower()]

    if not matches:
        return {"error": f"No reminders found matching: {query}"}
    if len(matches) > 1:
        return {
            "error": "Multiple reminders match. Be more specific.",
            "matches": [{"name": r.title(), "list": r.calendar().title()} for r in matches],
        }

    r = matches[0]
    name = r.title()
    list_title = r.calendar().title()
    ok, error = _store.removeReminder_commit_error_(r, True, None)
    if not ok:
        return {"error": str(error)}

    return {"deleted": True, "name": name, "list": list_title}


@mcp.tool()
def edit_reminder(
    query: str,
    list_name: Optional[str] = None,
    new_name: Optional[str] = None,
    due: Optional[str] = None,
    notes: Optional[str] = None,
    priority: Optional[str] = None,
    mark_incomplete: bool = False,
) -> dict:
    """Edit a reminder. Use due='clear' or notes='clear' to remove values."""
    _ensure_access()
    calendars = None
    if list_name:
        cal = _find_calendar(list_name)
        if not cal:
            return {"error": f"List not found: {list_name}"}
        calendars = [cal]

    reminders = _fetch_reminders(calendars=calendars)
    q = query.lower()
    matches = [r for r in reminders if q in (r.title() or "").lower()]

    if not matches:
        return {"error": f"No reminders found matching: {query}"}
    if len(matches) > 1:
        return {
            "error": "Multiple reminders match. Be more specific.",
            "matches": [{"name": r.title(), "list": r.calendar().title()} for r in matches],
        }

    r = matches[0]
    if new_name:
        r.setTitle_(new_name)
    if notes == "clear":
        r.setNotes_("")
    elif notes:
        r.setNotes_(notes)
    if due == "clear":
        r.setDueDateComponents_(None)
    elif due:
        nsdate = _iso_to_ns_date(due)
        cal_obj = EventKit.NSCalendar.currentCalendar()
        components = cal_obj.components_fromDate_(
            EventKit.NSCalendarUnitYear
            | EventKit.NSCalendarUnitMonth
            | EventKit.NSCalendarUnitDay
            | EventKit.NSCalendarUnitHour
            | EventKit.NSCalendarUnitMinute
            | EventKit.NSCalendarUnitSecond,
            nsdate,
        )
        r.setDueDateComponents_(components)
    if priority and priority in PRIORITY_REVERSE:
        r.setPriority_(PRIORITY_REVERSE[priority])
    if mark_incomplete:
        r.setCompleted_(False)

    ok, error = _store.saveReminder_commit_error_(r, True, None)
    if not ok:
        return {"error": str(error)}

    result = _serialize_reminder(r)
    result["updated"] = True
    return result


@mcp.tool()
def move_reminder(query: str, to_list: str, from_list: Optional[str] = None) -> dict:
    """Move a reminder to a different list."""
    _ensure_access()
    target_cal = _find_calendar(to_list)
    if not target_cal:
        return {"error": f"Target list not found: {to_list}"}

    calendars = None
    if from_list:
        cal = _find_calendar(from_list)
        if not cal:
            return {"error": f"Source list not found: {from_list}"}
        calendars = [cal]

    reminders = _fetch_reminders(calendars=calendars)
    q = query.lower()
    matches = [r for r in reminders if q in (r.title() or "").lower()]

    if not matches:
        return {"error": f"No reminders found matching: {query}"}
    if len(matches) > 1:
        return {
            "error": "Multiple reminders match. Be more specific.",
            "matches": [{"name": r.title(), "list": r.calendar().title()} for r in matches],
        }

    r = matches[0]
    old_list = r.calendar().title()
    r.setCalendar_(target_cal)
    ok, error = _store.saveReminder_commit_error_(r, True, None)
    if not ok:
        return {"error": str(error)}

    result = _serialize_reminder(r)
    result["moved"] = True
    result["from_list"] = old_list
    return result


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
