import logging
from inspect import iscoroutinefunction
from typing import Any, Callable, Dict, Union, get_origin

from litellm import ContextWindowExceededError
from pydantic import BaseModel

import dspy
from dspy.primitives.program import Module
from dspy.primitives.tool import Tool

logger = logging.getLogger(__name__)


class AsyncReActWrapper:
    def __init__(self, signature, tools: list[Union[Callable, Tool]], max_iters=5):
        """
        Async wrapper for ReAct that supports async tools.
        `tools` is either a list of functions, callable classes, or `dspy.Tool` instances.
        Tools can be either sync or async functions.
        """
        self.react = dspy.ReAct(signature, tools, max_iters)
        self.tools = self.react.tools
        self.max_iters = max_iters

    async def __call__(self, **input_args):
        trajectory = {}
        for idx in range(self.max_iters):
            try:
                pred = await self._call_with_potential_trajectory_truncation(self.react.react, trajectory, **input_args)
            except Exception as e:
                logger.error("Error calling react: %s", e)
                raise

            trajectory[f"thought_{idx}"] = pred.next_thought
            trajectory[f"tool_name_{idx}"] = pred.next_tool_name
            trajectory[f"tool_args_{idx}"] = pred.next_tool_args

            try:
                tool = self.tools[pred.next_tool_name]

                if pred.next_tool_name == "finish":
                    trajectory[f"observation_{idx}"] = "Completed."
                    break
                
                # Parse tool arguments
                parsed_tool_args = {}
                for k, v in pred.next_tool_args.items():
                    if hasattr(tool, "args") and k in tool.args:
                        arg_type = tool.args[k]
                        if isinstance((origin := get_origin(arg_type) or arg_type), type) and issubclass(
                            origin, BaseModel
                        ):
                            parsed_tool_args[k] = arg_type.model_validate(v)
                            continue
                    parsed_tool_args[k] = v
                
                # Execute the tool based on whether it's async or not
                if iscoroutinefunction(tool.func):
                    trajectory[f"observation_{idx}"] = await tool.func(**parsed_tool_args)
                else:
                    trajectory[f"observation_{idx}"] = tool.func(**parsed_tool_args)
                    
            except Exception as e:
                trajectory[f"observation_{idx}"] = f"Failed to execute: {e}"
                logger.error("Tool execution failed: %s", e)

        extract = await self._call_with_potential_trajectory_truncation(self.react.extract, trajectory, **input_args)
        return dspy.Prediction(trajectory=trajectory, **extract)

    async def _call_with_potential_trajectory_truncation(self, module, trajectory, **input_args):
        while True:
            try:
                return module(
                    **input_args,
                    trajectory=self._format_trajectory(trajectory),
                )
            except ContextWindowExceededError:
                logger.warning("Trajectory exceeded the context window, truncating the oldest tool call information.")
                trajectory = self.truncate_trajectory(trajectory)

    def _format_trajectory(self, trajectory: Dict[str, Any]):
        adapter = dspy.settings.adapter or dspy.ChatAdapter()
        # Use make_signature instead of directly calling Signature
        from dspy.signatures.signature import make_signature
        trajectory_keys = ", ".join(trajectory.keys())
        trajectory_signature = make_signature(f"{trajectory_keys} -> x")
        return adapter.format_fields(trajectory_signature, trajectory, role="user")
    
    def truncate_trajectory(self, trajectory):
        """Truncates the trajectory so that it fits in the context window."""
        keys = list(trajectory.keys())
        if len(keys) < 4:
            # Every tool call has 4 keys: thought, tool_name, tool_args, and observation.
            raise ValueError(
                "The trajectory is too long so your prompt exceeded the context window, but the trajectory cannot be "
                "truncated because it only has one tool call."
            )

        for key in keys[:4]:
            trajectory.pop(key)

        return trajectory