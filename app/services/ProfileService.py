from ..agents.OpenAiClientBase import OpenAiClientBase

class ProfileService(OpenAiClientBase):
    
    # Refactor this to use dspy, its not always outputing the json in the correct format
    def analyze_user_profile(self, message):
        messages=[
                {
                    "role": "system",
                    "content": '''
                    You are an expert in identify the personality traits of your user.
                    Your response must be in json format with the following structure:
                        - analysis: provide a personality analysis of the user based on their answers to the questions. Do not simply summarize the answers, but provide a unique analysis of the user.
                        - news_topics: Should be a list of queries that are one or two words and be a good query parameter for calling a news API. Your topics should be derived from your analyis. Example formats: 2 words - Rock climbing - 1 word -AI
                        '''
                    },
                    {
                'role': 'user',
                'content': f'''{message}''',
                }
                
            ]
        
        response = self.pass_to_openai(messages, json=True)
            

        return response
    
    def get_profile(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'first_name': 1, 'last_name': 1, 'username': 1, 'avatar_url': 1, 'analysis': 1})
        
        if user_doc:
            user_doc.pop('_id')
        
        return user_doc

    @staticmethod
    def extract_data_for_prompt(answers):
        """ 
        Extracts the data from the answers dictionary and formats it for the prompt
        """
        prompt = ''
        for category, questions in answers.items():
            for question, answer in questions.items():
                prompt += f'{category}: {question} - Answer: {answer}\n'
        
        return prompt
    
    def prepare_analysis_prompt(self, uid):
        """
        Generates a prompt to analyze
        """
        
        q_a = self.load_questions(uid)
        prompt = ProfileService.extract_data_for_prompt(q_a)

        return prompt
        
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
    
    def load_questions(self, uid):
        """
        Fetches the question/answers map from the user's profile in MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """

        # Find the profile document by user ID reference
        question_docs = self.db['questions'].find({'uid': uid})

        questions_array = []
        for question_doc in question_docs:
            question_doc['_id'] = str(question_doc['_id'])
            questions_array.append(question_doc)

        return questions_array
    
    def update_user_profile(self, uid, updates):
        users_collection = self.db['users']  # Access the 'users' collection
       
        if 'news_topics' in updates:
            news_topics_list = [topic.lower().strip() for topic in updates['news_topics']]
            updates['news_topics'] = {"$addToSet": {"news_topics": {"$each": news_topics_list}}}

        user_doc = users_collection.find_one({"_id": uid})
        if user_doc:
            # Update existing user
            if 'news_topics' in updates:
                # Special handling for news_topics to use $addToSet for array elements
                news_topics_update = updates.pop('news_topics')
                users_collection.update_one({"_id": uid}, {"$set": updates, **news_topics_update})
            else:
                users_collection.update_one({"_id": uid}, {"$set": updates})
        else:
            # Create new user
            updates['_id'] = uid  # Ensure the document has the UID as its _id
            users_collection.insert_one(updates)
  