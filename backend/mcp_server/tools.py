import sys
import os
# When run as subprocess (python -m mcp_server.tools), ensure backend/ is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from graph.client import get_graph
from graph.queries import (
    query_connected_accounts,
    query_trace_fraud_ring,
    query_transaction_path,
    query_investigation_history,
    query_flag_account,
    query_risk_neighbors,
)

mcp = FastMCP("fraud-investigation")


@mcp.tool()
def get_connected_accounts(transaction_id: str) -> list:
    """Find all accounts linked to a flagged transaction via shared devices, transfers, or same customer."""
    graph = get_graph()
    return query_connected_accounts(graph, transaction_id)


@mcp.tool()
def trace_fraud_ring(account_id: str) -> list:
    """Trace fraud ring members up to 3 relationship hops from an account."""
    graph = get_graph()
    return query_trace_fraud_ring(graph, account_id)


@mcp.tool()
def get_transaction_path(from_account_id: str, to_account_id: str) -> dict:
    """Find the shortest path between two accounts in the graph."""
    graph = get_graph()
    return query_transaction_path(graph, from_account_id, to_account_id)


@mcp.tool()
def get_investigation_history(account_id: str) -> list:
    """Retrieve past agent investigation sessions stored in the graph for this account."""
    graph = get_graph()
    return query_investigation_history(graph, account_id)


@mcp.tool()
def flag_account(account_id: str, reason: str) -> dict:
    """Mark an account as flagged with a given reason. This writes to FalkorDB."""
    graph = get_graph()
    return query_flag_account(graph, account_id, reason)


@mcp.tool()
def get_risk_neighbors(account_id: str) -> list:
    """Get all direct neighbors of an account with their labels, relationship types, and risk scores."""
    graph = get_graph()
    return query_risk_neighbors(graph, account_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
