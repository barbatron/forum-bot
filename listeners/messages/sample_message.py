from logging import Logger

from slack_bolt import BoltContext, Say


def sample_message_callback(context: BoltContext, say: Say, logger: Logger):
    try:
        greeting = context.matches[0]
        say(f"Hi there! I noticed you said '{greeting}'.")
    except Exception as e:
        logger.error(e)
