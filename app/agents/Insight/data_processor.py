import uuid
import logging
from datetime import datetime, timezone

from app.agents.insight.contradiction_handler import (
    handle_contradiction,
    resolve_entry_contradiction
)
from app.agents.insight.helpers import get_nested_dict_value, parse_collection_items

logger = logging.getLogger(__name__)

async def process_user_data(agent, db, result):
    """
    Processes user data from the DSPy result including contradictions and user entries.
    """
    try:
        user_collection = db['insight']
        current_timestamp = datetime.now(timezone.utc).isoformat()
        current_profile = await agent.insight_db_manager.get_current_profile(user_collection)
        
        # Prepare contradictions if any
        contradiction_dicts = None
        if result.contradictions:
            contradiction_dicts = _prepare_contradictions(result.contradictions, current_timestamp)
        
        # Initialize the DB operations object
        push_operations, update_operations = await _handle_entries_and_contradictions(
            agent, user_collection, result.user_entries, current_profile, current_timestamp,
            contradiction_dicts
        )
        
        await agent.insight_db_manager.execute_db_operations(user_collection, push_operations, update_operations)
        updated_data = await agent.insight_db_manager.fetch_updated_data(user_collection)
        await agent.notify_clients(updated_data)
        return f"Successfully processed {len(result.user_entries)} entries and updated the database"
    except Exception as e:
        logger.error("Error processing user data: %s", str(e))
        return f"Error processing user data: {str(e)}"

def _prepare_contradictions(contradictions, current_timestamp):
    contradiction_dicts = []
    for contradiction in contradictions:
        # If the contradiction has the pydantic method model_dump, use it.
        contradiction_dict = contradiction.model_dump() if hasattr(contradiction, 'model_dump') else contradiction
        contradiction_dict.setdefault('detected_at', current_timestamp)
        contradiction_dict.setdefault('id', str(uuid.uuid4()))
        contradiction_dicts.append(contradiction_dict)
    return contradiction_dicts

async def _handle_entries_and_contradictions(agent, user_collection, user_entries, current_profile, current_timestamp, contradiction_dicts=None):
    push_operations = {'$push': {}}
    update_operations = []
    
    if contradiction_dicts:
        for contradiction in contradiction_dicts:
            await handle_contradiction(agent, user_collection, contradiction, push_operations)
    
    for entry in user_entries:
        entry_dict = entry.model_dump() if hasattr(entry, 'model_dump') else entry
        await _handle_user_entry(agent, user_collection, entry_dict, current_profile, push_operations,
                                  update_operations, current_timestamp, contradiction_dicts)
    return push_operations, update_operations

async def _handle_user_entry(agent, user_collection, entry_dict, current_profile, push_operations, update_operations, current_timestamp, contradiction_dicts=None):
    category_name = entry_dict['category']['name'].replace(' ', '_').lower()
    subcategory_name = entry_dict['category']['subcategory'].replace(' ', '_').lower()
    data_type = entry_dict['category'].get('data_type', 'single_value')
    
    entry_id = f"{category_name}.{subcategory_name}.{str(uuid.uuid4())}"
    
    entry_copy = {**entry_dict, 'timestamp': current_timestamp, 'superseded': False, 'entry_id': entry_id}
    entry_copy.pop('category', None)
    
    if contradiction_dicts:
        should_process = await resolve_entry_contradiction(
            agent, user_collection, entry_copy, contradiction_dicts[0],
            push_operations, entry_id, current_timestamp)
        if not should_process:
            return

    await _update_profile_data(entry_copy, current_profile, push_operations,
                               update_operations, category_name, subcategory_name, data_type, current_timestamp)

async def _update_profile_data(entry_copy, current_profile, push_operations, update_operations, category_name, subcategory_name, data_type, current_timestamp):
    existing_data = get_nested_dict_value(current_profile, category_name, subcategory_name)
    profile_path = f"profile_data.{category_name}.{subcategory_name}"
    category_path = f"questions_data.{category_name}.{subcategory_name}"
    
    # Maintain profile history if there is existing data
    if existing_data:
        version_path = f"profile_history.{category_name}.{subcategory_name}"
        item = {
            'value': existing_data,
            'timestamp': current_timestamp,
            'change_type': 'update',
            'triggered_by': entry_copy.get('question', 'conversation')
        }
        if version_path not in push_operations['$push']:
            push_operations['$push'][version_path] = item
        else:
            # Ensure $each is used when multiple items are added
            current_val = push_operations['$push'][version_path]
            if not isinstance(current_val, dict) or '$each' not in current_val:
                push_operations['$push'][version_path] = {'$each': [current_val]}
            push_operations['$push'][version_path]['$each'].append(item)
    
    # Update the entries in the question data
    if category_path not in push_operations['$push']:
        push_operations['$push'][category_path] = entry_copy
    else:
        current_val = push_operations['$push'][category_path]
        if not isinstance(current_val, dict) or '$each' not in current_val:
            push_operations['$push'][category_path] = {'$each': [current_val]}
        push_operations['$push'][category_path]['$each'].append(entry_copy)
    
    # Generate profile update document
    profile_update = _generate_profile_update(entry_copy, existing_data, data_type, current_timestamp)
    update_operations.append({'$set': {profile_path: profile_update}})

def _generate_profile_update(entry_copy, existing_data, data_type, current_timestamp):
    base = {
        "created_at": existing_data.get('created_at', current_timestamp) if existing_data else current_timestamp,
        "updated_at": current_timestamp
    }
    if data_type == 'single_value':
        return {**base, "value": entry_copy['answer'], 'entry_id': entry_copy['entry_id']}
    elif data_type == 'collection':
        items = parse_collection_items(entry_copy['answer'])
        current_items = existing_data.get('items', []) if existing_data else []
        # Merge unique items ignoring case
        for item in items:
            if item.lower() not in map(str.lower, current_items):
                current_items.append(item)
        return {**base, "items": current_items}