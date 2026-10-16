import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

import falkordb
import time

FALKORDB_HOST = os.environ.get('FALKORDB_HOST', 'localhost')
FALKORDB_PORT = int(os.environ.get('FALKORDB_PORT', '6379'))
GRAPH_NAME = os.environ.get('GRAPH_NAME', 'fraud_investigation')


def connect():
    """Connect to FalkorDB, drop the old graph if it exists, then return a fresh graph handle."""
    client = falkordb.FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    try:
        client.delete_graph(GRAPH_NAME)
        print(f"[seed] Dropped existing graph '{GRAPH_NAME}'.")
    except Exception:
        print(f"[seed] Graph '{GRAPH_NAME}' did not exist — creating fresh.")
    graph = client.select_graph(GRAPH_NAME)
    return graph


def create_indexes(graph):
    indexes = [
        "CREATE INDEX ON :Transaction(id)",
        "CREATE INDEX ON :Transaction(status)",
        "CREATE INDEX ON :Account(id)",
        "CREATE INDEX ON :Account(status)",
        "CREATE INDEX ON :Customer(id)",
        "CREATE INDEX ON :Merchant(id)",
        "CREATE INDEX ON :Device(id)",
        "CREATE INDEX ON :AgentSession(session_id)",
    ]
    for q in indexes:
        try:
            graph.query(q)
        except Exception as exc:
            print(f"[seed] Index warning (may already exist): {exc}")
    print("[seed] Indexes created.")


def create_customers(graph):
    customers = [
        {
            "id": "CUST-001", "name": "Alice Johnson",
            "email": "alice@example.com", "phone": "+1-555-0101",
            "country": "US", "kyc_status": "verified",
            "risk_score": 0.05, "created_at": 1700000000,
        },
        {
            "id": "CUST-002", "name": "Bob Smith",
            "email": "bob@example.com", "phone": "+1-555-0102",
            "country": "US", "kyc_status": "verified",
            "risk_score": 0.08, "created_at": 1700100000,
        },
        {
            "id": "CUST-003", "name": "Carol Davis",
            "email": "carol@example.com", "phone": "+1-555-0103",
            "country": "CA", "kyc_status": "verified",
            "risk_score": 0.10, "created_at": 1700200000,
        },
        # Fraudulent ring members
        {
            "id": "CUST-004", "name": "Dave Phantom",
            "email": "dave_ph@burner.io", "phone": "+1-555-0199",
            "country": "XX", "kyc_status": "pending",
            "risk_score": 0.85, "created_at": 1710000000,
        },
        {
            "id": "CUST-005", "name": "Eve Shadow",
            "email": "eve_sh@burner.io", "phone": "+1-555-0198",
            "country": "XX", "kyc_status": "failed",
            "risk_score": 0.92, "created_at": 1710100000,
        },
    ]
    for c in customers:
        graph.query(
            "CREATE (:Customer {id:$id, name:$name, email:$email, phone:$phone, "
            "country:$country, kyc_status:$kyc_status, risk_score:$risk_score, created_at:$created_at})",
            c,
        )
    print(f"[seed] Created {len(customers)} customers.")


def create_accounts(graph):
    accounts = [
        {
            "id": "ACC-001", "account_type": "checking", "bank_name": "First National",
            "balance": 5200.0, "opened_date": 1700000000, "status": "active",
            "risk_score": 0.05, "flag_reason": None, "flagged_at": None, "flagged_by": None,
        },
        {
            "id": "ACC-002", "account_type": "savings", "bank_name": "City Bank",
            "balance": 12000.0, "opened_date": 1700100000, "status": "active",
            "risk_score": 0.07, "flag_reason": None, "flagged_at": None, "flagged_by": None,
        },
        {
            "id": "ACC-003", "account_type": "checking", "bank_name": "Metro Credit",
            "balance": 3100.0, "opened_date": 1700200000, "status": "active",
            "risk_score": 0.10, "flag_reason": None, "flagged_at": None, "flagged_by": None,
        },
        # Fraud ring core
        {
            "id": "ACC-004", "account_type": "checking", "bank_name": "Shell Bank A",
            "balance": 500.0, "opened_date": 1710000000, "status": "flagged",
            "risk_score": 0.90, "flag_reason": "structuring",
            "flagged_at": 1715000000, "flagged_by": "agent",
        },
        {
            "id": "ACC-005", "account_type": "checking", "bank_name": "Shell Bank B",
            "balance": 250.0, "opened_date": 1710100000, "status": "flagged",
            "risk_score": 0.88, "flag_reason": "rapid_transfers",
            "flagged_at": 1715100000, "flagged_by": "agent",
        },
        {
            "id": "ACC-006", "account_type": "credit", "bank_name": "Shell Bank A",
            "balance": -800.0, "opened_date": 1710200000, "status": "flagged",
            "risk_score": 0.85, "flag_reason": "ring_member",
            "flagged_at": 1715200000, "flagged_by": "agent",
        },
        # Mule accounts
        {
            "id": "ACC-007", "account_type": "savings", "bank_name": "Green Finance",
            "balance": 4500.0, "opened_date": 1712000000, "status": "flagged",
            "risk_score": 0.75, "flag_reason": "unusual_deposits",
            "flagged_at": 1716000000, "flagged_by": "agent",
        },
        {
            "id": "ACC-008", "account_type": "checking", "bank_name": "Green Finance",
            "balance": 1200.0, "opened_date": 1712100000, "status": "active",
            "risk_score": 0.55, "flag_reason": None, "flagged_at": None, "flagged_by": None,
        },
    ]
    for a in accounts:
        graph.query(
            "CREATE (:Account {id:$id, account_type:$account_type, bank_name:$bank_name, "
            "balance:$balance, opened_date:$opened_date, status:$status, risk_score:$risk_score, "
            "flag_reason:$flag_reason, flagged_at:$flagged_at, flagged_by:$flagged_by})",
            a,
        )
    print(f"[seed] Created {len(accounts)} accounts.")


def create_merchants(graph):
    merchants = [
        {"id": "MER-001", "name": "Amazon",          "category": "retail",        "country": "US", "risk_score": 0.05, "is_flagged": False},
        {"id": "MER-002", "name": "Shell Gas",        "category": "fuel",          "country": "US", "risk_score": 0.10, "is_flagged": False},
        {"id": "MER-003", "name": "Crypto Exchange",  "category": "crypto",        "country": "XX", "risk_score": 0.80, "is_flagged": True},
        {"id": "MER-004", "name": "QuickTransfer",    "category": "wire_transfer", "country": "XX", "risk_score": 0.88, "is_flagged": True},
        {"id": "MER-005", "name": "Best Buy",         "category": "electronics",   "country": "US", "risk_score": 0.15, "is_flagged": False},
    ]
    for m in merchants:
        graph.query(
            "CREATE (:Merchant {id:$id, name:$name, category:$category, country:$country, "
            "risk_score:$risk_score, is_flagged:$is_flagged})",
            m,
        )
    print(f"[seed] Created {len(merchants)} merchants.")


def create_devices(graph):
    devices = [
        {
            "id": "DEV-001", "fingerprint": "fp_a1b2c3", "device_type": "mobile",
            "os": "iOS 17", "ip_address": "192.168.1.10",
            "first_seen": 1700000000, "last_seen": 1716000000,
        },
        {
            "id": "DEV-002", "fingerprint": "fp_x9y8z7", "device_type": "mobile",
            "os": "Android 13", "ip_address": "10.0.0.99",
            "first_seen": 1710000000, "last_seen": 1716500000,
        },
        {
            "id": "DEV-003", "fingerprint": "fp_m3n4p5", "device_type": "desktop",
            "os": "Windows 11", "ip_address": "10.0.0.88",
            "first_seen": 1712000000, "last_seen": 1717000000,
        },
    ]
    for d in devices:
        graph.query(
            "CREATE (:Device {id:$id, fingerprint:$fingerprint, device_type:$device_type, "
            "os:$os, ip_address:$ip_address, first_seen:$first_seen, last_seen:$last_seen})",
            d,
        )
    print(f"[seed] Created {len(devices)} devices.")


def create_transactions(graph):
    transactions = [
        # --- Normal transactions (14) ---
        {"id": "TXN-001", "amount": 45.99,  "currency": "USD", "timestamp": 1714000000, "status": "normal",           "channel": "web",    "risk_score": 0.05, "description": "Amazon purchase"},
        {"id": "TXN-002", "amount": 120.0,  "currency": "USD", "timestamp": 1714100000, "status": "normal",           "channel": "pos",    "risk_score": 0.07, "description": "Best Buy"},
        {"id": "TXN-003", "amount": 35.50,  "currency": "USD", "timestamp": 1714200000, "status": "normal",           "channel": "mobile", "risk_score": 0.06, "description": "Gas station"},
        {"id": "TXN-004", "amount": 200.0,  "currency": "USD", "timestamp": 1714300000, "status": "normal",           "channel": "web",    "risk_score": 0.08, "description": "Online shopping"},
        {"id": "TXN-005", "amount": 55.0,   "currency": "USD", "timestamp": 1714400000, "status": "normal",           "channel": "atm",    "risk_score": 0.05, "description": "ATM withdrawal"},
        {"id": "TXN-006", "amount": 80.0,   "currency": "USD", "timestamp": 1714500000, "status": "normal",           "channel": "pos",    "risk_score": 0.09, "description": "Restaurant"},
        {"id": "TXN-007", "amount": 300.0,  "currency": "USD", "timestamp": 1714600000, "status": "normal",           "channel": "web",    "risk_score": 0.10, "description": "Utility bill"},
        {"id": "TXN-008", "amount": 175.0,  "currency": "USD", "timestamp": 1714700000, "status": "normal",           "channel": "mobile", "risk_score": 0.06, "description": "Subscription"},
        {"id": "TXN-009", "amount": 95.0,   "currency": "USD", "timestamp": 1714800000, "status": "normal",           "channel": "pos",    "risk_score": 0.07, "description": "Grocery store"},
        {"id": "TXN-010", "amount": 420.0,  "currency": "USD", "timestamp": 1714900000, "status": "normal",           "channel": "web",    "risk_score": 0.08, "description": "Flight booking"},
        {"id": "TXN-011", "amount": 60.0,   "currency": "USD", "timestamp": 1715000000, "status": "normal",           "channel": "atm",    "risk_score": 0.05, "description": "Cash withdrawal"},
        {"id": "TXN-012", "amount": 145.0,  "currency": "USD", "timestamp": 1715100000, "status": "normal",           "channel": "pos",    "risk_score": 0.09, "description": "Clothing store"},
        {"id": "TXN-013", "amount": 22.50,  "currency": "USD", "timestamp": 1715200000, "status": "normal",           "channel": "mobile", "risk_score": 0.04, "description": "Coffee shop"},
        {"id": "TXN-014", "amount": 500.0,  "currency": "USD", "timestamp": 1715300000, "status": "normal",           "channel": "web",    "risk_score": 0.11, "description": "Electronics"},
        # --- Flagged / fraud transactions (8) ---
        {"id": "TXN-015", "amount": 9500.0, "currency": "USD", "timestamp": 1715400000, "status": "flagged",          "channel": "web",    "risk_score": 0.88, "description": "Structuring — just under reporting threshold"},
        {"id": "TXN-016", "amount": 8750.0, "currency": "USD", "timestamp": 1715410000, "status": "flagged",          "channel": "mobile", "risk_score": 0.90, "description": "Rapid repeat transfer"},
        {"id": "TXN-017", "amount": 5000.0, "currency": "USD", "timestamp": 1715420000, "status": "flagged",          "channel": "web",    "risk_score": 0.85, "description": "Crypto exchange purchase"},
        {"id": "TXN-018", "amount": 4800.0, "currency": "USD", "timestamp": 1715430000, "status": "flagged",          "channel": "web",    "risk_score": 0.87, "description": "Wire to unknown account"},
        {"id": "TXN-019", "amount": 3200.0, "currency": "USD", "timestamp": 1715440000, "status": "confirmed_fraud",  "channel": "mobile", "risk_score": 0.95, "description": "Confirmed fraud — identity theft"},
        {"id": "TXN-020", "amount": 7100.0, "currency": "USD", "timestamp": 1715450000, "status": "confirmed_fraud",  "channel": "web",    "risk_score": 0.96, "description": "Confirmed fraud — account takeover"},
        {"id": "TXN-021", "amount": 2400.0, "currency": "USD", "timestamp": 1715460000, "status": "flagged",          "channel": "atm",    "risk_score": 0.82, "description": "Multiple ATM withdrawals same day"},
        {"id": "TXN-022", "amount": 6600.0, "currency": "USD", "timestamp": 1715470000, "status": "flagged",          "channel": "web",    "risk_score": 0.89, "description": "High-risk merchant transfer"},
    ]
    for t in transactions:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, currency:$currency, "
            "timestamp:$timestamp, status:$status, channel:$channel, "
            "risk_score:$risk_score, description:$description})",
            t,
        )
    print(f"[seed] Created {len(transactions)} transactions.")


def create_relationships(graph):
    # ---- OWNS (Customer -> Account) ----
    owns = [
        ("CUST-001", "ACC-001"),
        ("CUST-002", "ACC-002"),
        ("CUST-003", "ACC-003"),
        ("CUST-004", "ACC-004"),
        ("CUST-004", "ACC-005"),
        ("CUST-005", "ACC-006"),
        ("CUST-005", "ACC-007"),
        ("CUST-005", "ACC-008"),
    ]
    for c, a in owns:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (a:Account {id:$aid}) "
            "CREATE (c)-[:OWNS {since: 1700000000}]->(a)",
            {"cid": c, "aid": a},
        )
    print(f"[seed] Created {len(owns)} OWNS relationships.")

    # ---- MADE (Account -> Transaction) ----
    made = [
        ("ACC-001", "TXN-001", 1714000000, "web"),
        ("ACC-001", "TXN-002", 1714100000, "pos"),
        ("ACC-002", "TXN-003", 1714200000, "mobile"),
        ("ACC-002", "TXN-004", 1714300000, "web"),
        ("ACC-003", "TXN-005", 1714400000, "atm"),
        ("ACC-003", "TXN-006", 1714500000, "pos"),
        ("ACC-001", "TXN-007", 1714600000, "web"),
        ("ACC-002", "TXN-008", 1714700000, "mobile"),
        ("ACC-003", "TXN-009", 1714800000, "pos"),
        ("ACC-001", "TXN-010", 1714900000, "web"),
        ("ACC-002", "TXN-011", 1715000000, "atm"),
        ("ACC-003", "TXN-012", 1715100000, "pos"),
        ("ACC-001", "TXN-013", 1715200000, "mobile"),
        ("ACC-002", "TXN-014", 1715300000, "web"),
        # Fraud ring
        ("ACC-004", "TXN-015", 1715400000, "web"),
        ("ACC-004", "TXN-016", 1715410000, "mobile"),
        ("ACC-005", "TXN-017", 1715420000, "web"),
        ("ACC-005", "TXN-018", 1715430000, "web"),
        ("ACC-006", "TXN-019", 1715440000, "mobile"),
        ("ACC-006", "TXN-020", 1715450000, "web"),
        ("ACC-007", "TXN-021", 1715460000, "atm"),
        ("ACC-008", "TXN-022", 1715470000, "web"),
    ]
    for a, t, ts, ch in made:
        graph.query(
            "MATCH (a:Account {id:$aid}), (t:Transaction {id:$tid}) "
            "CREATE (a)-[:MADE {at:$ts, channel:$ch}]->(t)",
            {"aid": a, "tid": t, "ts": ts, "ch": ch},
        )
    print(f"[seed] Created {len(made)} MADE relationships.")

    # ---- AT (Transaction -> Merchant) ----
    at_rels = [
        ("TXN-001", "MER-001"), ("TXN-002", "MER-005"), ("TXN-003", "MER-002"),
        ("TXN-004", "MER-001"), ("TXN-005", "MER-002"), ("TXN-006", "MER-002"),
        ("TXN-007", "MER-001"), ("TXN-008", "MER-005"), ("TXN-009", "MER-002"),
        ("TXN-010", "MER-001"), ("TXN-011", "MER-002"), ("TXN-012", "MER-005"),
        ("TXN-013", "MER-002"), ("TXN-014", "MER-005"),
        ("TXN-015", "MER-004"), ("TXN-016", "MER-004"), ("TXN-017", "MER-003"),
        ("TXN-018", "MER-004"), ("TXN-019", "MER-003"), ("TXN-020", "MER-004"),
        ("TXN-021", "MER-002"), ("TXN-022", "MER-004"),
    ]
    for t, m in at_rels:
        graph.query(
            "MATCH (t:Transaction {id:$tid}), (m:Merchant {id:$mid}) "
            "CREATE (t)-[:AT {processed_at: 1715000000}]->(m)",
            {"tid": t, "mid": m},
        )
    print(f"[seed] Created {len(at_rels)} AT relationships.")

    # ---- USED (Account -> Device) ----
    used = [
        ("ACC-001", "DEV-001", 1714000000, 1716000000, 14),
        ("ACC-002", "DEV-001", 1714100000, 1715000000, 8),
        ("ACC-004", "DEV-002", 1710000000, 1715500000, 22),  # fraud ring shares DEV-002
        ("ACC-005", "DEV-002", 1710100000, 1715600000, 18),  # fraud ring shares DEV-002
        ("ACC-006", "DEV-003", 1712000000, 1716000000, 15),  # ring + mule share DEV-003
        ("ACC-007", "DEV-003", 1712100000, 1716100000, 12),  # ring + mule share DEV-003
        ("ACC-003", "DEV-001", 1714200000, 1715100000, 6),
    ]
    for a, d, fu, lu, uc in used:
        graph.query(
            "MATCH (a:Account {id:$aid}), (d:Device {id:$did}) "
            "CREATE (a)-[:USED {first_used:$fu, last_used:$lu, use_count:$uc}]->(d)",
            {"aid": a, "did": d, "fu": fu, "lu": lu, "uc": uc},
        )
    print(f"[seed] Created {len(used)} USED relationships.")

    # ---- SHARED_DEVICE (shortcut edges for fast ring detection) ----
    shared = [
        ("ACC-004", "ACC-005", "DEV-002", "2024-01 to 2024-05"),
        ("ACC-006", "ACC-007", "DEV-003", "2024-03 to 2024-06"),
    ]
    for a1, a2, did, period in shared:
        graph.query(
            "MATCH (a1:Account {id:$a1}), (a2:Account {id:$a2}) "
            "CREATE (a1)-[:SHARED_DEVICE {device_id:$did, overlap_period:$period}]->(a2)",
            {"a1": a1, "a2": a2, "did": did, "period": period},
        )
    print(f"[seed] Created {len(shared)} SHARED_DEVICE relationships.")

    # ---- TRANSFERRED_TO (ring cycle: ACC-004 -> ACC-005 -> ACC-006 -> ACC-004) ----
    transfers = [
        ("ACC-004", "ACC-005", 8750.0, 1715410000, "REF-T001", True),
        ("ACC-005", "ACC-006", 8500.0, 1715420000, "REF-T002", True),
        ("ACC-006", "ACC-004", 8200.0, 1715430000, "REF-T003", True),   # closes the ring
        ("ACC-006", "ACC-007", 4000.0, 1715460000, "REF-T004", True),   # laundering to mule
        ("ACC-007", "ACC-008", 3500.0, 1715470000, "REF-T005", False),  # mule to clean account
        ("ACC-001", "ACC-002",  200.0, 1714600000, "REF-T006", False),  # normal transfer
    ]
    for a1, a2, amt, ts, ref, flagged in transfers:
        graph.query(
            "MATCH (a1:Account {id:$a1}), (a2:Account {id:$a2}) "
            "CREATE (a1)-[:TRANSFERRED_TO {amount:$amt, timestamp:$ts, reference:$ref, flagged:$flagged}]->(a2)",
            {"a1": a1, "a2": a2, "amt": amt, "ts": ts, "ref": ref, "flagged": flagged},
        )
    print(f"[seed] Created {len(transfers)} TRANSFERRED_TO relationships.")


if __name__ == '__main__':
    print(f"[seed] Connecting to FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT} ...")
    graph = connect()

    print("[seed] Creating indexes ...")
    create_indexes(graph)

    print("[seed] Seeding nodes ...")
    create_customers(graph)
    create_accounts(graph)
    create_merchants(graph)
    create_devices(graph)
    create_transactions(graph)

    print("[seed] Seeding relationships ...")
    create_relationships(graph)

    print()
    print("=" * 60)
    print("Seed complete.")
    print("  5 customers  (CUST-001 … CUST-005)")
    print("  8 accounts   (ACC-001  … ACC-008)")
    print("  5 merchants  (MER-001  … MER-005)")
    print("  3 devices    (DEV-001  … DEV-003)")
    print(" 22 transactions (TXN-001 … TXN-022)")
    print()
    print("Fraud ring: ACC-004 -> ACC-005 -> ACC-006 -> ACC-004 (cycle)")
    print("Shared device: ACC-004 & ACC-005 share DEV-002")
    print("               ACC-006 & ACC-007 share DEV-003")
    print("=" * 60)
