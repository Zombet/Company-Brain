import os
import sys
import uuid
import json
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

from langchain_groq import ChatGroq
from langchain.agents.factory import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent.memory import persist_session

SYSTEM_PROMPT = """You are a Fraud Investigation Agent with access to a FalkorDB graph database. \
Every answer must cite the graph data you retrieved.

Investigation workflow:
1. Call get_investigation_history first — check if this account was already investigated.
2. Use get_connected_accounts or get_risk_neighbors to map the neighborhood.
3. Use trace_fraud_ring to identify ring membership (multi-hop).
4. Use get_transaction_path to prove specific connections.
5. If evidence warrants it, call flag_account with a precise reason.
6. Summarize: list every account touched, every relationship type traversed, and your chain of reasoning."""

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_script = Path(os.path.join(_backend_dir, 'mcp_server', 'tools.py'))


async def run_investigation(query: str, session_id: str = None, stream_callback=None) -> dict:
    """Run the fraud investigation agent on a query using LangChain 1.x + MCPAdapter."""
    session_id = session_id or str(uuid.uuid4())
    started_at = int(datetime.utcnow().timestamp())

    groq_api_key = os.environ.get('GROQ_API_KEY', '')

    # MCPAdapter with a Path target launches the tools.py script over stdio
    async with MCPAdapter(_tools_script) as adapter:
        tools = await adapter.list_tools()

        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0,
            api_key=groq_api_key,
        )

        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=query)]}
        )

    ended_at = int(datetime.utcnow().timestamp())

    # Extract messages from the result
    messages = result.get("messages", [])

    # The final answer is the last AIMessage that isn't a tool call
    final_answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            final_answer = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    # Build intermediate steps for serialization and memory persistence
    steps_serializable = []
    tool_steps = []  # for persist_session: list of (tool_name, tool_input, observation) tuples

    ai_tool_msgs = {msg.id: msg for msg in messages if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None)}
    tool_results = {msg.tool_call_id: msg for msg in messages if isinstance(msg, ToolMessage)}

    for ai_msg in messages:
        if not isinstance(ai_msg, AIMessage):
            continue
        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        for tc in tool_calls:
            tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            tool_input = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
            obs_msg = tool_results.get(tc_id)
            observation = obs_msg.content if obs_msg else ""

            steps_serializable.append({
                "tool": tool_name,
                "tool_input": tool_input,
                "observation": str(observation)[:2000],
            })
            tool_steps.append((tool_name, tool_input, str(observation)[:2000]))

            # Stream each step if callback provided
            if stream_callback:
                await stream_callback({
                    "tool": tool_name,
                    "tool_input": tool_input,
                    "observation": str(observation)[:2000],
                })

    await persist_session(
        session_id=session_id,
        query=query,
        conclusion=final_answer,
        tool_steps=tool_steps,
        started_at=started_at,
        ended_at=ended_at,
    )

    return {
        "session_id": session_id,
        "answer": final_answer,
        "steps": steps_serializable,
    }
