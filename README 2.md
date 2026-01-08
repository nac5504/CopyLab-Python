# CopyLab Python SDK

A lightweight Python SDK for integrating with the CopyLab notification system using secure API calls.

## Installation

```bash
pip install -e /path/to/python_sdk
```

Or with pip from git:
```bash
pip install git+https://github.com/nac5504/CopyLab.git#subdirectory=python_sdk
```

## Usage

```python
from CopyLab import CopyLab

# Configure with your API key
CopyLab.configure(api_key="cl_yourapp_xxxx...")

# Identify user (optional but recommended)
CopyLab.identify(user_id="user123")

# Generate a notification
result = CopyLab.generate_notification(
    placement_id="welcome_message",
    variables={"user_name": "John"}
)
print(result["title"])   # "Welcome, John!"
print(result["message"]) # "We're glad you're here."

# Topic subscriptions
CopyLab.subscribe_to_topic("daily_updates")
CopyLab.unsubscribe_from_topic("daily_updates")
subscribers = CopyLab.get_topic_subscribers("daily_updates")

# Analytics
CopyLab.log_app_open()
CopyLab.log_push_open(notification_id="notif_123")
```
