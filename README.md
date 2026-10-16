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

The schema promotes shared attributes to nodes so fraud rings become traversable paths. A shared device is only discoverable as a multi-hop connection if the device is a node, not a property.

### Node Types (13)

#### Data Layer

| Label | ID Prefix | Key Properties |
|---|---|---|
| **Customer** | `C_` | `id`, `name`, `email`, `kyc_status`, `risk_score`, `community_id`, `community_computed_at` |
| **Account** | `A_` | `id`, `account_type`, `bank_name`, `balance`, `status` (`active`\|`frozen`), `risk_score` |
| **Transaction** | `T_` | `id`, `amount`, `currency`, `ts`, `status`, `channel`, `risk_score` |
| **Device** | `D_` | `id`, `fingerprint`, `device_type`, `os`, `first_seen`, `last_seen` |
| **IP** | `IP_` | `id`, `address`, `country`, `isp` |
| **Phone** | *(none)* | `id`, `number`, `carrier` |
| **Address** | `ADDR_` | `id`, `street`, `city`, `country` |
| **Email** | *(none)* | `id`, `address`, `domain` |
| **Merchant** | *(none)* | `id`, `name`, `category`, `country`, `risk_score` |

#### Agent / Audit Layer

| Label | ID Prefix | Key Properties |
|---|---|---|
| **Alert** | `AL_` | `id`, `type`, `severity`, `ts` |
| **Case** | `CASE_` | `id`, `status`, `opened_at`, `closed_at` |
| **Decision** | `DEC_` | `id`, `verdict`, `confidence`, `rationale`, `ts` |
| **Evidence** | `EV_` | `id`, `kind`, `summary`, `entities`, `payload` |
| **Action** | `ACT_` | `id`, `type`, `dry_run`, `reason`, `ts` |

### Relationship Types

| Type | From → To | Key Properties |
|---|---|---|
| **OWNS** | Customer → Account | `since` |
| **SENT** | Account → Transaction | `ts`, `amount` |
| **TO** | Transaction → Account | — |
| **USED_DEVICE** | Customer → Device | `first_seen`, `last_seen` |
| **LOGGED_IN_FROM** | Customer → IP | `ts` |
| **HAS_PHONE** | Customer → Phone | — |
| **LIVES_AT** | Customer → Address | — |
| **HAS_EMAIL** | Customer → Email | — |
| **AT** | Transaction → Merchant | `processed_at` |
| **TRIGGERED_BY** | Alert → Transaction\|Account | — |
| **CONTAINS** | Case → Alert | — |
| **ABOUT** | Decision → Case | — |
| **EVIDENCED_BY** | Decision → Evidence | — |
| **LED_TO** | Decision → Action | — |
| **TARGETS** | Action → Account\|Customer\|Case | — |

### ID Convention

The prefix on every ID tells tools which label to query, enabling safe, label-aware lookups without ambiguity:

```
C_     Customer        A_     Account         T_     Transaction
D_     Device          IP_    IP              ADDR_  Address
AL_    Alert           CASE_  Case            DEC_   Decision
EV_    Evidence        ACT_   Action
```

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

- `"Investigate C_kunal — are they part of a fraud ring?"`
- `"Trace money flow from A_john1 over the last 7 days"`
- `"Why was alert AL_ring_alert triggered?"`
- `"Find path between A_kunal1 and A_lisa1"`
- `"What accounts are linked to T_mule1?"`
- `"Flag A_kingpin1 for suspicious activity"`
- `"Which customers share Device D_shared1?"`
- `"Detect communities starting from C_aryan"`

## Seeded Fraud Scenarios

The synthetic seed data is not random — each scenario is crafted to reward smart graph queries and test the agent's discernment.

| Scenario | Description |
|---|---|
| **Fraud Ring** | 6–8 customers (including `C_kunal`, `C_aryan`, `C_ifrah`) with no direct links but all reachable through 2 shared devices (`D_ring1`, `D_ring2`) and 1 shared address (`ADDR_ring1`) — 3 hops apart. |
| **Mule Chain** | Money passes through a chain `C_john → C_sarah → C_mike → C_lisa` (accounts `A_john1 → A_sarah1 → A_mike1 → A_lisa1`) with decreasing amounts over short intervals ending at a cash-out. |
| **Circular Flow** | Funds cycle back to their origin: `A_circ1 → A_circ2 → A_circ3 → A_circ1`, making the money appear to move without leaving the ring. |
| **Decoy (False Positive)** | Legitimate family members `C_raj`, `C_meera`, and `C_aditya` share a device and address — they look suspicious on naive queries but should be cleared by the agent. |
| **Bridge / Kingpin** | `C_kingpin` controls a high-centrality account (`A_kingpin1`) that bridges two otherwise-unconnected clusters; not obvious by transaction volume alone, revealed by betweenness centrality. |

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
