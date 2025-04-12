import os
import json
import random
import datetime
from typing import Dict, List, Optional, Tuple


class TimeSlotManager:
    """Manager for time slots configuration"""

    def __init__(self, config_path: str = None):
        """
        Initialize the time slot manager

        Args:
            config_path: Path to the time slots configuration file
        """
        if config_path is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "time_slots.json")

        self.config_path = config_path
        self.slots = self._load_slots()

    def _load_slots(self) -> List[Dict]:
        """Load time slots from configuration file"""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                return config.get("slots", [])
        except Exception as e:
            print(f"Error loading time slots: {str(e)}")
            return []

    def _parse_time(self, time_str: str) -> Tuple[int, int]:
        """Parse time string into hours and minutes"""
        hours, minutes = map(int, time_str.split(":"))
        return hours, minutes

    def get_next_slot(self) -> Optional[Dict]:
        """
        Get the next available time slot

        Returns:
            Dict with day_of_week, start_time, and end_time
            Returns None if no slots are available
        """
        if not self.slots:
            return None

        # For simple implementation, just return a random slot
        return random.choice(self.slots)

    def get_datetime_for_slot(
        self, slot: Dict
    ) -> Tuple[datetime.datetime, datetime.datetime]:
        """
        Convert a slot to actual start and end datetime objects

        Args:
            slot: Dict containing day_of_week, start_time, and end_time

        Returns:
            Tuple of (start_datetime, end_datetime)
        """
        # Get current date
        today = datetime.datetime.now().date()

        # Map day names to weekday numbers (0=Monday, 6=Sunday)
        day_mapping = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }

        target_day = day_mapping.get(slot["day_of_week"])
        if target_day is None:
            raise ValueError(f"Invalid day of week: {slot['day_of_week']}")

        # Calculate days until the next occurrence of target_day
        current_weekday = today.weekday()
        days_ahead = (target_day - current_weekday) % 7
        if days_ahead == 0:  # If it's today, schedule for next week
            days_ahead = 7

        # Get the date for the event
        event_date = today + datetime.timedelta(days=days_ahead)

        # Parse start and end times
        start_hour, start_minute = self._parse_time(slot["start_time"])
        end_hour, end_minute = self._parse_time(slot["end_time"])

        # Create datetime objects
        start_datetime = datetime.datetime(
            event_date.year, event_date.month, event_date.day, start_hour, start_minute
        )

        end_datetime = datetime.datetime(
            event_date.year, event_date.month, event_date.day, end_hour, end_minute
        )

        return start_datetime, end_datetime
