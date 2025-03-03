import uuid
import logging
from datetime import datetime, timezone

from app.agents.insight.contradiction_handler import process_contradictions
from app.agents.insight.helpers import get_nested_dict_value, parse_collection_items

logger = logging.getLogger(__name__)

async def process_user_data(agent, result):
    try:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        current_profile = await agent.insight_db_manager.get_current_profile()
        
        await _handle_entries_and_contradictions(
            agent,
            result,
            current_profile,
            current_timestamp,
        )
        
        updated_data = await agent.insight_db_manager.fetch_updated_data()
        await agent.notify_clients(updated_data)
        return f"Successfully processed {len(result.user_entries)} entries and updated the database"
    except Exception as e:
        logger.error("Error processing user data: %s", str(e))
        return f"Error processing user data: {str(e)}"

async def _handle_entries_and_contradictions(agent, result, current_profile, current_timestamp):
    for entry in result.user_entries:
        entry_dict = entry.model_dump() if hasattr(entry, 'model_dump') else entry
        
        category_name = entry_dict['category']['name'].replace(' ', '_').lower()
        subcategory_name = entry_dict['category']['subcategory'].replace(' ', '_').lower()
        data_type = entry_dict['category'].get('data_type', 'single_value')
        
        entry_id = f"{category_name}.{subcategory_name}.{str(uuid.uuid4())}"
        entry_copy = {**entry_dict, 'timestamp': current_timestamp, 'entry_id': entry_id}
        entry_copy.pop('category', None)
        
        should_process = await process_contradictions(
            agent,
            result.contradictions,
            entry_copy,
            current_timestamp
        )
        
        if should_process:
            await _update_profile_data(
                agent,
                entry_copy,
                current_profile,
                category_name,
                subcategory_name,
                data_type,
                current_timestamp
            )

async def _update_profile_data(agent, entry_copy, current_profile, category_name, subcategory_name, data_type, current_timestamp):
    existing_data = get_nested_dict_value(current_profile, category_name, subcategory_name)
    
    # Maintain profile history if there is existing data
    if existing_data:
        await agent.insight_db_manager.update_profile_version_history(
            category_name,
            subcategory_name,
            existing_data,
            current_timestamp,
            entry_copy.get('question', 'conversation')
        )
    
    # Add new entry to questions data
    await agent.insight_db_manager.add_questions_entry(
        category_name,
        subcategory_name,
        entry_copy
    )
    
    # Update profile data
    profile_update = _generate_profile_update(entry_copy, existing_data, data_type, current_timestamp)
    await agent.insight_db_manager.update_profile_data(
        category_name,
        subcategory_name,
        profile_update
    )

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