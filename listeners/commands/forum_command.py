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


def announce_voting_start(
    client: WebClient, channel_id: str, store: TopicGatheringStore, voting_duration: int, end_time: datetime.datetime
):
    """Announce the start of voting period."""
    topics_text = store.format_topics_for_voting()

    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"🗳️ *Voting has started!* 🗳️\n\n"
            f"You have {voting_duration} minutes to vote (until {end_time.strftime('%H:%M:%S')}).\n\n"
            f"*How to vote:*\nUse `/forum vote <number>` to vote for a topic. You can vote for multiple topics.\n\n"
            f"*Available Topics:*\n{topics_text}"
        ),
    )


def announce_voting_results(client: WebClient, channel_id: str, store: TopicGatheringStore):
    """Announce the results of voting."""
    results_text = store.format_voting_results()

    client.chat_postMessage(
        channel=channel_id, text=f"🏆 *Voting Results* 🏆\n\nHere are the final results, sorted by votes:\n\n{results_text}"
    )


def handle_expiry(client: WebClient, logger: Logger):
    """Handle expiry of topic gathering session and start voting period."""
    store = TopicGatheringStore.get_instance()
    expiry_result = store.check_expiry()

    if expiry_result:
        count, channel_id, messages = expiry_result
        if channel_id and messages:
            # Announce topic gathering ended
            announce_forum_results(client, channel_id, messages)
            logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")

            # Start voting period if we have topics and a configured voting duration
            if messages and hasattr(store, "voting_duration_minutes"):
                voting_duration = store.voting_duration_minutes
                end_time = store.start_voting(voting_duration)
                announce_voting_start(client, channel_id, store, voting_duration, end_time)
                logger.info(f"Voting period started for {voting_duration} minutes.")

                # Schedule the end of voting period
                schedule_voting_expiry(voting_duration, client, logger)


def handle_voting_expiry(client: WebClient, logger: Logger):
    """Handle expiry of voting period."""
    store = TopicGatheringStore.get_instance()
    expiry_result = store.check_voting_expiry()

    if expiry_result:
        channel_id, messages = expiry_result
        if channel_id:
            # Announce voting results
            announce_voting_results(client, channel_id, store)
            logger.info("Voting period automatically ended due to time expiry.")


def schedule_expiry(duration_minutes: int, client: WebClient, logger: Logger):
    """Schedule a timer to check for expiry after the specified duration."""
    seconds = duration_minutes * 60
    timer = threading.Timer(seconds, handle_expiry, args=[client, logger])
    timer.daemon = True
    timer.start()

    store = TopicGatheringStore.get_instance()
    store.current_timer = timer


def schedule_voting_expiry(duration_minutes: int, client: WebClient, logger: Logger):
    """Schedule a timer to check for voting expiry after the specified duration."""
    seconds = duration_minutes * 60
    timer = threading.Timer(seconds, handle_voting_expiry, args=[client, logger])
    timer.daemon = True
    timer.start()

    store = TopicGatheringStore.get_instance()
    store.current_voting_timer = timer


def forum_command_callback(command, ack: Ack, respond: Respond, client: WebClient, logger: Logger):
    try:
        ack()

        command_text = command.get("text", "").strip()
        store = TopicGatheringStore.get_instance()

        # Check if a previously active session has expired
        expiry_result = store.check_expiry()
        if expiry_result:
            count, channel_id, messages = expiry_result
            if channel_id and messages:
                announce_forum_results(client, channel_id, messages)
                logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")

                # Start voting period if we have topics and a configured voting duration
                if messages and hasattr(store, "voting_duration_minutes"):
                    voting_duration = store.voting_duration_minutes
                    end_time = store.start_voting(voting_duration)
                    announce_voting_start(client, channel_id, store, voting_duration, end_time)
                    logger.info(f"Voting period started for {voting_duration} minutes.")

                    # Schedule the end of voting period
                    schedule_voting_expiry(voting_duration, client, logger)

        # Also check if a voting period has expired
        voting_expiry_result = store.check_voting_expiry()
        if voting_expiry_result:
            channel_id, _ = voting_expiry_result
            if channel_id:
                announce_voting_results(client, channel_id, store)
                logger.info("Voting period automatically ended due to time expiry.")

        # Handle start command with optional parameters for topic gathering and voting durations
        start_match = re.match(r"start(?:\s+(\d+))?(?:\s+(\d+))?", command_text)
        if start_match:
            # Extract durations if provided
            gathering_duration = int(start_match.group(1)) if start_match.group(1) else 30
            voting_duration = int(start_match.group(2)) if start_match.group(2) else 15

            # Check if already active
            if store.is_active() or store.is_voting_active():
                respond("A topic gathering or voting session is already active!")
                return

            # Start topic gathering and store the channel ID
            channel_id = command.get("channel_id")
            end_time = store.start_gathering(gathering_duration, voting_duration, channel_id)

            # Schedule the expiry timer
            schedule_expiry(gathering_duration, client, logger)

            respond(
                f"Topic gathering has started! I'll collect topics for {gathering_duration} minutes (until {end_time.strftime('%H:%M:%S')}).\n"
                f"Afterwards, there will be a {voting_duration} minute voting period.\n"
                f"Use `/forum suggest your topic here` to submit topics."
            )

            # Announce in the channel that topic gathering has started
            client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"📢 *Topic gathering has started!* 📢\n"
                    f"Use `/forum suggest your topic here` to submit topics in the next {gathering_duration} minutes.\n"
                    f"This will be followed by a {voting_duration} minute voting period."
                ),
            )

        elif command_text == "stop":
            if store.is_active():
                count, channel_id, messages = store.stop_gathering()
                respond(f"Topic gathering has ended. Collected {count} topics.")

                # Announce the collected topics in the channel
                if channel_id:
                    announce_forum_results(client, channel_id, messages)

                    # Start voting period if we have topics
                    if messages:
                        voting_duration = store.voting_duration_minutes if hasattr(store, "voting_duration_minutes") else 15
                        end_time = store.start_voting(voting_duration)
                        announce_voting_start(client, channel_id, store, voting_duration, end_time)
                        schedule_voting_expiry(voting_duration, client, logger)

            elif store.is_voting_active():
                channel_id, _ = store.stop_voting()
                respond("Voting period has ended.")

                # Announce the voting results in the channel
                if channel_id:
                    announce_voting_results(client, channel_id, store)

            else:
                respond("No active topic gathering or voting session.")

        elif command_text == "status":
            if store.is_active():
                time_left = store.end_time - datetime.datetime.now()
                minutes_left = max(0, int(time_left.total_seconds() / 60))
                respond(
                    f"Topic gathering is active with {minutes_left} minutes remaining. {len(store.get_messages())} topics collected so far."
                )
            elif store.is_voting_active():
                time_left = store.voting_end_time - datetime.datetime.now()
                minutes_left = max(0, int(time_left.total_seconds() / 60))
                respond(f"Voting is active with {minutes_left} minutes remaining.")
            else:
                respond("No active topic gathering or voting session.")

        elif command_text.startswith("suggest "):
            # Not allowed during voting period
            if store.is_voting_active():
                respond(
                    "Topic gathering has ended. We're now in the voting period. Use `/forum vote <number>` to vote for topics."
                )
                return

            # Check if a previously active session has expired
            expiry_result = store.check_expiry()
            if expiry_result:
                count, channel_id, messages = expiry_result
                if channel_id:
                    announce_forum_results(client, channel_id, messages)
                    logger.info(f"Forum automatically ended due to time expiry. Collected {count} topics.")

                    # Start voting period if we have topics
                    if messages and hasattr(store, "voting_duration_minutes"):
                        voting_duration = store.voting_duration_minutes
                        end_time = store.start_voting(voting_duration)
                        announce_voting_start(client, channel_id, store, voting_duration, end_time)
                        logger.info(f"Voting period started for {voting_duration} minutes.")
                        schedule_voting_expiry(voting_duration, client, logger)

                respond(
                    "The topic gathering session has expired. Your topic was not recorded. We're now in the voting period."
                )
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

        elif command_text.startswith("vote "):
            if not store.is_voting_active():
                respond("There is no active voting session.")
                return

            # Get the topic number after "vote "
            try:
                topic_num = int(command_text[5:].strip())
                topic_idx = topic_num - 1  # Convert to 0-based index

                if topic_idx < 0 or topic_idx >= len(store.messages):
                    respond(f"Invalid topic number. Please use a number between 1 and {len(store.messages)}.")
                    return

                # Record the vote
                user_id = command.get("user_id")
                store.add_vote(user_id, topic_idx)

                # Provide feedback
                topic = store.messages[topic_idx]
                respond(
                    f'You voted for topic {topic_num}: "{topic.text}" by <@{topic.user_id}>. '
                    + f"This topic now has {store.get_vote_count(topic_idx)} vote(s)."
                )

            except ValueError:
                respond("Please provide a valid topic number to vote for. Example: `/forum vote 3`")

        else:
            respond(
                "Unknown command. Available commands:\n"
                "• `/forum start [topic_minutes] [voting_minutes]` - Start topic gathering\n"
                "• `/forum stop` - End current session\n"
                "• `/forum status` - Check status\n"
                "• `/forum suggest your topic here` - Submit a topic\n"
                "• `/forum vote number` - Vote for a topic"
            )

    except Exception as e:
        logger.error(f"Error processing forum command: {e}")
        respond("Sorry, something went wrong processing that command.")
