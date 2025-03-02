from datetime import datetime, timezone
from bson import ObjectId

class InsightDbManager:
    def __init__(self, uid, db):
        self.uid = uid
        self.db = db

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

        await self.db['insight'].update_one(
            {'uid': self.uid}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            },
            upsert=True
        )

    async def fetch_updated_data(self, user_collection):
        projection = {
            '_id': 0,
            'profile_data': 1,
            'questions_data': 1,
            'review_queue': 1,
            'contradictions': 1,
            'contradiction_review_queue': 1
        }
        return await user_collection.find_one({'uid': self.uid}, projection)

    async def execute_db_operations(self, user_collection, push_operations, update_operations):
        if push_operations.get('$push'):
            await user_collection.update_one({'uid': self.uid}, push_operations, upsert=True)

        for operation in update_operations:
            await user_collection.update_one({'uid': self.uid}, operation, upsert=True)

    async def handle_keep_existing_resolution(self, push_operations, resolution_record, entry_copy):
        resolution_record['resolution'] = 'kept_existing_value'
        push_operations['$push'].setdefault('resolved_contradictions', []).append(resolution_record)
        entry_copy['superseded'] = True

    async def handle_needs_clarification_resolution(self, push_operations, contradiction, entry_copy):
        push_operations['$push'].setdefault('contradiction_review_queue', []).append({
            **contradiction, 'entry_data': entry_copy, 'status': 'pending'
        })

    async def handle_merge_resolution(self, user_collection, push_operations, resolution_record, entry_id):
        resolution_record['resolution'] = 'merged_values'
        push_operations['$push'].setdefault('resolved_contradictions', []).append(resolution_record)
        await self.mark_entries_partially_superseded(user_collection, entry_id)

    async def handle_keep_new_resolution(self, user_collection, push_operations, resolution_record, entry_id):
        resolution_record['resolution'] = 'used_new_value'
        push_operations['$push'].setdefault('resolved_contradictions', []).append(resolution_record)
        await self.mark_entries_superseded(user_collection, entry_id)

    def _parse_entry_id(self, entry_id):
        """Extract category and subcategory from the structured entry_id"""
        parts = entry_id.split('.')
        if len(parts) >= 3:
            return parts[0], parts[1]
        return None, None

    async def mark_entries_superseded(self, user_collection, entry_id):
        category, subcategory = self._parse_entry_id(entry_id)
        if category and subcategory:
            await user_collection.update_many(
                {'uid': self.uid},
                {'$set': {f"questions_data.{category}.{subcategory}.$[elem].superseded": True}},
                array_filters=[{"elem.entry_id": {'$ne': entry_id}, "elem.superseded": {'$ne': True}}]
            )

    async def mark_entries_partially_superseded(self, user_collection, entry_id):
        category, subcategory = self._parse_entry_id(entry_id)
        if category and subcategory:
            await user_collection.update_many(
                {'uid': self.uid},
                {'$set': {f"questions_data.{category}.{subcategory}.$[elem].partially_superseded": True}},
                array_filters=[{"elem.entry_id": {'$ne': entry_id}, "elem.superseded": {'$ne': True}}]
            )

    async def get_current_profile(self, user_collection):
        current_data = await user_collection.find_one({'uid': self.uid}, {'_id': 0, 'profile_data': 1}) or {}
        return current_data.get('profile_data', {})