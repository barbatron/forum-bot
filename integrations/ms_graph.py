import os
import json
import logging
import requests
import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MSGraphAPI:
    """Microsoft Graph API integration for Outlook Calendar events"""

    def __init__(self):
        # Load configuration from environment variables
        self.tenant_id = os.environ.get("MS_TENANT_ID")
        self.client_id = os.environ.get("MS_CLIENT_ID")
        self.client_secret = os.environ.get("MS_CLIENT_SECRET")
        self.user_id = os.environ.get("MS_USER_ID", "me")
        self.access_token = None
        self.token_expiration = None

    def _get_access_token(self) -> str:
        """Get or refresh the access token for the Microsoft Graph API"""
        # Check if token is valid
        if (
            self.access_token
            and self.token_expiration
            and self.token_expiration > datetime.datetime.now()
        ):
            return self.access_token

        # Get new token
        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )

        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        response = requests.post(token_url, data=token_data)
        response_data = response.json()

        if "access_token" not in response_data:
            logger.error(f"Failed to get access token: {response_data}")
            raise Exception("Failed to authenticate with Microsoft Graph API")

        self.access_token = response_data["access_token"]
        # Set token expiration (subtract 5 minutes as a safety margin)
        self.token_expiration = datetime.datetime.now() + datetime.timedelta(
            seconds=response_data["expires_in"] - 300
        )

        return self.access_token

    def create_calendar_event(
        self,
        subject: str,
        body: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        attendees: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a calendar event using Microsoft Graph API

        Args:
            subject: Event subject/title
            body: Event description
            start_time: Event start time (datetime object)
            end_time: Event end time (datetime object)
            attendees: List of email addresses for attendees

        Returns:
            Dict with event details or None if creation failed
        """
        token = self._get_access_token()

        # Format event data
        event_data = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "UTC",
            },  # You may want to make this configurable
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "UTC",
            },  # You may want to make this configurable
            "attendees": [
                {
                    "emailAddress": {"address": email, "name": ""},
                    "type": "required",
                }  # Graph API will resolve names
                for email in attendees
            ],
        }

        # API endpoint
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/calendar/events"

        # Headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(event_data))

            if response.status_code >= 200 and response.status_code < 300:
                return response.json()
            else:
                logger.error(
                    f"Failed to create event: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None

    def get_event_link(self, event_id: str) -> str:
        """
        Get the web link to an event

        Args:
            event_id: The ID of the event

        Returns:
            String URL to the event in Outlook Web
        """
        token = self._get_access_token()

        url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/calendar/events/{event_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return data.get("webLink", "")
            else:
                logger.error(
                    f"Failed to get event link: {response.status_code} - {response.text}"
                )
                return ""

        except Exception as e:
            logger.error(f"Error getting event link: {str(e)}")
            return ""
