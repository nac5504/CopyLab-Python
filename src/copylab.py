"""
CopyLab SDK - Notification Template System

This module provides functions to generate notification content from templates
stored in Firestore. Templates support variable substitution with default values.

Usage:
    from copylab import generate_notification
    
    # Generate notification from template
    result = generate_notification(
        placement_id="chat_message_sent",
        variables={
            "message_author_name": "John",
            "message_text": "Hello everyone!"
        },
        data={"target_tab": "community_chat"}
    )
    
    # Use the result
    send_notification(
        title=result["title"],
        message=result["message"],
        data=result["data"]
    )
    
Logging:
    CopyLab uses Python's logging module. Configure log level to control verbosity:
    
    import logging
    logging.getLogger('copylab').setLevel(logging.DEBUG)  # Verbose output
    logging.getLogger('copylab').setLevel(logging.WARNING)  # Errors only
"""

from firebase_admin import firestore, credentials, initialize_app, get_app
import firebase_admin
import os
import logging
import time
from functools import wraps

# Configure CopyLab logger
logger = logging.getLogger('copylab')

# Detect if running in Google Cloud Functions environment
_IS_CLOUD_FUNCTION = os.environ.get('FUNCTION_TARGET') is not None or os.environ.get('K_SERVICE') is not None

# Add a default handler if none exists (prevents "No handler found" warnings)
if not logger.handlers:
    handler = logging.StreamHandler()
    
    if _IS_CLOUD_FUNCTION:
        # Cloud Functions: Use structured logging format for better Firebase Console display
        # Logs with severity levels appear properly in Firebase Console > Functions > Logs
        handler.setFormatter(logging.Formatter(
            '[CopyLab] %(levelname)s: %(message)s'
        ))
    else:
        # Local development: Include timestamps
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [CopyLab] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    logger.addHandler(handler)
    
    # Set log level from environment variable or default to INFO
    log_level = os.environ.get('COPYLAB_LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))


def _log_performance(func):
    """Decorator to log function execution time for performance monitoring."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        # Log function entry with key arguments
        arg_summary = _summarize_args(args, kwargs, func_name)
        logger.debug(f"→ {func_name}({arg_summary})")
        
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Log success with timing
            result_summary = _summarize_result(result, func_name)
            logger.debug(f"← {func_name} completed in {elapsed_ms:.2f}ms{result_summary}")
            
            # Warn if operation is slow
            if elapsed_ms > 1000:
                logger.warning(f"⚠️ Slow operation: {func_name} took {elapsed_ms:.2f}ms")
            
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"✗ {func_name} failed after {elapsed_ms:.2f}ms: {e}")
            raise
    
    return wrapper


def _summarize_args(args, kwargs, func_name: str) -> str:
    """Create a concise summary of function arguments for logging."""
    parts = []
    
    # Handle common function signatures
    if func_name in ('generate_notification', 'get_random_template', 'get_placement_config'):
        if args:
            parts.append(f"placement_id='{args[0]}'")
        elif 'placement_id' in kwargs:
            parts.append(f"placement_id='{kwargs['placement_id']}'")
    elif func_name == 'get_topic_subscribers':
        if args:
            parts.append(f"topic_id='{args[0]}'")
        elif 'topic_id' in kwargs:
            parts.append(f"topic_id='{kwargs['topic_id']}'")
    elif func_name == 'get_collection_ref':
        if args:
            parts.append(f"collection='{args[0]}'")
    
    return ', '.join(parts) if parts else '...'


def _summarize_result(result, func_name: str) -> str:
    """Create a concise summary of function result for logging."""
    if result is None:
        return " → None"
    
    if func_name == 'get_topic_subscribers' and isinstance(result, list):
        return f" → {len(result)} subscribers"
    elif func_name == 'get_random_template' and isinstance(result, dict):
        template_name = result.get('name', 'Unknown')
        return f" → template '{template_name}'"
    elif func_name == 'generate_notification' and isinstance(result, dict):
        used = result.get('template_used', False)
        name = result.get('template_name', 'N/A')
        return f" → template_used={used}, name='{name}'"
    
    return ""

# Global configuration
_CONFIG = {
    'service_account_path': None,
    'api_key': None,
    'app_id': None,
    'app_name': 'copylab'
}

_COPYLAB_APP = None

def configure(service_account_path: str = None, api_key: str = None, app_id: str = None):
    """
    Configure the CopyLab SDK.
    
    Args:
        service_account_path: Path to the serviceAccountKey.json file for the CopyLab project.
        api_key: The CopyLab API key. If app_id not provided, extracted from key.
        app_id: Explicit App ID (e.g. 'nomigo'). Required if no API key used.
    """
    global _CONFIG, _COPYLAB_APP
    if service_account_path:
        _CONFIG['service_account_path'] = service_account_path
        logger.info(f"Configured service account: {os.path.basename(service_account_path)}")
    if api_key:
        _CONFIG['api_key'] = api_key
        logger.info(f"Configured API key: {api_key[:10]}...")
    if app_id:
        _CONFIG['app_id'] = app_id
        logger.info(f"Configured app_id: {app_id}")
        
    # Reset app to force re-initialization
    _COPYLAB_APP = None

# ... (get_db is fine) ...

def get_app_id() -> str:
    """Extract App ID from config or API Key."""
    # 1. Prefer explicit app_id
    if _CONFIG.get('app_id'):
        return _CONFIG['app_id']
        
    # 2. Extract from API Key
    api_key = _CONFIG.get('api_key')
    if api_key and api_key.startswith('cl_'):
        parts = api_key.split('_')
        if len(parts) >= 2:
            return parts[1]
            
    return 'unknown'



@_log_performance
def get_db():
    """Get CopyLab Firestore database client."""
    global _COPYLAB_APP
    
    # If app already initialized, return client
    if _COPYLAB_APP:
        logger.debug("Using cached CopyLab app instance")
        return firestore.client(app=_COPYLAB_APP)
        
    try:
        # Try to initialize specific CopyLab app
        app_name = _CONFIG['app_name']
        
        # Check if app already exists in firebase_admin (singleton check)
        try:
            _COPYLAB_APP = get_app(app_name)
            logger.debug(f"Found existing Firebase app: {app_name}")
            return firestore.client(app=_COPYLAB_APP)
        except ValueError:
            # App not initialized yet
            pass

        # Initialize with service account if provided or found
        sa_path = _CONFIG['service_account_path']
        
        # Auto-discovery: Check for 'copylab-service-account.json' in current dir
        if not sa_path:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(current_dir, 'copylab-service-account.json')
            if os.path.exists(default_path):
                sa_path = default_path
                logger.debug(f"Auto-discovered service account: {default_path}")

        if sa_path and os.path.exists(sa_path):
            cred = credentials.Certificate(sa_path)
            _COPYLAB_APP = initialize_app(cred, name=app_name)
            logger.info(f"✅ Initialized with service account: {os.path.basename(sa_path)}")
            return firestore.client(app=_COPYLAB_APP)
            
        # Fallback: Use default app (Nomigo project) if no specific config
        # This handles backward compatibility
        try:
            from .config import db
            logger.debug("Using fallback config.db")
            return db
        except ImportError:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            logger.debug("Using default Firebase app")
            return firestore.client()
            
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")
        # Last resort fallback
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        return firestore.client()



def get_collection_ref(collection_name: str):
    """
    Get a reference to a Firestore collection, scoped to the current App ID.
    Format: apps/{app_id}/{collection_name}
    """
    db = get_db()
    app_id = get_app_id()
    
    if app_id and app_id != 'unknown':
        logger.debug(f"Collection ref: apps/{app_id}/{collection_name}")
        return db.collection('apps').document(app_id).collection(collection_name)
    else:
        # Fallback to root collection if no valid keys (backward compatibility)
        logger.warning(f"No valid API Key configured. Using root collection for '{collection_name}'.")
        return db.collection(collection_name)


@_log_performance
def get_topic_subscribers(topic_id: str) -> list[str]:
    """
    Get list of user IDs subscribed to a CopyLab topic.
    """
    try:
        # Use scoped collection
        ref = get_collection_ref('copylab_topics')
        doc = ref.document(topic_id).get()
        
        if doc.exists:
            subscriber_ids = doc.to_dict().get('subscriber_ids', [])
            logger.info(f"📊 Found {len(subscriber_ids)} subscribers for topic '{topic_id}'")
            return subscriber_ids
        else:
            logger.warning(f"No subscribers found for topic '{topic_id}'")
            return []
    except Exception as e:
        logger.error(f"Error fetching topic subscribers for '{topic_id}': {e}")
        return []

# ... (Conditional logic helpers unchanged)



# =============================================================================
# COMPUTED VARIABLES - Conditional variable generation
# =============================================================================

def evaluate_condition(condition: dict, variables: dict) -> bool:
    """
    Evaluate a single condition against provided variables.
    
    Condition format: {"variable": "var_name", "operator": "equals", "value": "target"}
    Operators: equals, not_equals, contains, greater_than, less_than, exists
    """
    var_name = condition.get('variable', '')
    operator = condition.get('operator', 'equals')
    target_value = condition.get('value', '')
    
    actual_value = variables.get(var_name)
    
    # Handle 'exists' operator
    if operator == 'exists':
        return actual_value is not None and actual_value != ''
    
    # If variable doesn't exist, condition fails (except for not_equals)
    if actual_value is None:
        return operator == 'not_equals'
    
    # Convert to strings for comparison
    actual_str = str(actual_value)
    target_str = str(target_value)
    
    if operator == 'equals':
        return actual_str == target_str
    elif operator == 'not_equals':
        return actual_str != target_str
    elif operator == 'contains':
        return target_str in actual_str
    elif operator == 'greater_than':
        try:
            return float(actual_str) > float(target_str)
        except ValueError:
            return actual_str > target_str
    elif operator == 'less_than':
        try:
            return float(actual_str) < float(target_str)
        except ValueError:
            return actual_str < target_str
    
    return False


def apply_template_filters(filters: list, variables: dict) -> list:
    """
    Apply template filters to determine eligible template IDs.
    
    Each filter maps variable values to lists of template IDs.
    Returns the intersection of eligible templates across all filters.
    If no filters, returns None (meaning all templates eligible).
    
    Config format:
    {
        "inputVariable": "craving_time",
        "cases": [
            {"value": "Morning", "templateIds": ["tmpl_1", "tmpl_2"]},
            {"value": "Night", "templateIds": ["tmpl_3"]}
        ],
        "defaultTemplateIds": ["tmpl_4"]
    }
    """
    if not filters:
        return None  # No filters = all templates eligible
    
    eligible_sets = []
    
    for filter_config in filters:
        input_var = filter_config.get('inputVariable', '')
        cases = filter_config.get('cases', [])
        default_ids = filter_config.get('defaultTemplateIds', [])
        
        actual_value = str(variables.get(input_var, ''))
        
        # Find matching case
        matched_ids = None
        for case in cases:
            case_value = str(case.get('value', ''))
            if actual_value == case_value:
                matched_ids = case.get('templateIds', [])
                break
        
        # Use default if no case matched
        if matched_ids is None:
            matched_ids = default_ids
        
        if matched_ids:
            eligible_sets.append(set(matched_ids))
    
    if not eligible_sets:
        return None  # No filters matched = all templates eligible
    
    # Return intersection of all filter results
    result = eligible_sets[0]
    for s in eligible_sets[1:]:
        result = result.intersection(s)
    
    return list(result) if result else []


import random


def _filter_templates_by_conditions(templates: list, variables: dict) -> list:
    """
    Filter templates based on their conditions.
    Templates with no conditions are always included.
    Templates with conditions are only included if ALL conditions match.
    """
    filtered = []
    for template in templates:
        conditions = template.get('conditions', [])
        if not conditions:
            # No conditions = always eligible
            filtered.append(template)
        else:
            # Check all conditions
            all_match = all(evaluate_condition(c, variables) for c in conditions)
            if all_match:
                filtered.append(template)
    return filtered


def _weighted_random_choice(templates: list) -> dict | None:
    """
    Selects a template using weighted random selection.
    Templates with weight=0 are excluded.
    If no weights are set, falls back to equal probability.
    """
    if not templates:
        return None
    
    # Filter templates with weight and extract weights
    weighted_templates = [(t, t.get('weight', 0)) for t in templates]
    
    # Check if any template has a weight > 0
    total_weight = sum(w for _, w in weighted_templates)
    
    if total_weight > 0:
        # Use weighted selection - templates with weight=0 are effectively excluded
        templates_with_weight = [(t, w) for t, w in weighted_templates if w > 0]
        if not templates_with_weight:
            return random.choice(templates)
        
        weights = [w for _, w in templates_with_weight]
        selected_templates = [t for t, _ in templates_with_weight]
        return random.choices(selected_templates, weights=weights, k=1)[0]
    else:
        # No weights set - equal probability for all
        return random.choice(templates)


def get_random_template(placement_id: str, variables: dict = None, eligible_template_ids: list = None) -> dict | None:
    """
    Fetches a template for a given placement, using weighted random selection.
    Templates with higher weights have a higher probability of being selected.
    If variables provided, filters templates by their conditions first.
    If eligible_template_ids provided, only considers those templates.
    
    Args:
        placement_id: The ID of the notification placement (e.g. "chat_message_sent")
        variables: Optional dict of variables to filter templates by conditions
        eligible_template_ids: Optional list of template IDs to limit selection to
        
    Returns:
        Template dict with 'title_template', 'body_template', 'name' or None if not found
    """
    variables = variables or {}

    try:
        # Use scoped collection
        # NOTE: get_collection_ref usually returns 'apps/{app_id}/{collection}'
        # But notification_templates logic assumes it's reading from a collection.
        # Yes, we want to read from apps/{app_id}/notification_templates
        parent_ref = get_collection_ref('notification_templates').document(placement_id)
        parent_doc = parent_ref.get()
        
        if parent_doc.exists:
            parent_data = parent_doc.to_dict()
            
            # OPTIMIZATION: Check for activeTemplateIds array first
            active_ids = parent_data.get('activeTemplateIds', [])
            
            if active_ids:
                # Fetch all active templates to get their weights
                templates_ref = parent_ref.collection('templates')
                all_templates = []
                
                for template_id in active_ids:
                    template_doc = templates_ref.document(template_id).get()
                    if template_doc.exists:
                        template = template_doc.to_dict()
                        if template.get('isActive') is True:
                            template['id'] = template_doc.id
                            template['_placement_id'] = placement_id
                            template['_placement_name'] = parent_data.get('name', placement_id)
                            template['_placement_defaults'] = parent_data.get('previewDefaults', {})
                            template['_placement_variables'] = parent_data.get('variables', [])
                            template['_placement_data'] = parent_data.get('defaultData', {})
                            all_templates.append(template)
                
                if all_templates:
                    # Filter by eligible template IDs if provided
                    if eligible_template_ids is not None:
                        all_templates = [t for t in all_templates if t.get('id') in eligible_template_ids]
                        if not all_templates:
                            return None  # No eligible templates from filter
                    # Filter by template conditions if variables provided
                    eligible = _filter_templates_by_conditions(all_templates, variables)
                    if eligible:
                        return _weighted_random_choice(eligible)
            
            # Fallback: Fetch all templates if activeTemplateIds missing or failed
            templates_ref = parent_ref.collection('templates')
            templates_stream = templates_ref.stream()
            
            # Filter for active templates only
            templates = []
            for t in templates_stream:
                data = t.to_dict()
                if data.get('isActive') is True:
                    # Inject ID if not present
                    if 'id' not in data: 
                        data['id'] = t.id
                    data['_placement_id'] = placement_id
                    data['_placement_name'] = parent_data.get('name', placement_id)
                    data['_placement_defaults'] = parent_data.get('previewDefaults', {})
                    data['_placement_variables'] = parent_data.get('variables', [])
                    data['_placement_data'] = parent_data.get('defaultData', {})
                    templates.append(data)
            
            if templates:
                # Filter by eligible template IDs if provided
                if eligible_template_ids is not None:
                    templates = [t for t in templates if t.get('id') in eligible_template_ids]
                    if not templates:
                        return None  # No eligible templates from filter
                # Filter by template conditions if variables provided
                eligible = _filter_templates_by_conditions(templates, variables)
                if eligible:
                    return _weighted_random_choice(eligible)
            
    except Exception as e:
        logger.error(f"Error fetching template for placement '{placement_id}': {e}")
    
    return None


@_log_performance
def get_placement_config(placement_id: str) -> dict | None:
    """
    Fetches the placement configuration including variables and default values.
    
    Args:
        placement_id: The ID of the notification placement
        
    Returns:
        Placement config dict with 'variables', 'previewDefaults', 'name' or None
    """

    try:
        # Use scoped collection
        doc_ref = get_collection_ref('notification_templates').document(placement_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            config = {
                'id': placement_id,
                'name': data.get('name', placement_id),
                'variables': data.get('variables', []),
                'defaults': data.get('previewDefaults', {}),
                'default_data': data.get('defaultData', {}),
                'templateFilters': data.get('templateFilters', []),
                'activeTemplateId': data.get('activeTemplateId')
            }
            logger.debug(f"Loaded placement config for '{placement_id}': {len(config.get('variables', []))} variables")
            return config
        else:
            logger.warning(f"Placement '{placement_id}' not found in Firestore")
    except Exception as e:
        logger.error(f"Error fetching placement '{placement_id}': {e}")
    
    return None


def apply_template(template_string: str, variables: dict, defaults: dict = None) -> str:
    """
    Replaces placeholders in a template string with provided values.
    Falls back to default values if a variable is not provided.
    
    Args:
        template_string: The template with {variable_name} placeholders
        variables: Dict of variable names to values (without braces)
        defaults: Optional dict of default values for variables not in `variables`
        
    Returns:
        The template string with all placeholders replaced
    """
    if not template_string:
        return ""
    
    defaults = defaults or {}
    result = template_string
    
    # Find all {variable_name} patterns
    import re
    placeholders = re.findall(r'\{([^}]+)\}', template_string)
    
    for var_name in placeholders:
        placeholder = f"{{{var_name}}}"
        
        # Check if value provided in variables dict
        if var_name in variables:
            value = str(variables[var_name])
        # Check defaults (stored with braces as keys)
        elif placeholder in defaults:
            value = str(defaults[placeholder])
        # Check defaults without braces
        elif var_name in defaults:
            value = str(defaults[var_name])
        else:
            # Keep placeholder if no value found
            value = placeholder
            logger.warning(f"No value provided for variable {placeholder}")
        
        result = result.replace(placeholder, value)
    
    return result


def _process_notification_content(
    title: str,
    message: str,
    data: dict,
    variables: dict,
    defaults: dict = None,
    max_length: int = None
) -> dict:
    """
    Internal helper to apply variable substitution to title, message, and all string values in data.
    Truncates message if max_length is provided.
    """
    defaults = defaults or {}
    variables = variables or {}
    
    # Process title and message
    processed_title = apply_template(title, variables, defaults)
    processed_message = apply_template(message, variables, defaults)
    
    # Truncate message if needed
    if max_length and len(processed_message) > max_length:
        processed_message = processed_message[:max_length-3] + "..."
    
    # Process data values
    processed_data = {}
    for k, v in data.items():
        if isinstance(v, str):
            processed_data[k] = apply_template(v, variables, defaults)
        else:
            processed_data[k] = v
            
    return {
        'title': processed_title,
        'message': processed_message,
        'data': processed_data
    }


def generate_notification(
    placement_id: str,
    variables: dict = None,
    data: dict = None,
    fallback_title: str = None,
    fallback_message: str = None,
    max_length: int = 200
) -> dict:
    """
    Generates a complete notification from a template.
    
    Args:
        placement_id: The ID of the notification placement (e.g. "chat_message_sent")
        variables: Dict of variable values (keys without braces, e.g. {"user_name": "John"})
        data: Additional data to include in the notification payload
        fallback_title: Title to use if no active template exists
        fallback_message: Message to use if no active template exists
        
    Returns:
        Dict with 'title', 'message', 'data', and 'template_used' (bool)
        
    Example:
        result = generate_notification(
            placement_id="streak_reminder",
            variables={"user_name": "Sarah", "streak_count": "5"},
            data={"target_tab": "profile"}
        )
        # result = {
        #     "title": "Hey Sarah! 🔥",
        #     "message": "Keep your 5 day streak going!",
        #     "data": {"target_tab": "profile"},
        #     "template_used": True
        # }
    """
    variables = variables or {}
    data = data or {}
    
    # Fetch placement config to get template filters
    placement_config = get_placement_config(placement_id)
    
    # Apply template filters to get eligible template IDs
    eligible_template_ids = None
    if placement_config and placement_config.get('templateFilters'):
        eligible_template_ids = apply_template_filters(placement_config['templateFilters'], variables)
    
    # Fetch a random template (filtered by conditions and eligible IDs)
    template = get_random_template(placement_id, variables, eligible_template_ids)
    
    if template:
        # Get placement defaults for fallback values
        defaults = template.get('_placement_defaults', {})
        
        # Merge template data with runtime data
        # Template data keys are processed for variables, then runtime data overrides them
        # Note: We process everything at the end, so we just merge raw dictionaries here
        template_data = template.get('data') or template.get('_placement_data', {})
        
        # We need to process template data *before* merging with runtime data if we want runtime data to override specific processed values?
        # OR we treat them all as candidates for processing.
        # The prompt said: "processes notification title, message, and data for variable regular expressions before final outputs"
        
        # Let's merge first. 
        # But wait, `_process_notification_content` takes a single data dict.
        # If template data has {var} and runtime data has explicit value, runtime wins.
        # If runtime data has {var}, it should be processed too.
        
        merged_data = template_data.copy()
        merged_data.update(data)
        
        # Use helper
        processed = _process_notification_content(
            title=template.get('title_template', ''),
            message=template.get('body_template', ''),
            data=merged_data,
            variables=variables,
            defaults=defaults,
            max_length=max_length
        )
        
        # Add attribution data to processed_data
        # We add it AFTER substitution to avoid users accidentally overriding it,
        # but before return.
        processed['data']['copylab_placement_id'] = placement_id
        processed['data']['copylab_placement_name'] = template.get('_placement_name', placement_id)
        processed['data']['copylab_template_id'] = template.get('id', 'unknown')
        processed['data']['copylab_template_name'] = template.get('name', 'Unknown')
        
        return {
            'title': processed['title'],
            'message': processed['message'],
            'data': processed['data'],
            'template_used': True,
            'template_name': template.get('name', 'Unknown')
        }
    else:
        # No template found - use fallbacks
        logger.warning(f"No active template for placement '{placement_id}', using fallbacks")
        
        # Try to get defaults from placement config if possible (even if no template active)
        placement_config = get_placement_config(placement_id)
        defaults = placement_config.get('defaults', {}) if placement_config else {}
        
        processed = _process_notification_content(
            title=fallback_title or '',
            message=fallback_message or '',
            data=data,
            variables=variables,
            defaults=defaults,
            max_length=max_length
        )

        # Attribution for fallback
        placement_name = placement_config.get('name', placement_id) if placement_config else placement_id
        processed['data']['copylab_placement_id'] = placement_id
        processed['data']['copylab_placement_name'] = placement_name
        processed['data']['copylab_template_id'] = 'fallback'
        processed['data']['copylab_template_name'] = 'Fallback'
        
        return {
            'title': processed['title'],
            'message': processed['message'],
            'data': processed['data'],
            'template_used': False,
            'template_name': None
        }


def generate_notification_safe(
    placement_id: str,
    variables: dict = None,
    data: dict = None,
    fallback_title: str = "Notification",
    fallback_message: str = ""
) -> dict:
    """
    Same as generate_notification but never raises exceptions.
    Returns fallback values if any error occurs.
    """
    try:
        return generate_notification(
            placement_id=placement_id,
            variables=variables,
            data=data,
            fallback_title=fallback_title,
            fallback_message=fallback_message
        )
    except Exception as e:
        logger.error(f"Error generating notification for '{placement_id}': {e}")
        return {
            'title': fallback_title,
            'message': fallback_message,
            'data': data or {},
            'template_used': False,
            'template_name': None,
            'error': str(e)
        }


# Convenience function for quick notification generation
def notify(placement_id: str, **variables) -> dict:
    """
    Shorthand for generate_notification with keyword arguments as variables.
    
    Example:
        result = notify("chat_message", author_name="John", message_text="Hi!")
    """
    return generate_notification(placement_id=placement_id, variables=variables)
