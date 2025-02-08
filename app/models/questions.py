from pydantic import BaseModel
from typing import List 
# Question Category Container
class QuestionCategory(BaseModel):
    category: str
    questions: List[str] 
# Schema for Question Set
class QuestionSet(BaseModel):
    foundational_questions: List[QuestionCategory]
    objective_questions: List[QuestionCategory]