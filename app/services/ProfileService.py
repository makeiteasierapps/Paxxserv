class ProfileService:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
    
    def get_user_analysis(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'analysis': 1})
        
        if user_doc:
            return user_doc.get('analysis')
        
        return None
    def get_profile(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'first_name': 1, 'last_name': 1, 'username': 1, 'analysis': 1})
        
        if user_doc:
            user_doc.pop('_id')
        
        return user_doc

    def load_questions(self, uid, fetch_answered=False):
        """
        Fetches the question/answers map from the user's profile in MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        If fetchAnswered is True, only returns answered questions.
        """

        question_docs = self.db['questions'].find({'uid': uid})

        questions_array = []
        for question_doc in question_docs:
            question_doc['_id'] = str(question_doc['_id'])
            if fetch_answered:
                question_doc['questions'] = [q for q in question_doc['questions'] if q.get('answer') is not None]
                if not question_doc['questions']:
                    continue
            questions_array.append(question_doc)

        return questions_array
    
    def update_profile_answer(self, question_id, answer):
        """
        Update a single answer in the user's profile for MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """

        self.db['questions'].update_one(
            {'uid': self.uid, 'questions._id': question_id},
            {'$set': {'questions.$.answer': answer}}
        )

        return {'message': 'User answer updated'}, 200
    
    def update_user_profile(self, uid, updates):
        users_collection = self.db['users']  # Access the 'users' collection
       
        if 'topics' in updates:
            topics_list = [topic.lower().strip() for topic in updates['topics']]
            updates['topics'] = {"$addToSet": {"topics": {"$each": topics_list}}}

        user_doc = users_collection.find_one({"_id": uid})
        if user_doc:
            # Update existing user
            if 'topics' in updates:
                # Special handling for topics to use $addToSet for array elements
                topics = updates.pop('topics')
                users_collection.update_one({"_id": uid}, {"$set": updates, **topics})
            else:
                users_collection.update_one({"_id": uid}, {"$set": updates})
        else:
            # Create new user
            updates['_id'] = uid  # Ensure the document has the UID as its _id
            users_collection.insert_one(updates)
  