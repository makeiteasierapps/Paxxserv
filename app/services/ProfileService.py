from ..agents.OpenAiClientBase import OpenAiClientBase

class ProfileService(OpenAiClientBase):
    
    # Refactor this to use dspy, its not always outputing the json in the correct format
    def get_user_analysis(self, message):
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