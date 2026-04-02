from botbuilder.core import ActivityHandler, TurnContext

class MyBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text
        await turn_context.send_activity(f"You said: {user_text}")
