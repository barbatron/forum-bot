import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict


@dataclass
class TopicMessage:
    user_id: str
    text: str
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    votes: int = 0  # Track votes for each topic


class TopicGatheringStore:
    """Store for managing topic gathering sessions."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TopicGatheringStore()
        return cls._instance

    def __init__(self):
        # Topic gathering state
        self.active = False
        self.end_time = None
        self.channel_id = None
        self.messages: List[TopicMessage] = []
        self.current_timer = None

        # Voting state
        self.voting_active = False
        self.voting_end_time = None
        self.current_voting_timer = None
        self.user_votes: Dict[str, Set[int]] = defaultdict(
            set
        )  # User ID -> set of topic indices they voted for

        # Calendar event state
        self.events_created = False
        self.calendar_events: List[Dict[str, Any]] = []

        # Misc
        self.user_conversations: Dict[str, str] = {}

    # Topic gathering methods
    def start_gathering(
        self,
        duration_minutes: int = 30,
        voting_duration_minutes: int = 15,
        channel_id: str = None,
    ):
        """Start a topic gathering session for the specified duration."""
        self.active = True
        self.voting_active = False
        self.end_time = datetime.datetime.now() + datetime.timedelta(
            minutes=duration_minutes
        )
        self.channel_id = channel_id
        self.messages = []
        self.user_votes = defaultdict(set)
        self.events_created = False
        self.calendar_events = []
        self.voting_duration_minutes = voting_duration_minutes
        return self.end_time

    def stop_gathering(self):
        """Stop the current topic gathering session."""
        self.active = False
        stored_channel = self.channel_id
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

    # Voting methods
    def start_voting(self, duration_minutes: int = 15):
        """Start a voting period."""
        self.voting_active = True
        self.voting_end_time = datetime.datetime.now() + datetime.timedelta(
            minutes=duration_minutes
        )
        return self.voting_end_time

    def stop_voting(self):
        """Stop the current voting period."""
        self.voting_active = False
        stored_channel = self.channel_id
        stored_messages = self.messages.copy()
        self.voting_end_time = None

        # Cancel any existing timer
        if self.current_voting_timer:
            self.current_voting_timer.cancel()
            self.current_voting_timer = None

        return stored_channel, stored_messages

    def is_voting_active(self):
        """Check if voting is active."""
        if not self.voting_active:
            return False

        if self.voting_end_time and datetime.datetime.now() > self.voting_end_time:
            self.voting_active = False
            return False

        return True

    def check_voting_expiry(self) -> Optional[tuple]:
        """Check if voting has expired and return data for announcement."""
        if (
            self.voting_active
            and self.voting_end_time
            and datetime.datetime.now() > self.voting_end_time
        ):
            channel, messages = self.stop_voting()
            return channel, messages
        return None

    def add_vote(self, user_id: str, topic_index: int) -> bool:
        """Add a vote for a topic."""
        if not self.is_voting_active():
            return False

        if topic_index < 0 or topic_index >= len(self.messages):
            return False

        self.user_votes[user_id].add(topic_index)
        self.messages[topic_index].votes += 1
        return True

    def get_vote_count(self, topic_index: int) -> int:
        """Get the number of votes for a topic."""
        if topic_index < 0 or topic_index >= len(self.messages):
            return 0

        return self.messages[topic_index].votes

    def get_users_by_topic_vote(self) -> Dict[int, List[str]]:
        """
        Get a mapping of topic index to users who voted for it

        Returns:
            Dict mapping topic index to list of user IDs
        """
        topic_to_users = defaultdict(list)

        for user_id, topic_indices in self.user_votes.items():
            for topic_idx in topic_indices:
                topic_to_users[topic_idx].append(user_id)

        return topic_to_users

    def store_calendar_events(self, events: List[Dict[str, Any]]):
        """Store created calendar events"""
        self.calendar_events = events
        self.events_created = True

    def get_calendar_events(self) -> List[Dict[str, Any]]:
        """Get stored calendar events"""
        return self.calendar_events

    def get_sorted_topics(self) -> List[TopicMessage]:
        """Get topics sorted by votes (descending)."""
        return sorted(self.messages, key=lambda x: x.votes, reverse=True)

    def format_topics_for_display(self) -> str:
        """Format the collected topics for display in Slack."""
        if not self.messages:
            return "No topics were collected."

        result = []
        for i, msg in enumerate(self.messages, 1):
            result.append(f"{i}. <@{msg.user_id}>: {msg.text}")

        return "\n".join(result)

    def format_topics_for_voting(self) -> str:
        """Format the topics for voting display."""
        if not self.messages:
            return "No topics available for voting."

        result = []
        for i, msg in enumerate(self.messages, 1):
            result.append(f"{i}. <@{msg.user_id}>: {msg.text}")

        return "\n".join(result)

    def format_voting_results(self) -> str:
        """Format the voting results for display."""
        if not self.messages:
            return "No topics were available for voting."

        sorted_topics = self.get_sorted_topics()

        result = []
        for i, msg in enumerate(sorted_topics, 1):
            vote_text = f"{msg.votes} vote{'s' if msg.votes != 1 else ''}"
            result.append(f"{i}. <@{msg.user_id}>: {msg.text} - *{vote_text}*")

        return "\n".join(result)

    def register_conversation(self, user_id: str, conversation_id: str):
        """Register a conversation ID for a user."""
        self.user_conversations[user_id] = conversation_id

    def get_conversation(self, user_id: str):
        """Get the conversation ID for a user."""
        return self.user_conversations.get(user_id)
