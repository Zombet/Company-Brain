// ==========================================================================
// Fraud Investigation Agent — FalkorDB Reference Cypher Queries
// These are the six queries executed by the MCP tool server at runtime.
// ==========================================================================


// --------------------------------------------------------------------------
// 1. get_connected_accounts
//    Purpose: Return all accounts connected to a flagged transaction via
//             shared devices, transfers (up to 2 hops), or a common customer
//             owner.  Used as the first triage step in an investigation.
// --------------------------------------------------------------------------

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
ORDER BY conn.risk_score DESC;


// --------------------------------------------------------------------------
// 2. trace_fraud_ring
//    Purpose: Walk variable-length paths (1–3 hops) from a seed account and
//             surface any neighbor whose status is 'flagged' or
//             'confirmed_fraud'.  Returns hop count and the full path for
//             explainability.
// --------------------------------------------------------------------------

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
LIMIT 50;


// --------------------------------------------------------------------------
// 3. get_transaction_path
//    Purpose: Find the shortest path between two accounts (up to 10 hops).
//             Returns every node and relationship along the route so the
//             agent can cite the exact connection chain.
// --------------------------------------------------------------------------

MATCH (a1:Account {id: $from_account_id}),
      (a2:Account {id: $to_account_id})
WITH a1, a2
MATCH path = shortestPath((a1)-[*..10]-(a2))
RETURN
  [n IN nodes(path) | {id: n.id, labels: labels(n), risk_score: n.risk_score}] AS path_nodes,
  [r IN relationships(path) | {type: type(r), properties: properties(r)}]      AS path_rels,
  length(path) AS hop_count;


// --------------------------------------------------------------------------
// 4. get_investigation_history
//    Purpose: Retrieve the 20 most-recent AgentSession nodes that are linked
//             to this account via INVESTIGATED edges.  This gives the agent
//             cross-session memory — it knows what was already found before.
// --------------------------------------------------------------------------

MATCH (s:AgentSession)-[:INVESTIGATED]->(a:Account {id: $account_id})
RETURN
  s.session_id  AS session_id,
  s.started_at  AS started_at,
  s.query       AS query,
  s.conclusion  AS conclusion,
  s.tools_used  AS tools_used
ORDER BY s.started_at DESC
LIMIT 20;


// --------------------------------------------------------------------------
// 5. flag_account
//    Purpose: Write a flagging decision back into the graph — sets status,
//             reason, timestamp, and ensures risk_score >= 0.8.
//             This is the only mutating query; the agent's action changes
//             graph state that all future sessions will read.
// --------------------------------------------------------------------------

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
  a.flagged_at  AS flagged_at;


// --------------------------------------------------------------------------
// 6. get_risk_neighbors
//    Purpose: Single-hop neighborhood scan — return every node directly
//             connected to an account with its labels, relationship type,
//             risk score, and relationship properties.
// --------------------------------------------------------------------------

MATCH (a:Account {id: $account_id})-[r]-(neighbor)
RETURN
  neighbor.id         AS neighbor_id,
  labels(neighbor)    AS neighbor_labels,
  type(r)             AS relationship_type,
  neighbor.risk_score AS risk_score,
  neighbor.status     AS status,
  properties(r)       AS rel_properties
ORDER BY neighbor.risk_score DESC;
