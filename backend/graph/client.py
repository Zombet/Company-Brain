import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import falkordb
from config import FALKORDB_HOST, FALKORDB_PORT, GRAPH_NAME

_client = None
_graph = None


def get_graph():
    """Return the FalkorDB graph handle, reconnecting if the connection was lost."""
    global _client, _graph
    if _graph is None:
        _connect()
        return _graph

    # Ping to verify the connection is still alive; reconnect on failure.
    try:
        _graph.query("RETURN 1")
    except Exception:
        _connect()

    return _graph


def _connect():
    global _client, _graph
    _client = falkordb.FalkorDB(host=FALKORDB_HOST, port=int(FALKORDB_PORT))
    _graph = _client.select_graph(GRAPH_NAME)
