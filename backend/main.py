import os
import sys
import json
import uuid
import asyncio
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.client import get_graph
from graph.queries import (
    query_connected_accounts,
    query_trace_fraud_ring,
    query_transaction_path,
    query_investigation_history,
    query_flag_account,
    query_risk_neighbors,
)
from agent.fraud_agent import run_investigation

app = FastAPI(title="Fraud Investigation Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvestigateRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class FlagRequest(BaseModel):
    account_id: str
    reason: str


@app.get("/health")
async def health_check():
    try:
        graph = get_graph()
        graph.query("RETURN 1")
        return {"status": "ok", "falkordb": "connected"}
    except Exception as e:
        return {"status": "error", "falkordb": f"disconnected: {str(e)}"}


@app.post("/api/investigate")
async def investigate(request: InvestigateRequest):
    try:
        result = await run_investigation(
            query=request.query,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str):
    try:
        graph = get_graph()
        result = graph.query(
            "MATCH (a:Account {id: $id}) RETURN a",
            {"id": account_id}
        )
        if not result.result_set:
            raise HTTPException(status_code=404, detail="Account not found")
        node = result.result_set[0][0]
        props = node.properties if hasattr(node, 'properties') else str(node)
        return {"id": account_id, "properties": props}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_id}/neighbors")
async def get_neighbors(account_id: str):
    try:
        graph = get_graph()
        return {"account_id": account_id, "neighbors": query_risk_neighbors(graph, account_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_id}/history")
async def get_history(account_id: str):
    try:
        graph = get_graph()
        return {"account_id": account_id, "history": query_investigation_history(graph, account_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions/{transaction_id}/connected")
async def get_connected(transaction_id: str):
    try:
        graph = get_graph()
        return {
            "transaction_id": transaction_id,
            "connected_accounts": query_connected_accounts(graph, transaction_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/flag")
async def flag_account_endpoint(request: FlagRequest):
    try:
        graph = get_graph()
        return query_flag_account(graph, request.account_id, request.reason)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/path")
async def get_path(from_account: str, to_account: str):
    try:
        graph = get_graph()
        return query_transaction_path(graph, from_account, to_account)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/overview")
async def graph_overview():
    try:
        graph = get_graph()
        labels = ['Account', 'Transaction', 'Customer', 'Merchant', 'Device', 'AgentSession']
        counts = {}
        for label in labels:
            r = graph.query(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            counts[label] = r.result_set[0][0] if r.result_set else 0

        rel_types = [
            'MADE', 'OWNS', 'AT', 'USED',
            'TRANSFERRED_TO', 'SHARED_DEVICE', 'INVESTIGATED', 'FLAGGED_DURING',
        ]
        edge_counts = {}
        for rt in rel_types:
            r = graph.query(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
            edge_counts[rt] = r.result_set[0][0] if r.result_set else 0

        flagged_r = graph.query(
            "MATCH (a:Account) WHERE a.status IN ['flagged','confirmed_fraud'] RETURN count(a) AS cnt"
        )
        flagged_txn = graph.query(
            "MATCH (t:Transaction) WHERE t.status IN ['flagged','confirmed_fraud'] RETURN count(t) AS cnt"
        )
        return {
            "node_counts": counts,
            "edge_counts": edge_counts,
            "flagged_accounts": flagged_r.result_set[0][0] if flagged_r.result_set else 0,
            "flagged_transactions": flagged_txn.result_set[0][0] if flagged_txn.result_set else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/investigate")
async def investigate_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        query = data.get('query', '')
        session_id = data.get('session_id', None)

        steps_sent = []

        async def step_callback(step):
            await websocket.send_json({"type": "step", "data": step})
            steps_sent.append(step)

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
