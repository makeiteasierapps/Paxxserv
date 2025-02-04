class ProfileService:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid

    async def get_profile(self, uid):
        user_doc = await self.db['users'].find_one(
            {'_id': uid}, 
            {'first_name': 1, 'last_name': 1, 'username': 1, 'analysis': 1, 'avatar_path': 1, 'is_admin': 1}
        )
        
        if user_doc:
            user_doc.pop('_id')
        
        return user_doc
    
    async def update_user_profile(self, uid, updates):
        users_collection = self.db['users']
       
        if 'topics' in updates:
            topics_list = [topic.lower().strip() for topic in updates['topics']]
            updates['topics'] = {"$addToSet": {"topics": {"$each": topics_list}}}

        user_doc = await users_collection.find_one({"_id": uid})
        if user_doc:
            # Update existing user
            if 'topics' in updates:
                # Special handling for topics to use $addToSet for array elements
                topics = updates.pop('topics')
                await users_collection.update_one(
                    {"_id": uid}, 
                    {"$set": updates, **topics}
                )
            else:
                await users_collection.update_one(
                    {"_id": uid}, 
                    {"$set": updates}
                )
        else:
            # Create new user
            updates['_id'] = uid  # Ensure the document has the UID as its _id
            await users_collection.insert_one(updates)