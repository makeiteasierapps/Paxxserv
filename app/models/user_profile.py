from typing import List, Optional
from pydantic import BaseModel
def create_original_json_structure() -> dict:
    return {
        "foundational": [
            {
                "category": "Basic Demographics",
                "data": [BasicDemographics().model_dump()]
            },
            {
                "category": "Personal Background",
                "data": [PersonalBackground().model_dump()]
            },
            {
                "category": "Interests and Hobbies",
                "data": [InterestsAndHobbies().model_dump()]
            },
            {
                "category": "Social Relationships",
                "data": [SocialRelationships().model_dump()]
            },
            {
                "category": "Emotional Well-being and Self-View",
                "data": [EmotionalWellbeing().model_dump()]
            },
            {
                "category": "Identity and Personal Narrative",
                "data": [IdentityAndPersonalNarrative().model_dump()]
            }
        ],
        "objective": [
            {
                "category": "Daily Routine",
                "data": [DailyRoutine().model_dump()]
            },
            {
                "category": "Work Life Balance",
                "data": [WorkLifeBalance().model_dump()]
            },
            {
                "category": "Lifestyle Preferences",
                "data": [LifestylePreferences().model_dump()]
            },
            {
                "category": "Goals and Aspirations",
                "data": [GoalsAndAspirations().model_dump()]
            },
            {
                "category": "Values and Beliefs",
                "data": [ValuesAndBeliefs().model_dump()]
            },
            {
                "category": "Behavior Patterns",
                "data": [BehaviorPatterns().model_dump()]
            },
            {
                "category": "Challenges and Pain Points",
                "data": [ChallengesAndPainPoints().model_dump()]
            },
            {
                "category": "Technology and System Features",
                "data": [TechnologyAndSystemFeatures().model_dump()]
            },
            {
                "category": "Mindset and Attitude",
                "data": [MindsetAndAttitude().model_dump()]
            },
            {
                "category": "Emotional Intelligence",
                "data": [EmotionalIntelligence().model_dump()]
            },
            {
                "category": "Personal Growth",
                "data": [PersonalGrowth().model_dump()]
            },
            {
                "category": "Future Social Relationship Goals",
                "data": [FutureSocialRelationshipGoals().model_dump()]
            },
            {
                "category": "Future Identity",
                "data": [FutureIdentity().model_dump()]
            }
        ]
    }

# Basic Demographics Models
class Location(BaseModel):
    city: Optional[str] = ""
    country: Optional[str] = ""

class BasicDemographics(BaseModel):
    name: Optional[str] = ""
    age_range: Optional[str] = ""
    gender_identity: Optional[str] = ""
    location: Location
    language_preferences: Optional[str] = ""
    relationship_status: Optional[str] = ""
    family_structure: Optional[str] = ""

# Personal Background Models
class EducationBackground(BaseModel):
    level: Optional[str] = ""
    fields_of_study: List[str] = []

class ProfessionalBackground(BaseModel):
    industry: Optional[str] = ""
    roles: List[str] = []
    achievements: List[str] = []

class CulturalInfluences(BaseModel):
    heritage: Optional[str] = ""
    traditions: List[str] = []
    languages_spoken: List[str] = []

class PersonalBackground(BaseModel):
    education_background: EducationBackground
    professional_background: ProfessionalBackground
    cultural_influences: CulturalInfluences
    significant_life_events: List[str] = []
    childhood_and_family_experience: Optional[str] = ""
    major_transitions: List[str] = []
    personal_challenges: Optional[str] = ""

# Interests and Hobbies Model
class InterestsAndHobbies(BaseModel):
    regular_hobbies: List[str] = []
    current_interests: List[str] = []
    artistic_inclinations: Optional[str] = ""
    learning_interests: List[str] = []
    passions: Optional[str] = ""
    hobbies_shared_with_others: List[str] = []
    comfort_activities: List[str] = []

# Social Relationships Model
class SocialRelationships(BaseModel):
    relationship_history: Optional[str] = ""
    current_dynamics: Optional[str] = ""
    interaction_patterns: Optional[str] = ""

# Emotional Well-being Models
class EmotionalLandscape(BaseModel):
    mood_patterns: List[str] = []
    emotional_triggers: List[str] = []

class SelfPerception(BaseModel):
    strengths: List[str] = []
    weaknesses: List[str] = []
    self_worth: Optional[str] = ""

class CopingMechanisms(BaseModel):
    handling_stress: Optional[str] = ""
    emotional_regulation: Optional[str] = ""

class EmotionalWellbeing(BaseModel):
    emotional_landscape: EmotionalLandscape
    self_perception: SelfPerception
    coping_mechanisms: CopingMechanisms

# Identity Models
class LifePhilosophy(BaseModel):
    guiding_principles: List[str] = []
    life_meaning: Optional[str] = ""

class PersonalStorytelling(BaseModel):
    narratives_about_self: List[str] = []
    life_lessons: List[str] = []

class IdentityAndPersonalNarrative(BaseModel):
    life_philosophy: LifePhilosophy
    pivotal_past_experiences: List[str] = []
    personal_storytelling: PersonalStorytelling

# Foundational Category Container
class FoundationalCategory(BaseModel):
    category: str
    data: List[BasicDemographics | PersonalBackground | InterestsAndHobbies | 
               SocialRelationships | EmotionalWellbeing | IdentityAndPersonalNarrative]

# Objective Models
class DailyRoutine(BaseModel):
    work: Optional[str] = ""
    leisure: Optional[str] = ""
    exercise: Optional[str] = ""

class WorkLifeBalance(BaseModel):
    hours: Optional[str] = ""
    flexibility: Optional[str] = ""
    stress_management: Optional[str] = ""

class LifestylePreferences(BaseModel):
    daily_routine: DailyRoutine
    work_life_balance: WorkLifeBalance
    travel_types_and_destinations: List[str] = []
    health_and_wellbeing_practices: List[str] = []

class GoalsAndAspirations(BaseModel):
    short_term_goals: List[str] = []
    long_term_objectives: List[str] = []
    aspirational_projects: List[str] = []
    legacy_and_impact: Optional[str] = ""

class ValuesAndBeliefs(BaseModel):
    core_values: List[str] = []
    philosophical_alignments: List[str] = []
    social_concerns: List[str] = []
    community_involvement: List[str] = []

class BehaviorPatterns(BaseModel):
    preferred_communication_style: Optional[str] = ""
    interaction_frequency: Optional[str] = ""
    typical_engagement_levels: Optional[str] = ""
    networking_approach: Optional[str] = ""

class ChallengesAndPainPoints(BaseModel):
    current_barriers: List[str] = []
    areas_seeking_improvement: List[str] = []
    stressors_and_anxiety_sources: List[str] = []
    conflict_and_resolution_methods: List[str] = []

class TechnologyAndSystemFeatures(BaseModel):
    experience_with_systems: Optional[str] = ""
    favorite_features: List[str] = []
    least_liked_features: List[str] = []
    preferred_tools: List[str] = []
    desired_technological_innovations: List[str] = []

class MindsetAndAttitude(BaseModel):
    growth: Optional[str] = ""
    fixed: Optional[str] = ""
    resilient: Optional[str] = ""

class EmotionalIntelligence(BaseModel):
    self_awareness: Optional[str] = ""
    empathy: Optional[str] = ""
    adaptability: Optional[str] = ""

class PersonalGrowth(BaseModel):
    mindset_and_attitude: MindsetAndAttitude
    learning_style_and_preferences: List[str] = []
    emotional_intelligence: EmotionalIntelligence
    self_reflection_and_feedback_reception: Optional[str] = ""

class FutureSocialRelationshipGoals(BaseModel):
    desired_relationship_changes: List[str] = []
    community_impact_goals: List[str] = []

class FutureIdentity(BaseModel):
    future_identity_aspirations: List[str] = []
    future_narratives_about_self: List[str] = []
    aspirational_life_lessons_and_purpose: Optional[str] = ""

# Objective Category Container
class ObjectiveCategory(BaseModel):
    category: str
    data: List[LifestylePreferences | GoalsAndAspirations | ValuesAndBeliefs |
               BehaviorPatterns | ChallengesAndPainPoints | TechnologyAndSystemFeatures |
               PersonalGrowth | FutureSocialRelationshipGoals | FutureIdentity]

# Main User Profile Model
class UserProfile(BaseModel):
    foundational: List[FoundationalCategory]
    objective: List[ObjectiveCategory]
