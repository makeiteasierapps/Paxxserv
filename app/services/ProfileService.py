class ProfileService:
    def __init__(self, db, openai_client):
        self.db = db
        self.openai_client = openai_client
        self.model = 'gpt-4o'

    # Refactor this to use dspy, its not always outputing the json in the correct format
    def pass_to_profile_agent(self, message):
        response = self.openai_client.chat.completions.create(
            model=self.model,
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
                
            ],
            response_format={ "type": "json_object" },
        )
        return response.choices[0].message.content