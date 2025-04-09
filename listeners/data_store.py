import datetime
from dataclasses import dataclass, field
from typing import Dict, List


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
        self.messages: List[TopicMessage] = []
        # Map from user_id to their conversation ID with the bot
        self.user_conversations: Dict[str, str] = {}
    
    def start_gathering(self, duration_minutes: int = 30):
        """Start a topic gathering session for the specified duration."""
        self.active = True
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        self.messages = []
        return self.end_time
    
    def stop_gathering(self):
        """Stop the current topic gathering session."""
        self.active = False
        self.end_time = None
        return len(self.messages)
    
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
        
        if datetime.datetime.now() > self.end_time:
            self.active = False
            return False
        
        return True
    
    def get_messages(self):
        """Get all gathered messages."""
        return self.messages
    
    def register_conversation(self, user_id: str, conversation_id: str):
        """Register a conversation ID for a user."""
        self.user_conversations[user_id] = conversation_id
    
    def get_conversation(self, user_id: str):
        """Get the conversation ID for a user."""
        return self.user_conversations.get(user_id)
