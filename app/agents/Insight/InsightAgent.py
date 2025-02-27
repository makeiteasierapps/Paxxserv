from datetime import datetime, timezone
import asyncio
import threading
import os
import logging
import json
import re
import uuid
import dspy
from typing import List, Optional, Union, Literal, Any
from bson import ObjectId
from pydantic import BaseModel, Field
from app.agents.BossAgent import BossAgentConfig, BossAgent
from app.utils.AsyncReAct import AsyncReActWrapper
from app.services.MongoDbClient import MongoDbClient

logger = logging.getLogger(__name__)

class Category(BaseModel):
    name: str = Field(description="The category this answer belongs to.")
    subcategory: str = Field(description="A subcategory that best describes this answer.")
    data_type: Literal["single_value", "collection", "object"] = Field(
        description="How this data should be stored: 'single_value' for one piece of info, 'collection' for lists of items, 'object' for structured data.",
        default="single_value"
    )

class Contradiction(BaseModel):
    category: str = Field(description="The category containing the contradiction")
    subcategory: str = Field(description="The subcategory containing the contradiction")
    data_type: str = Field(description="The data type (single_value, collection, object)")
    existing_value: Any = Field(description="The value currently in the profile")
    new_value: Any = Field(description="The newly extracted value")
    entry_id: str = Field(description="Reference to the corresponding user entry")
    recommended_action: str = Field(
        description="Recommended action: 'keep_new', 'keep_existing', 'merge', or 'needs_clarification'"
    )
    reasoning: str = Field(description="Explanation of why this is a contradiction and the recommended action")

class UserEntry(BaseModel):
    question: str = Field(description="The original question that prompted the user's response.")
    answer: str = Field(description="A specific piece of user-provided information.")
    category: Category = Field(description="The category and subcategory that best describes this answer.")
    parsed_value: Optional[Union[str, List[str], dict]] = Field(
        default=None, 
        description="The parsed version of the answer - either a single value, a list of items, or key-value pairs"
    )
    confidence: float = Field(
        default=0.8, 
        description="Confidence score from 0.0 to 1.0 indicating certainty of extraction",
        ge=0.0,  # Greater than or equal to 0
        le=1.0   # Less than or equal to 1
    )

class InsightSignature(dspy.Signature):
    """Extract information from the conversation and check for contradictions with existing profile data.
    
    For each extracted piece of information, determine:
    1. Its category, subcategory, and data_type
    2. A confidence score (0.0-1.0) indicating how certain you are about this extraction
    3. Whether it contradicts existing profile information
    
    If you detect a contradiction, explicitly flag it and recommend a resolution strategy.
    """
    
    conversation: List[dict] = dspy.InputField(desc="The conversation history between user and agent")
    profile: dict = dspy.InputField(desc="The user's existing profile data")
    user_entries: List[UserEntry] = dspy.OutputField(desc="Extracted and categorized user information with confidence scores")
    contradictions: List[Contradiction] = dspy.OutputField(desc="Identified contradictions between new information and existing profile")

class InsightAgent(BossAgent):
    def __init__(self, config: BossAgentConfig, db, uid):
        super().__init__(config)
        self.uid = uid
        self.db = db
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.lm = None

    def _initialize_dspy(self):
        try:
            self.lm = dspy.LM('openai/gpt-4o-mini')
            dspy.configure(lm=self.lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
    
    def _initialize_react_agent(self):
        self._initialize_dspy()

        # Create the tool for processing user data
        process_data_tool = dspy.Tool(
            func=self._process_user_data,
            name="extract_user_data",
            desc="Process and store user information with proper categorization",
            args={
                "user_entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                            "category": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "subcategory": {"type": "string"},
                                    "data_type": {"type": "string", "enum": ["single_value", "collection", "object"]}
                                }
                            },
                            "parsed_value": {"type": "object"}
                        }
                    }
                }
            }
        )
        
        # Create and return ReAct agent with our tool
        agent = AsyncReActWrapper(
            InsightSignature,
            tools=[process_data_tool]
        )
        
        agent = dspy.Predict(InsightSignature)
        return agent
    
    def _initialize_agent(self):
        self._initialize_dspy()
        return dspy.ChainOfThought(InsightSignature)
    
    async def _process_user_data(self, db, user_entries, contradictions=None):
        try:
            contradictions = contradictions or []
            user_collection = db['insight']
            update_query = {'uid': self.uid}
            
            # Get current profile data
            current_data = await user_collection.find_one(
                {'uid': self.uid}, 
                {'_id': 0, 'profile_data': 1}
            ) or {'profile_data': {}}
            
            current_profile = current_data.get('profile_data', {})
            update_operations = []
            current_timestamp = datetime.now(timezone.utc).isoformat()
            
            # Operations for questions_data and other collections
            push_operations = {'$push': {}}
            
            # Convert contradictions to dicts if they're model objects
            contradiction_dicts = []
            for contradiction in contradictions:
                if hasattr(contradiction, 'model_dump'):
                    contradiction_dict = contradiction.model_dump()
                else:
                    contradiction_dict = contradiction
                    
                # Add timestamp and unique ID if needed
                if 'detected_at' not in contradiction_dict:
                    contradiction_dict['detected_at'] = current_timestamp
                if 'id' not in contradiction_dict or not contradiction_dict['id']:
                    contradiction_dict['id'] = str(uuid.uuid4())
                    
                contradiction_dicts.append(contradiction_dict)
                
            # Store contradiction information if any
            for contradiction in contradiction_dicts:
                category_name = contradiction.get('category', '').replace(' ', '_').lower()
                subcategory_name = contradiction.get('subcategory', '').replace(' ', '_').lower()
                
                # Store in contradictions collection
                contradiction_path = f"contradictions.{category_name}.{subcategory_name}"
                push_operations['$push'][contradiction_path] = contradiction
                
                # Mark contradicted entries in questions_data as superseded
                # This allows us to filter them out when exporting for fine-tuning
                entry_id = contradiction.get('entry_id')
                if entry_id:
                    await user_collection.update_many(
                        {'uid': self.uid, f"questions_data.{category_name}.{subcategory_name}.entry_id": entry_id},
                        {'$set': {f"questions_data.{category_name}.{subcategory_name}.$.superseded": True}}
                    )

                # For contradictions needing clarification, add to review queue
                if contradiction.get('recommended_action') == 'needs_clarification':
                    push_operations['$push']['contradiction_review_queue'] = contradiction
            
            # Convert user entries to dicts if they're model objects
            entry_dicts = []
            for entry in user_entries:
                if hasattr(entry, 'model_dump'):
                    entry_dict = entry.model_dump()
                else:
                    entry_dict = entry
                entry_dicts.append(entry_dict)
                
            # Define threshold for automatic acceptance
            CONFIDENCE_THRESHOLD = 0.7
            
            # Process each user entry
            for entry_dict in entry_dicts:
                category_name = entry_dict['category']['name'].replace(' ', '_').lower()
                subcategory_name = entry_dict['category']['subcategory'].replace(' ', '_').lower()
                data_type = entry_dict['category'].get('data_type', 'single_value')
                confidence = entry_dict.get('confidence', 0.8)
                
                category_path = f"questions_data.{category_name}.{subcategory_name}"
                profile_path = f"profile_data.{category_name}.{subcategory_name}"
                
                # Add to questions_data (always)
                entry_copy = entry_dict.copy()
                entry_copy['timestamp'] = current_timestamp
                category_info = entry_copy.pop('category')
                
                # For low confidence items, flag for review
                if confidence < CONFIDENCE_THRESHOLD:
                    review_path = f"review_queue.{category_name}.{subcategory_name}"
                    push_operations['$push'][review_path] = {
                        **entry_copy,
                        "status": "pending",
                        "flagged_reason": "low_confidence"
                    }
                    continue

                # Check if this entry is involved in a contradiction
                entry_contradictions = [c for c in contradiction_dicts if 
                                    c.get('category', '').replace(' ', '_').lower() == category_name and 
                                    c.get('subcategory', '').replace(' ', '_').lower() == subcategory_name]

                print(f"Entry contradictions: {entry_contradictions}")
                
                # Set default superseded status
                entry_copy['superseded'] = False

                # If contradictions exist, handle according to recommended action
                if entry_contradictions:
                    contradiction = entry_contradictions[0]  # Use the first matching contradiction
                    recommended_action = contradiction.get('recommended_action', 'needs_clarification')
                    
                    # Record this resolution regardless of the action taken
                    resolution_record = {
                        **contradiction,
                        'resolved_at': current_timestamp
                    }
                    
                    if recommended_action == 'keep_existing':
                        # Skip updating profile, just record the resolution
                        resolution_record['resolution'] = 'kept_existing_value'
                        push_operations['$push']['resolved_contradictions'] = resolution_record
                        
                        # Mark this entry as superseded since we're keeping the existing value
                        entry_copy['superseded'] = True
                        continue  # Skip the rest of the processing for this entry
                        
                    elif recommended_action == 'needs_clarification':
                        # Flag for human review, skip updating profile
                        push_operations['$push']['contradiction_review_queue'] = {
                            **contradiction,
                            'entry_data': entry_copy,
                            'status': 'pending'
                        }
                        continue  # Skip the rest of the processing for this entry
                        
                    elif recommended_action == 'merge':
                        # Record that we're doing a merge
                        resolution_record['resolution'] = 'merged_values'
                        push_operations['$push']['resolved_contradictions'] = resolution_record
                        
                        # Mark the existing entries as partially superseded
                        await user_collection.update_many(
                            {'uid': self.uid, f"questions_data.{category_name}.{subcategory_name}.superseded": {'$ne': True}},
                            {'$set': {f"questions_data.{category_name}.{subcategory_name}.$[elem].partially_superseded": True}},
                            array_filters=[{"elem.entry_id": {'$ne': entry_dict.get('entry_id')}}]
                        )
                    else:  # 'keep_new' or any other value
                        # Proceed with normal update and record resolution
                        resolution_record['resolution'] = 'used_new_value'
                        push_operations['$push']['resolved_contradictions'] = resolution_record
                        
                        # Mark all previous entries in this category/subcategory as superseded
                        await user_collection.update_many(
                            {'uid': self.uid},
                            {'$set': {f"questions_data.{category_name}.{subcategory_name}.$[elem].superseded": True}},
                            array_filters=[{"elem.superseded": {'$ne': True}}]
                        )

                
                # Get existing data for this category/subcategory
                existing_data = self._get_nested_dict_value(current_profile, category_name, subcategory_name, default=None)
                
                # Create a version record before updating (for temporal tracking)
                if existing_data:
                    version_path = f"profile_history.{category_name}.{subcategory_name}"
                    push_operations['$push'][version_path] = {
                        'value': existing_data,
                        'timestamp': current_timestamp,
                        'change_type': 'update',
                        'triggered_by': entry_dict.get('question', 'conversation')
                    }
                
                push_operations['$push'][category_path] = entry_copy

                # Update profile data based on data type
                if data_type == 'single_value':
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "value": entry_dict['answer'],
                                "confidence": confidence,
                                "created_at": existing_data.get('created_at', current_timestamp) if existing_data else current_timestamp,
                                "updated_at": current_timestamp
                            }
                        }
                    })
                
                elif data_type == 'collection':
                    items = self._parse_collection_items(entry_dict['answer'])
                    
                    # Get current collection or initialize empty
                    current_items = []
                    current_confidence = {}
                    if existing_data:
                        current_items = existing_data.get('items', [])
                        current_confidence = existing_data.get('confidence', {})
                    
                    # Handle merge recommendation for collections
                    is_merge = any(c.get('recommended_action') == 'merge' for c in entry_contradictions)
                    
                    # Add new items with their confidence scores
                    for item in items:
                        item_key = item.lower()
                        # For merges, we add new items without removing existing ones
                        if item_key not in [x.lower() for x in current_items]:
                            current_items.append(item)
                            current_confidence[item] = confidence
                        elif confidence > current_confidence.get(item, 0) or is_merge:
                            # Update confidence if new extraction has higher confidence
                            current_confidence[item] = confidence
                    
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "items": current_items,
                                "confidence": current_confidence,
                                "created_at": existing_data.get('created_at', current_timestamp) if existing_data else current_timestamp,
                                "updated_at": current_timestamp
                            }
                        }
                    })
                    
                elif data_type == 'object':
                    properties = self._parse_object_properties(entry_dict['answer'])
                    
                    # Merge with existing properties
                    current_properties = {}
                    current_confidence = {}
                    if existing_data:
                        current_properties = existing_data.get('properties', {})
                        current_confidence = existing_data.get('confidence', {})
                    
                    # Handle merge recommendation for objects
                    is_merge = any(c.get('recommended_action') == 'merge' for c in entry_contradictions)
                    
                    # Update properties and their confidence
                    for key, value in properties.items():
                        current_properties[key] = value
                        current_confidence[key] = max(confidence, current_confidence.get(key, 0)) if is_merge else confidence
                    
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "properties": current_properties,
                                "confidence": current_confidence,
                                "created_at": existing_data.get('created_at', current_timestamp) if existing_data else current_timestamp,
                                "updated_at": current_timestamp
                            }
                        }
                    })
            
            # Execute operations
            if push_operations['$push']:
                await user_collection.update_one(update_query, push_operations, upsert=True)
            
            for operation in update_operations:
                await user_collection.update_one(update_query, operation, upsert=True)
            
            # Return updated data for client notification
            updated_data = await user_collection.find_one(
                {'uid': self.uid}, 
                {'_id': 0, 'profile_data': 1, 'questions_data': 1, 'review_queue': 1, 'contradictions': 1}
            )
            
            await self.sio.emit('insight_user_data', json.dumps(updated_data))
            
            # If there are items in the contradiction review queue, notify the admin interface
            if 'contradiction_review_queue' in updated_data and updated_data['contradiction_review_queue']:
                await self.sio.emit('insight_contradictions', json.dumps({'review_queue': updated_data['contradiction_review_queue']}))
            
            return f"Successfully processed {len(user_entries)} entries and updated the database"

        except Exception as e:
            error_msg = f"Error processing user data: {str(e)}"
            logging.error(error_msg)
            return error_msg

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

    async def _analyze_conversation_task(self, conversation):
        # Get existing profile data
        client = MongoDbClient('paxxium')
        user_collection = client.db['insight']
        profile_data = await user_collection.find_one(
            {'uid': self.uid},
            {'_id': 0, 'profile_data': 1}
        ) or {'profile_data': {}}

        agent = dspy.asyncify(self._initialize_agent())
        result = await agent(
            conversation=conversation,
            profile=profile_data['profile_data']
        )

        if result.user_entries:
            await self._process_user_data(client.db, result.user_entries, result.contradictions)

    async def _create_message(self, message_from: str, message_content: str):
        """
        Creates a new message in the insight document.
        """
        current_time = datetime.now(timezone.utc).isoformat()
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'current_time': current_time,
        }

        await self.db['insight'].update_one(
            {'uid': self.uid}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            },
            upsert=True
        )
    
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
        await self._create_message('user', user_message.get('content'))
        return await super().process_message(user_input, 'insight', lambda cid, msg: self._create_message('agent', msg))
    
    