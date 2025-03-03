from datetime import datetime, timezone
from bson import ObjectId
from app.agents.insight.helpers import parse_entry_id

class InsightDbManager:
    def __init__(self, uid, db):
        self.uid = uid
        self.db = db
        self.user_collection = db['insight']

    async def create_message(self, message_from: str, message_content: str):
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

        await self.user_collection.update_one(
            {'uid': self.uid}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            },
            upsert=True
        )

    async def add_new_contradiction(self, contradiction_path, contradiction):
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {contradiction_path: contradiction}}
        )

    async def fetch_updated_data(self):
        projection = {
            '_id': 0,
            'profile_data': 1,
            'questions_data': 1,
            'review_queue': 1,
            'contradictions': 1,
            'contradiction_review_queue': 1
        }
        return await self.user_collection.find_one({'uid': self.uid}, projection)

    async def handle_needs_clarification_resolution(self, contradiction, entry_dict):
        """Handle cases where the contradiction needs human clarification"""
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {
                'contradiction_review_queue': {
                    **contradiction,
                    'entry_data': entry_dict,
                    'status': 'pending'
                }
            }}
        )

    async def handle_keep_existing_resolution(self, resolution_record):
        """Handle cases where we keep the existing value"""
        resolution_record['resolution'] = 'kept_existing_value'
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {'resolved_contradictions': resolution_record}}
        )

    async def handle_merge_resolution(self, resolution_record, old_entry_id):
        """Handle cases where values should be merged"""
        old_category, old_subcategory = parse_entry_id(old_entry_id)
        
        # Remove old entry
        if old_category and old_subcategory:
            await self.user_collection.update_one(
                {'uid': self.uid},
                {'$pull': {
                    f"questions_data.{old_category}.{old_subcategory}": {
                        'entry_id': old_entry_id
                    }
                }}
            )
        
        resolution_record['resolution'] = 'merged_values'
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {'resolved_contradictions': resolution_record}}
        )

    async def handle_keep_new_resolution(self, resolution_record, old_entry_id):
        """Handle cases where we keep the new value"""
        old_category, old_subcategory = parse_entry_id(old_entry_id)
        
        # Remove old entry
        if old_category and old_subcategory:
            await self.user_collection.update_one(
                {'uid': self.uid},
                {'$pull': {
                    f"questions_data.{old_category}.{old_subcategory}": {
                        'entry_id': old_entry_id
                    }
                }}
            )
        
        resolution_record['resolution'] = 'used_new_value'
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {'resolved_contradictions': resolution_record}}
        )

    async def get_current_profile(self):
        current_data = await self.user_collection.find_one({'uid': self.uid}, {'_id': 0, 'profile_data': 1}) or {}
        return current_data.get('profile_data', {})

    async def update_profile_version_history(self, category_name, subcategory_name, existing_data, current_timestamp, trigger):
        """Add existing data to profile history before updating"""
        version_path = f"profile_history.{category_name}.{subcategory_name}"
        item = {
            'value': existing_data,
            'timestamp': current_timestamp,
            'change_type': 'update',
            'triggered_by': trigger
        }
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {version_path: item}}
        )

    async def add_questions_entry(self, category_name, subcategory_name, entry_data):
        """Add new entry to questions data"""
        category_path = f"questions_data.{category_name}.{subcategory_name}"
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$push': {category_path: entry_data}}
        )

    async def update_profile_data(self, category_name, subcategory_name, profile_update):
        """Update profile data with new values"""
        profile_path = f"profile_data.{category_name}.{subcategory_name}"
        await self.user_collection.update_one(
            {'uid': self.uid},
            {'$set': {profile_path: profile_update}}
        )