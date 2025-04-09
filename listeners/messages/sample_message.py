from logging import Logger

from slack_bolt import BoltContext, Say


def sample_message_callback(context: BoltContext, say: Say, logger: Logger):
    try:
        # greeting = context["matches"][0]
        say(f"talk to me again and I'll fucking kill you, {say.channel.capitalize()}")
    except Exception as e:
        logger.error(e)
