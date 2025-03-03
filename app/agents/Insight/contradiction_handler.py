import logging
from app.agents.insight.helpers import parse_entry_id
logger = logging.getLogger(__name__)

async def process_contradictions(agent, contradictions, entry_dict, current_timestamp):
    """
    Processes contradictions and handles their resolution in a single pass.
    
    Returns:
        bool: Whether the entry should be processed further
    """

    if not contradictions:
        return True
    
    contradiction_dicts = [
        contradiction.model_dump() if hasattr(contradiction, 'model_dump') else contradiction
        for contradiction in contradictions
    ]

    category_name, subcategory_name = parse_entry_id(contradiction_dicts[0]['entry_id'])
    contradiction_path = f"contradictions.{category_name}.{subcategory_name}"
    
    for contradiction in contradiction_dicts:
        # Add contradiction directly to DB
        await agent.insight_db_manager.add_new_contradiction(
            contradiction_path,
            contradiction
        )
        
        if contradiction.get('recommended_action') == 'needs_clarification':
            await agent.insight_db_manager.handle_needs_clarification_resolution(
                contradiction, 
                entry_dict
            )
            return False
        
        resolution = contradiction.get('recommended_action')
        resolution_record = {
            'timestamp': current_timestamp,
            'entry_id': entry_dict['entry_id']
        }
        
        if resolution == 'keep_existing':
            await agent.insight_db_manager.handle_keep_existing_resolution(
                resolution_record, 
                entry_dict
            )
            return False
            
        elif resolution in ['merge', 'keep_new']:
            if resolution == 'merge':
                await agent.insight_db_manager.handle_merge_resolution(
                    resolution_record, 
                    contradiction['entry_id']
                )
            else:  # keep_new
                await agent.insight_db_manager.handle_keep_new_resolution(
                    resolution_record,
                    contradiction['entry_id']
                )
            
    return True