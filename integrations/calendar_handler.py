import os
import logging
from typing import List, Dict, Any

from integrations.ms_graph import MSGraphAPI
from integrations.time_slots import TimeSlotManager
from listeners.data_store import TopicMessage

logger = logging.getLogger(__name__)


class CalendarEventHandler:
    """Handler for creating calendar events from forum topics"""

    def __init__(self):
        self.graph_api = MSGraphAPI()
        self.slot_manager = TimeSlotManager()
        # Get top N topics to schedule from environment variable
        self.top_topics_count = int(os.environ.get("TOP_TOPICS_COUNT", "3"))
        self.event_duration_minutes = int(
            os.environ.get("EVENT_DURATION_MINUTES", "60")
        )

    def get_user_email(self, user_id: str) -> str:
        """
        Get email address for a Slack user ID
        For simplicity, we assume Slack user ID + "@example.com"
        In a real implementation, you would query Slack API or a mapping
        """
        # This is a simplified example - in real implementation, you would:
        # 1. Query Slack API for user email or
        # 2. Maintain a mapping between Slack IDs and emails
        return f"{user_id}@example.com"

    def create_events_for_winning_topics(
        self, topics: List[TopicMessage], votes_by_user: Dict[str, List[int]]
    ) -> List[Dict[str, Any]]:
        """
        Create calendar events for winning topics

        Args:
            topics: List of all topic messages
            votes_by_user: Dictionary mapping user IDs to the topic indices they voted for

        Returns:
            List of created event information dictionaries
        """
        # Sort topics by votes (descending)
        sorted_topics = sorted(topics, key=lambda x: x.votes, reverse=True)

        # Get the top N topics
        top_topics = sorted_topics[: self.top_topics_count]

        created_events = []

        # For each winning topic, create a calendar event
        for topic in top_topics:
            # Create reverse mapping from topic index to users who voted for it
            topic_index = topics.index(topic)
            attendee_user_ids = [
                user_id
                for user_id, voted_indices in votes_by_user.items()
                if topic_index in voted_indices
            ]

            # Add the topic creator as an attendee
            if topic.user_id not in attendee_user_ids:
                attendee_user_ids.append(topic.user_id)

            # Get email addresses for attendees
            attendee_emails = [
                self.get_user_email(user_id) for user_id in attendee_user_ids
            ]

            # Get next available time slot
            slot = self.slot_manager.get_next_slot()
            if not slot:
                logger.error("No time slots available for scheduling events")
                continue

            # Get datetimes for the slot
            try:
                start_time, end_time = self.slot_manager.get_datetime_for_slot(slot)

                # Create event subject and body
                subject = f"Forum topic: {topic.text[:50]}" + (
                    "..." if len(topic.text) > 50 else ""
                )
                body = f"""
                <h3>Forum Topic Discussion</h3>
                <p><strong>Topic:</strong> {topic.text}</p>
                <p><strong>Suggested by:</strong> <@{topic.user_id}></p>
                <p><strong>Votes received:</strong> {topic.votes}</p>
                """

                # Create the event
                event_result = self.graph_api.create_calendar_event(
                    subject=subject,
                    body=body,
                    start_time=start_time,
                    end_time=end_time,
                    attendees=attendee_emails,
                )

                if event_result:
                    # Add event information to return list
                    created_events.append(
                        {
                            "topic": topic,
                            "event_id": event_result.get("id"),
                            "event_link": event_result.get("webLink")
                            or self.graph_api.get_event_link(
                                event_result.get("id", "")
                            ),
                            "start_time": start_time,
                            "end_time": end_time,
                            "day": slot["day_of_week"],
                            "attendees": attendee_user_ids,
                        }
                    )
            except Exception as e:
                logger.error(f"Error creating event for topic '{topic.text}': {str(e)}")

        return created_events

    def format_event_announcement(self, event_info: Dict[str, Any]) -> str:
        """
        Format an event announcement for Slack

        Args:
            event_info: Dictionary with event information

        Returns:
            Formatted message text
        """
        topic = event_info["topic"]
        start_time = event_info["start_time"].strftime("%H:%M")
        end_time = event_info["end_time"].strftime("%H:%M")
        day = event_info["day"]
        event_link = event_info["event_link"]
        attendees = event_info["attendees"]

        # Format attendee list (mention users)
        attendee_mentions = [f"<@{uid}>" for uid in attendees]
        if len(attendee_mentions) > 5:
            # If many attendees, truncate the list
            attendee_text = (
                ", ".join(attendee_mentions[:5])
                + f" and {len(attendee_mentions) - 5} others"
            )
        else:
            attendee_text = ", ".join(attendee_mentions)

        message = (
            f"📅 *Calendar Event Created* 📅\n\n"
            f"*Topic:* {topic.text}\n"
            f"*When:* {day} from {start_time} to {end_time}\n"
            f"*Suggested by:* <@{topic.user_id}>\n"
            f"*Attendees:* {attendee_text}\n\n"
        )

        if event_link:
            message += f"*<{event_link}|View in Outlook Calendar>*\n"

        message += "\n_Calendar invitations have been sent to all participants._"

        return message
