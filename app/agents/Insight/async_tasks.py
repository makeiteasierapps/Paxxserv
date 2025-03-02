import asyncio
import logging

logger = logging.getLogger(__name__)

def create_background_task_runner(task_func):
    """
    Returns a function that can run an async task (task_func) in a new event loop.
    """
    async def wrapped_task(*args, **kwargs):
        try:
            await task_func(*args, **kwargs)
        except Exception as e:
            logger.error("Error in background task %s: %s", task_func.__name__, str(e))

    def run_in_thread(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(wrapped_task(*args, **kwargs))
        finally:
            loop.close()

    return run_in_thread