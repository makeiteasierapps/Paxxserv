import threading
import logging
import json
from app.agents.BossAgent import BossAgent, BossAgentConfig
from app.agents.insight.conversation_analyzer import analyze_conversation
from app.agents.insight.insight_db_manager import InsightDbManager
from app.agents.insight.async_tasks import create_background_task_runner

logger = logging.getLogger(__name__)


class InsightAgent(BossAgent):
    def __init__(self, config: BossAgentConfig, db, uid):
        super().__init__(config)
        self.uid = uid
        self.db = db
        self.insight_db_manager = InsightDbManager(uid, db)

    async def handle_user_input(self, user_input):
        # Start the conversation analysis as a background task
        conversation_analyzer = create_background_task_runner(analyze_conversation)
        thread = threading.Thread(
            target=conversation_analyzer,
            args=(self, user_input),
            name="conversation_analyzer"
        )
        thread.daemon = True
        thread.start()

        # Process the last user message normally
        user_message = user_input[-1]
        await self.insight_db_manager.create_message('user', user_message.get('content'))
        return await super().process_message(
            user_input,
            'insight',
            lambda cid, msg: self.insight_db_manager.create_message('agent', msg)
        )

    async def notify_clients(self, updated_data):
        await self.sio.emit('insight_user_data', json.dumps(updated_data))

        contradiction_queue = updated_data.get('contradiction_review_queue', [])
        if contradiction_queue:
            await self.sio.emit('insight_contradictions', json.dumps({'review_queue': contradiction_queue}))
    