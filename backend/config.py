from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FALKORDB_HOST = os.environ.get("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.environ.get("FALKORDB_PORT", "6379"))
GRAPH_NAME = os.environ.get("GRAPH_NAME", "fraud_investigation")
