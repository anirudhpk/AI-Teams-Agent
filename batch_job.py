from unreplied_scanner import scan_unreplied_messages
from ai_engine import summarize_messages
from graph_sender import send_message
from owner_context import get_owner_context


def run_batch(hours: int = 4):
    """
    Batch job:
    - Scans 1:1 Teams chats from last `hours`
    - Identifies unreplied, actionable messages
    - Sends a concise summary to owner's bot/DM chat
    """

    # 🔹 Resolve owner dynamically
    owner_id, owner_chat_id = get_owner_context()

    if not owner_id or not owner_chat_id:
        print("❌ Owner context not initialized yet")
        return

    # 🔍 Scan unreplied messages
    actionable = scan_unreplied_messages(owner_id, hours)

    if not actionable:
        print("✅ No pending Teams messages")
        return

    # 🧠 AI summarization
    summary_points = summarize_messages(actionable)

    if not summary_points:
        print("ℹ️ No meaningful summary generated")
        return

    # 📩 Build message
    message = "🕒 <b>Teams messages pending your attention</b><br><br>"


    if summary_points.get("actionable"):
        message += "<b>🔴 Action required</b><br>"
        for point in summary_points["actionable"]:
            message += f"• {point}<br>"
        message += "<br>"

    if summary_points.get("fyi"):
        message += "<b>🟡 FYI</b><br>"
        for point in summary_points["fyi"]:
            message += f"• {point}<br>"

    # 🚀 Send summary to owner DM / bot chat
    send_message(
        chat_id=owner_chat_id,
        user_id=owner_id,
        text=message
    )

    print(f"✅ Summary sent ({len(actionable)} actionable messages)")


if __name__ == "__main__":
    run_batch()