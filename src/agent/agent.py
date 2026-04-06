import os
import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """
        TODO: Implement the system prompt that instructs the agent to follow ReAct.
        Should include:
        1.  Available tools and their descriptions.
        2.  Format instructions: Thought, Action, Observation.
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
        You are an intelligent assistant. You have access to the following tools:
        {tool_descriptions}

        Use the following format:
        Thought: your line of reasoning.
        Action: tool_name(arguments)
        Observation: result of the tool call.
        ... (repeat Thought/Action/Observation if needed)
        Final Answer: your final response.
        """

    def run(self, user_input: str) -> str:
        """
        ReAct loop: Thought -> Action -> Observation -> ... -> Final Answer.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        current_prompt = user_input
        steps = 0

        while steps < self.max_steps:
            result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            response_text = result["content"]
            logger.log_event("LLM_RESPONSE", {"step": steps, "response": response_text})
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )

            # Check for Final Answer
            final_match = re.search(r"Final Answer:\s*(.*)", response_text, re.DOTALL)
            if final_match:
                answer = final_match.group(1).strip()
                logger.log_event("AGENT_END", {"steps": steps, "answer": answer})
                return answer

            # Parse Action
            action_match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", response_text)
            if action_match:
                tool_name = action_match.group(1).strip()
                tool_args = action_match.group(2).strip().strip('"\'')
                observation = self._execute_tool(tool_name, tool_args)
                current_prompt = f"{current_prompt}\n{response_text}\nObservation: {observation}"
            else:
                # No action and no final answer — treat response as final
                logger.log_event("AGENT_END", {"steps": steps})
                return response_text.strip()

            steps += 1

        logger.log_event("AGENT_END", {"steps": steps, "reason": "max_steps_reached"})
        return "Max steps reached without a final answer."

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """
        Helper method to execute tools by name.
        """
        logger.log_event("TOOL_EXECUTING", {"tool": tool_name, "args": args})
        print(f"  [Tool] {tool_name}({args})")

        for tool in self.tools:
            if tool['name'] == tool_name:
                func = tool.get('func')
                if callable(func):
                    try:
                        result = str(func(args))
                        logger.log_event("TOOL_RESULT", {"tool": tool_name, "result": result})
                        print(f"  [Observation] {result}")
                        return result
                    except Exception as e:
                        error = f"Error calling {tool_name}: {e}"
                        logger.log_event("TOOL_ERROR", {"tool": tool_name, "error": str(e)})
                        print(f"  [Error] {error}")
                        return error
                return f"Tool {tool_name} has no callable 'func'."
        return f"Tool {tool_name} not found."
