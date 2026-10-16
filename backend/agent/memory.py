import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.client import get_graph
from graph.queries import persist_session_to_graph


async def persist_session(session_id, query, conclusion, tools_used, started_at, ended_at):
    """Parse LangChain intermediate steps and persist session memory to FalkorDB."""
    graph = get_graph()

    investigated_ids = []
    flagged_ids = []
    flag_reasons = []
    tools_used_names = []

    try:
        for action, observation in tools_used:
            tool_name = getattr(action, 'tool', '')
            tool_input = getattr(action, 'tool_input', {})
            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except Exception:
                    tool_input = {}
            tools_used_names.append(tool_name)
            if 'account_id' in tool_input:
                investigated_ids.append(tool_input['account_id'])
            if tool_name == 'flag_account':
                flagged_ids.append(tool_input.get('account_id', ''))
                flag_reasons.append(tool_input.get('reason', ''))
    except Exception as e:
        print(f"Warning: could not parse intermediate steps: {e}")

    session_data = {
        'session_id': session_id,
        'started_at': started_at,
        'ended_at': ended_at,
        'query': query,
        'conclusion': conclusion,
        'tools_used': json.dumps(list(set(tools_used_names))),
        'account_ids': json.dumps(list(set(investigated_ids))),
        'investigated_ids': list(set(investigated_ids)),
        'flagged_ids': [f for f in flagged_ids if f],
        'flag_reason': ', '.join(flag_reasons),
    }

    try:
        persist_session_to_graph(graph, session_data)
    except Exception as e:
        print(f"Warning: failed to persist session to graph: {e}")
