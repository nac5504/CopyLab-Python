"""
CopyLab Python SDK (Client)

A lightweight Python SDK for integrating with the CopyLab notification system.
Uses HTTP API calls to the CopyLab Cloud Functions.

Usage:
    from copylab_client import CopyLab
    
    # Configure
    CopyLab.configure(api_key="cl_yourapp_xxx...")
    CopyLab.identify(user_id="user123")
    
    # Generate notification
    result = CopyLab.generate_notification(
        placement_id="welcome_message",
        variables={"user_name": "John"}
    )
    
    # Topic subscriptions
    CopyLab.subscribe_to_topic("daily_updates")
    
    # Analytics
    CopyLab.log_app_open()
"""

import requests
from typing import Optional, Dict, Any, List


class CopyLabError(Exception):
    """Base exception for CopyLab SDK errors."""
    pass


class CopyLab:
    """CopyLab SDK - Static methods for notification management."""
    
    _api_key: Optional[str] = None
    _user_id: Optional[str] = None
    _base_url: str = "https://us-central1-copylab-3f220.cloudfunctions.net"
    _timeout: int = 30
    
    @classmethod
    def configure(cls, api_key: str, base_url: Optional[str] = None):
        """
        Configure the CopyLab SDK with your API key.
        
        Args:
            api_key: Your CopyLab API key (starts with cl_)
            base_url: Optional custom API base URL
        """
        cls._api_key = api_key
        if base_url:
            cls._base_url = base_url
        print(f"✅ CopyLab: Configured with API Key: {api_key[:15]}...")
    
    @classmethod
    def identify(cls, user_id: str):
        """
        Identify the current user.
        
        Args:
            user_id: Your user's unique ID
        """
        cls._user_id = user_id
        print(f"👤 CopyLab: Identified user: {user_id}")
    
    @classmethod
    def logout(cls):
        """Clear the identified user."""
        cls._user_id = None
        print("👤 CopyLab: Logged out user")
    
    @classmethod
    def _make_request(
        cls,
        endpoint: str,
        method: str = "POST",
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make an API request to CopyLab Cloud Functions."""
        if not cls._api_key:
            raise CopyLabError("CopyLab not configured. Call CopyLab.configure(api_key=...) first.")
        
        url = f"{cls._base_url}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": cls._api_key
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=cls._timeout)
            else:
                response = requests.post(url, headers=headers, json=body, timeout=cls._timeout)
            
            data = response.json()
            
            if "error" in data:
                raise CopyLabError(f"API Error: {data['error']}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise CopyLabError(f"Request failed: {e}")
    
    # =========================================================================
    # Notification Generation
    # =========================================================================
    
    @classmethod
    def generate_notification(
        cls,
        placement_id: str,
        variables: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        fallback_title: Optional[str] = None,
        fallback_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a notification from a template.
        
        Args:
            placement_id: The notification placement ID (e.g., "welcome_message")
            variables: Template variables to substitute
            data: Additional data payload
            fallback_title: Fallback title if no template found
            fallback_message: Fallback message if no template found
            
        Returns:
            Dict with 'title', 'message', 'data', 'template_used', 'template_name'
        """
        body = {
            "placement_id": placement_id,
            "variables": variables or {},
            "data": data or {}
        }
        
        if fallback_title:
            body["fallback_title"] = fallback_title
        if fallback_message:
            body["fallback_message"] = fallback_message
        
        return cls._make_request("generate_notification", body=body)
    
    # =========================================================================
    # Topic Subscriptions
    # =========================================================================
    
    @classmethod
    def get_topic_subscribers(cls, topic_id: str) -> List[str]:
        """
        Get list of user IDs subscribed to a topic.
        
        Args:
            topic_id: The topic ID
            
        Returns:
            List of subscriber user IDs
        """
        result = cls._make_request(
            "get_topic_subscribers",
            method="GET",
            params={"topic_id": topic_id}
        )
        return result.get("subscriber_ids", [])
    
    @classmethod
    def subscribe_to_topic(cls, topic_id: str, user_id: Optional[str] = None):
        """
        Subscribe a user to a topic.
        
        Args:
            topic_id: The topic ID
            user_id: User ID (uses identified user if not provided)
        """
        body = {
            "topic_id": topic_id,
            "user_id": user_id or cls._user_id
        }
        
        if not body["user_id"]:
            raise CopyLabError("No user_id provided and no user identified. Call CopyLab.identify() first.")
        
        cls._make_request("subscribe_to_topic", body=body)
        print(f"📊 CopyLab: Subscribed to topic {topic_id}")
    
    @classmethod
    def unsubscribe_from_topic(cls, topic_id: str, user_id: Optional[str] = None):
        """
        Unsubscribe a user from a topic.
        
        Args:
            topic_id: The topic ID
            user_id: User ID (uses identified user if not provided)
        """
        body = {
            "topic_id": topic_id,
            "user_id": user_id or cls._user_id
        }
        
        if not body["user_id"]:
            raise CopyLabError("No user_id provided and no user identified. Call CopyLab.identify() first.")
        
        cls._make_request("unsubscribe_from_topic", body=body)
        print(f"📊 CopyLab: Unsubscribed from topic {topic_id}")
    
    # =========================================================================
    # Analytics
    # =========================================================================
    
    @classmethod
    def log_push_open(
        cls,
        user_id: Optional[str] = None,
        notification_id: Optional[str] = None,
        placement_id: Optional[str] = None,
        template_id: Optional[str] = None,
        platform: str = "python"
    ):
        """
        Log a push notification open event.
        
        Args:
            user_id: User ID (uses identified user if not provided)
            notification_id: The notification ID
            placement_id: The placement ID
            template_id: The template ID
            platform: Platform identifier
        """
        body = {
            "user_id": user_id or cls._user_id,
            "platform": platform
        }
        
        if not body["user_id"]:
            raise CopyLabError("No user_id provided and no user identified.")
        
        if notification_id:
            body["notification_id"] = notification_id
        if placement_id:
            body["placement_id"] = placement_id
        if template_id:
            body["template_id"] = template_id
        
        cls._make_request("log_push_open", body=body)
        print("📊 CopyLab: Logged push_open event")
    
    @classmethod
    def log_app_open(cls, user_id: Optional[str] = None, platform: str = "python"):
        """
        Log an app open event.
        
        Args:
            user_id: User ID (uses identified user if not provided)
            platform: Platform identifier
        """
        body = {
            "user_id": user_id or cls._user_id,
            "platform": platform
        }
        
        if not body["user_id"]:
            raise CopyLabError("No user_id provided and no user identified.")
        
        cls._make_request("log_app_open", body=body)
        print("📱 CopyLab: Logged app open")
    
    @classmethod
    def sync_notification_permission(
        cls,
        notification_status: str,
        user_id: Optional[str] = None,
        platform: str = "python"
    ):
        """
        Sync notification permission status.
        
        Args:
            notification_status: Permission status (e.g., "authorized", "denied")
            user_id: User ID (uses identified user if not provided)
            platform: Platform identifier
        """
        body = {
            "user_id": user_id or cls._user_id,
            "notification_status": notification_status,
            "platform": platform
        }
        
        if not body["user_id"]:
            raise CopyLabError("No user_id provided and no user identified.")
        
        cls._make_request("sync_notification_permission", body=body)
        print(f"📊 CopyLab: Synced notification status: {notification_status}")
