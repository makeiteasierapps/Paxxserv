class ProfileService:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
    
    async def get_user_analysis(self, uid):
        user_doc = await self.db['users'].find_one({'_id': uid}, {'analysis': 1})
        
        if user_doc:
            return user_doc.get('analysis')
        
        return None

    async def get_profile(self, uid):
        user_doc = await self.db['users'].find_one(
            {'_id': uid}, 
            {'first_name': 1, 'last_name': 1, 'username': 1, 'analysis': 1, 'avatar_path': 1, 'is_admin': 1}
        )
        
        if user_doc:
            user_doc.pop('_id')
        
        return user_doc

    async def load_questions(self, uid, fetch_answered=False):
        """
        Fetches the question/answers map from the user's profile in MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        If fetchAnswered is True, only returns answered questions.
        """
        questions_cursor = self.db['questions'].find({'uid': uid})
        questions_array = []
        
        async for question_doc in questions_cursor:
            question_doc['_id'] = str(question_doc['_id'])
            if fetch_answered:
                question_doc['questions'] = [q for q in question_doc['questions'] if q.get('answer') is not None]
                if not question_doc['questions']:
                    continue
            questions_array.append(question_doc)

        return questions_array
    
    async def update_profile_answer(self, question_id, answer):
        """
        Update a single answer in the user's profile for MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """
        await self.db['questions'].update_one(
            {'uid': self.uid, 'questions._id': question_id},
            {'$set': {'questions.$.answer': answer}}
        )

        return {'message': 'User answer updated'}, 200
    
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