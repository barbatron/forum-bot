from logging import Logger

from slack_bolt import BoltContext, Say
from slack_sdk import WebClient

from listeners.data_store import TopicGatheringStore


def direct_message_callback(
    context: BoltContext, say: Say, client: WebClient, message: dict, logger: Logger
):
    try:
        store = TopicGatheringStore.get_instance()

        # Only process if topic gathering is active
        if not store.is_active():
            return

        # Check if this is a DM (im) channel
        if message.get("channel_type") != "im":
            return

        user_id = message.get("user")
        text = message.get("text", "").strip()

        if not text:
            return

        # Store the message
        if store.add_message(user_id, text):
            say(f"Thank you! Your topic has been recorded: '{text}'")

    except Exception as e:
        logger.error(f"Error processing direct message: {e}")
