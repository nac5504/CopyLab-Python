# CopyLab Python SDK

A Python SDK for generating dynamic notification content from CopyLab templates on your backend.

## Installation

### Via pip

Install the latest version directly from GitHub:

```bash
pip install git+https://github.com/nac5504/CopyLab-Python.git
```

## Usage

### 1. Configuration

Initialize the SDK with your credentials. You can provide a service account path directly or rely on environment auto-discovery.

```python
import copylab

# Option A: Explicit Service Account
copylab.configure(
    service_account_path="path/to/serviceAccountKey.json",
    app_id="my-app-id"
)

# Option B: API Key (if supported by your setup)
copylab.configure(api_key="cl_my_app_id_xxxx")
```

### 2. Generating Notifications

Fetch a template and generate personalized content for a user.

```python
# Generate content for a specific placement
notification = copylab.generate_notification(
    placement_id="chat_message",
    variables={
        "sender_name": "Sarah",
        "message_preview": "Hey, are you going to the event?"
    },
    # Optional: Fallback if no template is active
    fallback_title="New Message",
    fallback_message="You have a new message from Sarah."
)

if notification["template_used"]:
    print(f"Generated: {notification['title']} - {notification['message']}")
else:
    print("Using fallback content")

# Use the result to send your push notification
# send_push(title=notification['title'], body=notification['message'], data=notification['data'])
```

### 3. Quick Notify

For simple use cases, you can use the shorthand `notify` function:

```python
result = copylab.notify("daily_reminder", streak_days=5, user_name="Alex")
```

## Updating

To update the SDK to the latest version, add the `--upgrade` flag:

```bash
pip install --upgrade git+https://github.com/nac5504/CopyLab-Python.git
```
