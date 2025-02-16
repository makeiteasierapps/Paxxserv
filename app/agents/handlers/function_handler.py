from typing import Dict, List, Any, Callable, Mapping
import threading
import json
import logging
import asyncio
from fastapi import FastAPI
from pprint import pprint

def create_runner(func, args):
    async def wrapped_func(*args):
        try:
            await func(*args)
        except Exception as e:
            logging.error("Error in background task: %s", str(e))
    
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(wrapped_func(*args))
        finally:
            loop.close()
    return run_in_thread

class FunctionHandler:
    def __init__(self, function_map: Mapping[str, Callable]):
        self.function_map = function_map

    def process_function_calls(self, tool_calls: List[Any], messages: List[Dict], system_content: str) -> List[Dict]:
        conversation_messages = [
            {"role": "system", "content": system_content},
            *messages
        ]
        
        for tool_call in tool_calls:
            try:
                function_name = tool_call.function.name
                if not self.function_map:
                    raise ValueError("No function mapping provided")
                if function_name not in self.function_map:
                    raise ValueError(f"Unknown function: {function_name}")

                arguments = json.loads(tool_call.function.arguments)
                function_to_call = self.function_map[function_name]
                result = function_to_call(**arguments)

                if isinstance(result, dict) and 'background' in result:
                    runner = create_runner(result['function'], result['args'])
                    thread = threading.Thread(target=runner)
                    thread.daemon = True
                    thread.start()
                    print('Background task created and detached')
                    
                    conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result['background']
                    })
                else:
                    conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
            except Exception as e:
                logging.error("Error executing function %s: %s", tool_call.function.name, str(e))
                conversation_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error executing function: {str(e)}"
                })

        return conversation_messages

    @staticmethod
    def is_function_call_response(response: Any) -> bool:
        return (hasattr(response, 'tool_calls') and 
                isinstance(response.tool_calls, list) and 
                len(response.tool_calls) > 0)