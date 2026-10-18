# Fraud Investigation Agent
### FalkorDB Hackathon — Track 1: Agents That Act on Connected Data

A real-time fraud investigation agent that uses **FalkorDB as its reasoning engine**. The agent traverses a graph of customers, accounts, transactions, devices, addresses, and IPs to detect fraud rings, mule chains, circular flows, and kingpin accounts — and explains every finding by citing the exact graph path it followed.

FalkorDB is not a side store. Every tool call is a Cypher query. Remove FalkorDB and the agent answers nothing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User / Browser                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│           React 18 + Cytoscape.js  (Vite, port 5173)               │
│  Chat panel (streaming)  │  Graph panel (nodes appear per tool)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST + WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FastAPI  (port 8000)                               │
│                                                                     │
│   LangChain ReAct Agent ──────────────────► OpenRouter LLM API     │
│          │                                  (llama-3.3-70b)        │
│          │ MCP stdio                                                │
│          ▼                                                          │
│   FastMCP Tool Server (12 tools)                                   │
│   get_entity_profile  │  detect_communities  │  find_paths         │
│   trace_money_flow    │  score_cluster       │  freeze_account ...  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Cypher queries
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FalkorDB  (port 6379 + browser UI port 3000)          │
│              graph: fraud_investigation                             │
│  43 nodes · 67 relationships · 5 fraud scenarios seeded            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Graph Data Model

The schema promotes shared attributes to **nodes** instead of properties. A shared device is only discoverable as a multi-hop path if the device is a node — that is what makes the connections traversable.

### Node Labels (13)

#### Data Layer

| Label | ID Prefix | Key Properties |
|-------|-----------|----------------|
| **Customer** | `C_` | `id`, `name`, `kyc_status`, `risk_score`, `community_id` |
| **Account** | `A_` | `id`, `bank_name`, `balance`, `status` (`active`\|`frozen`), `risk_score` |
| **Transaction** | `T_` | `id`, `amount`, `ts` (Unix epoch), `status`, `risk_score` |
| **Device** | `D_` | `id`, `fingerprint`, `device_type`, `first_seen`, `last_seen` |
| **Address** | `ADDR_` | `id`, `street`, `city`, `country` |
| **IP** | `IP_` | `id`, `address`, `country` |
| **Phone** | `PH_` | `id`, `number` |
| **Merchant** | `M_` | `id`, `name`, `category`, `risk_score` |

#### Agent / Audit Layer

| Label | ID Prefix | Key Properties |
|-------|-----------|----------------|
| **Alert** | `AL_` | `id`, `type`, `severity`, `triggered_at` |
| **Case** | `CASE_` | `id`, `status`, `opened_at`, `summary` |
| **Evidence** | `EV_` | `id`, `kind`, `summary`, `entities`, `payload` |
| **Decision** | `DEC_` | `id`, `verdict`, `confidence`, `rationale`, `created_at` |
| **Action** | `ACT_` | `id`, `type`, `dry_run`, `reason`, `ts` |

### Relationship Types (15)

| Relationship | From → To | Properties |
|---|---|---|
| `OWNS` | Customer → Account | `since` |
| `SENT` | Account → Transaction | `amount`, `ts` |
| `TO` | Transaction → Account | — |
| `USED_DEVICE` | Customer → Device | `first_seen`, `last_seen` |
| `LOGGED_IN_FROM` | Customer → IP | `ts` |
| `HAS_PHONE` | Customer → Phone | — |
| `LIVES_AT` | Customer → Address | — |
| `AT` | Transaction → Merchant | `processed_at` |
| `TRIGGERED_BY` | Alert → Transaction | — |
| `CONTAINS` | Case → Alert | — |
| `HAS_EVIDENCE` | Case → Evidence | — |
| `ABOUT` | Decision → Case | — |
| `EVIDENCED_BY` | Decision → Evidence | — |
| `LED_TO` | Decision → Action | — |
| `TARGETS` | Action → Account\|Customer\|Case | — |

### Why this schema detects fraud

Two customers sharing a device is **only a traversable path** if Device is a node:

```
(C_kunal)-[:USED_DEVICE]->(D_ring1)<-[:USED_DEVICE]-(C_aryan)
```

As a property on Customer, this connection doesn't exist until you write a join query. As a node, the agent finds it with a single 2-hop traversal.

---

## Seeded Fraud Scenarios

The synthetic data is crafted so each scenario rewards a specific graph query pattern.

| Scenario | Entities | What the graph reveals |
|---|---|---|
| **Fraud Ring** | C_kunal, C_aryan, C_ifrah, C_priya, C_hassan, C_nina, C_riya, C_dev | 8 customers with no direct links, all reachable through shared devices D_ring1, D_ring2 and address ADDR_ring1 — 2-3 hops |
| **Mule Chain** | C_john → C_sarah → C_mike → C_lisa | Decreasing amounts ($10K→$9.2K→$8.5K→$8K) over 2 hours ending at a cash-out merchant |
| **Circular Flow** | C_omar, C_diana, C_felix | A_omar1→A_diana1→A_felix1→A_omar1: money returns to origin |
| **Decoy (false positive)** | C_raj, C_meera, C_aditya | Legitimate family sharing a device and address — risk scores ≤0.15, all KYC verified, cleared by agent |
| **Kingpin Bridge** | C_kingpin / A_kingpin1 | One account bridges the fraud ring and mule chain; invisible by volume, revealed by degree centrality |

---

## Cypher Queries the Product Depends On

These are the queries executed on every investigation. The product stops working without them.

### 1. Community detection — finds the full fraud ring

```cypher
MATCH (seed {id: $id})-[*1..8]-(member)
WHERE member.id <> $id
RETURN DISTINCT member.id AS mid, labels(member) AS mlabels, member.risk_score AS mrisk
```

Write-back (batch, not per-node to avoid engine panic):
```cypher
UNWIND $ids AS mid
MATCH (m:Customer {id: mid})
SET m.community_id = $cid, m.community_computed_at = timestamp()
```

### 2. Shortest path — proves connection between two entities

FalkorDB requires `shortestPath` in a `WITH` clause, not `MATCH`:

```cypher
MATCH (x {id: $a}), (y {id: $b})
WITH shortestPath((x)-[*1..6]-(y)) AS p
RETURN [n IN nodes(p) | n.id]        AS ids,
       [r IN relationships(p) | type(r)] AS rels,
       length(p) AS hops
```

### 3. Shared attributes — finds bridge nodes connecting two entities

```cypher
MATCH (x {id: $a})-[*1..2]-(bridge)-[*1..2]-(y {id: $b})
WHERE bridge.id <> $a AND bridge.id <> $b
RETURN DISTINCT bridge.id AS bridge_id, labels(bridge) AS bridge_labels,
       bridge.risk_score AS bridge_risk
```

### 4. Money flow tracing — detects mule chains and structuring

```cypher
MATCH (a:Account {id: $id})-[:SENT]->(t:Transaction)-[:TO]->(b:Account)
WHERE t.ts >= $start_ts
RETURN t.id AS txn_id, t.amount AS amount, t.ts AS ts, b.id AS dest
```

### 5. Degree centrality — identifies the kingpin

```cypher
UNWIND $ids AS nid
MATCH (n {id: nid})-[r]-()
RETURN n.id AS nid, labels(n) AS nlabels, count(r) AS degree, n.risk_score AS risk_score
```

### 6. Cluster risk scoring — quantifies ring danger

```cypher
MATCH (n {community_id: $cid})
RETURN count(n) AS member_count, avg(n.risk_score) AS avg_risk, max(n.risk_score) AS max_risk
```

```cypher
MATCH (c:Customer {community_id: $cid})-[:USED_DEVICE]->(d:Device)
RETURN count(DISTINCT d) AS shared_devs
```

### 7. Account freeze write-back — agent action persisted to graph

```cypher
MATCH (a:Account {id: $account_id})
SET a.status = 'frozen'

CREATE (act:Action {
  id: $action_id, type: 'freeze_account',
  dry_run: $dry_run, reason: $reason, ts: timestamp()
})
MATCH (act:Action {id: $action_id}), (a:Account {id: $account_id})
CREATE (act)-[:TARGETS]->(a)
```

### 8. Entity profile — 1-hop context for any node

```cypher
MATCH (n:Customer {id: $id})-[r]-(nb)
RETURN type(r) AS rel, labels(nb) AS nb_labels, nb.id AS nb_id,
       nb.name AS nb_name, properties(r) AS rel_props
```

---

## Agent Tools (12)

The LangChain agent selects from these tools via MCP (stdio transport). Each tool is a Cypher query — no tool works without FalkorDB.

| Tool | Type | Purpose |
|------|------|---------|
| `get_entity_profile` | Read | 1-hop context for any entity |
| `expand_neighborhood` | Read | Variable-depth traversal (2-6 hops) |
| `find_paths` | Read | Shortest path between two entities |
| `shared_attributes` | Read | Bridge nodes connecting two entities |
| `detect_communities` | Read + Write | Full ring detection with write-back |
| `rank_central_nodes` | Read | Degree centrality — find the kingpin |
| `trace_money_flow` | Read | Inbound/outbound flow with velocity score |
| `score_cluster` | Read | Aggregate risk score for a community |
| `freeze_account` | **Write** | Sets account.status=frozen, creates Action node |
| `open_case` | **Write** | Creates Case linked to Alerts |
| `flag_cluster` | **Write** | Raises risk scores for ring members |
| `escalate_to_human` | **Write** | Creates escalation Action node |

---

## Local Setup Instructions

### Prerequisites

| Requirement | Version | Install |
|---|---|---|
| Python | 3.11+ | python.org |
| Node.js | 18+ | nodejs.org |
| Docker | any | docker.com |
| Git | any | git-scm.com |

### Step 1 — Clone and configure

```bash
git clone <your-repo-url>
cd Company-Brain
```

Create a `.env` file in the project root:

```env
# LLM — OpenRouter (free tier, no card required)
# Sign up at openrouter.ai, get key starting with sk-or-v1-...
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct
LLM_PROVIDER=openrouter

# FalkorDB
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
GRAPH_NAME=fraud_investigation

# Fallback LLM options (set LLM_PROVIDER=groq or LLM_PROVIDER=gemini)
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_API_KEY=your_gemini_key_here
```

### Step 2 — Start FalkorDB

```bash
docker run -d \
  -p 6379:6379 \
  -p 3000:3000 \
  --restart unless-stopped \
  --name falkordb \
  falkordb/falkordb
```

- Database: `localhost:6379`
- Browser UI: `http://localhost:3000`

### Step 3 — Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

### Step 4 — Seed the graph

```bash
python data/seed_graph.py
```

Expected output:
```
Seed complete — node counts by label:
  Customer    19    Account      20    Transaction  21
  Device       3    Address       2    IP           19
  Phone       19    Merchant      2    Alert         3
  Case         2    Evidence      2    Decision      2    Action  2
```

### Step 5 — Start the backend

```bash
cd backend
uvicorn main:app --port 8000
```

Verify: `http://localhost:8000/health` → `{"status": "ok", "falkordb": "connected"}`

### Step 6 — Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

---

## Free Cloud Deployment

The project can be fully deployed for free using these services:

| Component | Service | Free tier |
|---|---|---|
| FalkorDB | [FalkorDB Cloud](https://app.falkordb.cloud) | Free instance |
| Backend | [Render.com](https://render.com) | Free web service |
| Frontend | [Vercel](https://vercel.com) | Free static hosting |
| LLM | [OpenRouter](https://openrouter.ai) | Free models (llama-3.3-70b) |

### Deploy FalkorDB Cloud

1. Sign up at [app.falkordb.cloud](https://app.falkordb.cloud)
2. Create a free instance
3. Copy the connection string: `redis://:<password>@<host>:<port>`
4. Update `.env`:
   ```env
   FALKORDB_HOST=your-cloud-host
   FALKORDB_PORT=your-cloud-port
   FALKORDB_PASSWORD=your-cloud-password
   ```
5. Run `python data/seed_graph.py` to seed the cloud instance

### Deploy Backend on Render

1. Push code to GitHub
2. Sign up at [render.com](https://render.com)
3. New → Web Service → connect your repo
4. Settings:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add all `.env` variables under Environment
6. Deploy

### Deploy Frontend on Vercel

1. Sign up at [vercel.com](https://vercel.com)
2. Import your GitHub repo
3. Settings:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Add environment variable:
   - `VITE_API_URL` = your Render backend URL
5. Update `frontend/vite.config.js` proxy to point to the Render URL for production

---

## Example Queries to Try

```
Investigate the fraud ring starting from C_kunal
Trace the mule chain starting from A_john1
Find path between C_kunal and C_kingpin
Is the family of C_raj suspicious? They share a device and address
Investigate circular money flow involving C_omar
Who is the kingpin connecting the ring and mule chain?
Find fraud ring from AL_ring_alert
```

---

## Tech Stack

| Component | Technology | Version |
|---|---|---|
| Graph database | FalkorDB | latest |
| Backend | Python + FastAPI | 3.11 / 0.138 |
| Agent framework | LangChain | 1.4.6 |
| LLM | OpenRouter / llama-3.3-70b-instruct | — |
| MCP tool server | FastMCP | 4.1.0 |
| Frontend | React + Vite | 18 / 5.4 |
| Graph visualization | Cytoscape.js | 3.30 |

---

## Hackathon Submission

**Track**: Track 1 — Agents That Act on Connected Data

**Why FalkorDB is load-bearing**: Every one of the 12 agent tools executes a Cypher query. The fraud ring is only discoverable because Device and Address are nodes — shared attributes become traversable paths. The agent's memory (past investigations, decisions, actions) lives in the graph as `AgentSession`, `Decision`, `Evidence`, and `Action` nodes. Remove FalkorDB and the product stops entirely — there is no fallback store.

---

## Disclosure

Built with AI coding assistance (Kiro). All code understood and explainable by the submitter.
