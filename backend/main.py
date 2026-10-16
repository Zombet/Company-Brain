import os
import sys
import json
import uuid
import asyncio
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.client import get_graph
from graph.queries import (
    get_entity_profile,
    expand_neighborhood,
    find_paths,
    shared_attributes,
    detect_communities,
    freeze_account,
    open_case,
    escalate_to_human,
)
from agent.fraud_agent import run_investigation

app = FastAPI(title="Fraud Investigation Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class InvestigateRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class FreezeRequest(BaseModel):
    account_id: str
    reason: str
    evidence_ids: List[str] = []
    dry_run: bool = True


class OpenCaseRequest(BaseModel):
    alert_ids: List[str] = []
    reason: str
    evidence_ids: List[str] = []


class EscalateRequest(BaseModel):
    case_id: str
    reason: str
    evidence_ids: List[str] = []


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    try:
        graph = get_graph()
        graph.query("RETURN 1")
        return {"status": "ok", "falkordb": "connected"}
    except Exception as e:
        return {"status": "error", "falkordb": f"disconnected: {str(e)}"}


# ---------------------------------------------------------------------------
# Investigation (REST + WebSocket)
# ---------------------------------------------------------------------------

@app.post("/api/investigate")
async def investigate(request: InvestigateRequest):
    try:
        result = await run_investigation(
            query=request.query,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/investigate")
async def investigate_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        query = data.get("query", "")
        session_id = data.get("session_id", None)

        async def step_callback(step):
            await websocket.send_json({"type": "step", "data": step})

        result = await run_investigation(
            query=query,
            session_id=session_id,
            stream_callback=step_callback,
        )
        await websocket.send_json({"type": "done", "data": result})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entity read endpoints (FEAT-002)
# ---------------------------------------------------------------------------

@app.get("/api/entity/{entity_id}")
async def get_entity(entity_id: str):
    """Return full node properties and 1-hop neighbours for any entity."""
    try:
        graph = get_graph()
        result = get_entity_profile(graph, entity_id)
        if not result.get("node"):
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entity/{entity_id}/neighborhood")
async def get_neighborhood(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=6),
    rel_types: Optional[str] = Query(default=None, description="Comma-separated relationship types"),
):
    """Expand the network around an entity to a given hop depth."""
    try:
        graph = get_graph()
        rel_list = [r.strip() for r in rel_types.split(",")] if rel_types else None
        return expand_neighborhood(graph, entity_id, depth, rel_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paths")
async def get_paths(
    from_id: str = Query(...),
    to_id: str = Query(...),
    max_hops: int = Query(default=6, ge=1, le=10),
):
    """Find the shortest path between two entities."""
    try:
        graph = get_graph()
        return {"paths": find_paths(graph, from_id, to_id, max_hops)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shared")
async def get_shared(
    a: str = Query(...),
    b: str = Query(...),
):
    """Find bridge nodes shared between two entities."""
    try:
        graph = get_graph()
        return {"bridges": shared_attributes(graph, a, b)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/community/{seed_id}")
async def get_community(seed_id: str):
    """Detect the community around a seed entity."""
    try:
        graph = get_graph()
        return detect_communities(graph, seed_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Action endpoints (FEAT-002)
# ---------------------------------------------------------------------------

@app.post("/api/action/freeze")
async def action_freeze(request: FreezeRequest):
    """Freeze an account (dry_run=True by default)."""
    try:
        graph = get_graph()
        return freeze_account(graph, request.account_id, request.reason, request.evidence_ids, request.dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/action/open-case")
async def action_open_case(request: OpenCaseRequest):
    """Open a new investigation Case."""
    try:
        graph = get_graph()
        return open_case(graph, request.alert_ids, request.reason, request.evidence_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/action/escalate")
async def action_escalate(request: EscalateRequest):
    """Escalate a case to a human analyst."""
    try:
        graph = get_graph()
        return escalate_to_human(graph, request.case_id, request.reason, request.evidence_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Graph overview (updated for new schema labels)
# ---------------------------------------------------------------------------

@app.get("/api/graph/overview")
async def graph_overview():
    try:
        graph = get_graph()
        node_labels = [
            "Customer", "Account", "Transaction", "Device", "Address",
            "IP", "Phone", "Merchant", "Alert", "Case", "Evidence",
            "Decision", "Action",
        ]
        node_counts = {}
        for label in node_labels:
            r = graph.query(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            node_counts[label] = r.result_set[0][0] if r.result_set else 0

        rel_types = [
            "OWNS", "SENT", "TO", "USED_DEVICE", "LOGGED_IN_FROM",
            "LIVES_AT", "HAS_PHONE", "AT", "TRIGGERED_BY", "CONTAINS",
            "HAS_EVIDENCE", "ABOUT", "EVIDENCED_BY", "LED_TO", "TARGETS",
        ]
        edge_counts = {}
        for rt in rel_types:
            r = graph.query(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
            edge_counts[rt] = r.result_set[0][0] if r.result_set else 0

        flagged_r = graph.query(
            "MATCH (a:Account) WHERE a.status IN ['flagged','confirmed_fraud','frozen'] RETURN count(a) AS cnt"
        )
        flagged_txn = graph.query(
            "MATCH (t:Transaction) WHERE t.status IN ['flagged','confirmed_fraud'] RETURN count(t) AS cnt"
        )
        return {
            "node_counts": node_counts,
            "edge_counts": edge_counts,
            "flagged_accounts": flagged_r.result_set[0][0] if flagged_r.result_set else 0,
            "flagged_transactions": flagged_txn.result_set[0][0] if flagged_txn.result_set else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str):
    try:
        graph = get_graph()
        result = graph.query("MATCH (a:Account {id: $id}) RETURN a", {"id": account_id})
        if not result.result_set:
            raise HTTPException(status_code=404, detail="Account not found")
        node = result.result_set[0][0]
        props = node.properties if hasattr(node, "properties") else str(node)
        return {"id": account_id, "properties": props}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_id}/neighbors")
async def get_neighbors(account_id: str):
    try:
        graph = get_graph()
        result = get_entity_profile(graph, account_id)
        return {"account_id": account_id, "neighbors": result.get("neighbors", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
