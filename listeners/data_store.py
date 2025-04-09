import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TopicMessage:
    user_id: str
    text: str
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


class TopicGatheringStore:
    """Store for managing topic gathering sessions."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TopicGatheringStore()
        return cls._instance

    def __init__(self):
        self.active = False
        self.end_time = None
        self.channel_id = None  # Store the channel where the forum was started
        self.messages: List[TopicMessage] = []
        self.current_timer = None  # Store reference to the active timer
        # Map from user_id to their conversation ID with the bot
        self.user_conversations: Dict[str, str] = {}

    def start_gathering(self, duration_minutes: int = 30, channel_id: str = None):
        """Start a topic gathering session for the specified duration."""
        self.active = True
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        self.channel_id = channel_id
        self.messages = []
        return self.end_time

    def stop_gathering(self):
        """Stop the current topic gathering session."""
        self.active = False
        stored_channel = self.channel_id
        self.channel_id = None
        stored_messages = self.messages.copy()
        self.end_time = None

        # Cancel any existing timer
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None

        return len(self.messages), stored_channel, stored_messages

    def add_message(self, user_id: str, text: str):
        """Add a message to the store."""
        if not self.is_active():
            return False

        self.messages.append(TopicMessage(user_id=user_id, text=text))
        return True

    def is_active(self):
        """Check if topic gathering is active."""
        if not self.active:
            return False

        if self.end_time and datetime.datetime.now() > self.end_time:
            # Time expired, forum should be closed
            self.active = False
            return False

        return True

    def get_messages(self):
        """Get all gathered messages."""
        return self.messages

    def check_expiry(self) -> Optional[tuple]:
        """Check if gathering has expired and return data for announcement if it has."""
        if self.active and self.end_time and datetime.datetime.now() > self.end_time:
            count, channel, messages = self.stop_gathering()
            return count, channel, messages
        return None

    def format_topics_for_display(self) -> str:
        """Format the collected topics for display in Slack."""
        if not self.messages:
            return "No topics were collected."

        result = []
        for i, msg in enumerate(self.messages, 1):
            result.append(f"{i}. <@{msg.user_id}>: {msg.text}")

        return "\n".join(result)

    def register_conversation(self, user_id: str, conversation_id: str):
        """Register a conversation ID for a user."""
        self.user_conversations[user_id] = conversation_id

    def get_conversation(self, user_id: str):
        """Get the conversation ID for a user."""
        return self.user_conversations.get(user_id)
