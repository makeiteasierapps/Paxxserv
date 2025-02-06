from typing import List, Optional
from pydantic import BaseModel, Field
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
    city: Optional[str] = None
    country: Optional[str] = None

class BasicDemographics(BaseModel):
    name: Optional[str] = None
    age_range: Optional[str] = None
    gender_identity: Optional[str] = None
    location: Optional[Location] = Field(default_factory=Location)
    language_preferences: Optional[str] = None
    relationship_status: Optional[str] = None
    family_structure: Optional[str] = None

# Personal Background Models
class EducationBackground(BaseModel):
    level: Optional[str] = None
    fields_of_study: List[str] = Field(default_factory=list)

class ProfessionalBackground(BaseModel):
    industry: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)

class CulturalInfluences(BaseModel):
    heritage: Optional[str] = None
    traditions: List[str] = Field(default_factory=list)
    languages_spoken: List[str] = Field(default_factory=list)

class PersonalBackground(BaseModel):
    education_background: EducationBackground
    professional_background: ProfessionalBackground
    cultural_influences: CulturalInfluences
    significant_life_events: List[str] = Field(default_factory=list)
    childhood_and_family_experience: Optional[str] = None
    major_transitions: List[str] = Field(default_factory=list)
    personal_challenges: Optional[str] = None

# Interests and Hobbies Model
class InterestsAndHobbies(BaseModel):
    regular_hobbies: List[str] = Field(default_factory=list)
    current_interests: List[str] = Field(default_factory=list)
    artistic_inclinations: Optional[str] = None
    learning_interests: List[str] = Field(default_factory=list)
    passions: Optional[str] = None
    hobbies_shared_with_others: List[str] = Field(default_factory=list)
    comfort_activities: List[str] = Field(default_factory=list)

# Social Relationships Model
class SocialRelationships(BaseModel):
    relationship_history: Optional[str] = None
    current_dynamics: Optional[str] = None
    interaction_patterns: Optional[str] = None

# Emotional Well-being Models
class EmotionalLandscape(BaseModel):
    mood_patterns: List[str] = Field(default_factory=list)
    emotional_triggers: List[str] = Field(default_factory=list)

class SelfPerception(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    self_worth: Optional[str] = None

class CopingMechanisms(BaseModel):
    handling_stress: Optional[str] = None
    emotional_regulation: Optional[str] = None

class EmotionalWellbeing(BaseModel):
    emotional_landscape: EmotionalLandscape
    self_perception: SelfPerception
    coping_mechanisms: CopingMechanisms

# Identity Models
class LifePhilosophy(BaseModel):
    guiding_principles: List[str] = Field(default_factory=list)
    life_meaning: Optional[str] = None

class PersonalStorytelling(BaseModel):
    narratives_about_self: List[str] = Field(default_factory=list)
    life_lessons: List[str] = Field(default_factory=list)

class IdentityAndPersonalNarrative(BaseModel):
    life_philosophy: LifePhilosophy
    pivotal_past_experiences: List[str] = Field(default_factory=list)
    personal_storytelling: PersonalStorytelling

# Objective Models
class DailyRoutine(BaseModel):
    work: Optional[str] = None
    leisure: Optional[str] = None
    exercise: Optional[str] = None

class WorkLifeBalance(BaseModel):
    hours: Optional[str] = None
    flexibility: Optional[str] = None
    stress_management: Optional[str] = None

class LifestylePreferences(BaseModel):
    daily_routine: DailyRoutine
    work_life_balance: WorkLifeBalance
    travel_types_and_destinations: List[str] = Field(default_factory=list)
    health_and_wellbeing_practices: List[str] = Field(default_factory=list)

class GoalsAndAspirations(BaseModel):
    short_term_goals: List[str] = Field(default_factory=list)
    long_term_objectives: List[str] = Field(default_factory=list)
    aspirational_projects: List[str] = Field(default_factory=list)
    legacy_and_impact: Optional[str] = None

class ValuesAndBeliefs(BaseModel):
    core_values: List[str] = Field(default_factory=list)
    philosophical_alignments: List[str] = Field(default_factory=list)
    social_concerns: List[str] = Field(default_factory=list)
    community_involvement: List[str] = Field(default_factory=list)

class BehaviorPatterns(BaseModel):
    preferred_communication_style: Optional[str] = None
    interaction_frequency: Optional[str] = None
    typical_engagement_levels: Optional[str] = None
    networking_approach: Optional[str] = None

class ChallengesAndPainPoints(BaseModel):
    current_barriers: List[str] = Field(default_factory=list)
    areas_seeking_improvement: List[str] = Field(default_factory=list)
    stressors_and_anxiety_sources: List[str] = Field(default_factory=list)
    conflict_and_resolution_methods: List[str] = Field(default_factory=list)

class TechnologyAndSystemFeatures(BaseModel):
    experience_with_systems: Optional[str] = None
    favorite_features: List[str] = Field(default_factory=list)
    least_liked_features: List[str] = Field(default_factory=list)
    preferred_tools: List[str] = Field(default_factory=list)
    desired_technological_innovations: List[str] = Field(default_factory=list)

class MindsetAndAttitude(BaseModel):
    growth: Optional[str] = None
    fixed: Optional[str] = None
    resilient: Optional[str] = None

class EmotionalIntelligence(BaseModel):
    self_awareness: Optional[str] = None
    empathy: Optional[str] = None
    adaptability: Optional[str] = None

class PersonalGrowth(BaseModel):
    mindset_and_attitude: MindsetAndAttitude
    learning_style_and_preferences: List[str] = Field(default_factory=list)
    emotional_intelligence: EmotionalIntelligence
    self_reflection_and_feedback_reception: Optional[str] = None

class FutureSocialRelationshipGoals(BaseModel):
    desired_relationship_changes: List[str] = Field(default_factory=list)
    community_impact_goals: List[str] = Field(default_factory=list)

class FutureIdentity(BaseModel):
    future_identity_aspirations: List[str] = Field(default_factory=list)
    future_narratives_about_self: List[str] = Field(default_factory=list)
    aspirational_life_lessons_and_purpose: Optional[str] = None

# Main User Profile Model
class UserProfile(BaseModel):
    foundational: List[BasicDemographics | PersonalBackground | InterestsAndHobbies | 
               SocialRelationships | EmotionalWellbeing | IdentityAndPersonalNarrative]
    
    objective: List[LifestylePreferences | GoalsAndAspirations | ValuesAndBeliefs |
               BehaviorPatterns | ChallengesAndPainPoints | TechnologyAndSystemFeatures |
               PersonalGrowth | FutureSocialRelationshipGoals | FutureIdentity]
