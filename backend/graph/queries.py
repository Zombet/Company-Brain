import sys
import os
import uuid
import time

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


def _label_from_id(entity_id: str) -> str:
    """Detect the node label from the entity ID prefix convention."""
    prefix_map = {
        "C_": "Customer",
        "A_": "Account",
        "T_": "Transaction",
        "D_": "Device",
        "ADDR_": "Address",
        "IP_": "IP",
        "PH_": "Phone",
        "M_": "Merchant",
        "AL_": "Alert",
        "CASE_": "Case",
        "EV_": "Evidence",
        "DEC_": "Decision",
        "ACT_": "Action",
    }
    for prefix, label in prefix_map.items():
        if entity_id.startswith(prefix):
            return label
    return "Customer"


# ---------------------------------------------------------------------------
# 1. Get entity profile (1-hop context)
# ---------------------------------------------------------------------------

def get_entity_profile(graph, entity_id: str) -> dict:
    """Return node properties and all 1-hop neighbours for any entity.

    Use this tool as the starting point for every investigation.
    Detects label from ID prefix (C_->Customer, A_->Account, T_->Transaction, etc.).
    """
    label = _label_from_id(entity_id)
    try:
        # Fetch node properties
        props_result = graph.query(
            f"MATCH (n:{label} {{id: $id}}) RETURN properties(n) AS props",
            {"id": entity_id},
        )
        props_rows = props_result.result_set if props_result and props_result.result_set else []
        node_props = props_rows[0][0] if props_rows else {}
        if hasattr(node_props, "properties"):
            node_props = node_props.properties
        if not isinstance(node_props, dict):
            node_props = {}

        # Fetch neighbours
        nb_result = graph.query(
            f"""MATCH (n:{label} {{id: $id}})-[r]-(nb)
RETURN type(r) AS rel, labels(nb) AS nb_labels, nb.id AS nb_id,
       nb.name AS nb_name, properties(r) AS rel_props""",
            {"id": entity_id},
        )
        nb_rows = _rows_to_dicts(nb_result)
        neighbors = []
        for row in nb_rows:
            nb_label_list = row.get("nb_labels", [])
            neighbors.append({
                "rel": row.get("rel", ""),
                "label": nb_label_list[0] if nb_label_list else "",
                "id": row.get("nb_id", ""),
                "name": row.get("nb_name", ""),
                "rel_props": row.get("rel_props", {}),
            })

        return {"node": node_props, "neighbors": neighbors}
    except Exception as exc:
        print(f"[queries] get_entity_profile warning: {exc}")
        return {"node": {}, "neighbors": []}


# ---------------------------------------------------------------------------
# 2. Expand neighbourhood (variable-depth traversal)
# ---------------------------------------------------------------------------

def expand_neighborhood(graph, entity_id: str, depth: int = 2, rel_types: list = None) -> dict:
    """Return all nodes and edges reachable within *depth* hops.

    Use this tool when you need to map the wider network around an entity.
    Returns Cytoscape-compatible {nodes, edges} format.

    rel_types: optional list of relationship type strings to filter traversal.
    """
    depth = max(1, min(int(depth), 6))  # guard bounds

    rel_filter = ""
    if rel_types:
        rel_filter = ":" + "|".join(rel_types)

    cypher = f"""MATCH path = (n {{id: $id}})-[{rel_filter}*1..{depth}]-(nb)
WHERE nb.id <> $id
WITH nb, relationships(path) AS rels, nodes(path) AS pnodes
RETURN nb.id AS nb_id, labels(nb) AS nb_labels, properties(nb) AS nb_props,
       [rel IN rels | [startNode(rel).id, type(rel), endNode(rel).id, properties(rel)]] AS edge_list"""

    try:
        result = graph.query(cypher, {"id": entity_id})
        rows = result.result_set if result and result.result_set else []

        nodes_seen = {}
        edges_seen = {}

        # Always include the seed node
        seed_props_r = graph.query(
            "MATCH (n {id: $id}) RETURN labels(n) AS lbs, properties(n) AS props",
            {"id": entity_id},
        )
        if seed_props_r and seed_props_r.result_set:
            seed_row = seed_props_r.result_set[0]
            seed_lbs = seed_row[0] if seed_row[0] else []
            seed_ps = seed_row[1] if seed_row[1] else {}
            if hasattr(seed_ps, "properties"):
                seed_ps = seed_ps.properties
            nodes_seen[entity_id] = {
                "data": {
                    "id": entity_id,
                    "label": seed_lbs[0] if seed_lbs else "",
                    "properties": seed_ps if isinstance(seed_ps, dict) else {},
                }
            }

        for row in rows:
            nb_id = row[0]
            nb_labels = row[1] or []
            nb_props = row[2] or {}
            if hasattr(nb_props, "properties"):
                nb_props = nb_props.properties
            edge_list = row[3] or []

            if nb_id and nb_id not in nodes_seen:
                nodes_seen[nb_id] = {
                    "data": {
                        "id": nb_id,
                        "label": nb_labels[0] if nb_labels else "",
                        "properties": nb_props if isinstance(nb_props, dict) else {},
                    }
                }

            for edge in edge_list:
                if not edge or len(edge) < 3:
                    continue
                src, rel_type, tgt = edge[0], edge[1], edge[2]
                edge_props = edge[3] if len(edge) > 3 else {}
                if hasattr(edge_props, "properties"):
                    edge_props = edge_props.properties
                edge_key = f"{src}-{rel_type}-{tgt}"
                if edge_key not in edges_seen:
                    edges_seen[edge_key] = {
                        "data": {
                            "id": edge_key,
                            "source": src,
                            "target": tgt,
                            "type": rel_type,
                            "properties": edge_props if isinstance(edge_props, dict) else {},
                        }
                    }

        return {
            "nodes": list(nodes_seen.values()),
            "edges": list(edges_seen.values()),
        }
    except Exception as exc:
        print(f"[queries] expand_neighborhood warning: {exc}")
        return {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# 3. Find paths between two entities
# ---------------------------------------------------------------------------

def find_paths(graph, a: str, b: str, max_hops: int = 6) -> list:
    """Return the shortest path between two entities.

    Use this tool when you need to prove whether and how two entities are
    connected. Returns a list of path dicts with node IDs and relationship types.
    Returns [] when no path exists.
    """
    max_hops = max(1, min(int(max_hops), 10))
    cypher = f"""MATCH (x {{id: $a}}),(y {{id: $b}})
WITH shortestPath((x)-[*1..{max_hops}]-(y)) AS p
RETURN [n IN nodes(p) | n.id] AS ids,
       [r IN relationships(p) | type(r)] AS rels,
       length(p) AS hops"""
    try:
        result = graph.query(cypher, {"a": a, "b": b})
        rows = _rows_to_dicts(result)
        paths = []
        for row in rows:
            if row.get("ids") is None:
                continue
            paths.append({
                "ids": row.get("ids", []),
                "rels": row.get("rels", []),
                "hops": row.get("hops", 0),
            })
        return paths
    except Exception as exc:
        print(f"[queries] find_paths warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 4. Shared attributes (bridge nodes)
# ---------------------------------------------------------------------------

def shared_attributes(graph, a: str, b: str) -> list:
    """Find bridge nodes that connect two entities within 2 hops each.

    Use this tool when you need to understand WHY two entities look linked.
    Returns shared devices, IPs, addresses, or other bridge nodes.
    """
    cypher = """MATCH (x {id: $a})-[*1..2]-(bridge)-[*1..2]-(y {id: $b})
WHERE bridge.id <> $a AND bridge.id <> $b
RETURN DISTINCT bridge.id AS bridge_id, labels(bridge) AS bridge_labels,
       bridge.name AS bridge_name, bridge.risk_score AS bridge_risk"""
    try:
        result = graph.query(cypher, {"a": a, "b": b})
        return _rows_to_dicts(result)
    except Exception as exc:
        print(f"[queries] shared_attributes warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 5. Detect communities (BFS ring detection)
# ---------------------------------------------------------------------------

def detect_communities(graph, seed_id: str) -> dict:
    """Identify a community of entities connected to the seed within 8 hops.

    Use this tool when you suspect a fraud ring and need to enumerate its members.
    Writes community_id back to Customer and Account nodes only (not bridge nodes).
    """
    community_id = "COM_" + seed_id

    # Step 1: traverse and collect members (read-only)
    cypher = """MATCH (seed {id: $id})-[*1..8]-(member)
WHERE member.id <> $id
RETURN DISTINCT member.id AS mid, labels(member) AS mlabels,
       member.risk_score AS mrisk, member.name AS mname"""
    try:
        result = graph.query(cypher, {"id": seed_id})
        rows = _rows_to_dicts(result)

        members = []
        customer_ids = []
        account_ids = []
        for row in rows:
            mid = row.get("mid")
            if not mid:
                continue
            mlabels = row.get("mlabels") or []
            members.append({
                "id": mid,
                "labels": mlabels,
                "risk_score": row.get("mrisk"),
                "name": row.get("mname"),
            })
            # Collect IDs for batch write-back (only meaningful node types)
            if "Customer" in mlabels:
                customer_ids.append(mid)
            elif "Account" in mlabels:
                account_ids.append(mid)

        # Step 2: batch write-back using UNWIND — one query per node type
        # This avoids the per-node loop that crashes FalkorDB
        if customer_ids:
            try:
                graph.query(
                    "UNWIND $ids AS mid MATCH (m:Customer {id: mid}) "
                    "SET m.community_id = $cid, m.community_computed_at = timestamp()",
                    {"ids": customer_ids, "cid": community_id},
                )
            except Exception as wb_exc:
                print(f"[queries] detect_communities Customer write-back warning: {wb_exc}")

        if account_ids:
            try:
                graph.query(
                    "UNWIND $ids AS mid MATCH (m:Account {id: mid}) "
                    "SET m.community_id = $cid, m.community_computed_at = timestamp()",
                    {"ids": account_ids, "cid": community_id},
                )
            except Exception as wb_exc:
                print(f"[queries] detect_communities Account write-back warning: {wb_exc}")

        return {
            "community_id": community_id,
            "members": members,
            "size": len(members),
        }
    except Exception as exc:
        print(f"[queries] detect_communities warning: {exc}")
        return {"community_id": community_id, "members": [], "size": 0}


# ---------------------------------------------------------------------------
# 6. Rank central nodes by degree
# ---------------------------------------------------------------------------

def rank_central_nodes(graph, node_ids: list) -> list:
    """Rank a set of nodes by their degree (connection count) as a centrality proxy.

    Use this tool to identify the kingpin — the highest-centrality node in a cluster.
    Returns nodes sorted descending by degree.
    """
    if not node_ids:
        return []
    # Batch all IDs in a single UNWIND query instead of N individual queries
    try:
        result = graph.query(
            "UNWIND $ids AS nid MATCH (n {id: nid})-[r]-() "
            "RETURN n.id AS nid, labels(n) AS nlabels, count(r) AS degree, n.risk_score AS risk_score",
            {"ids": list(node_ids)},
        )
        rows = _rows_to_dicts(result)
        ranked = []
        for row in rows:
            nlabels = row.get("nlabels") or []
            ranked.append({
                "id": row.get("nid", ""),
                "label": nlabels[0] if nlabels else "",
                "degree": row.get("degree", 0),
                "risk_score": row.get("risk_score"),
            })
        ranked.sort(key=lambda x: x.get("degree", 0), reverse=True)
        return ranked
    except Exception as exc:
        print(f"[queries] rank_central_nodes warning: {exc}")
        return []


# ---------------------------------------------------------------------------
# 7. Trace money flow
# ---------------------------------------------------------------------------

def trace_money_flow(graph, account_id: str, window_seconds: int = 0) -> dict:
    """Trace inbound and outbound transactions within a time window.

    Use this tool to detect mule chains, rapid pass-through, or structuring patterns.
    window_seconds=0 means no time filter (show all transactions).
    """
    try:
        if window_seconds > 0:
            start_ts = int(time.time()) - int(window_seconds)
            ts_filter = "WHERE t.ts >= $start_ts"
            params_out = {"id": account_id, "start_ts": start_ts}
            params_in = {"id": account_id, "start_ts": start_ts}
        else:
            ts_filter = ""
            params_out = {"id": account_id, "start_ts": 0}
            params_in = {"id": account_id, "start_ts": 0}

        # Outbound
        out_result = graph.query(
            f"""MATCH (a:Account {{id: $id}})-[:SENT]->(t:Transaction)-[:TO]->(b:Account)
{ts_filter}
RETURN t.id AS txn_id, t.amount AS amount, t.ts AS ts, b.id AS dest, t.status AS status""",
            params_out,
        )
        outbound = _rows_to_dicts(out_result)

        # Inbound
        in_result = graph.query(
            f"""MATCH (b:Account)-[:SENT]->(t:Transaction)-[:TO]->(a:Account {{id: $id}})
{ts_filter}
RETURN t.id AS txn_id, t.amount AS amount, t.ts AS ts, b.id AS src, t.status AS status""",
            params_in,
        )
        inbound = _rows_to_dicts(in_result)

        inbound_total = sum(float(r.get("amount") or 0) for r in inbound)
        outbound_total = sum(float(r.get("amount") or 0) for r in outbound)
        net_flow = inbound_total - outbound_total
        total_txns = len(inbound) + len(outbound)
        velocity_score = min(1.0, total_txns / 10.0)

        return {
            "account_id": account_id,
            "inbound": inbound,
            "outbound": outbound,
            "net_flow": net_flow,
            "velocity_score": velocity_score,
        }
    except Exception as exc:
        print(f"[queries] trace_money_flow warning: {exc}")
        return {"account_id": account_id, "inbound": [], "outbound": [], "net_flow": 0, "velocity_score": 0}


# ---------------------------------------------------------------------------
# 8. Score a cluster
# ---------------------------------------------------------------------------

def score_cluster(graph, community_id: str) -> dict:
    """Compute an aggregate risk score for a community/cluster.

    Use this tool after detect_communities to quantify how risky the ring is.
    Combines average risk, shared devices, shared addresses, and flagged transactions.
    """
    try:
        members_r = graph.query(
            "MATCH (n {community_id: $cid}) RETURN n.id AS nid, labels(n) AS nlabels, n.risk_score AS risk_score",
            {"cid": community_id},
        )
        member_rows = _rows_to_dicts(members_r)
        member_count = len(member_rows)

        risks = [float(r.get("risk_score") or 0) for r in member_rows]
        avg_risk = sum(risks) / max(1, len(risks))
        max_risk = max(risks) if risks else 0.0

        # Shared devices
        dev_r = graph.query(
            "MATCH (c:Customer {community_id: $cid})-[:USED_DEVICE]->(d:Device) RETURN count(DISTINCT d) AS shared_devs",
            {"cid": community_id},
        )
        shared_devs = dev_r.result_set[0][0] if dev_r and dev_r.result_set else 0

        # Shared addresses
        addr_r = graph.query(
            "MATCH (c:Customer {community_id: $cid})-[:LIVES_AT]->(a:Address) RETURN count(DISTINCT a) AS shared_addrs",
            {"cid": community_id},
        )
        shared_addrs = addr_r.result_set[0][0] if addr_r and addr_r.result_set else 0

        # Flagged transactions
        flag_r = graph.query(
            "MATCH (c:Customer {community_id: $cid})-[:OWNS]->(:Account)-[:SENT]->(t:Transaction) WHERE t.status='flagged' RETURN count(t) AS flagged_txns",
            {"cid": community_id},
        )
        flagged_txn_count = flag_r.result_set[0][0] if flag_r and flag_r.result_set else 0

        cluster_score = min(
            1.0,
            avg_risk * 0.4
            + (shared_devs / max(1, member_count)) * 0.3
            + (flagged_txn_count / max(1, member_count)) * 0.3,
        )

        return {
            "community_id": community_id,
            "member_count": member_count,
            "avg_risk": avg_risk,
            "max_risk": max_risk,
            "shared_devices": shared_devs,
            "shared_addresses": shared_addrs,
            "flagged_transactions": flagged_txn_count,
            "cluster_score": cluster_score,
        }
    except Exception as exc:
        print(f"[queries] score_cluster warning: {exc}")
        return {"community_id": community_id, "cluster_score": 0.0}


# ---------------------------------------------------------------------------
# 9. Freeze account (action tool)
# ---------------------------------------------------------------------------

def freeze_account(graph, account_id: str, reason: str, evidence_ids: list, dry_run: bool = True) -> dict:
    """Freeze an account and create an auditable Action node.

    Use this tool when investigation confirms an account should be frozen.
    Required: reason (str), evidence_ids (list[str]).
    dry_run=True by default — set False to apply the freeze.
    """
    action_id = "ACT_" + str(uuid.uuid4())[:8]
    try:
        if not dry_run:
            graph.query(
                "MATCH (a:Account {id: $id}) SET a.status = 'frozen'",
                {"id": account_id},
            )

        graph.query(
            """CREATE (act:Action {
                id: $action_id,
                type: 'freeze_account',
                dry_run: $dry_run,
                reason: $reason,
                ts: timestamp()
            })""",
            {"action_id": action_id, "dry_run": dry_run, "reason": reason},
        )

        graph.query(
            """MATCH (act:Action {id: $action_id}), (a:Account {id: $account_id})
CREATE (act)-[:TARGETS]->(a)""",
            {"action_id": action_id, "account_id": account_id},
        )

        for ev_id in (evidence_ids or []):
            try:
                graph.query(
                    """MATCH (act:Action {id: $action_id}), (ev:Evidence {id: $ev_id})
CREATE (act)-[:USES_EVIDENCE]->(ev)""",
                    {"action_id": action_id, "ev_id": ev_id},
                )
            except Exception as ev_exc:
                print(f"[queries] freeze_account evidence link warning: {ev_exc}")

        return {
            "action_id": action_id,
            "type": "freeze_account",
            "dry_run": dry_run,
            "account_id": account_id,
            "status": "frozen" if not dry_run else "dry_run",
        }
    except Exception as exc:
        print(f"[queries] freeze_account warning: {exc}")
        return {"action_id": action_id, "type": "freeze_account", "dry_run": dry_run, "error": str(exc)}


# ---------------------------------------------------------------------------
# 10. Open a case
# ---------------------------------------------------------------------------

def open_case(graph, alert_ids: list, reason: str, evidence_ids: list) -> dict:
    """Open a new investigation Case and link it to alerts and evidence.

    Use this tool when you have enough signals to start a formal case.
    Required: reason (str), evidence_ids (list[str]).
    """
    case_id = "CASE_" + str(uuid.uuid4())[:8]
    try:
        graph.query(
            """CREATE (c:Case {
                id: $case_id,
                status: 'open',
                opened_at: timestamp(),
                summary: $reason
            })""",
            {"case_id": case_id, "reason": reason},
        )

        for alert_id in (alert_ids or []):
            try:
                graph.query(
                    """MATCH (c:Case {id: $case_id}), (al:Alert {id: $alert_id})
CREATE (c)-[:CONTAINS]->(al)""",
                    {"case_id": case_id, "alert_id": alert_id},
                )
            except Exception as al_exc:
                print(f"[queries] open_case alert link warning: {al_exc}")

        if evidence_ids:
            ev_id = "EV_" + str(uuid.uuid4())[:8]
            ev_entities = json_safe_list(evidence_ids)
            graph.query(
                """CREATE (ev:Evidence {
                    id: $ev_id,
                    kind: 'case_summary',
                    summary: $reason,
                    entities: $entities,
                    payload: '{}'
                })""",
                {"ev_id": ev_id, "reason": reason, "entities": ev_entities},
            )
            graph.query(
                """MATCH (c:Case {id: $case_id}), (ev:Evidence {id: $ev_id})
CREATE (c)-[:HAS_EVIDENCE]->(ev)""",
                {"case_id": case_id, "ev_id": ev_id},
            )

        return {"case_id": case_id, "status": "open", "alert_count": len(alert_ids or [])}
    except Exception as exc:
        print(f"[queries] open_case warning: {exc}")
        return {"case_id": case_id, "status": "error", "error": str(exc)}


def json_safe_list(lst):
    """Ensure list contains only strings for graph storage."""
    return [str(x) for x in lst] if lst else []


# ---------------------------------------------------------------------------
# 14. Detect circular money flow
# ---------------------------------------------------------------------------

def detect_circular_flow(graph, account_id: str) -> dict:
    """Detect circular money flows (cycles) starting from an account.

    Use this when investigating circular flow or money laundering cycles.
    Looks for 3-hop cycles: A -> B -> C -> A.
    """
    def _safe_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    cypher = """
MATCH (a:Account {id: $id})-[:SENT]->(t1:Transaction)-[:TO]->(b:Account)
MATCH (b)-[:SENT]->(t2:Transaction)-[:TO]->(c:Account)
MATCH (c)-[:SENT]->(t3:Transaction)-[:TO]->(a)
WHERE b <> a AND c <> b AND c <> a
  AND t1 <> t2 AND t2 <> t3 AND t1 <> t3
RETURN a.id AS start, t1.amount AS amt1, t1.ts AS ts1,
       b.id AS mid1, t2.amount AS amt2, t2.ts AS ts2,
       c.id AS mid2, t3.amount AS amt3, t3.ts AS ts3
LIMIT 5
"""
    try:
        result = graph.query(cypher, {"id": account_id})
        rows = _rows_to_dicts(result)
        if rows:
            r = rows[0]
            if not (r.get("start") and r.get("mid1") and r.get("mid2")):
                return {"cycle_found": False}
            return {
                "cycle_found": True,
                "path": [r["start"], r["mid1"], r["mid2"], r["start"]],
                "amounts": [_safe_float(r["amt1"]), _safe_float(r["amt2"]), _safe_float(r["amt3"])],
                "timestamps": [r["ts1"], r["ts2"], r["ts3"]],
                "extracted": _safe_float(r["amt1"]) - _safe_float(r["amt3"]),
            }
        return {"cycle_found": False}
    except Exception as e:
        print(f"[queries] detect_circular_flow warning: {e}")
        return {"cycle_found": False}
# ---------------------------------------------------------------------------
# 11. Flag a cluster
# ---------------------------------------------------------------------------

def flag_cluster(graph, community_id: str, reason: str, evidence_ids: list, dry_run: bool = True) -> dict:
    """Raise risk scores for all accounts in a community cluster.

    Use this tool when the whole ring is confirmed suspicious.
    Required: reason (str), evidence_ids (list[str]).
    dry_run=True by default — set False to apply score increases.
    """
    action_id = "ACT_" + str(uuid.uuid4())[:8]
    try:
        acct_r = graph.query(
            "MATCH (c:Customer {community_id: $cid})-[:OWNS]->(a:Account) RETURN DISTINCT a.id AS acct_id, a.risk_score AS risk_score",
            {"cid": community_id},
        )
        acct_rows = _rows_to_dicts(acct_r)
        members_flagged = len(acct_rows)

        if not dry_run:
            for row in acct_rows:
                acct_id = row.get("acct_id")
                if acct_id:
                    try:
                        graph.query(
                            "MATCH (a:Account {id: $id}) SET a.risk_score = CASE WHEN a.risk_score + 0.2 > 1.0 THEN 1.0 ELSE a.risk_score + 0.2 END",
                            {"id": acct_id},
                        )
                    except Exception as upd_exc:
                        print(f"[queries] flag_cluster update warning for {acct_id}: {upd_exc}")

        graph.query(
            """CREATE (act:Action {
                id: $action_id,
                type: 'flag_cluster',
                community_id: $community_id,
                dry_run: $dry_run,
                reason: $reason,
                ts: timestamp()
            })""",
            {"action_id": action_id, "community_id": community_id, "dry_run": dry_run, "reason": reason},
        )

        return {
            "action_id": action_id,
            "community_id": community_id,
            "members_flagged": members_flagged,
            "dry_run": dry_run,
        }
    except Exception as exc:
        print(f"[queries] flag_cluster warning: {exc}")
        return {"action_id": action_id, "community_id": community_id, "members_flagged": 0, "dry_run": dry_run, "error": str(exc)}


# ---------------------------------------------------------------------------
# 12. Escalate to human
# ---------------------------------------------------------------------------

def escalate_to_human(graph, case_id: str, reason: str, evidence_ids: list) -> dict:
    """Escalate a case to a human analyst and create an auditable Action node.

    Use this tool when the agent cannot make a high-confidence decision alone.
    Required: reason (str), evidence_ids (list[str]).
    """
    action_id = "ACT_" + str(uuid.uuid4())[:8]
    try:
        graph.query(
            """CREATE (act:Action {
                id: $action_id,
                type: 'escalate_to_human',
                reason: $reason,
                ts: timestamp()
            })""",
            {"action_id": action_id, "reason": reason},
        )

        graph.query(
            """MATCH (act:Action {id: $action_id}), (c:Case {id: $case_id})
CREATE (act)-[:TARGETS]->(c)""",
            {"action_id": action_id, "case_id": case_id},
        )

        for ev_id in (evidence_ids or []):
            try:
                graph.query(
                    """MATCH (act:Action {id: $action_id}), (ev:Evidence {id: $ev_id})
CREATE (act)-[:USES_EVIDENCE]->(ev)""",
                    {"action_id": action_id, "ev_id": ev_id},
                )
            except Exception as ev_exc:
                print(f"[queries] escalate_to_human evidence link warning: {ev_exc}")

        return {"action_id": action_id, "case_id": case_id, "reason": reason}
    except Exception as exc:
        print(f"[queries] escalate_to_human warning: {exc}")
        return {"action_id": action_id, "case_id": case_id, "reason": reason, "error": str(exc)}


# ---------------------------------------------------------------------------
# 13. Persist an agent session to the graph (kept for memory.py)
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
        return

    session_id = params["session_id"]

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
                {"session_id": session_id, "investigated_ids": investigated_ids},
            )
        except Exception as exc:
            print(f"[queries] persist_session_to_graph – INVESTIGATED link warning: {exc}")

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
