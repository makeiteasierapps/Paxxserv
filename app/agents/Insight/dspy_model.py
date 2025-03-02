from typing import List, Optional, Union, Literal, Any
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
    category: str = Field(description="The category containing the contradiction")
    subcategory: str = Field(description="The subcategory containing the contradiction")
    data_type: str = Field(description="The data type (single_value, collection)")
    existing_value: Any = Field(description="The value currently in the profile")
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
    parsed_value: Optional[Union[str, List[str], dict, int, float]] = Field(
        default=None, 
        description="The parsed version of the answer - either a single value or a list of values"
    )
    confidence: float = Field(
        default=0.8, 
        description="Confidence score from 0.0 to 1.0 indicating certainty of extraction",
        ge=0.0,  # Greater than or equal to 0
        le=1.0   # Less than or equal to 1
    )

class InsightSignature(Signature):
    """Extract information from the conversation and check for contradictions with existing profile data.
    
    For each extracted piece of information, determine:
    1. Its category, subcategory, and data_type
    2. A confidence score (0.0-1.0) indicating how certain you are about this extraction
    3. Whether it contradicts existing profile information
    
    If you detect a contradiction, explicitly flag it and recommend a resolution strategy.
    """
    
    conversation: List[dict] = InputField(desc="The conversation history between user and agent")
    profile: dict = InputField(desc="The user's existing profile data")
    user_entries: List[UserEntry] = OutputField(desc="Extracted and categorized user information with confidence scores")
    contradictions: List[Contradiction] = OutputField(desc="Identified contradictions between new information and existing profile")
