import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import falkordb
from config import FALKORDB_HOST, FALKORDB_PORT, GRAPH_NAME

_client = None
_graph = None


def get_graph():
    global _client, _graph
    if _graph is None:
        _client = falkordb.FalkorDB(host=FALKORDB_HOST, port=int(FALKORDB_PORT))
        _graph = _client.select_graph(GRAPH_NAME)
    return _graph
