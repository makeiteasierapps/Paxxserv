import logging

logger = logging.getLogger(__name__)
def parse_entry_id(entry_id):
    """Extract category and subcategory from the structured entry_id"""
    parts = entry_id.split('.')
    if len(parts) >= 3:
        return parts[0], parts[1]
    return None, None

async def handle_contradiction(agent, user_collection, contradiction, push_operations):
    """
    Handles a contradiction by adding it to the appropriate MongoDB path and updating existing entries.
    """
    
    category_name, subcategory_name = parse_entry_id(contradiction['entry_id'])
    contradiction_path = f"contradictions.{category_name}.{subcategory_name}"
    push_operations['$push'].setdefault(contradiction_path, []).append(contradiction)

    entry_id = contradiction.get('entry_id')
    if entry_id:
        await user_collection.update_many(
            {'uid': agent.uid, f"questions_data.{category_name}.{subcategory_name}.entry_id": entry_id},
            {'$set': {f"questions_data.{category_name}.{subcategory_name}.$.superseded": True}}
        )

    if contradiction.get('recommended_action') == 'needs_clarification':
        push_operations['$push'].setdefault('contradiction_review_queue', []).append(contradiction)


async def resolve_entry_contradiction(agent, user_collection, entry_copy, contradiction, push_operations, entry_id, current_timestamp):
    """
    Handles resolution of a user entry if a contradiction exists.
    Returns True if the entry should be processed further.
    """
    recommended_action = contradiction.get('recommended_action', 'needs_clarification')
    resolution_record = {**contradiction, 'resolved_at': current_timestamp}

    if recommended_action == 'keep_existing':
        await agent.insight_db_manager.handle_keep_existing_resolution(push_operations, resolution_record, entry_copy)
        return False
    elif recommended_action == 'needs_clarification':
        await agent.insight_db_manager.handle_needs_clarification_resolution(push_operations, contradiction, entry_copy)
        return False
    elif recommended_action == 'merge':
        await agent.insight_db_manager.handle_merge_resolution(
            user_collection, push_operations, resolution_record, entry_id
        )
    else:  # assumed to be 'keep_new'
        await agent.insight_db_manager.handle_keep_new_resolution(
            user_collection, push_operations, resolution_record, entry_id
        )
    return True