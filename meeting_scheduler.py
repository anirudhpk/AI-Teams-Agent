import requests
from graph_sender import get_token

import requests
from datetime import datetime, timedelta, timezone
from graph_sender import get_token

GRAPH = "https://graph.microsoft.com/v1.0"


def find_first_available_slot(
    user_id,
    attendees,
    duration_minutes,
    time_windows
):
    """
    time_windows example:
    ["2026-01-05T09:00 IST - 2026-01-05T12:00 IST"]
    """

    token = get_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 👉 For now, pick FIRST window only (safe + deterministic)
    window = time_windows[0]

    # Very simple parser (you already cleaned text earlier)
    # start_str, end_str = [p.strip() for p in window.split(" - ", 1)]
    # start = start_str.strip()
    # end = end_str.strip()
    start, end = parse_simple_window(window)

    payload = {
        "schedules": attendees,
        "startTime": {
            "dateTime": start.isoformat(),
            "timeZone": "UTC"
        },
        "endTime": {
            "dateTime": end.isoformat(),
            "timeZone": "UTC"
        },
        "availabilityViewInterval": duration_minutes
    }
    print("anirudh")
    print(payload)
    r = requests.post(
        f"{GRAPH}/me/calendar/getSchedule",
        headers=headers,
        json=payload
    )
    r.raise_for_status()

    data = r.json()

    # 👉 Find first free slot
    sched = data["value"][0]

    availability = sched["availabilityView"]  # e.g. "0000"
    interval = duration_minutes  # 30 minutes

    for idx, slot in enumerate(availability):
        if slot == "0":  # FREE
            return start + timedelta(minutes=idx * interval)

    raise RuntimeError("No available time slot found")

def create_draft_event(
    user_id,
    subject,
    attendees,
    start_time,
    duration_minutes
):
    token = get_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    start_dt = start_time
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    payload = {
        "subject": subject,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "UTC"
        },
        "attendees": [
            {
                "emailAddress": {"address": a},
                "type": "required"
            }
            for a in attendees
        ]
    }

    r = requests.post(
        f"{GRAPH}/me/events",
        headers=headers,
        json=payload
    )
    r.raise_for_status()

    return r.json()["id"]

def schedule_meeting(
    user_id,
    attendees,
    subject,
    duration_minutes,
    time_windows
):

    # (You already implemented availability logic – reuse it)
    start_time = find_first_available_slot(
        user_id, attendees, duration_minutes, time_windows
    )

    create_draft_event(
        user_id=user_id,
        subject=subject,
        attendees=attendees,
        start_time=start_time,
        duration_minutes=duration_minutes
    )

    return (
        "Meeting created in Outlook.\n"
        f"Subject: {subject}\n"
        f"Start: {start_time}\n"
        "Good luck with the meeting."
    )

def parse_simple_window(window):
    # window = "10 - 12"
    start_hour, end_hour = [int(p.strip()) for p in window.split("-")]

    today = datetime.now().date()

    start = datetime.combine(today, datetime.min.time()) + timedelta(hours=start_hour)
    end   = datetime.combine(today, datetime.min.time()) + timedelta(hours=end_hour)

    start = start.replace(tzinfo=timezone.utc)
    end   = end.replace(tzinfo=timezone.utc)

    return start, end

