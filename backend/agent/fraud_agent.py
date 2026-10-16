import os
import sys
import uuid
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from agent.memory import persist_session

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

SYSTEM_PROMPT = """You are a Fraud Investigation Agent. You have access to a graph database (FalkorDB) that stores transactions, accounts, customers, devices, and their relationships.

Your tools query the graph directly. Every answer you give must cite the graph data you retrieved — the tool call result is your evidence.

Investigation workflow:
1. Call get_investigation_history first — check if this account was already investigated.
2. Use get_connected_accounts or get_risk_neighbors to map the neighborhood.
3. Use trace_fraud_ring to identify ring membership (multi-hop).
4. Use get_transaction_path to prove specific connections.
5. If evidence warrants it, call flag_account with a precise reason.
6. Summarize: list every account touched, every relationship type traversed, and the chain of reasoning. This summary is stored as session memory.

You have access to the following tools:
{tools}

Tool names: {tool_names}

Use this EXACT format:
Thought: what you are about to do
Action: tool_name
Action Input: {{"param": "value"}}
Observation: <tool result>
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: <structured investigation report listing every account touched, relationship types traversed, risk scores found, and your conclusion>

Question: {input}
{agent_scratchpad}"""

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_script = os.path.join(_backend_dir, 'mcp_server', 'tools.py')


async def run_investigation(query: str, session_id: str = None, stream_callback=None) -> dict:
    """Run the fraud investigation agent on a query."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    session_id = session_id or str(uuid.uuid4())
    started_at = int(datetime.utcnow().timestamp())

    groq_api_key = os.environ.get('GROQ_API_KEY', '')

    async with MultiServerMCPClient({
        "fraud-tools": {
            "command": sys.executable,
            "args": [_tools_script],
            "transport": "stdio",
            "env": {**os.environ, "PYTHONPATH": _backend_dir}
        }
    }) as mcp_client:
        tools = mcp_client.get_tools()

        llm = ChatGroq(
            model="llama3-70b-8192",
            temperature=0,
            api_key=groq_api_key,
        )

        prompt = PromptTemplate.from_template(SYSTEM_PROMPT)
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True,
        )

        result = await agent_executor.ainvoke({"input": query})

    ended_at = int(datetime.utcnow().timestamp())
    intermediate_steps = result.get('intermediate_steps', [])

    await persist_session(
        session_id=session_id,
        query=query,
        conclusion=result.get('output', ''),
        tools_used=intermediate_steps,
        started_at=started_at,
        ended_at=ended_at,
    )

    steps_serializable = []
    for action, observation in intermediate_steps:
        steps_serializable.append({
            'tool': getattr(action, 'tool', str(action)),
            'tool_input': getattr(action, 'tool_input', {}),
            'observation': str(observation)[:2000],
        })

    return {
        'session_id': session_id,
        'answer': result.get('output', ''),
        'steps': steps_serializable,
    }
