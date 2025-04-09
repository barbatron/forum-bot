from slack_bolt import App
from .sample_command import sample_command_callback
from .forum_command import forum_command_callback


def register(app: App):
    app.command("/sample-command")(sample_command_callback)
    app.command("/forum")(forum_command_callback)
