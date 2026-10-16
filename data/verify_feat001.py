import falkordb

g = falkordb.FalkorDB().select_graph('fraud_investigation')

checks = [
    ("C_kunal name contains Kunal",
     "MATCH (c:Customer {id:'C_kunal'}) RETURN c.name",
     lambda r: r and 'Kunal' in r[0][0]),

    ("C_raj risk_score <= 0.15",
     "MATCH (c:Customer {id:'C_raj'}) RETURN c.risk_score",
     lambda r: r and r[0][0] <= 0.15),

    ("C_raj LIVES_AT ADDR_family1",
     "MATCH (c:Customer {id:'C_raj'})-[:LIVES_AT]->(a:Address {id:'ADDR_family1'}) RETURN a.id",
     lambda r: len(r) > 0),

    ("T_bridge1 amount == 15000",
     "MATCH (t:Transaction {id:'T_bridge1'}) RETURN t.amount",
     lambda r: r and r[0][0] == 15000),

    ("CASE_001 contains at least 1 Alert",
     "MATCH (ca:Case {id:'CASE_001'})-[:CONTAINS]->(al:Alert) RETURN al.id",
     lambda r: len(r) >= 1),

    ("T_ring1 ts is integer",
     "MATCH (t:Transaction {id:'T_ring1'}) RETURN t.ts",
     lambda r: r and isinstance(r[0][0], int)),
]

all_pass = True
for desc, query, check in checks:
    result = g.query(query)
    rs = result.result_set
    passed = check(rs)
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"[{status}] {desc} => {rs}")

print()
if all_pass:
    print("All acceptance criteria passed.")
else:
    print("SOME CHECKS FAILED — see above.")
