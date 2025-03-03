import threading
import logging
import json
from app.agents.insight.conversation_analyzer import analyze_conversation
from app.agents.insight.insight_db_manager import InsightDbManager
from app.agents.insight.async_tasks import create_background_task_runner

logger = logging.getLogger(__name__)


class InsightAgent():
    def __init__(self,db, uid, sio):
        self.uid = uid
        self.db = db
        self.sio = sio
        self.insight_db_manager = InsightDbManager(uid, db)

    async def handle_user_input(self, user_input):
        # Start the conversation analysis as a background task
        conversation_analyzer = create_background_task_runner(analyze_conversation)
        thread = threading.Thread(
            target=conversation_analyzer,
            args=(user_input, self.uid, self.sio),
            name="conversation_analyzer"
        )
        thread.daemon = True
        thread.start()

    async def notify_clients(self, updated_data):
        await self.sio.emit('insight_user_data', json.dumps(updated_data))
        contradiction_queue = updated_data.get('contradiction_review_queue', [])
        if contradiction_queue:
            await self.sio.emit('insight_contradictions', json.dumps({'review_queue': contradiction_queue}))
    