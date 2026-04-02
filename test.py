from meeting_scheduler import find_first_available_slot

OWNER_ID = "e1a9186a-95f7-4c66-a310-3dc324c6086a"

slot = find_first_available_slot(
    OWNER_ID,
    ["ramya@callaider.onmicrosoft.com"],
    30,
    ["2026-01-05T09:00 - 2026-01-05T12:00"]
)

print("First available slot:", slot)