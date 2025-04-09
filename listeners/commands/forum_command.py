import re
import datetime
import threading
from logging import Logger

from slack_bolt import Ack, Respond
from slack_sdk import WebClient

from listeners.data_store import TopicGatheringStore


def announce_forum_results(client: WebClient, channel_id: str, topics: list):
    """Announce forum results to the channel."""
    if not topics:
        client.chat_postMessage(
            channel=channel_id, text="📝 *Topic gathering has ended* 📝\nNo topics were collected during this session."
        )
        return

    # Format topics for display
    topics_text = []
    for i, msg in enumerate(topics, 1):
        topics_text.append(f"{i}. <@{msg.user_id}>: {msg.text}")

    formatted_topics = "\n".join(topics_text)

    client.chat_postMessage(
        channel=channel_id, text=f"📝 *Topic gathering has ended* 📝\n\n*Collected Topics:*\n{formatted_topics}"
    )


def handle_expiry(client: WebClient, logger: Logger):
    """Handle expiry of topic gathering session."""
    store = TopicGatheringStore.get_instance()
    expiry_result = store.check_expiry()

    if expiry_result:
        count, channel_id, messages = expiry_result
        if channel_id:
            announce_forum_results(client, channel_id, messages)
            logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")


def schedule_expiry(duration_minutes: int, client: WebClient, logger: Logger):
    """Schedule a timer to check for expiry after the specified duration."""
    # Schedule the expiry check to run after the duration
    seconds = duration_minutes * 60
    timer = threading.Timer(seconds, handle_expiry, args=[client, logger])
    timer.daemon = True  # Allow the timer thread to exit when the main program exits
    timer.start()

    # Store the timer reference so it can be canceled if needed
    store = TopicGatheringStore.get_instance()
    store.current_timer = timer


def forum_command_callback(command, ack: Ack, respond: Respond, client: WebClient, logger: Logger):
    try:
        ack()

        # Parse command text
        command_text = command.get("text", "").strip()
        store = TopicGatheringStore.get_instance()

        # Check if a previously active session has expired
        expiry_result = store.check_expiry()
        if expiry_result:
            count, channel_id, messages = expiry_result
            if channel_id:
                announce_forum_results(client, channel_id, messages)
                logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")

        if re.match(r"start\s*(\d+)?", command_text):
            # Extract duration if provided
            match = re.match(r"start\s*(\d+)?", command_text)
            duration = int(match.group(1)) if match.group(1) else 30

            # Check if already active
            if store.is_active():
                respond("Topic gathering is already active!")
                return

            # Start topic gathering and store the channel ID
            channel_id = command.get("channel_id")
            end_time = store.start_gathering(duration, channel_id)

            # Schedule the expiry timer
            schedule_expiry(duration, client, logger)

            respond(
                f"Topic gathering has started! I'll collect topics for {duration} minutes (until {end_time.strftime('%H:%M:%S')}). Use `/forum suggest your topic here` to submit topics."
            )

            # Announce in the channel that topic gathering has started
            client.chat_postMessage(
                channel=channel_id,
                text=f"📢 *Topic gathering has started!* 📢\nUse `/forum suggest your topic here` to submit topics in the next {duration} minutes.",
            )

        elif command_text == "stop":
            if not store.is_active():
                respond("Topic gathering is not currently active.")
                return

            # Cancel any scheduled timer
            if hasattr(store, "current_timer") and store.current_timer:
                store.current_timer.cancel()
                store.current_timer = None

            count, channel_id, messages = store.stop_gathering()
            respond(f"Topic gathering has ended. Collected {count} topics.")

            # Announce the collected topics in the channel
            if channel_id:
                announce_forum_results(client, channel_id, messages)

        elif command_text == "status":
            if store.is_active():
                time_left = store.end_time - datetime.datetime.now()
                minutes_left = int(time_left.total_seconds() / 60)
                respond(
                    f"Topic gathering is active with {minutes_left} minutes remaining. {len(store.get_messages())} topics collected so far."
                )
            else:
                respond("No active topic gathering session.")

        elif command_text.startswith("suggest "):
            # Check if a previously active session has expired
            expiry_result = store.check_expiry()
            if expiry_result:
                count, channel_id, messages = expiry_result
                if channel_id:
                    announce_forum_results(client, channel_id, messages)
                    logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")
                respond("The topic gathering session has expired. Your topic was not recorded.")
                return

            if not store.is_active():
                respond("Topic gathering is not currently active. Ask an admin to start a topic gathering session first.")
                return

            # Get the text after "suggest "
            topic_text = command_text[8:].strip()
            if not topic_text:
                respond("Please provide a topic to suggest.")
                return

            # Store the topic suggestion
            user_id = command.get("user_id")
            store.add_message(user_id, topic_text)

            # Provide feedback (visible only to the command issuer)
            respond(f"Thank you! Your topic has been recorded: '{topic_text}'")

        else:
            respond(
                "Unknown command. Available commands:\n• `/forum start [minutes]` - Start topic gathering\n• `/forum stop` - End topic gathering\n• `/forum status` - Check status\n• `/forum suggest your topic here` - Submit a topic"
            )

    except Exception as e:
        logger.error(f"Error processing forum command: {e}")
        respond("Sorry, something went wrong processing that command.")
