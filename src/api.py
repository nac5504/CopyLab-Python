"""
CopyLab API - Cloud Functions HTTP Endpoints

This module provides secure HTTP API endpoints for the CopyLab notification system.
API key validation ensures only authorized clients can access tenant data.
"""

import json
import os
from functools import wraps

from firebase_admin import firestore, credentials, initialize_app, get_app
import firebase_admin
from firebase_functions import https_fn

# Lazy initialization for Firebase/Firestore
_db = None

def get_db():
    """Get Firestore client with lazy initialization."""
    global _db
    if _db is None:
        try:
            get_app()
        except ValueError:
            initialize_app()
        _db = firestore.client()
    return _db

# =============================================================================
# API KEY VALIDATION
# =============================================================================

def validate_api_key(request) -> tuple[str, str] | None:
    """
    Validates the API key from request headers and extracts the app_id.
    
    Returns:
        tuple of (api_key, app_id) if valid, None if invalid
    """
    api_key = request.headers.get('X-API-Key') or request.headers.get('x-api-key')
    
    if not api_key:
        return None
    
    # API key format: cl_{app_id}_{random_hex}
    if not api_key.startswith('cl_'):
        return None
    
    parts = api_key.split('_')
    if len(parts) < 3:
        return None
    
    app_id = parts[1]
    
    # Verify API key exists in Firestore
    key_doc = get_db().collection('apps').document(app_id).collection('api_keys').document(api_key).get()
    
    if not key_doc.exists:
        return None
    
    return (api_key, app_id)


def require_api_key(f):
    """Decorator that requires a valid API key for the endpoint."""
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        result = validate_api_key(request)
        if result is None:
            return https_fn.Response(
                json.dumps({'error': 'Invalid or missing API key'}),
                status=401,
                headers={'Content-Type': 'application/json'}
            )
        
        api_key, app_id = result
        # Inject app_id into request for use in handler
        request.app_id = app_id
        request.api_key = api_key
        return f(request, *args, **kwargs)
    
    return decorated_function


def get_collection_ref(app_id: str, collection_name: str):
    """Get a Firestore collection reference scoped to an app."""
    return get_db().collection('apps').document(app_id).collection(collection_name)


def cors_response(data: dict, status: int = 200):
    """Create a JSON response with CORS headers."""
    return https_fn.Response(
        json.dumps(data),
        status=status,
        headers={
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-API-Key'
        }
    )


# =============================================================================
# API ENDPOINTS
# =============================================================================

@https_fn.on_request()
def generate_notification(request: https_fn.Request) -> https_fn.Response:
    """
    Generate a notification from a template.
    
    POST /generate_notification
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "placement_id": "chat_message_sent",
            "variables": {"user_name": "John"},
            "data": {"target_tab": "chat"}
        }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    # Validate API key
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        placement_id = body.get('placement_id')
        variables = body.get('variables', {})
        data = body.get('data', {})
        fallback_title = body.get('fallback_title')
        fallback_message = body.get('fallback_message')
        
        if not placement_id:
            return cors_response({'error': 'placement_id is required'}, 400)
        
        # Import the core copylab module for template generation
        # This reuses the existing logic for template selection and variable substitution
        from src.copylab import configure, generate_notification as gen_notif
        
        # Configure for this app
        configure(app_id=app_id)
        
        # Generate notification
        result = gen_notif(
            placement_id=placement_id,
            variables=variables,
            data=data,
            fallback_title=fallback_title,
            fallback_message=fallback_message
        )
        
        return cors_response(result)
        
    except Exception as e:
        print(f"Error in generate_notification: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def get_topic_subscribers(request: https_fn.Request) -> https_fn.Response:
    """
    Get subscribers for a topic.
    
    GET /get_topic_subscribers?topic_id={topic_id}
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'GET':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        topic_id = request.args.get('topic_id')
        if not topic_id:
            return cors_response({'error': 'topic_id is required'}, 400)
        
        ref = get_collection_ref(app_id, 'copylab_topics')
        doc = ref.document(topic_id).get()
        
        if doc.exists:
            subscriber_ids = doc.to_dict().get('subscriber_ids', [])
            return cors_response({'subscriber_ids': subscriber_ids})
        else:
            return cors_response({'subscriber_ids': []})
            
    except Exception as e:
        print(f"Error in get_topic_subscribers: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def subscribe_to_topic(request: https_fn.Request) -> https_fn.Response:
    """
    Subscribe a user to a topic.
    
    POST /subscribe_to_topic
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "topic_id": "community_alerts",
            "user_id": "user123"
        }
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        topic_id = body.get('topic_id')
        user_id = body.get('user_id')
        
        if not topic_id or not user_id:
            return cors_response({'error': 'topic_id and user_id are required'}, 400)
        
        ref = get_collection_ref(app_id, 'copylab_topics')
        ref.document(topic_id).set({
            'subscriber_ids': firestore.ArrayUnion([user_id]),
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        return cors_response({'success': True})
        
    except Exception as e:
        print(f"Error in subscribe_to_topic: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def unsubscribe_from_topic(request: https_fn.Request) -> https_fn.Response:
    """
    Unsubscribe a user from a topic.
    
    POST /unsubscribe_from_topic
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "topic_id": "community_alerts",
            "user_id": "user123"
        }
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        topic_id = body.get('topic_id')
        user_id = body.get('user_id')
        
        if not topic_id or not user_id:
            return cors_response({'error': 'topic_id and user_id are required'}, 400)
        
        ref = get_collection_ref(app_id, 'copylab_topics')
        ref.document(topic_id).update({
            'subscriber_ids': firestore.ArrayRemove([user_id]),
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        return cors_response({'success': True})
        
    except Exception as e:
        print(f"Error in unsubscribe_from_topic: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def log_push_open(request: https_fn.Request) -> https_fn.Response:
    """
    Log a push notification open event.
    
    POST /log_push_open
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "user_id": "user123",
            "placement_id": "chat_message",
            "template_id": "tmpl_abc",
            "notification_id": "notif_xyz",
            "platform": "ios"
        }
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        user_id = body.get('user_id')
        
        if not user_id:
            return cors_response({'error': 'user_id is required'}, 400)
        
        data = {
            'user_id': user_id,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'platform': body.get('platform', 'unknown'),
            'type': body.get('type', 'unknown')
        }
        
        # Add optional fields
        for field in ['notification_id', 'placement_id', 'placement_name', 'template_id', 'template_name']:
            if body.get(field):
                data[field] = body[field]
        
        ref = get_collection_ref(app_id, 'copylab_push_open')
        ref.add(data)
        
        return cors_response({'success': True})
        
    except Exception as e:
        print(f"Error in log_push_open: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def log_app_open(request: https_fn.Request) -> https_fn.Response:
    """
    Log an app open event.
    
    POST /log_app_open
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "user_id": "user123",
            "platform": "ios"
        }
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        user_id = body.get('user_id')
        
        if not user_id:
            return cors_response({'error': 'user_id is required'}, 400)
        
        data = {
            'timestamp': firestore.SERVER_TIMESTAMP,
            'platform': body.get('platform', 'unknown')
        }
        
        ref = get_collection_ref(app_id, 'copylab_users')
        ref.document(user_id).collection('app_opens').add(data)
        
        return cors_response({'success': True})
        
    except Exception as e:
        print(f"Error in log_app_open: {e}")
        return cors_response({'error': str(e)}, 500)


@https_fn.on_request()
def sync_notification_permission(request: https_fn.Request) -> https_fn.Response:
    """
    Sync a user's notification permission status.
    
    POST /sync_notification_permission
    Headers:
        X-API-Key: cl_{app_id}_{secret}
    Body:
        {
            "user_id": "user123",
            "notification_status": "authorized",
            "platform": "ios"
        }
    """
    if request.method == 'OPTIONS':
        return cors_response({})
    
    if request.method != 'POST':
        return cors_response({'error': 'Method not allowed'}, 405)
    
    result = validate_api_key(request)
    if result is None:
        return cors_response({'error': 'Invalid or missing API key'}, 401)
    
    api_key, app_id = result
    
    try:
        body = request.get_json()
        user_id = body.get('user_id')
        notification_status = body.get('notification_status')
        
        if not user_id or not notification_status:
            return cors_response({'error': 'user_id and notification_status are required'}, 400)
        
        data = {
            'notification_status': notification_status,
            'last_updated': firestore.SERVER_TIMESTAMP,
            'platform': body.get('platform', 'unknown')
        }
        
        ref = get_collection_ref(app_id, 'copylab_users')
        ref.document(user_id).set(data, merge=True)
        
        return cors_response({'success': True})
        
    except Exception as e:
        print(f"Error in sync_notification_permission: {e}")
        return cors_response({'error': str(e)}, 500)
