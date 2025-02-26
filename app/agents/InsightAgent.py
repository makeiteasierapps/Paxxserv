from datetime import datetime, timezone
import asyncio
import threading
import os
import logging
import json
import re
import dspy
from typing import List, Optional, Union, Literal
from bson import ObjectId
from pydantic import BaseModel, Field
from app.agents.BossAgent import BossAgentConfig, BossAgent
from app.utils.AsyncReAct import AsyncReActWrapper
from app.services.MongoDbClient import MongoDbClient

logger = logging.getLogger(__name__)
# Enhanced Pydantic models with data type
class Category(BaseModel):
    name: str = Field(description="The category this answer belongs to.")
    subcategory: str = Field(description="A subcategory that best describes this answer.")
    data_type: Literal["single_value", "collection", "object"] = Field(
        description="How this data should be stored: 'single_value' for one piece of info, 'collection' for lists of items, 'object' for structured data.",
        default="single_value"
    )

class UserEntry(BaseModel):
    question: str = Field(description="The original question that prompted the user's response.")
    answer: str = Field(description="A specific piece of user-provided information.")
    category: Category = Field(description="The category and subcategory that best describes this answer.")
    parsed_value: Optional[Union[str, List[str], dict]] = Field(
        default=None, 
        description="The parsed version of the answer - either a single value, a list of items, or key-value pairs"
    )

class InsightSignature(dspy.Signature):
    """Only extract information not already in the user's profile data.
    
    For each extracted piece of information, determine its category, subcategory, and data_type.
    Use data_type 'single_value' for facts that are singular (like birth date or favorite color),
    'collection' for data that represents lists of items (like hobbies, foods liked, friends),
    and 'object' for structured information with multiple properties (like daily routines, preferences with reasons).
    """
    
    conversation: List[dict] = dspy.InputField(desc="The conversation history between user and agent")
    profile: dict = dspy.InputField(desc="The user's existing profile data")
    user_entries: List[UserEntry] = dspy.OutputField(desc="Extracted and categorized user information")

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
        
        class ExtractUserInsights(dspy.Module):
            def __init__(self, lm):
                super().__init__()
                self.predictor = dspy.ChainOfThought(InsightSignature)
                self.lm = lm
                
            def forward(self, conversation, profile):
                # First, get the user entries with categories and data types
                result = self.predictor(conversation=conversation, profile=profile)
                
                # Then, parse the values for each entry based on its data type
                for entry in result.user_entries:
                    # Check if we need to parse the data
                    if entry.parsed_value is None:
                        entry.parsed_value = self._parse_value(
                            entry.answer, 
                            entry.category.data_type,
                            entry.category.name,
                            entry.category.subcategory
                        )
                        
                return result
                
            def _parse_value(self, answer, data_type, category, subcategory):
                """Parse the answer based on its data type"""
                if data_type == "single_value":
                    return answer.strip()
                    
                elif data_type == "collection":
                    return self._parse_collection(answer, category, subcategory)
                    
                elif data_type == "object":
                    return self._parse_object(answer, category, subcategory)
                    
                return answer
                
            def _parse_collection(self, answer, category, subcategory):
                """Extract a list of items from the answer"""
                prompt = f"""
                Extract all distinct items from this answer about {category}/{subcategory}.
                Return them as a JSON array of strings.
                
                Answer: "{answer}"
                
                JSON Items:
                """
                
                try:
                    response = self.lm.generate(prompt)
                    items = json.loads(response.strip())
                    return items if isinstance(items, list) else [items]
                except Exception as e:
                    logger.error("Error parsing collection: %s", e)
                    # Fallback to simple extraction
                    return [item.strip() for item in re.split(r'[,;]|\band\b', answer) if item.strip()]
                    
            def _parse_object(self, answer, category, subcategory):
                """Extract structured data from the answer"""
                prompt = f"""
                Extract key pieces of information from this answer about {category}/{subcategory}.
                Return them as a JSON object with property names and values.
                
                Answer: "{answer}"
                
                JSON Properties:
                """
                
                try:
                    response = self.lm.generate(prompt)
                    properties = json.loads(response.strip())
                    return properties if isinstance(properties, dict) else {}
                except Exception as e:
                    logger.error("Error parsing object: %s", e)
                    # Fallback to simple extraction
                    properties = {}
                    for match in re.finditer(r'(\w+(?:\s+\w+)*)\s*(?:is|:)\s*([^,.;]+)', answer):
                        key, value = match.groups()
                        properties[key.strip().lower()] = value.strip()
                    return properties
        
        return ExtractUserInsights(self.lm)
    
    async def _process_user_data(self, db, user_entries):
        try:
            user_entries = [entry if isinstance(entry, dict) else entry.model_dump() for entry in user_entries]
            logger.info("Processing user data: %s", user_entries)
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
            
            # Operations for questions_data (always append)
            push_operations = {'$push': {}}
            
            for entry in user_entries:
                category_name = entry['category']['name'].replace(' ', '_').lower()
                subcategory_name = entry['category']['subcategory'].replace(' ', '_').lower()
                data_type = entry['category'].get('data_type', 'single_value')  # Default to single_value
                category_path = f"questions_data.{category_name}.{subcategory_name}"
                profile_path = f"profile_data.{category_name}.{subcategory_name}"
                # Add to questions_data (always)
                entry_copy = entry.copy()
                entry_copy['timestamp'] = current_timestamp
                category_info = entry_copy.pop('category')  # Remove category before storing
                parsed_value = entry_copy.pop('parsed_value', None)  # Remove parsed_value from questions_data storage
                push_operations['$push'][category_path] = entry_copy
                
                # Get existing data for this category/subcategory
                existing_data = self._get_nested_dict_value(current_profile, category_name, subcategory_name, default=None)
                
                # Update profile data based on type
                if data_type == 'single_value':
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "value": entry['answer'],
                                "last_updated": current_timestamp
                            }
                        }
                    })
                
                elif data_type == 'collection':
                    # Use the parsed collection if available
                    if parsed_value and isinstance(parsed_value, list):
                        items = parsed_value
                    else:
                        items = self._extract_items_from_answer(entry['answer'])
                    
                    # Get current collection or initialize empty
                    current_items = []
                    if existing_data and 'items' in existing_data:
                        current_items = existing_data['items']
                    
                    # Add new items avoiding duplicates
                    for item in items:
                        if item.lower() not in [x.lower() for x in current_items]:
                            current_items.append(item)
                    
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "items": current_items,
                                "last_updated": current_timestamp
                            }
                        }
                    })
                    
                elif data_type == 'object':
                    # Use the parsed properties if available
                    if parsed_value and isinstance(parsed_value, dict):
                        properties = parsed_value
                    else:
                        properties = self._extract_properties_from_answer(entry['answer'])
                    
                    # Merge with existing properties
                    current_properties = {}
                    if existing_data and 'properties' in existing_data:
                        current_properties = existing_data['properties']
                    
                    # Merge objects
                    merged_properties = {**current_properties, **properties}
                    
                    update_operations.append({
                        '$set': {
                            f"{profile_path}": {
                                "properties": merged_properties,
                                "last_updated": current_timestamp
                            }
                        }
                    })
            
            # Execute operations
            if push_operations['$push']:
                await user_collection.update_one(update_query, push_operations, upsert=True)
            
            for operation in update_operations:
                await user_collection.update_one(update_query, operation, upsert=True)
            
            # Return updated data
            updated_data = await user_collection.find_one(
                {'uid': self.uid}, 
                {'_id': 0, 'profile_data': 1, 'questions_data': 1}
            )
            await self.sio.emit('insight_user_data', json.dumps(updated_data))
                
            return f"Successfully processed {len(user_entries)} entries and updated the database"

        except Exception as e:
            error_msg = f"Error processing user data: {str(e)}"
            logging.error(error_msg)
            return error_msg
    
    def _get_nested_dict_value(self, dictionary, *keys, default=None):
        """Helper method to safely get nested dictionary values"""
        current = dictionary
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def _extract_items_from_answer(self, answer):
        """Fallback method to extract items from an answer if LLM parsing fails"""
        items = [item.strip() for item in re.split(r'[,;]|\band\b', answer) if item.strip()]
        return items
    
    def _extract_properties_from_answer(self, answer):
        """Fallback method to extract properties from an answer if LLM parsing fails"""
        properties = {}
        for match in re.finditer(r'(\w+(?:\s+\w+)*)\s*(?:is|:)\s*([^,.;]+)', answer):
            key, value = match.groups()
            properties[key.strip().lower()] = value.strip()
        return properties
        
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
            await self._process_user_data(client.db, result.user_entries)

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