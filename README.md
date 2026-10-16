# Fraud Investigation Agent — FalkorDB Hackathon Track 1

A real-time fraud investigation agent where FalkorDB is the irreplaceable core. The agent uses LangChain + Groq (openai/gpt-oss-120b) as the reasoning engine, FastMCP as the tool layer, and every tool makes a direct Cypher query to the graph. Fraud ring detection, multi-hop account tracing, session memory, and account flagging all live in FalkorDB — removing the graph stops the product entirely.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          User / Browser                                │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ HTTP / WebSocket
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│              React UI  (Vite + Cytoscape.js)  :5173                   │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ REST + WebSocket
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   FastAPI  (port 8000)                                │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │              LangChain ReAct Agent                           │    │
│   │                                                             │    │
│   │  calls tools via ◄──────────────────────► Groq API          │    │
│   │                                           openai/gpt-oss-120b  │    │
│   └────────────────────────┬────────────────────────────────────┘    │
└────────────────────────────┼───────────────────────────────────────── ┘
                             │ stdio (subprocess)
                             ▼
┌───────────────────────────────────────────────────────────────────────┐
│                  FastMCP Tool Server                                  │
│   get_connected_accounts  |  trace_fraud_ring  |  flag_account       │
│   get_transaction_path    |  get_risk_neighbors | get_investigation.. │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ Cypher queries
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                  FalkorDB  (port 6379)                                │
│              graph: fraud_investigation                               │
└───────────────────────────────────────────────────────────────────────┘
```

## Graph Data Model

### Node Types (6)

| Label | Key Properties |
|---|---|
| **Transaction** | `id`, `amount`, `currency`, `timestamp`, `status`, `channel`, `risk_score`, `description` |
| **Account** | `id`, `account_type`, `bank_name`, `balance`, `status`, `risk_score`, `flag_reason`, `flagged_at`, `flagged_by` |
| **Customer** | `id`, `name`, `email`, `phone`, `country`, `kyc_status`, `risk_score` |
| **Merchant** | `id`, `name`, `category`, `country`, `risk_score`, `is_flagged` |
| **Device** | `id`, `fingerprint`, `device_type`, `os`, `ip_address`, `first_seen`, `last_seen` |
| **AgentSession** | `session_id`, `started_at`, `ended_at`, `query`, `conclusion`, `tools_used`, `account_ids` |

### Relationship Types (8)

| Type | From → To | Key Properties |
|---|---|---|
| **MADE** | Account → Transaction | `at` (timestamp), `channel` |
| **OWNS** | Customer → Account | `since` |
| **AT** | Transaction → Merchant | `processed_at` |
| **USED** | Account → Device | `first_used`, `last_used`, `use_count` |
| **TRANSFERRED_TO** | Account → Account | `amount`, `timestamp`, `reference`, `flagged` |
| **SHARED_DEVICE** | Account → Account | `device_id`, `overlap_period` |
| **INVESTIGATED** | AgentSession → Account | `role` |
| **FLAGGED_DURING** | AgentSession → Account | `reason` |

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- FalkorDB running on `localhost:6379`
  ```bash
  docker run -p 6379:6379 falkordb/falkordb
  ```
- Groq API key

### Environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
GRAPH_NAME=fraud_investigation
```

### Backend

```bash
cd Company-Brain
pip install -r backend/requirements.txt
python data/seed_graph.py
cd backend
uvicorn main:app --reload
```

The API will be available at http://localhost:8000.  
Health check: http://localhost:8000/health

### Frontend

```bash
cd Company-Brain/frontend
npm install
npm run dev
```

Open http://localhost:5173

## Cypher Queries

The six Cypher queries the product depends on, as executed by the MCP tool server.

### 1. `get_connected_accounts` — Multi-hop account discovery

Follows `USED → Device ← USED`, `TRANSFERRED_TO`, and `OWNS → Customer ← OWNS` paths from the transaction's source account.

```cypher
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
```

### 2. `trace_fraud_ring` — Variable-length path to flagged neighbors

Walks up to 3 hops from the target account and returns any neighbor whose status is `flagged` or `confirmed_fraud`.

```cypher
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
```

### 3. `get_transaction_path` — Shortest path between two accounts

Uses `shortestPath()` to prove a direct connection and returns every node and relationship along the route. FalkorDB requires `shortestPath` in a `WITH`/`RETURN` clause (not a `MATCH` clause).

```cypher
MATCH (a1:Account {id: $from_account_id}),
      (a2:Account {id: $to_account_id})
WITH shortestPath((a1)-[*1..10]-(a2)) AS path
RETURN
  [n IN nodes(path) | {id: n.id, labels: labels(n), risk_score: n.risk_score}] AS path_nodes,
  [r IN relationships(path) | {type: type(r), properties: properties(r)}]      AS path_rels,
  length(path) AS hop_count
```

### 4. `get_investigation_history` — Session memory from the graph

Fetches the 20 most-recent `AgentSession` nodes linked to this account via `INVESTIGATED` edges, giving the agent cross-session memory.

```cypher
MATCH (s:AgentSession)-[:INVESTIGATED]->(a:Account {id: $account_id})
RETURN
  s.session_id  AS session_id,
  s.started_at  AS started_at,
  s.query       AS query,
  s.conclusion  AS conclusion,
  s.tools_used  AS tools_used
ORDER BY s.started_at DESC
LIMIT 20
```

### 5. `flag_account` — Write flagging status back to the graph

Marks an account as flagged, records the reason, and ensures the risk score reaches at least 0.8.

```cypher
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
```

### 6. `get_risk_neighbors` — Single-hop neighborhood scan

Returns every node directly connected to an account along with relationship type and risk metadata.

```cypher
MATCH (a:Account {id: $account_id})-[r]-(neighbor)
RETURN
  neighbor.id         AS neighbor_id,
  labels(neighbor)    AS neighbor_labels,
  type(r)             AS relationship_type,
  neighbor.risk_score AS risk_score,
  neighbor.status     AS status,
  properties(r)       AS rel_properties
ORDER BY neighbor.risk_score DESC
```

## Example Investigation Questions

- `"Investigate transaction TXN-015"`
- `"Trace fraud ring for ACC-004"`
- `"Find path between ACC-001 and ACC-006"`
- `"What accounts are linked to TXN-019?"`
- `"Check investigation history for ACC-004"`
- `"Flag ACC-008 for suspicious activity"`

## Tech Stack

| Component | Technology |
|---|---|
| Graph database | FalkorDB |
| Backend language | Python 3.11 |
| API server | FastAPI (REST + WebSocket) |
| Agent framework | LangChain |
| LLM | Groq / openai/gpt-oss-120b |
| Tool server | FastMCP (stdio transport) |
| Frontend | React 18 |
| Graph visualization | Cytoscape.js |
| Frontend build | Vite |

## Hackathon Track

**Track 1: Agents That Act on Connected Data**

The graph is not a side store — it is the reasoning substrate. Every agent decision follows edges. Every session is written back as nodes. Take FalkorDB out and the product does not run.

## Disclosure

Built with AI coding assistance (Kiro).
