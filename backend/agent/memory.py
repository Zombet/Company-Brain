import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.client import get_graph
from graph.queries import persist_session_to_graph

# Tool names that indicate an entity was investigated (contributes to investigated_ids)
_INVESTIGATION_TOOLS = {
    "get_entity_profile_tool",
    "expand_neighborhood_tool",
    "find_paths_tool",
    "shared_attributes_tool",
    "detect_communities_tool",
    "rank_central_nodes_tool",
    "trace_money_flow_tool",
    "score_cluster_tool",
}

# Tool names that indicate a freeze/flag action (contributes to flagged_ids)
_FREEZE_TOOLS = {
    "freeze_account_tool",
    "flag_cluster_tool",
}


async def persist_session(session_id, query, conclusion, tool_steps, started_at, ended_at):
    """Parse tool steps and persist session memory to FalkorDB.

    tool_steps: list of (tool_name, tool_input_dict, observation_str) tuples
    """
    graph = get_graph()

    investigated_ids = []
    flagged_ids = []
    flag_reasons = []
    tools_used_names = []

    try:
        for tool_name, tool_input, observation in tool_steps:
            if not isinstance(tool_input, dict):
                try:
                    tool_input = json.loads(tool_input) if isinstance(tool_input, str) else {}
                except Exception:
                    tool_input = {}

            tools_used_names.append(tool_name)

            # Collect entity IDs from investigation tools
            if tool_name in _INVESTIGATION_TOOLS:
                # entity_id / account_id / seed_id / a / b
                for key in ("entity_id", "account_id", "seed_id", "a", "b", "community_id"):
                    val = tool_input.get(key)
                    if val and isinstance(val, str):
                        investigated_ids.append(val)
                # node_ids is a list
                node_ids = tool_input.get("node_ids")
                if isinstance(node_ids, list):
                    investigated_ids.extend([n for n in node_ids if isinstance(n, str)])

            # Collect flagged account IDs from action tools
            if tool_name in _FREEZE_TOOLS:
                acct_id = tool_input.get("account_id")
                if acct_id:
                    flagged_ids.append(acct_id)
                    flag_reasons.append(tool_input.get("reason", ""))

            # open_case_tool / escalate_to_human_tool — track case_id as investigated
            if tool_name in ("open_case_tool", "escalate_to_human_tool"):
                case_id = tool_input.get("case_id")
                if case_id:
                    investigated_ids.append(case_id)

    except Exception as e:
        print(f"Warning: could not parse tool steps: {e}")

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
