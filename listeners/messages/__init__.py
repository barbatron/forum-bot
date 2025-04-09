import re

from slack_bolt import App
from .sample_message import sample_message_callback
# No longer using direct message handler
# from .direct_message import direct_message_callback


# To receive messages from a channel or dm your app must be a member!
def register(app: App):
    app.message(re.compile("(hi|hello|hey)"))(sample_message_callback)
    
    # No longer registering direct message handler since we're using slash commands instead
    # app.message()(direct_message_callback)
