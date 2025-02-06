from pydantic import BaseModel
from typing import List, Optional

# Question Category Container
class Question(BaseModel):
    text: str
    answer: Optional[str] = None

class QuestionCategory(BaseModel):
    category: str
    questions: List[Question]

# Schema for Question Set
class QuestionSet(BaseModel):
    foundational_questions: List[QuestionCategory]
    objective_questions: List[QuestionCategory]