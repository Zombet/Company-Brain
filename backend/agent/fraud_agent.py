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
from langchain.mcp import MCPAdapter
from langchain.agents.factory import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent.memory import persist_session

# ---------------------------------------------------------------------------
# System prompt — concise version to reduce LLM latency
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a Fraud Investigation Agent with access to a FalkorDB graph database.
Always cite the specific graph data returned by each tool. Be concise.

STRICT RULES:
- Use AT MOST 4 tool calls per investigation. Choose wisely.
- Never call the same tool twice with the same arguments.
- After 4 tool calls, write your final answer immediately.

Quick decision guide (pick the minimum tools needed):
- "Who is X / what is X linked to?" → get_entity_profile_tool only (1 tool)
- "Find ring / community" → detect_communities_tool → score_cluster_tool (2 tools)
- "How are X and Y connected?" → find_paths_tool (1 tool)
- "Full investigation" → get_entity_profile_tool → detect_communities_tool → score_cluster_tool → open_case_tool (4 tools max)
- "Is X suspicious?" → get_entity_profile_tool → score_cluster_tool (2 tools)

Graduated response (based on cluster_score or risk_score):
- < 0.4 → monitor only
- 0.4–0.7 → open_case_tool
- > 0.7 → open_case_tool + escalate_to_human_tool

End every response with: VERDICT: [what you found] | CONFIDENCE: [low/medium/high] | ACTION: [what to do]"""

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_script = Path(os.path.join(_backend_dir, 'mcp_server', 'tools.py'))

# ---------------------------------------------------------------------------
# Persistent MCP adapter — reuse across investigations to avoid subprocess
# startup overhead on every call.
# ---------------------------------------------------------------------------
_adapter = None
_adapter_tools = None


async def _get_tools():
    """Return cached MCP tools, reconnecting if the adapter is stale."""
    global _adapter, _adapter_tools
    try:
        if _adapter is not None and _adapter_tools is not None:
            return _adapter_tools
    except Exception:
        pass

    _adapter = MCPAdapter(_tools_script)
    await _adapter.__aenter__()
    _adapter_tools = await _adapter.list_tools()
    return _adapter_tools


async def run_investigation(query: str, session_id: str = None, stream_callback=None) -> dict:
    """Run the fraud investigation agent on a query."""
    session_id = session_id or str(uuid.uuid4())
    started_at = int(datetime.utcnow().timestamp())

    groq_api_key = os.environ.get('GROQ_API_KEY', '')
    groq_model = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-20b')

    # Get tools — reuses the persistent adapter if available
    try:
        tools = await _get_tools()
    except Exception:
        # Fallback: fresh adapter
        global _adapter, _adapter_tools
        _adapter = None
        _adapter_tools = None
        tools = await _get_tools()

    llm = ChatGroq(
        model=groq_model,
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

    messages = result.get("messages", [])

    # Final answer: last AIMessage without tool calls
    final_answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            final_answer = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    steps_serializable = []
    tool_steps = []

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
                "observation": str(observation)[:3000],
            })
            tool_steps.append((tool_name, tool_input, str(observation)[:3000]))

            if stream_callback:
                await stream_callback({
                    "tool": tool_name,
                    "tool_input": tool_input,
                    "observation": str(observation)[:3000],
                })

    try:
        await persist_session(
            session_id=session_id,
            query=query,
            conclusion=final_answer,
            tool_steps=tool_steps,
            started_at=started_at,
            ended_at=ended_at,
        )
    except Exception as e:
        print(f"[agent] persist_session warning: {e}")

    return {
        "session_id": session_id,
        "answer": final_answer,
        "steps": steps_serializable,
    }
