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

SYSTEM_PROMPT = """You are a Fraud Investigation Agent with full access to a FalkorDB graph database \
containing customers, accounts, transactions, devices, IP addresses, addresses, phones, merchants, \
alerts, cases, evidence, decisions, and actions.

Every answer MUST cite the specific graph data you retrieved. Never speculate without graph evidence.

Investigation workflow (10 steps):
1. Start with get_entity_profile_tool to understand the seed entity and its immediate connections.
2. Use expand_neighborhood_tool (depth=2) to map the wider community around the entity.
3. Call trace_money_flow_tool on any Account to detect mule chains, rapid pass-through, or structuring.
4. Use shared_attributes_tool to explain WHY two entities appear linked (shared device, IP, address).
5. Call find_paths_tool between suspicious entities to prove specific connections and hop distances.
6. Run detect_communities_tool on the most connected entity to enumerate the full fraud ring.
7. Use rank_central_nodes_tool on community members to identify the kingpin (highest-degree node).
8. Call score_cluster_tool to get a quantitative risk score for the whole ring.
9. For confirmed fraud: call freeze_account_tool (dry_run=True first), open_case_tool, flag_cluster_tool.
   For ambiguous findings: call escalate_to_human_tool with a clear reason.
10. Summarize: name every entity examined, every relationship type traversed, confidence level,
    and a narrative explaining how the ring is connected (e.g., "Alice and Bob share no direct link
    but both used Device D_dev1 within 2 days, which also connects to Account A_kunal_main that
    received funds from 4 flagged accounts").

Graduated response tiers:
- Low confidence  (<0.4 cluster_score): monitor only, no action.
- Medium confidence (0.4–0.7): step-up verification — open a case, request KYC refresh.
- High confidence  (>0.7): freeze hub account, flag cluster, escalate to human.

Explainability rules:
- For every finding, state which tool produced it and what the key graph data was.
- When clearing a false positive (e.g., legitimate family sharing a device), state your reasons.
- Always link your confidence level to specific graph signals (degree, velocity_score, shared attributes).

Action rules:
- Action tools (freeze_account_tool, open_case_tool, flag_cluster_tool) require reason and evidence_ids.
- Use dry_run=True unless the user explicitly requests a live action.
- Every action is written back to the graph as an Action node — this gives the system memory."""

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_script = Path(os.path.join(_backend_dir, 'mcp_server', 'tools.py'))


async def run_investigation(query: str, session_id: str = None, stream_callback=None) -> dict:
    """Run the fraud investigation agent on a query using LangChain + MCPAdapter."""
    session_id = session_id or str(uuid.uuid4())
    started_at = int(datetime.utcnow().timestamp())

    groq_api_key = os.environ.get('GROQ_API_KEY', '')

    # MCPAdapter with a Path target launches tools.py over stdio
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
                "observation": str(observation)[:2000],
            })
            tool_steps.append((tool_name, tool_input, str(observation)[:2000]))

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
