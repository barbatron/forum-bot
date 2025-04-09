import os
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from listeners import register_listeners

logging.basicConfig(level=logging.DEBUG)

from dotenv import load_dotenv

load_dotenv()  # take environment variables


# Initialization
app = App(token=os.environ.get("SLACK_BOT_USER_OAUTH_TOKEN"))

# Register Listeners
register_listeners(app)

# Start Bolt app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_LEVEL_TOKEN")).start()
