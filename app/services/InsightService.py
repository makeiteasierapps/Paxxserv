import logging
from pydantic import  BaseModel
from typing import List, Optional, Dict, Any


# Database Models
class Answer(BaseModel):
    question: str
    answer: str

class InsightDocument(BaseModel):
    questions_data: Dict[str, Dict[str, List[Answer]]]
    messages: Optional[List[Dict[str, Any]]] = None
    updated_at: Optional[str] = None

class InsightService:
    def __init__(self, db, sio, uid):
        self.db = db
        self.sio = sio
        self.uid = uid
        
    async def get_user_insight(self) -> Optional[InsightDocument]:
        """
        Fetches the user's insight document.
        Returns None if no document is found.
        """
        insight_doc = await self.db['insight'].find_one({'uid': self.uid}, {'messages._id': 0})
        if insight_doc:
            insight_doc['_id'] = str(insight_doc['_id'])
            return InsightDocument(**insight_doc)
        return None

    async def update_profile_answer(self, answer_data: Dict[str, Any]):
        """
        Update or add an answer in the user's profile categories structure.
        The answer will be stored under its respective category and subcategory.
        """
        try:
            index = answer_data['index']
            updated_answer = answer_data['answer']
            category = answer_data['category']
            subcategory = answer_data['subcategory']
            category_path = f"questions_data.{category}.{subcategory}.{index}.answer"
            await self.db['insight'].update_one(
                {'uid': self.uid},
                {'$set': {category_path: updated_answer}}  # Set the answer at the specific index
            )

            return {'message': 'Answer updated successfully'}, 200
            
        except Exception as e:
            logging.error("Error updating profile answer: %s", e)
            raise
