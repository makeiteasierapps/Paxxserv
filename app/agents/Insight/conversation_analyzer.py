import os
import logging
import dspy
from app.services.MongoDbClient import MongoDbClient
from app.agents.insight.dspy_model import InsightSignature
from app.agents.insight.data_processor import process_user_data

logger = logging.getLogger(__name__)

async def analyze_conversation(agent, conversation):
    """
    Analyzes the conversation using DSPy's chain-of-thought agent, retrieves profile data
    from the database, and hands off any entries/contradictions to the data processor.
    """
    try:
        # Load necessary API key and initialize the LM
        os.getenv('OPENAI_API_KEY')
        lm = dspy.LM('openai/gpt-4o-mini', max_tokens=10000, cache=False)
        
        with dspy.settings.context(lm=lm):
            # Retrieve the current profile using MongoDB
            client = MongoDbClient('paxxium')
            user_collection = client.db['insight']
            profile_data = await agent.insight_db_manager.get_current_profile(user_collection)

            # Process the conversation using DSPy
            agent_chain = dspy.ChainOfThought(InsightSignature)
            result = agent_chain(
                conversation=conversation,
                profile=profile_data
            )

            # If the result contains user entries, process them
            if result.user_entries:
                await process_user_data(agent, client.db, result)
                
    except Exception as e:
        logger.error("Error in analyze_conversation: %s", str(e))
