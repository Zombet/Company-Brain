import sys
import os
import json

# When run as subprocess (python -m mcp_server.tools), ensure backend/ is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from graph.client import get_graph
from graph.queries import (
    get_entity_profile,
    expand_neighborhood,
    find_paths,
    shared_attributes,
    detect_communities,
    rank_central_nodes,
    trace_money_flow,
    score_cluster,
    freeze_account,
    open_case,
    flag_cluster,
    escalate_to_human,
)

mcp = FastMCP("fraud-investigation")


def _str(data) -> str:
    """Serialize tool output to a JSON string.

    The OpenAI-compatible chat APIs require tool-message content to be a
    string, so every tool returns JSON text rather than a raw Python object.
    ``default=str`` guards against non-serializable FalkorDB types.
    """
    return json.dumps(data, default=str)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_entity_profile_tool(entity_id: str) -> str:
    """Get full node properties and all 1-hop neighbours for any entity.

    Use this tool as the first step of any investigation to understand what
    an entity looks like and who it is directly connected to.
    entity_id format: C_<name> | A_<name> | T_<id> | D_<id> | ADDR_<id> |
    IP_<id> | PH_<id> | M_<id> | AL_<id> | CASE_<id> | EV_<id> | DEC_<id> | ACT_<id>
    """
    graph = get_graph()
    return _str(get_entity_profile(graph, entity_id))


@mcp.tool()
def expand_neighborhood_tool(entity_id: str, depth: int = 2, rel_types: list = None) -> str:
    """Expand the network around an entity to a given hop depth.

    Use this tool when you need to map the wider community around an entity
    beyond 1-hop. Returns a Cytoscape-compatible {nodes, edges} structure.
    depth: 1-6. rel_types: optional list of relationship type strings to filter,
    e.g. ['USED_DEVICE', 'LOGGED_IN_FROM'].
    """
    graph = get_graph()
    return _str(expand_neighborhood(graph, entity_id, depth, rel_types))


@mcp.tool()
def find_paths_tool(a: str, b: str, max_hops: int = 6) -> str:
    """Find the shortest path between two entities in the graph.

    Use this tool when you need to know whether two entities are indirectly
    connected and what the connection chain looks like. Returns [] if no path
    exists within max_hops.
    """
    graph = get_graph()
    return _str(find_paths(graph, a, b, max_hops))


@mcp.tool()
def shared_attributes_tool(a: str, b: str) -> str:
    """Find bridge nodes that connect two entities within 2 hops each.

    Use this tool when two entities appear linked but have no direct edge.
    Reveals shared devices, IP addresses, phone numbers, or addresses.
    """
    graph = get_graph()
    return _str(shared_attributes(graph, a, b))


@mcp.tool()
def detect_communities_tool(seed_id: str) -> str:
    """Detect the community (potential fraud ring) around a seed entity.

    Use this tool when you suspect a fraud ring and need to enumerate its
    members up to 4 hops out. Writes community_id back to each member node
    so subsequent queries can filter by cluster.
    """
    graph = get_graph()
    return _str(detect_communities(graph, seed_id))


@mcp.tool()
def rank_central_nodes_tool(node_ids: list) -> str:
    """Rank nodes by degree centrality to identify the most connected entity.

    Use this tool after detect_communities to find the kingpin — the node
    with the most connections in the cluster. Pass the member ID list from
    detect_communities. Returns nodes sorted descending by degree.
    """
    graph = get_graph()
    return _str(rank_central_nodes(graph, node_ids))


@mcp.tool()
def trace_money_flow_tool(account_id: str, window_seconds: int = 86400) -> str:
    """Trace inbound and outbound transactions for an account within a time window.

    Use this tool to detect mule chains (A->B->C->D), rapid pass-through
    (money in and out within minutes), or structuring (amounts just under threshold).
    window_seconds defaults to 86400 (24 h). Returns inbound, outbound lists,
    net_flow, and velocity_score (0-1).
    """
    graph = get_graph()
    return _str(trace_money_flow(graph, account_id, window_seconds))


@mcp.tool()
def score_cluster_tool(community_id: str) -> str:
    """Compute an aggregate risk score for a community cluster.

    Use this tool after detect_communities to quantify how dangerous a ring is.
    Combines average member risk, shared device count, and flagged-transaction
    density into a single cluster_score (0-1).
    """
    graph = get_graph()
    return _str(score_cluster(graph, community_id))


# ---------------------------------------------------------------------------
# Action tools (require reason + evidence_ids)
# ---------------------------------------------------------------------------

@mcp.tool()
def freeze_account_tool(account_id: str, reason: str, evidence_ids: list, dry_run: bool = True) -> str:
    """Freeze an account and write an auditable Action node to the graph.

    Use this tool when investigation confirms an account should be frozen.
    Required: reason (str), evidence_ids (list[str]).
    dry_run=True by default — set dry_run=False to apply the freeze for real.
    The Action node is always written; the account status is only changed when
    dry_run=False.
    """
    graph = get_graph()
    return _str(freeze_account(graph, account_id, reason, evidence_ids, dry_run))


@mcp.tool()
def open_case_tool(alert_ids: list, reason: str, evidence_ids: list) -> str:
    """Open a new investigation Case and link it to alerts and evidence.

    Use this tool when there is sufficient signal to start a formal case.
    Required: reason (str), evidence_ids (list[str]).
    Returns case_id and status.
    """
    graph = get_graph()
    return _str(open_case(graph, alert_ids, reason, evidence_ids))


@mcp.tool()
def flag_cluster_tool(community_id: str, reason: str, evidence_ids: list, dry_run: bool = True) -> str:
    """Raise risk scores for all accounts in a community cluster.

    Use this tool when the whole ring is confirmed suspicious and you want to
    apply a risk-score increment to every member account.
    Required: reason (str), evidence_ids (list[str]).
    dry_run=True by default — set dry_run=False to apply score increases.
    """
    graph = get_graph()
    return _str(flag_cluster(graph, community_id, reason, evidence_ids, dry_run))


@mcp.tool()
def escalate_to_human_tool(case_id: str, reason: str, evidence_ids: list) -> str:
    """Escalate a case to a human analyst and record the escalation in the graph.

    Use this tool when the evidence is ambiguous, the cluster is large, or the
    confidence is below the threshold for autonomous action.
    Required: reason (str), evidence_ids (list[str]).
    Returns action_id and case_id.
    """
    graph = get_graph()
    return _str(escalate_to_human(graph, case_id, reason, evidence_ids))


if __name__ == "__main__":
    mcp.run(transport="stdio")
