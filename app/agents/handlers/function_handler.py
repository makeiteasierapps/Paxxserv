from typing import Dict, List, Any, Callable, Mapping
import threading
import json
import logging
import asyncio
class FunctionHandler:
    def __init__(self, function_map: Mapping[str, Callable]):
        self.function_map = function_map

    def process_function_calls(self, tool_calls: List[Any], messages: List[Dict], system_content: str) -> List[Dict]:
        """
        Non-blocking function to process function calls and return updated conversation messages
        """
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
                
                # Get the configuration without executing the function
                result = function_to_call(**arguments)

                if isinstance(result, dict) and 'background' in result:
                    # Run background task in separate event loop
                    def create_runner(func, args):
                        def run_in_thread():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(func(*args))
                            finally:
                                loop.close()
                        return run_in_thread

                    thread = threading.Thread(
                        target=create_runner(result['function'], result['args'])
                    )
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
        """Check if the response contains function calls"""
        return (hasattr(response, 'tool_calls') and 
                isinstance(response.tool_calls, list) and 
                len(response.tool_calls) > 0)