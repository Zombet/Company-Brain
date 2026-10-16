import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

import falkordb

FALKORDB_HOST = os.environ.get('FALKORDB_HOST', 'localhost')
FALKORDB_PORT = int(os.environ.get('FALKORDB_PORT', '6379'))
GRAPH_NAME    = os.environ.get('GRAPH_NAME', 'fraud_investigation')


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def connect():
    """Drop old graph and return a fresh handle."""
    client = falkordb.FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    existing = client.list_graphs()
    if GRAPH_NAME in existing:
        graph = client.select_graph(GRAPH_NAME)
        graph.delete()
        print(f"[seed] Dropped existing graph '{GRAPH_NAME}'.")
    else:
        print(f"[seed] Graph '{GRAPH_NAME}' did not exist — creating fresh.")
    return client.select_graph(GRAPH_NAME)


# ---------------------------------------------------------------------------
# Indexes  (CREATE INDEX FOR syntax required by FalkorDB)
# ---------------------------------------------------------------------------

def create_indexes(graph):
    labels = [
        "Customer", "Account", "Transaction", "Device", "Address",
        "IP", "Phone", "Merchant", "Alert", "Case", "Evidence",
        "Decision", "Action",
    ]
    for label in labels:
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        except Exception as exc:
            print(f"[seed] Index warning {label}.id: {exc}")
    # Extra index on Transaction.ts for temporal queries
    try:
        graph.query("CREATE INDEX FOR (n:Transaction) ON (n.ts)")
    except Exception as exc:
        print(f"[seed] Index warning Transaction.ts: {exc}")
    print("[seed] Indexes created.")


# ---------------------------------------------------------------------------
# Customers + Accounts
# ---------------------------------------------------------------------------

def create_customers_and_accounts(graph):
    # ------------------------------------------------------------------
    # Scenario 1 – Fraud Ring (8 members: 6 original + 2 associates)
    # ------------------------------------------------------------------
    ring_customers = [
        {"id": "C_kunal",  "name": "Kunal Sharma",  "country": "IN", "kyc_status": "pending", "risk_score": 0.88},
        {"id": "C_aryan",  "name": "Aryan Mehta",   "country": "IN", "kyc_status": "pending", "risk_score": 0.85},
        {"id": "C_ifrah",  "name": "Ifrah Khan",    "country": "PK", "kyc_status": "pending", "risk_score": 0.87},
        {"id": "C_priya",  "name": "Priya Patel",   "country": "IN", "kyc_status": "pending", "risk_score": 0.82},
        {"id": "C_hassan", "name": "Hassan Ali",    "country": "AE", "kyc_status": "pending", "risk_score": 0.90},
        {"id": "C_nina",   "name": "Nina Rossi",    "country": "IT", "kyc_status": "pending", "risk_score": 0.78},
        # Two additional ring associates — share D_ring2 and ADDR_ring1
        {"id": "C_riya",   "name": "Riya Desai",    "country": "IN", "kyc_status": "pending", "risk_score": 0.76},
        {"id": "C_dev",    "name": "Dev Anand",     "country": "IN", "kyc_status": "pending", "risk_score": 0.73},
    ]
    ring_accounts = [
        {"id": "A_kunal1",  "status": "active",  "risk_score": 0.88, "bank_name": "Shell Bank A"},
        {"id": "A_aryan1",  "status": "active",  "risk_score": 0.85, "bank_name": "Shell Bank B"},
        {"id": "A_ifrah1",  "status": "active",  "risk_score": 0.87, "bank_name": "Shell Bank C"},
        {"id": "A_priya1",  "status": "active",  "risk_score": 0.82, "bank_name": "Shell Bank D"},
        {"id": "A_hassan1", "status": "active",  "risk_score": 0.90, "bank_name": "Shell Bank E"},
        {"id": "A_nina1",   "status": "active",  "risk_score": 0.78, "bank_name": "Shell Bank F"},
        {"id": "A_riya1",   "status": "active",  "risk_score": 0.76, "bank_name": "Shell Bank G"},
        {"id": "A_dev1",    "status": "active",  "risk_score": 0.73, "bank_name": "Shell Bank H"},
    ]

    # ------------------------------------------------------------------
    # Scenario 2 – Mule Chain (4 members)
    # ------------------------------------------------------------------
    mule_customers = [
        {"id": "C_john",  "name": "John Carter",  "country": "US", "kyc_status": "pending", "risk_score": 0.75},
        {"id": "C_sarah", "name": "Sarah Lee",    "country": "US", "kyc_status": "pending", "risk_score": 0.70},
        {"id": "C_mike",  "name": "Mike Torres",  "country": "US", "kyc_status": "pending", "risk_score": 0.65},
        {"id": "C_lisa",  "name": "Lisa Wong",    "country": "US", "kyc_status": "pending", "risk_score": 0.60},
    ]
    mule_accounts = [
        {"id": "A_john1",  "status": "active", "risk_score": 0.75, "bank_name": "Quick Bank"},
        {"id": "A_sarah1", "status": "active", "risk_score": 0.70, "bank_name": "Quick Bank"},
        {"id": "A_mike1",  "status": "active", "risk_score": 0.65, "bank_name": "Quick Bank"},
        {"id": "A_lisa1",  "status": "active", "risk_score": 0.60, "bank_name": "Quick Bank"},
    ]

    # ------------------------------------------------------------------
    # Scenario 3 – Circular Flow (3 members)
    # ------------------------------------------------------------------
    circ_customers = [
        {"id": "C_omar",  "name": "Omar Hassan",   "country": "EG", "kyc_status": "pending", "risk_score": 0.65},
        {"id": "C_diana", "name": "Diana Prince",  "country": "GR", "kyc_status": "pending", "risk_score": 0.60},
        {"id": "C_felix", "name": "Felix Wagner",  "country": "DE", "kyc_status": "pending", "risk_score": 0.55},
    ]
    circ_accounts = [
        {"id": "A_omar1",  "status": "active", "risk_score": 0.65, "bank_name": "Euro Bank"},
        {"id": "A_diana1", "status": "active", "risk_score": 0.60, "bank_name": "Euro Bank"},
        {"id": "A_felix1", "status": "active", "risk_score": 0.55, "bank_name": "Euro Bank"},
    ]

    # ------------------------------------------------------------------
    # Scenario 4 – Decoy Family (3 members — legitimate)
    # ------------------------------------------------------------------
    family_customers = [
        {"id": "C_raj",    "name": "Raj Sharma",    "country": "IN", "kyc_status": "verified", "risk_score": 0.10},
        {"id": "C_meera",  "name": "Meera Sharma",  "country": "IN", "kyc_status": "verified", "risk_score": 0.08},
        {"id": "C_aditya", "name": "Aditya Sharma", "country": "IN", "kyc_status": "verified", "risk_score": 0.12},
    ]
    family_accounts = [
        {"id": "A_raj1",    "status": "active", "risk_score": 0.10, "bank_name": "City National"},
        {"id": "A_meera1",  "status": "active", "risk_score": 0.08, "bank_name": "City National"},
        {"id": "A_aditya1", "status": "active", "risk_score": 0.12, "bank_name": "City National"},
    ]

    # ------------------------------------------------------------------
    # Scenario 5 – Bridge / Kingpin (1 member)
    # ------------------------------------------------------------------
    kingpin_customers = [
        {"id": "C_kingpin", "name": "Victor Krane", "country": "XX", "kyc_status": "pending", "risk_score": 0.50},
    ]
    kingpin_accounts = [
        {"id": "A_kingpin1", "status": "active", "risk_score": 0.50, "bank_name": "Offshore Holdings"},
    ]

    # Cashout sink account (no customer owner — represents external cash-out)
    sink_accounts = [
        {"id": "A_cashout_sink", "status": "active", "risk_score": 0.95, "bank_name": "CashOut Express"},
    ]

    all_customers = (
        ring_customers + mule_customers + circ_customers
        + family_customers + kingpin_customers
    )
    all_accounts = (
        ring_accounts + mule_accounts + circ_accounts
        + family_accounts + kingpin_accounts + sink_accounts
    )
    cust_account_pairs = list(zip(
        [c["id"] for c in ring_customers],
        [a["id"] for a in ring_accounts],
    )) + list(zip(
        [c["id"] for c in mule_customers],
        [a["id"] for a in mule_accounts],
    )) + list(zip(
        [c["id"] for c in circ_customers],
        [a["id"] for a in circ_accounts],
    )) + list(zip(
        [c["id"] for c in family_customers],
        [a["id"] for a in family_accounts],
    )) + list(zip(
        [c["id"] for c in kingpin_customers],
        [a["id"] for a in kingpin_accounts],
    ))

    for c in all_customers:
        graph.query(
            "CREATE (:Customer {id:$id, name:$name, country:$country, "
            "kyc_status:$kyc_status, risk_score:$risk_score})",
            c,
        )
    print(f"[seed] Created {len(all_customers)} customers.")

    for a in all_accounts:
        graph.query(
            "CREATE (:Account {id:$id, status:$status, risk_score:$risk_score, "
            "bank_name:$bank_name})",
            a,
        )
    print(f"[seed] Created {len(all_accounts)} accounts.")

    for cid, aid in cust_account_pairs:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (a:Account {id:$aid}) "
            "CREATE (c)-[:OWNS]->(a)",
            {"cid": cid, "aid": aid},
        )
    print(f"[seed] Created {len(cust_account_pairs)} OWNS relationships.")

    return all_customers, all_accounts


# ---------------------------------------------------------------------------
# Bridge Nodes: Device, Address, IP, Phone, Merchant
# ---------------------------------------------------------------------------

def create_bridge_nodes(graph):
    devices = [
        {"id": "D_ring1",   "fingerprint": "fp_ring1",   "device_type": "mobile",  "os": "Android 13"},
        {"id": "D_ring2",   "fingerprint": "fp_ring2",   "device_type": "tablet",  "os": "iPadOS 17"},
        {"id": "D_family1", "fingerprint": "fp_family1", "device_type": "desktop", "os": "Windows 11"},
    ]
    for d in devices:
        graph.query(
            "CREATE (:Device {id:$id, fingerprint:$fingerprint, "
            "device_type:$device_type, os:$os})",
            d,
        )
    print(f"[seed] Created {len(devices)} devices.")

    addresses = [
        {"id": "ADDR_ring1",   "street": "123 Phantom Lane", "city": "Unknown", "country": "XX"},
        {"id": "ADDR_family1", "street": "45 Oak Street",    "city": "Mumbai",  "country": "IN"},
    ]
    for a in addresses:
        graph.query(
            "CREATE (:Address {id:$id, street:$street, city:$city, country:$country})",
            a,
        )
    print(f"[seed] Created {len(addresses)} addresses.")

    ips = [
        {"id": "IP_kunal",  "address": "10.0.1.1"},
        {"id": "IP_aryan",  "address": "10.0.1.2"},
        {"id": "IP_ifrah",  "address": "10.0.1.3"},
        {"id": "IP_priya",  "address": "10.0.1.4"},
        {"id": "IP_hassan", "address": "10.0.1.5"},
        {"id": "IP_nina",   "address": "10.0.1.6"},
        {"id": "IP_john",   "address": "10.0.2.1"},
        {"id": "IP_sarah",  "address": "10.0.2.2"},
        {"id": "IP_mike",   "address": "10.0.2.3"},
        {"id": "IP_lisa",   "address": "10.0.2.4"},
        {"id": "IP_omar",   "address": "10.0.3.1"},
        {"id": "IP_diana",  "address": "10.0.3.2"},
        {"id": "IP_felix",  "address": "10.0.3.3"},
        {"id": "IP_raj",    "address": "192.168.1.10"},
        {"id": "IP_meera",  "address": "192.168.1.11"},
        {"id": "IP_aditya", "address": "192.168.1.12"},
        {"id": "IP_kingpin","address": "172.16.0.1"},
        {"id": "IP_riya",   "address": "10.0.1.7"},
        {"id": "IP_dev",    "address": "10.0.1.8"},
    ]
    for ip in ips:
        graph.query("CREATE (:IP {id:$id, address:$address})", ip)
    print(f"[seed] Created {len(ips)} IP nodes.")

    phones = [
        {"id": "PH_kunal",  "number": "+91-9000000001"},
        {"id": "PH_aryan",  "number": "+91-9000000002"},
        {"id": "PH_ifrah",  "number": "+92-3000000001"},
        {"id": "PH_priya",  "number": "+91-9000000003"},
        {"id": "PH_hassan", "number": "+971-500000001"},
        {"id": "PH_nina",   "number": "+39-3000000001"},
        {"id": "PH_john",   "number": "+1-5550000001"},
        {"id": "PH_sarah",  "number": "+1-5550000002"},
        {"id": "PH_mike",   "number": "+1-5550000003"},
        {"id": "PH_lisa",   "number": "+1-5550000004"},
        {"id": "PH_omar",   "number": "+20-1000000001"},
        {"id": "PH_diana",  "number": "+30-6900000001"},
        {"id": "PH_felix",  "number": "+49-1700000001"},
        {"id": "PH_raj",    "number": "+91-9100000001"},
        {"id": "PH_meera",  "number": "+91-9100000002"},
        {"id": "PH_aditya", "number": "+91-9100000003"},
        {"id": "PH_kingpin","number": "+00-0000000000"},
        {"id": "PH_riya",   "number": "+91-9000000007"},
        {"id": "PH_dev",    "number": "+91-9000000008"},
    ]
    for ph in phones:
        graph.query("CREATE (:Phone {id:$id, number:$number})", ph)
    print(f"[seed] Created {len(phones)} phone nodes.")

    merchants = [
        {"id": "M_cashout", "name": "CashOut Express", "category": "money_transfer", "risk_score": 0.90},
        {"id": "M_retail",  "name": "FreshMart",        "category": "retail",         "risk_score": 0.05},
    ]
    for m in merchants:
        graph.query(
            "CREATE (:Merchant {id:$id, name:$name, category:$category, risk_score:$risk_score})",
            m,
        )
    print(f"[seed] Created {len(merchants)} merchants.")


# ---------------------------------------------------------------------------
# Transactions (all ts fields are integers)
# ---------------------------------------------------------------------------

def create_ring_transactions(graph):
    txns = [
        {"id": "T_ring1", "amount": 9500, "ts": 1728000000, "status": "flagged", "risk_score": 0.92},
        {"id": "T_ring2", "amount": 8800, "ts": 1728003600, "status": "flagged", "risk_score": 0.90},
        {"id": "T_ring3", "amount": 8200, "ts": 1728007200, "status": "flagged", "risk_score": 0.88},
        {"id": "T_ring4", "amount": 7600, "ts": 1728010800, "status": "flagged", "risk_score": 0.86},
        {"id": "T_ring5", "amount": 7000, "ts": 1728014400, "status": "flagged", "risk_score": 0.85},
        # Associates feeding into the ring
        {"id": "T_ring6", "amount": 6500, "ts": 1728016200, "status": "flagged", "risk_score": 0.80},
        {"id": "T_ring7", "amount": 6200, "ts": 1728018000, "status": "flagged", "risk_score": 0.77},
    ]
    for t in txns:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, ts:$ts, "
            "status:$status, risk_score:$risk_score})",
            t,
        )
    # SENT ... TO edges carry amount + ts
    edges = [
        ("A_kunal1",  "T_ring1", "A_aryan1",  9500, 1728000000),
        ("A_aryan1",  "T_ring2", "A_ifrah1",  8800, 1728003600),
        ("A_ifrah1",  "T_ring3", "A_priya1",  8200, 1728007200),
        ("A_priya1",  "T_ring4", "A_hassan1", 7600, 1728010800),
        ("A_hassan1", "T_ring5", "A_nina1",   7000, 1728014400),
        # Associates connect into the ring via nina's account
        ("A_riya1",   "T_ring6", "A_nina1",   6500, 1728016200),
        ("A_dev1",    "T_ring7", "A_kunal1",  6200, 1728018000),
    ]
    for src, tid, dst, amt, ts in edges:
        graph.query(
            "MATCH (s:Account {id:$src}), "
            "(t:Transaction {id:$tid}), "
            "(d:Account {id:$dst}) "
            "CREATE (s)-[:SENT {amount:$amt, ts:$ts}]->(t)-[:TO]->(d)",
            {"src": src, "tid": tid, "dst": dst, "amt": amt, "ts": ts},
        )
    # Alert
    graph.query(
        "CREATE (:Alert {id:'AL_ring_alert', type:'structuring', severity:'high', "
        "triggered_at:1728000000})"
    )
    graph.query(
        "MATCH (al:Alert {id:'AL_ring_alert'}), (t:Transaction {id:'T_ring1'}) "
        "CREATE (al)-[:TRIGGERED_BY]->(t)"
    )
    print("[seed] Created ring transactions + alert.")


def create_mule_transactions(graph):
    txns = [
        {"id": "T_mule1", "amount": 10000, "ts": 1728000000, "status": "flagged", "risk_score": 0.88},
        {"id": "T_mule2", "amount":  9200, "ts": 1728001800, "status": "flagged", "risk_score": 0.84},
        {"id": "T_mule3", "amount":  8500, "ts": 1728003600, "status": "flagged", "risk_score": 0.80},
        {"id": "T_mule4", "amount":  8000, "ts": 1728005400, "status": "flagged", "risk_score": 0.78},
    ]
    for t in txns:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, ts:$ts, "
            "status:$status, risk_score:$risk_score})",
            t,
        )
    chain = [
        ("A_john1",  "T_mule1", "A_sarah1",       10000, 1728000000),
        ("A_sarah1", "T_mule2", "A_mike1",          9200, 1728001800),
        ("A_mike1",  "T_mule3", "A_lisa1",          8500, 1728003600),
        ("A_lisa1",  "T_mule4", "A_cashout_sink",   8000, 1728005400),
    ]
    for src, tid, dst, amt, ts in chain:
        graph.query(
            "MATCH (s:Account {id:$src}), "
            "(t:Transaction {id:$tid}), "
            "(d:Account {id:$dst}) "
            "CREATE (s)-[:SENT {amount:$amt, ts:$ts}]->(t)-[:TO]->(d)",
            {"src": src, "tid": tid, "dst": dst, "amt": amt, "ts": ts},
        )
    # T_mule4 also connects to merchant
    graph.query(
        "MATCH (t:Transaction {id:'T_mule4'}), (m:Merchant {id:'M_cashout'}) "
        "CREATE (t)-[:AT]->(m)"
    )
    # Alert
    graph.query(
        "CREATE (:Alert {id:'AL_mule_alert', type:'rapid_layering', severity:'high', "
        "triggered_at:1728000000})"
    )
    graph.query(
        "MATCH (al:Alert {id:'AL_mule_alert'}), (t:Transaction {id:'T_mule1'}) "
        "CREATE (al)-[:TRIGGERED_BY]->(t)"
    )
    print("[seed] Created mule-chain transactions + alert.")


def create_circular_transactions(graph):
    txns = [
        {"id": "T_circ1", "amount": 5000, "ts": 1728100000, "status": "flagged", "risk_score": 0.75},
        {"id": "T_circ2", "amount": 4800, "ts": 1728103600, "status": "flagged", "risk_score": 0.73},
        {"id": "T_circ3", "amount": 4600, "ts": 1728107200, "status": "flagged", "risk_score": 0.71},
    ]
    for t in txns:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, ts:$ts, "
            "status:$status, risk_score:$risk_score})",
            t,
        )
    cycle = [
        ("A_omar1",  "T_circ1", "A_diana1", 5000, 1728100000),
        ("A_diana1", "T_circ2", "A_felix1", 4800, 1728103600),
        ("A_felix1", "T_circ3", "A_omar1",  4600, 1728107200),  # closes the cycle
    ]
    for src, tid, dst, amt, ts in cycle:
        graph.query(
            "MATCH (s:Account {id:$src}), "
            "(t:Transaction {id:$tid}), "
            "(d:Account {id:$dst}) "
            "CREATE (s)-[:SENT {amount:$amt, ts:$ts}]->(t)-[:TO]->(d)",
            {"src": src, "tid": tid, "dst": dst, "amt": amt, "ts": ts},
        )
    # Alert
    graph.query(
        "CREATE (:Alert {id:'AL_circ_alert', type:'circular_flow', severity:'medium', "
        "triggered_at:1728107200})"
    )
    graph.query(
        "MATCH (al:Alert {id:'AL_circ_alert'}), (t:Transaction {id:'T_circ3'}) "
        "CREATE (al)-[:TRIGGERED_BY]->(t)"
    )
    print("[seed] Created circular-flow transactions + alert.")


def create_decoy_transactions(graph):
    decoy_txns = [
        {"id": "T_decoy1", "amount": 250, "ts": 1728000000, "status": "normal", "risk_score": 0.04},
        {"id": "T_decoy2", "amount": 120, "ts": 1728086400, "status": "normal", "risk_score": 0.03},
        {"id": "T_decoy3", "amount": 500, "ts": 1728172800, "status": "normal", "risk_score": 0.05},
        {"id": "T_decoy4", "amount":  80, "ts": 1728259200, "status": "normal", "risk_score": 0.02},
        {"id": "T_decoy5", "amount": 350, "ts": 1728345600, "status": "normal", "risk_score": 0.04},
    ]
    for t in decoy_txns:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, ts:$ts, "
            "status:$status, risk_score:$risk_score})",
            t,
        )
    edges = [
        ("A_raj1",    "T_decoy1", "A_meera1",  250, 1728000000),
        ("A_meera1",  "T_decoy2", "A_aditya1", 120, 1728086400),
        ("A_raj1",    "T_decoy3", "A_aditya1", 500, 1728172800),
        ("A_aditya1", "T_decoy4", "A_raj1",     80, 1728259200),
        ("A_meera1",  "T_decoy5", "A_raj1",    350, 1728345600),
    ]
    for src, tid, dst, amt, ts in edges:
        graph.query(
            "MATCH (s:Account {id:$src}), "
            "(t:Transaction {id:$tid}), "
            "(d:Account {id:$dst}) "
            "CREATE (s)-[:SENT {amount:$amt, ts:$ts}]->(t)-[:TO]->(d)",
            {"src": src, "tid": tid, "dst": dst, "amt": amt, "ts": ts},
        )
    # No alerts — this cluster should be cleared as a decoy
    print("[seed] Created decoy family transactions (no alerts).")


def create_bridge_transactions(graph):
    txns = [
        {"id": "T_bridge1", "amount": 15000, "ts": 1728020000, "status": "flagged", "risk_score": 0.91},
        {"id": "T_bridge2", "amount": 12000, "ts": 1728006000, "status": "flagged", "risk_score": 0.89},
    ]
    for t in txns:
        graph.query(
            "CREATE (:Transaction {id:$id, amount:$amount, ts:$ts, "
            "status:$status, risk_score:$risk_score})",
            t,
        )
    edges = [
        # ring → kingpin
        ("A_nina1",  "T_bridge1", "A_kingpin1", 15000, 1728020000),
        # mule chain → kingpin
        ("A_john1",  "T_bridge2", "A_kingpin1", 12000, 1728006000),
    ]
    for src, tid, dst, amt, ts in edges:
        graph.query(
            "MATCH (s:Account {id:$src}), "
            "(t:Transaction {id:$tid}), "
            "(d:Account {id:$dst}) "
            "CREATE (s)-[:SENT {amount:$amt, ts:$ts}]->(t)-[:TO]->(d)",
            {"src": src, "tid": tid, "dst": dst, "amt": amt, "ts": ts},
        )
    print("[seed] Created bridge transactions (ring + mule → kingpin).")


# ---------------------------------------------------------------------------
# Customer ↔ Bridge-node relationships
# ---------------------------------------------------------------------------

def create_customer_relationships(graph):
    # USED_DEVICE — ring half 1 → D_ring1, ring half 2 → D_ring2
    used_device = [
        ("C_kunal",  "D_ring1", 1727500000, 1728020000),
        ("C_aryan",  "D_ring1", 1727510000, 1728015000),
        ("C_ifrah",  "D_ring1", 1727520000, 1728010000),
        ("C_priya",  "D_ring2", 1727500000, 1728020000),
        ("C_hassan", "D_ring2", 1727510000, 1728015000),
        ("C_nina",   "D_ring2", 1727520000, 1728010000),
        # Two new ring associates also use D_ring2
        ("C_riya",   "D_ring2", 1727530000, 1728005000),
        ("C_dev",    "D_ring2", 1727540000, 1728000000),
        # Decoy family shares one home desktop — legitimate
        ("C_raj",    "D_family1", 1720000000, 1728350000),
        ("C_meera",  "D_family1", 1720100000, 1728340000),
        ("C_aditya", "D_family1", 1720200000, 1728330000),
    ]
    for cid, did, fs, ls in used_device:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (d:Device {id:$did}) "
            "CREATE (c)-[:USED_DEVICE {first_seen:$fs, last_seen:$ls}]->(d)",
            {"cid": cid, "did": did, "fs": fs, "ls": ls},
        )
    print(f"[seed] Created {len(used_device)} USED_DEVICE relationships.")

    # LIVES_AT — ring members share ADDR_ring1; family shares ADDR_family1
    lives_at = [
        ("C_kunal",  "ADDR_ring1"),
        ("C_aryan",  "ADDR_ring1"),
        ("C_ifrah",  "ADDR_ring1"),
        ("C_priya",  "ADDR_ring1"),
        ("C_hassan", "ADDR_ring1"),
        ("C_nina",   "ADDR_ring1"),
        ("C_riya",   "ADDR_ring1"),
        ("C_dev",    "ADDR_ring1"),
        ("C_raj",    "ADDR_family1"),
        ("C_meera",  "ADDR_family1"),
        ("C_aditya", "ADDR_family1"),
    ]
    for cid, aid in lives_at:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (a:Address {id:$aid}) "
            "CREATE (c)-[:LIVES_AT]->(a)",
            {"cid": cid, "aid": aid},
        )
    print(f"[seed] Created {len(lives_at)} LIVES_AT relationships.")

    # LOGGED_IN_FROM — each customer → their own IP
    logged_in = [
        ("C_kunal",   "IP_kunal"),
        ("C_aryan",   "IP_aryan"),
        ("C_ifrah",   "IP_ifrah"),
        ("C_priya",   "IP_priya"),
        ("C_hassan",  "IP_hassan"),
        ("C_nina",    "IP_nina"),
        ("C_john",    "IP_john"),
        ("C_sarah",   "IP_sarah"),
        ("C_mike",    "IP_mike"),
        ("C_lisa",    "IP_lisa"),
        ("C_omar",    "IP_omar"),
        ("C_diana",   "IP_diana"),
        ("C_felix",   "IP_felix"),
        ("C_raj",     "IP_raj"),
        ("C_meera",   "IP_meera"),
        ("C_aditya",  "IP_aditya"),
        ("C_kingpin", "IP_kingpin"),
        ("C_riya",    "IP_riya"),
        ("C_dev",     "IP_dev"),
    ]
    for cid, ipid in logged_in:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (ip:IP {id:$ipid}) "
            "CREATE (c)-[:LOGGED_IN_FROM {ts:1728000000}]->(ip)",
            {"cid": cid, "ipid": ipid},
        )
    print(f"[seed] Created {len(logged_in)} LOGGED_IN_FROM relationships.")

    # HAS_PHONE — each customer → their Phone node
    has_phone = [
        ("C_kunal",   "PH_kunal"),
        ("C_aryan",   "PH_aryan"),
        ("C_ifrah",   "PH_ifrah"),
        ("C_priya",   "PH_priya"),
        ("C_hassan",  "PH_hassan"),
        ("C_nina",    "PH_nina"),
        ("C_john",    "PH_john"),
        ("C_sarah",   "PH_sarah"),
        ("C_mike",    "PH_mike"),
        ("C_lisa",    "PH_lisa"),
        ("C_omar",    "PH_omar"),
        ("C_diana",   "PH_diana"),
        ("C_felix",   "PH_felix"),
        ("C_raj",     "PH_raj"),
        ("C_meera",   "PH_meera"),
        ("C_aditya",  "PH_aditya"),
        ("C_kingpin", "PH_kingpin"),
        ("C_riya",    "PH_riya"),
        ("C_dev",     "PH_dev"),
    ]
    for cid, phid in has_phone:
        graph.query(
            "MATCH (c:Customer {id:$cid}), (ph:Phone {id:$phid}) "
            "CREATE (c)-[:HAS_PHONE]->(ph)",
            {"cid": cid, "phid": phid},
        )
    print(f"[seed] Created {len(has_phone)} HAS_PHONE relationships.")


# ---------------------------------------------------------------------------
# Agent / Audit Layer: Cases, Evidence, Decisions, Actions
# ---------------------------------------------------------------------------

def create_cases_and_decisions(graph):
    # ---- CASE_001: Fraud Ring ----
    graph.query(
        "CREATE (:Case {id:'CASE_001', status:'open', opened_at:1728000000, "
        "summary:'Suspected fraud ring via shared devices and address'})"
    )
    graph.query(
        "MATCH (ca:Case {id:'CASE_001'}), (al:Alert {id:'AL_ring_alert'}) "
        "CREATE (ca)-[:CONTAINS]->(al)"
    )
    graph.query(
        "CREATE (:Evidence {id:'EV_001', kind:'graph_path', "
        "summary:'8 customers share 2 devices and 1 address', "
        "entities:'C_kunal,C_aryan,C_ifrah,C_priya,C_hassan,C_nina,C_riya,C_dev,D_ring1,D_ring2,ADDR_ring1', "
        "payload:'{}'})"
    )
    graph.query(
        "MATCH (ca:Case {id:'CASE_001'}), (ev:Evidence {id:'EV_001'}) "
        "CREATE (ca)-[:HAS_EVIDENCE]->(ev)"
    )
    graph.query(
        "CREATE (:Decision {id:'DEC_001', verdict:'flag', confidence:0.85, "
        "rationale:'Shared device fingerprints across 8 unrelated customers', "
        "created_at:1728050000})"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_001'}), (ca:Case {id:'CASE_001'}) "
        "CREATE (dec)-[:ABOUT]->(ca)"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_001'}), (ev:Evidence {id:'EV_001'}) "
        "CREATE (dec)-[:EVIDENCED_BY]->(ev)"
    )
    graph.query(
        "CREATE (:Action {id:'ACT_001', type:'open_case', dry_run:false, "
        "reason:'Ring detected via shared device fingerprints', ts:1728050000})"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_001'}), (act:Action {id:'ACT_001'}) "
        "CREATE (dec)-[:LED_TO]->(act)"
    )
    graph.query(
        "MATCH (act:Action {id:'ACT_001'}), (a:Account {id:'A_kunal1'}) "
        "CREATE (act)-[:TARGETS]->(a)"
    )

    # ---- CASE_002: Mule Chain ----
    graph.query(
        "CREATE (:Case {id:'CASE_002', status:'open', opened_at:1728005400, "
        "summary:'Suspected mule chain: rapid pass-through A_john1 → A_cashout_sink'})"
    )
    graph.query(
        "MATCH (ca:Case {id:'CASE_002'}), (al:Alert {id:'AL_mule_alert'}) "
        "CREATE (ca)-[:CONTAINS]->(al)"
    )
    graph.query(
        "CREATE (:Evidence {id:'EV_002', kind:'temporal_path', "
        "summary:'4-hop chain from A_john1 to cash-out in under 2 hours, decreasing amounts', "
        "entities:'C_john,A_john1,A_sarah1,A_mike1,A_lisa1,A_cashout_sink,M_cashout', "
        "payload:'{}'})"
    )
    graph.query(
        "MATCH (ca:Case {id:'CASE_002'}), (ev:Evidence {id:'EV_002'}) "
        "CREATE (ca)-[:HAS_EVIDENCE]->(ev)"
    )
    graph.query(
        "CREATE (:Decision {id:'DEC_002', verdict:'flag', confidence:0.80, "
        "rationale:'Rapid layering with decreasing amounts ending at high-risk merchant', "
        "created_at:1728010000})"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_002'}), (ca:Case {id:'CASE_002'}) "
        "CREATE (dec)-[:ABOUT]->(ca)"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_002'}), (ev:Evidence {id:'EV_002'}) "
        "CREATE (dec)-[:EVIDENCED_BY]->(ev)"
    )
    graph.query(
        "CREATE (:Action {id:'ACT_002', type:'freeze_account', dry_run:true, "
        "reason:'Mule chain detected — dry-run freeze pending review', ts:1728010000})"
    )
    graph.query(
        "MATCH (dec:Decision {id:'DEC_002'}), (act:Action {id:'ACT_002'}) "
        "CREATE (dec)-[:LED_TO]->(act)"
    )
    graph.query(
        "MATCH (act:Action {id:'ACT_002'}), (a:Account {id:'A_john1'}) "
        "CREATE (act)-[:TARGETS]->(a)"
    )

    print("[seed] Created 2 cases, 2 evidence nodes, 2 decisions, 2 actions.")


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

def print_summary(graph):
    labels = [
        "Customer", "Account", "Transaction", "Device", "Address",
        "IP", "Phone", "Merchant", "Alert", "Case", "Evidence",
        "Decision", "Action",
    ]
    print()
    print("=" * 60)
    print("Seed complete — node counts by label:")
    for label in labels:
        result = graph.query(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        cnt = result.result_set[0][0] if result.result_set else 0
        print(f"  {label:<15} {cnt:>4}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(f"[seed] Connecting to FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT} ...")
    graph = connect()

    print("[seed] Creating indexes ...")
    create_indexes(graph)

    print("[seed] Creating customers and accounts ...")
    create_customers_and_accounts(graph)

    print("[seed] Creating bridge nodes (devices, addresses, IPs, phones, merchants) ...")
    create_bridge_nodes(graph)

    print("[seed] Creating Scenario 1 — Fraud Ring transactions ...")
    create_ring_transactions(graph)

    print("[seed] Creating Scenario 2 — Mule Chain transactions ...")
    create_mule_transactions(graph)

    print("[seed] Creating Scenario 3 — Circular Flow transactions ...")
    create_circular_transactions(graph)

    print("[seed] Creating Scenario 4 — Decoy Family transactions ...")
    create_decoy_transactions(graph)

    print("[seed] Creating Scenario 5 — Bridge/Kingpin transactions ...")
    create_bridge_transactions(graph)

    print("[seed] Creating customer → bridge-node relationships ...")
    create_customer_relationships(graph)

    print("[seed] Creating agent/audit layer (cases, evidence, decisions, actions) ...")
    create_cases_and_decisions(graph)

    print_summary(graph)
