from datetime import datetime, timezone
import asyncio
import threading
import os
import logging
import json
import re
import uuid
import dspy
from app.agents.insight.insight_db_manager import InsightDbManager
from app.agents.insight.dspy_model import InsightSignature
from app.agents.BossAgent import BossAgentConfig, BossAgent
from app.utils.AsyncReAct import AsyncReActWrapper
from app.services.MongoDbClient import MongoDbClient

logger = logging.getLogger(__name__)

class InsightAgent(BossAgent):
    def __init__(self, config: BossAgentConfig, db, uid):
        super().__init__(config)
        self.uid = uid
        self.db = db
        self.insight_db_manager = InsightDbManager(uid, db)

    # Keep this until we decide if we need tools or not.
    # def _initialize_react_agent(self):
        # 
   
    async def handle_user_input(self, user_input):
        # Start background tasks
        conversation_analyzer = self._create_background_task_runner(self._analyze_conversation_task)
        thread = threading.Thread(
            target=conversation_analyzer,
            args=(user_input,),
            name="conversation_analyzer"
        )
        thread.daemon = True
        thread.start()
        user_message = user_input[-1]
        # Continue with normal conversation processing
        await self.insight_db_manager.create_message('user', user_message.get('content'))
        return await super().process_message(user_input, 'insight', lambda cid, msg: self.insight_db_manager.create_message('agent', msg))
    
    async def _analyze_conversation_task(self, conversation):
        try:
            # Initialize DSPy settings in the main thread before starting background tasks
            os.getenv('OPENAI_API_KEY')
            lm = dspy.LM('openai/gpt-4o-mini', max_tokens=10000, cache=False)
            
            # Use context manager instead of configure
            with dspy.settings.context(lm=lm):
                # Get existing profile data
                client = MongoDbClient('paxxium')
                user_collection = client.db['insight']
                profile_data = await self.insight_db_manager.get_current_profile(user_collection)
                
                agent = dspy.ChainOfThought(InsightSignature)
                result = agent(
                    conversation=conversation,
                    profile=profile_data
                )

                if result.user_entries:
                    await self._process_user_data(client.db, result.user_entries, result.contradictions)
                
        except Exception as e:
            logging.error("Error in analyze_conversation_task: %s", str(e))

    async def _process_user_data(self, db, user_entries, contradictions=None):
        try:
            contradictions = contradictions or []
            user_collection = db['insight']
            current_timestamp = datetime.now(timezone.utc).isoformat()

            current_profile = await self.insight_db_manager.get_current_profile(user_collection)
            contradiction_dicts = None
            if contradictions:
                contradiction_dicts = self._prepare_contradictions(contradictions, current_timestamp)

            push_operations, update_operations = await self._handle_entries_and_contradictions(
                user_collection, user_entries, current_profile, current_timestamp, contradiction_dicts
            )

            await self.insight_db_manager.execute_db_operations(user_collection, push_operations, update_operations)

            updated_data = await self.insight_db_manager.fetch_updated_data(user_collection)
            await self._notify_clients(updated_data)

            return f"Successfully processed {len(user_entries)} entries and updated the database"

        except Exception as e:
            logging.error("Error processing user data: %s", str(e))
            return f"Error processing user data: {str(e)}"

    def _prepare_contradictions(self, contradictions, current_timestamp):
        contradiction_dicts = []
        for contradiction in contradictions:
            contradiction_dict = contradiction.model_dump() if hasattr(contradiction, 'model_dump') else contradiction
            contradiction_dict.setdefault('detected_at', current_timestamp)
            contradiction_dict.setdefault('id', str(uuid.uuid4()))
            contradiction_dicts.append(contradiction_dict)
        return contradiction_dicts

    async def _handle_entries_and_contradictions(self, user_collection, user_entries, current_profile, current_timestamp, contradiction_dicts=None):
        push_operations = {'$push': {}}
        update_operations = []

        if contradiction_dicts:
            for contradiction in contradiction_dicts:
                await self._handle_contradiction(user_collection, contradiction, push_operations)

        for entry in user_entries:
            entry_dict = entry.model_dump() if hasattr(entry, 'model_dump') else entry
            await self._handle_user_entry(
                user_collection, entry_dict, current_profile, push_operations, update_operations, current_timestamp, contradiction_dicts
            )

        return push_operations, update_operations

    async def _handle_contradiction(self, user_collection, contradiction, push_operations):
        category_name = contradiction['category'].replace(' ', '_').lower()
        subcategory_name = contradiction['subcategory'].replace(' ', '_').lower()
        contradiction_path = f"contradictions.{category_name}.{subcategory_name}"
        push_operations['$push'].setdefault(contradiction_path, []).append(contradiction)

        entry_id = contradiction.get('entry_id')
        if entry_id:
            await user_collection.update_many(
                {'uid': self.uid, f"questions_data.{category_name}.{subcategory_name}.entry_id": entry_id},
                {'$set': {f"questions_data.{category_name}.{subcategory_name}.$.superseded": True}}
            )

        if contradiction.get('recommended_action') == 'needs_clarification':
            push_operations['$push']['contradiction_review_queue'].append(contradiction)

    async def _handle_user_entry(self, user_collection, entry_dict, current_profile, push_operations, update_operations, current_timestamp, contradiction_dicts=None):
        CONFIDENCE_THRESHOLD = 0.7
        category_name = entry_dict['category']['name'].replace(' ', '_').lower()
        subcategory_name = entry_dict['category']['subcategory'].replace(' ', '_').lower()
        data_type = entry_dict['category'].get('data_type', 'single_value')
        confidence = entry_dict.get('confidence', 0.8)

        entry_copy = {**entry_dict, 'timestamp': current_timestamp, 'superseded': False}
        entry_copy.pop('category', None)

        if confidence < CONFIDENCE_THRESHOLD:
            review_path = f"review_queue.{category_name}.{subcategory_name}"
            push_operations['$push'].setdefault(review_path, []).append({
                **entry_copy, "status": "pending", "flagged_reason": "low_confidence"
            })
            return

        if contradiction_dicts:
            entry_contradictions = [
                c for c in contradiction_dicts
                if c['category'].replace(' ', '_').lower() == category_name and
                c['subcategory'].replace(' ', '_').lower() == subcategory_name
            ]

            if not await self._resolve_entry_contradiction(
                user_collection, entry_copy, entry_contradictions[0], push_operations, category_name, subcategory_name, current_timestamp
            ):
                return

        await self._update_profile_data(
            entry_dict, entry_copy, current_profile, push_operations, update_operations, category_name, subcategory_name, data_type, confidence, current_timestamp
        )

    async def _resolve_entry_contradiction(self, user_collection, entry_copy, contradiction, push_operations, category_name, subcategory_name, current_timestamp):
        recommended_action = contradiction.get('recommended_action', 'needs_clarification')
        resolution_record = {**contradiction, 'resolved_at': current_timestamp}

        if recommended_action == 'keep_existing':
            await self.insight_db_manager.handle_keep_existing_resolution(push_operations, resolution_record, entry_copy)
            return False

        if recommended_action == 'needs_clarification':
            await self.insight_db_manager.handle_needs_clarification_resolution(push_operations, contradiction, entry_copy)
            return False

        if recommended_action == 'merge':
            await self.insight_db_manager.handle_merge_resolution(
                user_collection, push_operations, resolution_record, 
                entry_copy, category_name, subcategory_name
            )
        else:  # keep_new
            await self.insight_db_manager.handle_keep_new_resolution(
                user_collection, push_operations, resolution_record, 
                category_name, subcategory_name
            )
        return True

    async def _update_profile_data(self, entry_dict, entry_copy, current_profile, push_operations, update_operations, category_name, subcategory_name, data_type, confidence, current_timestamp):
        existing_data = self._get_nested_dict_value(current_profile, category_name, subcategory_name)
        profile_path = f"profile_data.{category_name}.{subcategory_name}"
        category_path = f"questions_data.{category_name}.{subcategory_name}"

        if existing_data:
            version_path = f"profile_history.{category_name}.{subcategory_name}"
            if version_path not in push_operations['$push']:
                push_operations['$push'][version_path] = {
                    'value': existing_data, 'timestamp': current_timestamp, 'change_type': 'update', 'triggered_by': entry_dict.get('question', 'conversation')
                }
            else:
                # If we need to push multiple items, use $each
                if '$each' not in push_operations['$push'][version_path]:
                    current_value = push_operations['$push'][version_path]
                    push_operations['$push'][version_path] = {'$each': [current_value]}
                push_operations['$push'][version_path]['$each'].append({
                    'value': existing_data, 'timestamp': current_timestamp, 'change_type': 'update', 'triggered_by': entry_dict.get('question', 'conversation')
                })

        if category_path not in push_operations['$push']:
            push_operations['$push'][category_path] = entry_copy
        else:
            if '$each' not in push_operations['$push'][category_path]:
                current_value = push_operations['$push'][category_path]
                push_operations['$push'][category_path] = {'$each': [current_value]}
            push_operations['$push'][category_path]['$each'].append(entry_copy)

        profile_update = self._generate_profile_update(entry_dict, existing_data, data_type, confidence, current_timestamp)
        update_operations.append({'$set': {profile_path: profile_update}})

    def _generate_profile_update(self, entry_dict, existing_data, data_type, confidence, current_timestamp):
        base = {"created_at": existing_data.get('created_at', current_timestamp) if existing_data else current_timestamp, "updated_at": current_timestamp}
        if data_type == 'single_value':
            return {**base, "value": entry_dict['answer'], "confidence": confidence}
        if data_type == 'collection':
            items = self._parse_collection_items(entry_dict['answer'])
            current_items = existing_data.get('items', []) if existing_data else []
            current_confidence = existing_data.get('confidence', {}) if existing_data else {}
            for item in items:
                current_items.append(item) if item.lower() not in map(str.lower, current_items) else None
                current_confidence[item] = max(confidence, current_confidence.get(item, 0))
            return {**base, "items": current_items, "confidence": current_confidence}
        if data_type == 'object':
            properties = self._parse_object_properties(entry_dict['answer'])
            current_properties = existing_data.get('properties', {}) if existing_data else {}
            current_confidence = existing_data.get('confidence', {}) if existing_data else {}
            for key, value in properties.items():
                current_properties[key] = value
                current_confidence[key] = max(confidence, current_confidence.get(key, 0))
            return {**base, "properties": current_properties, "confidence": current_confidence}

    async def _notify_clients(self, updated_data):
        await self.sio.emit('insight_user_data', json.dumps(updated_data))

        contradiction_queue = updated_data.get('contradiction_review_queue', [])
        if contradiction_queue:
            await self.sio.emit('insight_contradictions', json.dumps({'review_queue': contradiction_queue}))
    
    def _parse_collection_items(self, answer):
        """Parse a text answer into a list of items."""
        # Split by common delimiters (commas, semicolons, 'and')
        items = []
        if answer:
            # First clean up common list formats
            cleaned = re.sub(r'\d+\.\s*', '', answer)  # Remove numbered lists (1., 2., etc)
            cleaned = re.sub(r'•\s*', '', cleaned)     # Remove bullet points
            cleaned = re.sub(r'-\s*', '', cleaned)     # Remove dashes
            
            # Split by common delimiters
            for item in re.split(r'[,;]|\band\b', cleaned):
                item = item.strip()
                if item and len(item) > 1:  # Avoid single characters and empty strings
                    items.append(item)
        
        return items
                    
    def _parse_object_properties(self, answer):
        """Parse a text answer into key-value properties."""
        properties = {}
        
        # Look for patterns like "Key: Value" or "Key is Value"
        for pattern in [
            r'(\w+(?:\s+\w+)*)\s*:\s*([^,.;]+)',           # Key: Value
            r'(\w+(?:\s+\w+)*)\s+is\s+([^,.;]+)',          # Key is Value
            r'(?:my|their|his|her)\s+(\w+)\s+is\s+([^,.;]+)',  # My/Their/His/Her Key is Value
            r'(?:I|they|he|she)\s+(?:like[s]?|prefer[s]?|enjoy[s]?|want[s]?)\s+([^,.;]+)'  # Preferences
        ]:
            for match in re.finditer(pattern, answer, re.IGNORECASE):
                if len(match.groups()) >= 2:
                    key, value = match.groups()[0], match.groups()[1]
                    properties[key.strip().lower()] = value.strip()
                elif len(match.groups()) == 1:
                    # For preferences without explicit keys
                    value = match.groups()[0]
                    properties["preference"] = value.strip()
        
        return properties

    def _get_nested_dict_value(self, dictionary, *keys, default=None):
        """Helper method to safely get nested dictionary values"""
        current = dictionary
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
        
    def _create_background_task_runner(self, task_func):
        async def wrapped_task(*args, **kwargs):
            try:
                await task_func(*args, **kwargs)
            except Exception as e:
                logging.error("Error in background task %s: %s", task_func.__name__, str(e))

        def run_in_thread(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(wrapped_task(*args, **kwargs))
            finally:
                loop.close()
        return run_in_thread
