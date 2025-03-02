from typing import List, Literal, Any
from pydantic import BaseModel, Field
from dspy import Signature, InputField, OutputField

class Category(BaseModel):
    name: str = Field(description="The category this answer belongs to.")
    subcategory: str = Field(description="A subcategory that best describes this answer.")
    data_type: Literal["single_value", "collection"] = Field(
        description="How this data should be stored: 'single_value' for one piece of info, 'collection' for lists of items.",
        default="single_value"
    )

class Contradiction(BaseModel):
    new_value: Any = Field(description="The newly extracted value")
    entry_id: str = Field(description="Reference to the corresponding user entry")
    recommended_action: str = Field(
        description="Recommended action: 'keep_new', 'keep_existing', 'merge', or 'needs_clarification'"
    )
    reasoning: str = Field(description="Explanation of why this is a contradiction and the recommended action")

class UserEntry(BaseModel):
    question: str = Field(description="The original question that prompted the user's response.")
    answer: str = Field(description="A specific piece of user-provided information.")
    category: Category = Field(description="The category and subcategory that best describes this answer.")

class InsightSignature(Signature):
    """Used to extract information from the conversation and check for contradictions with existing profile data.
    
    Only extract information not contained in the existing profile.
    For each extracted piece of information, determine:
    1. Its category, subcategory, and data_type
    2. Whether it contradicts existing profile information
    
    If you detect a contradiction, explicitly flag it and recommend a resolution strategy.
    """
    
    conversation: List[dict] = InputField(desc="The conversation history between user and agent")
    profile: dict = InputField(desc="The user's existing profile data")
    user_entries: List[UserEntry] = OutputField(desc="Extracted and categorized user information")
    contradictions: List[Contradiction] = OutputField(desc="Identified contradictions between new information and existing profile")
