import re
import datetime
from logging import Logger

from slack_bolt import Ack, Respond
from slack_sdk import WebClient

from listeners.data_store import TopicGatheringStore


def forum_command_callback(command, ack: Ack, respond: Respond, client: WebClient, logger: Logger):
    try:
        ack()
        
        # Parse command text
        command_text = command.get("text", "").strip()
        store = TopicGatheringStore.get_instance()
        
        if re.match(r"start\s*(\d+)?", command_text):
            # Extract duration if provided
            match = re.match(r"start\s*(\d+)?", command_text)
            duration = int(match.group(1)) if match.group(1) else 30
            
            # Check if already active
            if store.is_active():
                respond("Topic gathering is already active!")
                return
            
            # Start topic gathering
            end_time = store.start_gathering(duration)
            respond(f"Topic gathering has started! I'll collect topics for {duration} minutes (until {end_time.strftime('%H:%M:%S')}). Use `/forum suggest your topic here` to submit topics.")
            
            # Announce in the channel that topic gathering has started
            client.chat_postMessage(
                channel=command["channel_id"],
                text=f"📢 *Topic gathering has started!* 📢\nUse `/forum suggest your topic here` to submit topics in the next {duration} minutes."
            )
            
        elif command_text == "stop":
            if not store.is_active():
                respond("Topic gathering is not currently active.")
                return
                
            count = store.stop_gathering()
            respond(f"Topic gathering has ended. Collected {count} topics.")
            
        elif command_text == "status":
            if store.is_active():
                time_left = store.end_time - datetime.datetime.now()
                minutes_left = int(time_left.total_seconds() / 60)
                respond(f"Topic gathering is active with {minutes_left} minutes remaining. {len(store.get_messages())} topics collected so far.")
            else:
                respond("No active topic gathering session.")
                
        elif command_text.startswith("suggest "):
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
            respond("Unknown command. Available commands:\n• `/forum start [minutes]` - Start topic gathering\n• `/forum stop` - End topic gathering\n• `/forum status` - Check status\n• `/forum suggest your topic here` - Submit a topic")
            
    except Exception as e:
        logger.error(f"Error processing forum command: {e}")
        respond("Sorry, something went wrong processing that command.")
