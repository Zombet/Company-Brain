import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rows_to_dicts(result):
    """Convert a FalkorDB result set into a list of dicts.

    FalkorDB returns headers as a list of [type_code, column_name] pairs,
    e.g. [[1, 'account_id'], [1, 'status'], ...].  We extract the column
    name (index 1) so it can be used as a dict key.
    """
    if not result or not result.result_set:
        return []
    headers = []
    for h in result.header:
        if isinstance(h, (list, tuple)):
            headers.append(h[1])
        else:
            headers.append(h)
    return [dict(zip(headers, row)) for row in result.result_set]


# ---------------------------------------------------------------------------
# 1. Connected accounts for a flagged transaction
# ---------------------------------------------------------------------------

def query_connected_accounts(graph, transaction_id: str) -> list:
    """Return all accounts connected to the given transaction via shared
    devices, transfers, or a common customer owner."""
    cypher = """
MATCH (t:Transaction {id: $transaction_id})<-[:MADE]-(a:Account)
OPTIONAL MATCH (a)-[:USED]->(d:Device)<-[:USED]-(a2:Account)
  WHERE a2.id <> a.id
OPTIONAL MATCH (a)-[:TRANSFERRED_TO*1..2]-(a3:Account)
  WHERE a3.id <> a.id
OPTIONAL MATCH (a)<-[:OWNS]-(c:Customer)-[:OWNS]->(a4:Account)
  WHERE a4.id <> a.id
WITH a, collect(DISTINCT a2) + collect(DISTINCT a3) + collect(DISTINCT a4) AS connected
UNWIND connected AS conn
RETURN DISTINCT
  conn.id          AS account_id,
  conn.status      AS status,
  conn.risk_score  AS risk_score,
  conn.bank_name   AS bank_name
ORDER BY conn.risk_score DESC
"""
    try:
        result = graph.query(cypher, {"transaction_id": transaction_id})
        return _rows_to_dicts(result)
    except Exception as exc:
        print(f"[queries] query_connected_accounts warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 2. Trace fraud ring from an account
# ---------------------------------------------------------------------------

def query_trace_fraud_ring(graph, account_id: str) -> list:
    """Walk up to 3 hops from account_id and return neighbours that are
    flagged or confirmed fraud."""
    cypher = """
MATCH path = (start:Account {id: $account_id})-[*1..3]-(neighbor:Account)
WHERE neighbor.status IN ['flagged', 'confirmed_fraud']
  AND neighbor.id <> $account_id
WITH neighbor,
     length(path)          AS hops,
     [r IN relationships(path) | type(r)] AS rel_types,
     [n IN nodes(path) | n.id]            AS path_ids
RETURN DISTINCT
  neighbor.id         AS account_id,
  neighbor.status     AS status,
  neighbor.risk_score AS risk_score,
  hops,
  rel_types,
  path_ids
ORDER BY neighbor.risk_score DESC, hops ASC
LIMIT 50
"""
    try:
        result = graph.query(cypher, {"account_id": account_id})
        return _rows_to_dicts(result)
    except Exception as exc:
        print(f"[queries] query_trace_fraud_ring warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 3. Shortest transaction path between two accounts
# ---------------------------------------------------------------------------

def query_transaction_path(graph, from_account_id: str, to_account_id: str) -> dict:
    """Return the shortest path between two accounts, with node and
    relationship metadata.  Returns {} when no path exists."""
    cypher = """
MATCH (a1:Account {id: $from_account_id}),
      (a2:Account {id: $to_account_id})
WITH shortestPath((a1)-[*1..10]-(a2)) AS path
RETURN
  [n IN nodes(path) | {id: n.id, labels: labels(n), risk_score: n.risk_score}] AS path_nodes,
  [r IN relationships(path) | {type: type(r), properties: properties(r)}]      AS path_rels,
  length(path) AS hop_count
"""
    try:
        result = graph.query(
            cypher,
            {
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
            },
        )
        rows = _rows_to_dicts(result)
        return rows[0] if rows else {}
    except Exception as exc:
        print(f"[queries] query_transaction_path warning: {exc}")
        return {}


# ---------------------------------------------------------------------------
# 4. Past investigation sessions for an account
# ---------------------------------------------------------------------------

def query_investigation_history(graph, account_id: str) -> list:
    """Return the 20 most-recent agent sessions that investigated this account."""
    cypher = """
MATCH (s:AgentSession)-[:INVESTIGATED]->(a:Account {id: $account_id})
RETURN
  s.session_id  AS session_id,
  s.started_at  AS started_at,
  s.query       AS query,
  s.conclusion  AS conclusion,
  s.tools_used  AS tools_used
ORDER BY s.started_at DESC
LIMIT 20
"""
    try:
        result = graph.query(cypher, {"account_id": account_id})
        return _rows_to_dicts(result)
    except Exception as exc:
        print(f"[queries] query_investigation_history warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 5. Flag an account
# ---------------------------------------------------------------------------

def query_flag_account(graph, account_id: str, reason: str) -> dict:
    """Set an account's status to 'flagged' and record the reason.
    Returns the updated account info or {} on failure."""
    cypher = """
MATCH (a:Account {id: $account_id})
SET
  a.status      = 'flagged',
  a.flag_reason = $reason,
  a.flagged_at  = timestamp(),
  a.flagged_by  = 'agent',
  a.risk_score  = CASE WHEN a.risk_score < 0.8 THEN 0.8 ELSE a.risk_score END
RETURN
  a.id          AS account_id,
  a.status      AS new_status,
  a.flag_reason AS reason,
  a.flagged_at  AS flagged_at
"""
    try:
        result = graph.query(cypher, {"account_id": account_id, "reason": reason})
        rows = _rows_to_dicts(result)
        return rows[0] if rows else {}
    except Exception as exc:
        print(f"[queries] query_flag_account warning: {exc}")
        return {}


# ---------------------------------------------------------------------------
# 6. Risk neighbours of an account
# ---------------------------------------------------------------------------

def query_risk_neighbors(graph, account_id: str) -> list:
    """Return all direct neighbours of an account with their risk scores."""
    cypher = """
MATCH (a:Account {id: $account_id})-[r]-(neighbor)
RETURN
  neighbor.id         AS neighbor_id,
  labels(neighbor)    AS neighbor_labels,
  type(r)             AS relationship_type,
  neighbor.risk_score AS risk_score,
  neighbor.status     AS status,
  properties(r)       AS rel_properties
ORDER BY neighbor.risk_score DESC
"""
    try:
        result = graph.query(cypher, {"account_id": account_id})
        return _rows_to_dicts(result)
    except Exception as exc:
        print(f"[queries] query_risk_neighbors warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 7. Persist an agent session to the graph
# ---------------------------------------------------------------------------

def persist_session_to_graph(graph, session_data: dict):
    """Write a completed agent session into the graph as an AgentSession node
    and optionally link it to investigated / flagged Account nodes.

    session_data keys:
        session_id      str
        started_at      int  (epoch ms)
        ended_at        int  (epoch ms)
        query           str
        conclusion      str
        tools_used      list[str]
        account_ids     list[str]
        investigated_ids list[str]
        flagged_ids     list[str]
        flag_reason     str
    """
    # --- Step 1: Always create the session node --------------------------
    create_cypher = """
CREATE (s:AgentSession {
  session_id:  $session_id,
  started_at:  $started_at,
  ended_at:    $ended_at,
  query:       $query,
  conclusion:  $conclusion,
  tools_used:  $tools_used,
  account_ids: $account_ids
})
RETURN s.session_id AS persisted_session
"""
    params = {
        "session_id":   session_data.get("session_id", ""),
        "started_at":   session_data.get("started_at", 0),
        "ended_at":     session_data.get("ended_at", 0),
        "query":        session_data.get("query", ""),
        "conclusion":   session_data.get("conclusion", ""),
        "tools_used":   session_data.get("tools_used", []),
        "account_ids":  session_data.get("account_ids", []),
    }
    try:
        graph.query(create_cypher, params)
    except Exception as exc:
        print(f"[queries] persist_session_to_graph – CREATE node warning: {exc}")
        return  # Cannot proceed without the session node

    session_id = params["session_id"]

    # --- Step 2: Link to investigated accounts (only when list is non-empty)
    investigated_ids = session_data.get("investigated_ids") or []
    if investigated_ids:
        inv_cypher = """
MATCH (s:AgentSession {session_id: $session_id})
UNWIND $investigated_ids AS acc_id
  MATCH (a:Account {id: acc_id})
  CREATE (s)-[:INVESTIGATED {role: 'primary'}]->(a)
"""
        try:
            graph.query(
                inv_cypher,
                {
                    "session_id":      session_id,
                    "investigated_ids": investigated_ids,
                },
            )
        except Exception as exc:
            print(f"[queries] persist_session_to_graph – INVESTIGATED link warning: {exc}")

    # --- Step 3: Link to flagged accounts (only when list is non-empty) ---
    flagged_ids = session_data.get("flagged_ids") or []
    if flagged_ids:
        flag_cypher = """
MATCH (s:AgentSession {session_id: $session_id})
UNWIND $flagged_ids AS fid
  MATCH (af:Account {id: fid})
  CREATE (s)-[:FLAGGED_DURING {reason: $flag_reason}]->(af)
"""
        try:
            graph.query(
                flag_cypher,
                {
                    "session_id":  session_id,
                    "flagged_ids": flagged_ids,
                    "flag_reason": session_data.get("flag_reason", ""),
                },
            )
        except Exception as exc:
            print(f"[queries] persist_session_to_graph – FLAGGED_DURING link warning: {exc}")
