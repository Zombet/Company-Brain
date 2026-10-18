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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter
from langchain.agents.factory import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent.memory import persist_session

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a Fraud Investigation Agent with access to a FalkorDB graph database containing customers, accounts, transactions, devices, IPs, addresses, phones, merchants, alerts, cases, evidence, decisions, and actions.

RULES:
- Use AT MOST 4 tool calls. Never repeat the same tool with the same arguments.
- Every claim must reference a specific tool result (IDs, scores, amounts).
- Do not guess or speculate.

TOOL SELECTION:
IMPORTANT - ID FORMAT: All tool calls require IDs in the format C_name (Customer), A_name (Account), T_name (Transaction).
When the user says "kunal", use "C_kunal". When they say "aryan", use "C_aryan". When they say "kingpin", use "C_kingpin".
When they say "john", use "C_john". When they say "omar", use "C_omar".
Common mappings: kunal->C_kunal, aryan->C_aryan, ifrah->C_ifrah, priya->C_priya, hassan->C_hassan, nina->C_nina,
john->C_john, sarah->C_sarah, mike->C_mike, lisa->C_lisa, omar->C_omar, diana->C_diana, felix->C_felix,
raj->C_raj, meera->C_meera, aditya->C_aditya, kingpin->C_kingpin, victor->C_kingpin.
For accounts: john1->A_john1, kunal1->A_kunal1, kingpin1->A_kingpin1.
If a name is NOT in the common mappings above, call resolve_entity_tool(name) first to get the correct ID.
If unsure of the exact ID, use get_entity_profile_tool with your best guess of the C_ or A_ prefixed ID.
- Unknown name resolution: resolve_entity_tool (pass the bare name, returns the correct prefixed ID)
- Circular flow / money cycle detection: detect_circular_flow_tool (use Account ID, e.g. A_omar1)
- Entity context: get_entity_profile_tool
- Ring/community: detect_communities_tool then score_cluster_tool
- Money trail: trace_money_flow_tool
- Connection proof / bridge node / path between two entities: find_paths_tool
- Why two specific entities share a common attribute (same device/address): shared_attributes_tool
- Kingpin ranking within a community: rank_central_nodes_tool

REQUIRED RESPONSE FORMAT - always include all 5 sections:

## Investigation Summary
One paragraph: what was investigated, what the graph reveals overall.

## Graph Evidence
| Step | Tool | Key Findings |
|------|------|-------------|
(one row per tool call, quote specific IDs/scores/amounts from results)

## Fraud Indicators
Bullet list of every signal found:
- Shared device: [device ID] used by [customer IDs]
- Shared address: [address ID] linked to [customer IDs]
- Transfer chain: [account A] -> [account B] -> [account C] ([amounts])
- Flagged transactions: [IDs] with risk scores [values]
- High risk scores: [entity IDs] with scores [values]
- Community size: [N] members in [community ID]
- Cycle detected: money returned to origin via [path]

## Confidence Assessment
cluster_score: [value] | avg_risk: [value] | Confidence: [low/medium/high]
Two sentences explaining what graph signals drive this confidence.

## Recommended Action
- cluster_score < 0.4: Monitor [specific entities]
- cluster_score 0.4-0.7: Open case linking alerts [IDs]
- cluster_score > 0.7: Freeze account [specific account ID], escalate case [ID]"""

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_script = Path(os.path.join(_backend_dir, 'mcp_server', 'tools.py'))

# ---------------------------------------------------------------------------
# Persistent MCP adapter - reuse across calls to avoid subprocess startup
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
    groq_model = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')
    gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
    openrouter_api_key = os.environ.get('OPENROUTER_API_KEY', '')
    openrouter_model = os.environ.get('OPENROUTER_MODEL', 'meta-llama/llama-3.3-70b-instruct')
    llm_provider = os.environ.get('LLM_PROVIDER', 'groq')

    # Get tools - reuse persistent adapter
    try:
        tools = await _get_tools()
    except Exception:
        global _adapter, _adapter_tools
        _adapter = None
        _adapter_tools = None
        tools = await _get_tools()

    if llm_provider == 'openrouter' and openrouter_api_key:
        llm = ChatOpenAI(
            model=openrouter_model,
            temperature=0,
            api_key=openrouter_api_key,
            base_url='https://openrouter.ai/api/v1',
            default_headers={
                'HTTP-Referer': 'http://localhost:5173',
                'X-Title': 'Fraud Investigation Agent',
            },
        )
    elif llm_provider == 'gemini' and gemini_api_key:
        llm = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            temperature=0,
            google_api_key=gemini_api_key,
        )
    else:
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
        for tc in (getattr(ai_msg, "tool_calls", None) or []):
            tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            tool_input = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
            obs_msg = tool_results.get(tc_id)
            raw_obs = obs_msg.content if obs_msg else ""

            # Unwrap OpenRouter content-block format: [{"type":"text","text":"..."}]
            # so the frontend receives a plain JSON string, not a list of blocks
            if isinstance(raw_obs, list):
                text_blocks = [b.get("text", "") for b in raw_obs if isinstance(b, dict) and b.get("type") == "text"]
                observation = text_blocks[0] if text_blocks else json.dumps(raw_obs)
            else:
                observation = str(raw_obs) if raw_obs else ""

            step = {
                "tool": tool_name,
                "tool_input": tool_input,
                "observation": str(observation)[:4000],
            }
            steps_serializable.append(step)
            tool_steps.append((tool_name, tool_input, str(observation)[:4000]))

            if stream_callback:
                await stream_callback(step)

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
