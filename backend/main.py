import os
import re
import hashlib
import json
import time
import csv
import io
import urllib.request
import urllib.parse
import asyncio
import concurrent.futures
import threading
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
import psycopg2
import networkx as nx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import fitz

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    print("Warning: Camelot not available. PDF table extraction disabled.")

load_dotenv()

app = FastAPI(title="Evidencly API", version="0.3")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,https://evidencly.com,https://www.evidencly.com").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# ---------- Models ----------
class SearchRequest(BaseModel):
    wallet_address: str
    depth: int = 3

class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    cross_case_count: int = 0
    ingestion_id: str = ""

class NarrativeRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class InvestigationCreate(BaseModel):
    name: str
    starting_address: str

class InvestigationUpdate(BaseModel):
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    notes: Optional[Dict[str, str]] = None
    narrative: Optional[str] = None

class IngestionStatus(BaseModel):
    status: str
    sources_complete: List[str]
    sources_pending: List[str]
    node_count: int
    edge_count: int
    cross_case_count: int

# ---------- Helper Functions ----------
def extract_addresses_from_pdf(file_bytes: bytes) -> List[str]:
    addresses = set()
    temp_pdf = "/tmp/temp_pdf.pdf"
    with open(temp_pdf, "wb") as f:
        f.write(file_bytes)
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    addresses.update(re.findall(r"0x[a-fA-F0-9]{40}", text))
    if CAMELOT_AVAILABLE:
        try:
            tables = camelot.read_pdf(temp_pdf, pages="all", flavor="lattice")
            for table in tables:
                df = table.df
                for cell in df.values.flatten():
                    addresses.update(re.findall(r"0x[a-fA-F0-9]{40}", str(cell)))
        except Exception as e:
            print("Camelot extraction failed: " + str(e))
    try:
        os.remove(temp_pdf)
    except:
        pass
    return list(addresses)

def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def calculate_confidence(source_type: str) -> float:
    mapping = {
        "DOJ_FBI": 0.95,
        "Court_Document": 0.85,
        "ZachXBT": 0.70,
        "News": 0.50,
        "Community_OSINT": 0.40,
        "Etherscan": 0.60,
        "Twitter": 0.55,
        "WebSearch": 0.45,
        "Breadcrumbs": 0.65
    }
    return mapping.get(source_type, 0.30)

def add_node_if_not_exists(address: str, conn, confidence=0.6, source_type="Etherscan", node_type="Wallet", entity_subtype="Wallet") -> Optional[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM graph_nodes WHERE address = %s", (address.lower(),))
        existing = cur.fetchone()
        if existing:
            return existing["id"]
        cur.execute("""
            INSERT INTO graph_nodes (node_type, entity_subtype, address, label, confidence_score, source_type, metadata, ingestion_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (node_type, entity_subtype, address.lower(), None, confidence, source_type, "{}", "complete"))
        result = cur.fetchone()
        conn.commit()
        return result["id"] if result else None

def add_edge_if_not_exists(source_id: str, target_id: str, tx_hash: str, amount_eth: float, conn, edge_type="SENT_TO", evidence=None, block_timestamp=None) -> bool:
    evidence_json = json.dumps(evidence or [])
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO graph_edges (source_node_id, target_node_id, edge_type, tx_hash, amount_eth, evidence, block_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_node_id, target_node_id, edge_type) DO NOTHING
        """, (source_id, target_id, edge_type, tx_hash, amount_eth, evidence_json, block_timestamp))
        if cur.rowcount > 0:
            conn.commit()
            return True
    return False

def get_cross_case_count(address: str, conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT case_id) as count FROM case_addresses WHERE address = %s", (address.lower(),))
        result = cur.fetchone()
        return result["count"] if result else 0

def load_known_entities_from_github():
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as count FROM known_entities")
        count = cur.fetchone()["count"]
        if count >= 1000:
            conn.close()
            return
    try:
        url = "https://raw.githubusercontent.com/ethereum-lists/labels/master/labels.json"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            labels = response.json()
            with conn.cursor() as cur:
                for label in labels[:1000]:
                    address = label.get("address", "").lower()
                    name = label.get("name", "Unknown")
                    category = label.get("category", "Wallet")
                    if address:
                        cur.execute("""
                            INSERT INTO known_entities (address, label, entity_type, risk_level, source)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (address) DO NOTHING
                        """, (address, name, category, "Unknown", "Ethereum-Labels"))
                conn.commit()
            print("Imported " + str(len(labels[:1000])) + " known entities from GitHub")
    except Exception as e:
        print("Failed to import known entities: " + str(e))
    finally:
        conn.close()

# ---------- Threaded Ingestion Functions ----------
def fetch_etherscan(address: str, ingestion_id: str, results: dict):
    print("[ETHERSCAN] Thread started for " + address, flush=True)
    conn = get_db_conn()
    all_txs = {"txlist": [], "txlistinternal": [], "tokentx": []}
    for action in ["txlist", "txlistinternal", "tokentx"]:
        params = {"chainid": "1", "module": "account", "action": action, "address": address, "startblock": 0, "endblock": 99999999, "sort": "desc", "apikey": ETHERSCAN_API_KEY}
        url = "https://api.etherscan.io/v2/api?" + urllib.parse.urlencode(params)
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "1":
                    txs = data.get("result", [])
                    all_txs[action] = txs
                    print("[ETHERSCAN] " + action + " found " + str(len(txs)) + " txs", flush=True)
                else:
                    print("[ETHERSCAN] " + action + " error: " + str(data.get("message")), flush=True)
        except Exception as e:
            print("[ETHERSCAN] " + action + " exception: " + str(e), flush=True)
        time.sleep(0.25)

    node_id = add_node_if_not_exists(address, conn, confidence=0.6, source_type="Etherscan")
    if not node_id:
        print("[ETHERSCAN] Could not create node", flush=True)
        conn.close()
        results["etherscan"] = 0
        return

    count_edges = 0

    # Process normal txs with ETH value > 0.01
    for tx in all_txs["txlist"][:50]:
        to_addr = (tx.get("to") or "").lower()
        if not to_addr or to_addr == address.lower():
            continue
        value_eth = int(tx.get("value", 0)) / 1e18
        if value_eth < 0.01:
            continue
        target_id = add_node_if_not_exists(to_addr, conn, confidence=0.6, source_type="Etherscan")
        if target_id:
            ts = tx.get("timeStamp")
            bts = datetime.utcfromtimestamp(int(ts)) if ts else None
            if add_edge_if_not_exists(node_id, target_id, tx.get("hash", ""), value_eth, conn, "SENT_TO", block_timestamp=bts):
                count_edges += 1

    # Process internal txs with ETH value > 0.001
    for tx in all_txs["txlistinternal"][:50]:
        to_addr = (tx.get("to") or "").lower()
        if not to_addr or to_addr == address.lower():
            continue
        value_eth = int(tx.get("value", 0)) / 1e18
        if value_eth < 0.001:
            continue
        target_id = add_node_if_not_exists(to_addr, conn, confidence=0.6, source_type="Etherscan")
        if target_id:
            ts = tx.get("timeStamp")
            bts = datetime.utcfromtimestamp(int(ts)) if ts else None
            if add_edge_if_not_exists(node_id, target_id, tx.get("hash", ""), value_eth, conn, "SENT_TO", block_timestamp=bts):
                count_edges += 1

    # Process token transfers - any non-zero transfer
    for tx in all_txs["tokentx"][:100]:
        to_addr = (tx.get("to") or "").lower()
        if not to_addr or to_addr == address.lower():
            continue
        token_value = int(tx.get("value", 0))
        if token_value == 0:
            continue
        token_decimal = int(tx.get("tokenDecimal", 18))
        token_amount = token_value / (10 ** token_decimal)
        target_id = add_node_if_not_exists(to_addr, conn, confidence=0.6, source_type="Etherscan")
        if target_id:
            ts = tx.get("timeStamp")
            bts = datetime.utcfromtimestamp(int(ts)) if ts else None
            if add_edge_if_not_exists(node_id, target_id, tx.get("hash", ""), token_amount, conn, "SENT_TO", block_timestamp=bts):
                count_edges += 1

    print("[ETHERSCAN] Added " + str(count_edges) + " edges", flush=True)
    total = len(all_txs["txlist"]) + len(all_txs["txlistinternal"]) + len(all_txs["tokentx"])
    results["etherscan"] = total
    with conn.cursor() as cur:
        cur.execute("UPDATE graph_nodes SET ingestion_status = %s, ingestion_log = ingestion_log || %s WHERE address = %s", ("etherscan_complete", json.dumps([{"source": "etherscan", "count": total}]), address))
        conn.commit()
    conn.close()

def fetch_twitter(address: str, ingestion_id: str, results: dict):
    conn = get_db_conn()
    tweets = []
    try:
        brave_key = os.getenv("BRAVE_API_KEY", "")
        if brave_key:
            query = "site:twitter.com " + address
            headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": brave_key}
            resp = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": 5}, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("web", {}).get("results", []):
                    tweets.append({"url": result.get("url", ""), "text": result.get("title", ""), "date": result.get("page_age", ""), "author": "unknown"})
    except Exception as e:
        print("[TWITTER] Brave search error: " + str(e))
    node_id = add_node_if_not_exists(address, conn, confidence=0.55, source_type="Twitter")
    if node_id:
        for tweet in tweets:
            doc_id = add_node_if_not_exists("tweet_" + hashlib.md5(tweet["url"].encode()).hexdigest()[:16], conn, confidence=0.55, source_type="Twitter", node_type="Document", entity_subtype="SocialMedia")
            if doc_id:
                add_edge_if_not_exists(node_id, doc_id, None, 0, conn, "MENTIONED_IN", [tweet])
    results["twitter"] = len(tweets)
    print("[TWITTER] Found " + str(len(tweets)) + " results via Brave")
    with conn.cursor() as cur:
        cur.execute("UPDATE graph_nodes SET ingestion_status = %s, ingestion_log = ingestion_log || %s WHERE address = %s", ("twitter_complete", json.dumps([{"source": "twitter", "count": len(tweets)}]), address))
        conn.commit()
    conn.close()

def fetch_websearch(address: str, ingestion_id: str, results: dict):
    conn = get_db_conn()
    web_results = []
    try:
        brave_key = os.getenv("BRAVE_API_KEY", "")
        if brave_key:
            query = address + " hack OR exploit OR stolen OR scam OR Lazarus"
            headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": brave_key}
            resp = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": 10}, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("web", {}).get("results", []):
                    web_results.append({"title": result.get("title", ""), "url": result.get("url", ""), "description": result.get("description", "")})
                for result in data.get("news", {}).get("results", []):
                    web_results.append({"title": result.get("title", ""), "url": result.get("url", ""), "description": result.get("description", "")})
    except Exception as e:
        print("[WEBSEARCH] Brave search error: " + str(e))
    node_id = add_node_if_not_exists(address, conn, confidence=0.45, source_type="WebSearch")
    if node_id:
        for result in web_results:
            doc_id = add_node_if_not_exists("web_" + hashlib.md5(result["url"].encode()).hexdigest()[:16], conn, confidence=0.45, source_type="WebSearch", node_type="Document", entity_subtype="News")
            if doc_id:
                add_edge_if_not_exists(node_id, doc_id, None, 0, conn, "MENTIONED_IN", [result])
    results["websearch"] = len(web_results)
    print("[WEBSEARCH] Found " + str(len(web_results)) + " results via Brave")
    with conn.cursor() as cur:
        cur.execute("UPDATE graph_nodes SET ingestion_status = %s, ingestion_log = ingestion_log || %s WHERE address = %s", ("websearch_complete", json.dumps([{"source": "websearch", "count": len(web_results)}]), address))
        conn.commit()
    conn.close()

def fetch_breadcrumbs(address: str, ingestion_id: str, results: dict):
    conn = get_db_conn()
    entities = []
    try:
        url = "https://www.breadcrumbs.app/reports/" + address
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            labels_found = soup.find_all(class_="entity-label")
            for label in labels_found[:10]:
                entities.append(label.get_text(strip=True))
    except Exception as e:
        print("Breadcrumbs error: " + str(e))
    node_id = add_node_if_not_exists(address, conn, confidence=0.65, source_type="Breadcrumbs")
    if node_id and entities:
        with conn.cursor() as cur:
            cur.execute("UPDATE graph_nodes SET label = COALESCE(label, %s), entity_subtype = %s WHERE id = %s",
                       (entities[0][:100], "Sanctioned", node_id))
            conn.commit()
    results["breadcrumbs"] = len(entities)
    with conn.cursor() as cur:
        cur.execute("UPDATE graph_nodes SET ingestion_status = %s, ingestion_log = ingestion_log || %s WHERE address = %s",
                   ("breadcrumbs_complete", json.dumps([{"source": "breadcrumbs", "count": len(entities)}]), address))
        conn.commit()
    conn.close()

def fetch_networkx(address: str, ingestion_id: str, results: dict):
    conn = get_db_conn()
    try:
        G = nx.DiGraph()
        with conn.cursor() as cur:
            cur.execute("SELECT source_node_id, target_node_id FROM graph_edges LIMIT 10000")
            edges = cur.fetchall()
            for edge in edges:
                G.add_edge(str(edge["source_node_id"]), str(edge["target_node_id"]))
        node_id = None
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM graph_nodes WHERE address = %s", (address,))
            node = cur.fetchone()
            if node:
                node_id = str(node["id"])
        cluster_size = 0
        if node_id and G.has_node(node_id):
            for component in nx.weakly_connected_components(G):
                if node_id in component:
                    cluster_size = len(component)
                    break
        results["networkx"] = cluster_size
        with conn.cursor() as cur:
            cur.execute("UPDATE graph_nodes SET ingestion_status = %s, ingestion_log = ingestion_log || %s WHERE address = %s",
                       ("networkx_complete", json.dumps([{"source": "networkx", "cluster_size": cluster_size}]), address))
            conn.commit()
    except Exception as e:
        print("NetworkX error: " + str(e))
        results["networkx"] = 0
    conn.close()

def run_parallel_ingestion(address: str, ingestion_id: str):
    print("[INGESTION] Starting parallel ingestion for " + address, flush=True)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_etherscan, address, ingestion_id, results): "etherscan",
            executor.submit(fetch_twitter, address, ingestion_id, results): "twitter",
            executor.submit(fetch_websearch, address, ingestion_id, results): "websearch",
            executor.submit(fetch_breadcrumbs, address, ingestion_id, results): "breadcrumbs",
            executor.submit(fetch_networkx, address, ingestion_id, results): "networkx"
        }
        concurrent.futures.wait(futures.keys())
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute("UPDATE graph_nodes SET ingestion_status = %s WHERE address = %s", ("complete", address))
        conn.commit()
    conn.close()

# ---------- Graph Traversal ----------
def traverse_graph(node_id: str, depth: int, conn) -> tuple:
    # Cap depth and results to prevent runaway queries
    depth = min(depth, 10)
    edge_limit = 750

    with conn.cursor() as cur:
        cur.execute("""
            WITH RECURSIVE graph_paths AS (
                -- Seed: all edges directly touching the seed node
                SELECT
                    source_node_id,
                    target_node_id,
                    edge_type,
                    tx_hash,
                    amount_eth,
                    evidence,
                    block_timestamp,
                    1 AS hop,
                    ARRAY[source_node_id] AS visited
                FROM graph_edges
                WHERE source_node_id = %s::uuid

                UNION

                SELECT
                    source_node_id,
                    target_node_id,
                    edge_type,
                    tx_hash,
                    amount_eth,
                    evidence,
                    block_timestamp,
                    1 AS hop,
                    ARRAY[target_node_id] AS visited
                FROM graph_edges
                WHERE target_node_id = %s::uuid

                UNION ALL

                -- Recursive: expand frontier one hop at a time
                SELECT
                    e.source_node_id,
                    e.target_node_id,
                    e.edge_type,
                    e.tx_hash,
                    e.amount_eth,
                    e.evidence,
                    e.block_timestamp,
                    gp.hop + 1,
                    gp.visited || CASE
                        WHEN e.source_node_id = ANY(gp.visited) THEN e.target_node_id
                        ELSE e.source_node_id
                    END
                FROM graph_edges e
                JOIN graph_paths gp ON (
                    e.source_node_id = gp.target_node_id
                    OR e.target_node_id = gp.source_node_id
                )
                WHERE gp.hop < %s
                  AND NOT e.source_node_id = ANY(gp.visited)
                  AND NOT e.target_node_id = ANY(gp.visited)
            )
            SELECT DISTINCT ON (source_node_id, target_node_id)
                source_node_id AS source_id,
                target_node_id AS target_id,
                edge_type,
                tx_hash,
                amount_eth,
                evidence,
                block_timestamp,
                MIN(hop) AS hop_level
            FROM graph_paths
            GROUP BY source_node_id, target_node_id, edge_type, tx_hash, amount_eth, evidence, block_timestamp
            ORDER BY source_node_id, target_node_id, MIN(hop)
            LIMIT %s
        """, (node_id, node_id, depth, edge_limit))
        edge_rows = cur.fetchall()

        node_ids = set()
        node_ids.add(node_id)
        for row in edge_rows:
            node_ids.add(str(row["source_id"]))
            node_ids.add(str(row["target_id"]))
        node_id_list = list(node_ids)

        cur.execute("""
            SELECT id, node_type, entity_subtype, address, label, confidence_score, source_type, metadata
            FROM graph_nodes
            WHERE id = ANY(%s::uuid[])
        """, (node_id_list,))
        node_rows = cur.fetchall()

    nodes = []
    for nr in node_rows:
        node = {
            "id": str(nr["id"]),
            "type": nr["node_type"],
            "entity_subtype": nr.get("entity_subtype", "Wallet"),
            "address": nr["address"],
            "label": nr["label"],
            "confidence": float(nr["confidence_score"]) if nr["confidence_score"] else 0.0,
            "source_type": nr["source_type"],
            "metadata": nr["metadata"] or {}
        }
        nodes.append(node)

    edges = []
    for row in edge_rows:
        edges.append({
            "source": str(row["source_id"]),
            "target": str(row["target_id"]),
            "type": row["edge_type"],
            "tx_hash": row["tx_hash"],
            "amount_eth": float(row["amount_eth"]) if row["amount_eth"] else None,
            "evidence": row["evidence"] if row["evidence"] else [],
            "block_timestamp": row["block_timestamp"].isoformat() if row["block_timestamp"] else None,
            "hop_level": row["hop_level"]
        })

    return nodes, edges

def enrich_node_from_known_entities(address: str, conn):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT label, entity_type, entity_subtype, risk_level, source, notes
                FROM known_entities WHERE address = %s
            """, (address.lower(),))
            row = cur.fetchone()
        if row:
            return {
                "label": row["label"],
                "entity_type": row["entity_type"],
                "entity_subtype": row["entity_subtype"],
                "risk_level": row["risk_level"],
                "source": row["source"],
                "notes": row["notes"]
            }
        return None
    except Exception as e:
        print(f"enrich_node error {address}: {e}")
        return None

@app.get("/api/known_entities")
async def get_known_entities():
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT address, label, entity_type, entity_subtype, risk_level, source, notes, created_at
            FROM known_entities ORDER BY risk_level DESC, entity_type, label
        """)
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/enrich_all")
async def enrich_all_nodes(x_admin_token: str = Header(None)):
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, address FROM graph_nodes WHERE address NOT LIKE 'web_%'")
        nodes = cur.fetchall()
    updated = 0
    for node in nodes:
        entity = enrich_node_from_known_entities(node["address"], conn)
        if entity:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE graph_nodes SET label=%s, entity_type=%s, risk_level=%s
                    WHERE id=%s
                """, (entity["label"], entity["entity_type"], entity["risk_level"], node["id"]))
            conn.commit()
            updated += 1
    conn.close()
    return {"total": len(nodes), "updated": updated}

# ---------- API Routes ----------
@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/search")
async def search_graph(req: SearchRequest, background_tasks: BackgroundTasks):
    conn = get_db_conn()
    addr = req.wallet_address.lower()
    ingestion_id = hashlib.md5((addr + str(time.time())).encode()).hexdigest()[:16]
    with conn.cursor() as cur:
        cur.execute("SELECT id, ingestion_status FROM graph_nodes WHERE address = %s", (addr,))
        node = cur.fetchone()
    cross_case_count = get_cross_case_count(addr, conn)
    node_id = None
    if not node:
        add_node_if_not_exists(addr, conn, confidence=0.3, source_type="Pending", entity_subtype="Wallet")
        background_tasks.add_task(run_parallel_ingestion, addr, ingestion_id)
        nodes = []
        edges = []
    else:
        node_id = node["id"]
        nodes, edges = traverse_graph(node_id, req.depth, conn)
        if node["ingestion_status"] != "complete":
            background_tasks.add_task(run_parallel_ingestion, addr, ingestion_id)
    conn.close()
    return {
        "nodes": nodes,
        "edges": edges,
        "cross_case_count": cross_case_count,
        "ingestion_id": ingestion_id,
        "seed_id": str(node_id)
    }

@app.get("/api/search/{address}/status")
async def get_ingestion_status(address: str):
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ingestion_status, ingestion_log, (SELECT COUNT(*) FROM graph_nodes) as node_count,
                   (SELECT COUNT(*) FROM graph_edges) as edge_count
            FROM graph_nodes
            WHERE address = %s
        """, (address.lower(),))
        node = cur.fetchone()
    cross_case_count = get_cross_case_count(address, conn)
    conn.close()
    if not node:
        raise HTTPException(status_code=404, detail="Address not found")
    log = node["ingestion_log"] or []
    completed_sources = []
    pending_sources = []
    all_sources = ["etherscan", "twitter", "websearch", "breadcrumbs", "networkx"]
    for source in all_sources:
        found = False
        for entry in log:
            if source in str(entry):
                found = True
                break
        if found:
            completed_sources.append(source)
        else:
            pending_sources.append(source)
    return {
        "status": node["ingestion_status"],
        "sources_complete": completed_sources,
        "sources_pending": pending_sources,
        "node_count": node["node_count"],
        "edge_count": node["edge_count"],
        "cross_case_count": cross_case_count
    }

@app.post("/api/import/csv")
async def import_csv(file: UploadFile = File(...), case_id: Optional[str] = Form(None), background_tasks: BackgroundTasks = None):
    contents = await file.read()
    text = contents.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    addresses = []
    for row in reader:
        for cell in row:
            if re.match(r"0x[a-fA-F0-9]{40}", cell.strip()):
                addresses.append(cell.strip())
    if not case_id:
        case_id = hashlib.md5((file.filename + str(time.time())).encode()).hexdigest()[:16]
    conn = get_db_conn()
    for addr in addresses[:100]:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO case_addresses (case_id, address, added_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (case_id, address) DO NOTHING
            """, (case_id, addr.lower(), "csv_import"))
            conn.commit()
        if background_tasks:
            background_tasks.add_task(run_parallel_ingestion, addr, "bulk_" + addr[:8])
    conn.close()
    return {
        "case_id": case_id,
        "addresses_imported": len(addresses[:100]),
        "ingestion_started": True
    }

@app.post("/api/attest")
async def attest_document(file: UploadFile = File(...), source_type: str = Form(...), case_id: Optional[str] = Form(None)):
    if source_type not in ["DOJ_FBI", "Court_Document", "ZachXBT", "News", "Community_OSINT"]:
        raise HTTPException(status_code=400, detail="Invalid source_type")
    contents = await file.read()
    sha256_hash = compute_sha256(contents)
    addresses = extract_addresses_from_pdf(contents)
    if not addresses:
        raise HTTPException(status_code=400, detail="No Ethereum addresses found in PDF")
    conn = get_db_conn()
    cur = conn.cursor()
    updated_nodes = []
    for addr in addresses:
        cur.execute("SELECT id, confidence_score FROM graph_nodes WHERE LOWER(address) = %s", (addr.lower(),))
        node = cur.fetchone()
        if not node:
            continue
        new_confidence = calculate_confidence(source_type)
        cur.execute("""
            UPDATE graph_nodes
            SET confidence_score = GREATEST(confidence_score, %s),
                source_type = COALESCE(source_type, %s),
                source_hash = %s
            WHERE id = %s
            RETURNING id, address, label, confidence_score
        """, (new_confidence, source_type, sha256_hash, node["id"]))
        updated = cur.fetchone()
        if case_id:
            cur.execute("""
                INSERT INTO case_addresses (case_id, address, added_by, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (case_id, address) DO NOTHING
            """, (case_id, addr, source_type, json.dumps({"source_hash": sha256_hash})))
        cur.execute("SELECT id FROM graph_nodes WHERE label ILIKE %s", ("Lazarus Group%",))
        lazarus = cur.fetchone()
        if lazarus and updated:
            cur.execute("""
                INSERT INTO graph_edges (source_node_id, target_node_id, edge_type, tx_hash, evidence)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_node_id, target_node_id, edge_type) DO NOTHING
            """, (updated["id"], lazarus["id"], "ATTRIBUTED_TO", sha256_hash, json.dumps([{"source": source_type, "hash": sha256_hash}])))
        updated_nodes.append({
            "address": updated["address"],
            "label": updated["label"],
            "confidence": float(updated["confidence_score"])
        })
    conn.commit()
    cur.close()
    conn.close()
    return {
        "status": "success",
        "source_hash": sha256_hash,
        "addresses_matched": len(updated_nodes),
        "updated_entities": updated_nodes,
        "case_id": case_id
    }

@app.post("/api/narrative")
async def generate_narrative(graph_data: dict):
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    context = "Investigation covers " + str(len(nodes)) + " entities and " + str(len(edges)) + " relationships.\n"
    for node in nodes[:20]:
        label = node.get("label", node.get("address", "unknown"))
        node_type = node.get("entity_subtype", node.get("type", "unknown"))
        risk = node.get("risk_level", "Unknown")
        context += "- " + str(label) + " (type: " + str(node_type) + ", risk: " + str(risk) + ")\n"
    for edge in edges[:20]:
        context += "  -> " + str(edge.get("type")) + " from source to target"
        if edge.get("amount_eth"):
            context += " (amount: " + str(edge["amount_eth"]) + " ETH)"
        context += "\n"
    prompt = "You are an on-chain intelligence analyst. Based on the following investigation data, write a concise factual paragraph (4-5 sentences) explaining the fund flow and attribution. Plain English for a journalist. Include risk assessment.\n\nData:\n" + context + "\n\nParagraph:"
    headers = {"Authorization": "Bearer " + DEEPSEEK_API_KEY, "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 400}
    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        narrative = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        narrative = "Error generating narrative: " + str(e)
    return {"narrative": narrative}

@app.post("/api/export")
async def export_report(graph_data: str = Form(...), narrative: str = Form(""), notes: str = Form(""), case_name: str = Form("Investigation Report"), address: str = Form("")):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    from reportlab.lib import colors
    import io

    graph = json.loads(graph_data)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    case_id = hashlib.sha256(json.dumps(graph).encode()).hexdigest()[:16]

    # Fetch annotations from DB
    annotations = {}
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT address, note FROM node_annotations")
        for row in cur.fetchall():
            annotations[row["address"]] = row["note"]
        cur.close()
        conn.close()
    except:
        pass

    # Fetch timeline from DB
    timeline_events = []
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.tx_hash, e.amount_eth, e.block_timestamp,
                   sn.address as src, sn.label as src_label,
                   tn.address as tgt, tn.label as tgt_label
            FROM graph_edges e
            JOIN graph_nodes sn ON sn.id = e.source_node_id
            JOIN graph_nodes tn ON tn.id = e.target_node_id
            WHERE e.block_timestamp IS NOT NULL
            ORDER BY e.block_timestamp ASC LIMIT 50
        """)
        timeline_events = cur.fetchall()
        cur.close()
        conn.close()
    except:
        pass

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    col_width = width - 2 * margin

    def check_page(y, needed=40):
        if y < needed:
            c.showPage()
            c.setFillColorRGB(0.05, 0.07, 0.09)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            return height - margin
        return y

    def section_header(y, text):
        y = check_page(y, 60)
        c.setFillColorRGB(0.05, 0.58, 0.53)
        c.rect(margin, y - 4, col_width, 20, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin + 6, y + 3, text)
        return y - 28

    def body_text(y, text, size=9, color=(0.8, 0.85, 0.9)):
        y = check_page(y)
        c.setFillColorRGB(*color)
        c.setFont("Helvetica", size)
        wrapped = simpleSplit(text, "Helvetica", size, col_width - 10)
        for line in wrapped:
            y = check_page(y)
            c.drawString(margin + 6, y, line)
            y -= size + 3
        return y

    # Dark background
    c.setFillColorRGB(0.05, 0.07, 0.09)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Header bar
    c.setFillColorRGB(0.05, 0.58, 0.53)
    c.rect(0, height - 80, width, 80, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, height - 45, "EVIDENCLY")
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.8, 0.95, 0.93)
    c.drawString(margin, height - 62, "On-Chain Intelligence Report")

    c.setFillColorRGB(0.6, 0.65, 0.7)
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin, height - 45, "Generated: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    c.drawRightString(width - margin, height - 60, "Case ID: " + case_id)

    y = height - 100

    # Case name + address
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, case_name)
    y -= 18
    if address:
        c.setFillColorRGB(0.05, 0.58, 0.53)
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, "Seed Address: " + address)
    y -= 20

    # Summary stats
    c.setFillColorRGB(0.13, 0.16, 0.2)
    c.rect(margin, y - 30, col_width / 3 - 5, 36, fill=1, stroke=0)
    c.rect(margin + col_width / 3 + 5, y - 30, col_width / 3 - 5, 36, fill=1, stroke=0)
    c.rect(margin + 2 * col_width / 3 + 10, y - 30, col_width / 3 - 10, 36, fill=1, stroke=0)
    c.setFillColorRGB(0.05, 0.58, 0.53)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(margin + col_width / 6, y - 10, str(len(nodes)))
    c.drawCentredString(margin + col_width / 2, y - 10, str(len(edges)))
    c.drawCentredString(margin + 5 * col_width / 6, y - 10, str(len(annotations)))
    c.setFillColorRGB(0.6, 0.65, 0.7)
    c.setFont("Helvetica", 8)
    c.drawCentredString(margin + col_width / 6, y - 24, "Entities")
    c.drawCentredString(margin + col_width / 2, y - 24, "Relationships")
    c.drawCentredString(margin + 5 * col_width / 6, y - 24, "Annotations")
    y -= 50

    # AI Narrative
    if narrative and narrative.strip():
        y = section_header(y, "AI NARRATIVE")
        y = body_text(y, narrative)
        y -= 10

    # Entity table
    y = section_header(y, "ENTITY TABLE")
    headers = ["Address", "Label", "Type", "Risk", "Confidence"]
    col_w = [180, 90, 70, 55, 60]
    c.setFillColorRGB(0.13, 0.16, 0.2)
    c.rect(margin, y - 2, col_width, 16, fill=1, stroke=0)
    c.setFillColorRGB(0.7, 0.75, 0.8)
    c.setFont("Helvetica-Bold", 8)
    x = margin + 4
    for i, h in enumerate(headers):
        c.drawString(x, y + 1, h)
        x += col_w[i]
    y -= 18
    for node in nodes[:40]:
        y = check_page(y, 20)
        c.setFillColorRGB(0.08, 0.1, 0.13)
        c.rect(margin, y - 2, col_width, 14, fill=1, stroke=0)
        addr = (node.get("address") or "")
        risk = node.get("risk_level") or "Unknown"
        if risk == "Critical": c.setFillColorRGB(0.86, 0.15, 0.15)
        elif risk == "High": c.setFillColorRGB(0.98, 0.45, 0.09)
        elif risk == "Medium": c.setFillColorRGB(0.96, 0.62, 0.04)
        else: c.setFillColorRGB(0.6, 0.65, 0.7)
        c.setFont("Helvetica", 7)
        x = margin + 4
        c.drawString(x, y, addr[:28] + ("…" if len(addr) > 28 else ""))
        x += col_w[0]
        c.drawString(x, y, (node.get("label") or "Unlabeled")[:14])
        x += col_w[1]
        c.drawString(x, y, (node.get("entity_type") or node.get("type") or "Wallet")[:10])
        x += col_w[2]
        c.drawString(x, y, risk)
        x += col_w[3]
        c.drawString(x, y, str(round((node.get("confidence") or 0) * 100)) + "%")
        y -= 14
    y -= 6

    # Annotations
    if annotations:
        y = section_header(y, "INVESTIGATOR ANNOTATIONS")
        for addr, note in list(annotations.items())[:20]:
            y = check_page(y, 30)
            c.setFillColorRGB(0.05, 0.58, 0.53)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(margin + 6, y, addr[:42])
            y -= 12
            y = body_text(y, note, size=8)
            y -= 4
        y -= 6

    # Timeline
    if timeline_events:
        y = section_header(y, "TRANSACTION TIMELINE")
        for ev in timeline_events[:30]:
            y = check_page(y, 25)
            ts = ev["block_timestamp"].strftime("%Y-%m-%d %H:%M UTC") if ev["block_timestamp"] else "Unknown"
            src = (ev["src_label"] or ev["src"] or "")[:20]
            tgt = (ev["tgt_label"] or ev["tgt"] or "")[:20]
            amt = str(round(float(ev["amount_eth"]), 4)) if ev["amount_eth"] else "0"
            c.setFillColorRGB(0.4, 0.45, 0.5)
            c.setFont("Helvetica", 7)
            c.drawString(margin + 6, y, ts)
            c.setFillColorRGB(0.8, 0.85, 0.9)
            c.drawString(margin + 130, y, src + " → " + tgt + "  Ξ" + amt)
            if ev["tx_hash"]:
                c.setFillColorRGB(0.35, 0.55, 0.9)
                c.drawString(margin + 380, y, (ev["tx_hash"] or "")[:18] + "…")
            y -= 13
        y -= 6

    # Source integrity
    y = section_header(y, "SOURCE INTEGRITY")
    body_text(y, "All on-chain data sourced from Etherscan API. Graph hash: " + case_id + ". Node annotations stored in PostgreSQL with timestamps. This report is generated by Evidencly — open-source on-chain intelligence platform.", size=8)

    # Footer
    c.setFillColorRGB(0.13, 0.16, 0.2)
    c.rect(0, 0, width, 25, fill=1, stroke=0)
    c.setFillColorRGB(0.4, 0.45, 0.5)
    c.setFont("Helvetica", 7)
    c.drawString(margin, 9, "evidencly.com  |  Evidence on Chain  |  " + datetime.utcnow().strftime("%Y"))
    c.drawRightString(width - margin, 9, "CONFIDENTIAL — FOR INVESTIGATIVE USE ONLY")

    c.save()
    buffer.seek(0)
    safe_name = case_name.replace(" ", "_").replace("/", "-")[:40]
    return Response(content=buffer.read(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=evidencly_" + safe_name + ".pdf"})


@app.get("/api/investigations")
async def list_investigations():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, starting_address, created_at, updated_at,
               jsonb_array_length(nodes) as node_count,
               jsonb_array_length(edges) as edge_count
        FROM investigations
        ORDER BY updated_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"investigations": [{
        "investigation_id": r["id"],
        "name": r["name"],
        "starting_address": r["starting_address"],
        "node_count": r["node_count"] or 0,
        "edge_count": r["edge_count"] or 0,
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat()
    } for r in rows]}

@app.delete("/api/investigation/{inv_id}")
async def delete_investigation(inv_id: str):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM investigations WHERE id = %s", (inv_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"status": "deleted", "investigation_id": inv_id}

@app.post("/api/investigation/create")
async def create_investigation(inv: InvestigationCreate):
    inv_id = str(uuid.uuid4())[:8]
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO investigations (id, name, starting_address, nodes, edges, notes, narrative)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (inv_id, inv.name, inv.starting_address, "[]", "[]", "{}", ""))
    conn.commit()
    cur.close()
    conn.close()
    return {"investigation_id": inv_id, "name": inv.name, "starting_address": inv.starting_address}

@app.get("/api/investigation/{inv_id}")
async def load_investigation(inv_id: str):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, starting_address, nodes, edges, notes, narrative, created_at, updated_at
        FROM investigations
        WHERE id = %s
    """, (inv_id,))
    inv = cur.fetchone()
    cur.close()
    conn.close()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {
        "investigation_id": inv["id"],
        "name": inv["name"],
        "starting_address": inv["starting_address"],
        "nodes": inv["nodes"],
        "edges": inv["edges"],
        "notes": inv["notes"],
        "narrative": inv["narrative"],
        "created_at": inv["created_at"].isoformat(),
        "updated_at": inv["updated_at"].isoformat()
    }

@app.post("/api/investigation/{inv_id}/save")
async def save_investigation(inv_id: str, data: InvestigationUpdate):
    conn = get_db_conn()
    cur = conn.cursor()
    updates = []
    params = []
    if data.nodes is not None:
        updates.append("nodes = %s::jsonb")
        params.append(json.dumps(data.nodes))
    if data.edges is not None:
        updates.append("edges = %s::jsonb")
        params.append(json.dumps(data.edges))
    if data.notes is not None:
        updates.append("notes = %s::jsonb")
        params.append(json.dumps(data.notes))
    if data.narrative is not None:
        updates.append("narrative = %s")
        params.append(data.narrative)
    if not updates:
        cur.close()
        conn.close()
        return {"status": "no_changes", "investigation_id": inv_id}
    updates.append("updated_at = NOW()")
    params.append(inv_id)
    query = "UPDATE investigations SET " + ", ".join(updates) + " WHERE id = %s"
    cur.execute(query, params)
    conn.commit()
    updated = cur.rowcount > 0
    cur.close()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"status": "saved", "investigation_id": inv_id}

# ---------- Startup ----------

# ---------- Node Annotations ----------
class AnnotationSave(BaseModel):
    node_id: str
    address: str
    note: str

@app.get("/api/annotations/{address}")
async def get_annotation(address: str):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT note, updated_at FROM node_annotations WHERE address = %s", (address.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"address": address, "note": "", "updated_at": None}
    return {"address": address, "note": row["note"], "updated_at": row["updated_at"].isoformat()}

@app.post("/api/annotations")
async def save_annotation(data: AnnotationSave):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO node_annotations (node_id, address, note)
        VALUES (%s, %s, %s)
        ON CONFLICT (address) DO UPDATE SET note = EXCLUDED.note, updated_at = NOW()
    """, (data.node_id, data.address.lower(), data.note))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "saved", "address": data.address}

@app.delete("/api/annotations/{address}")
async def delete_annotation(address: str):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM node_annotations WHERE address = %s", (address.lower(),))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}


# ---------- Timeline ----------
@app.get("/api/timeline")
async def get_timeline():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            e.id,
            e.tx_hash,
            e.amount_eth,
            e.edge_type,
            e.block_timestamp,
            sn.address as source_address,
            sn.label as source_label,
            sn.entity_type as source_type,
            tn.address as target_address,
            tn.label as target_label,
            tn.entity_type as target_type
        FROM graph_edges e
        JOIN graph_nodes sn ON sn.id = e.source_node_id
        JOIN graph_nodes tn ON tn.id = e.target_node_id
        WHERE e.block_timestamp IS NOT NULL
        ORDER BY e.block_timestamp ASC
        LIMIT 200
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    events = []
    for r in rows:
        events.append({
            "id": str(r["id"]),
            "tx_hash": r["tx_hash"],
            "amount_eth": float(r["amount_eth"]) if r["amount_eth"] else 0,
            "edge_type": r["edge_type"],
            "timestamp": r["block_timestamp"].isoformat() if r["block_timestamp"] else None,
            "source_address": r["source_address"],
            "source_label": r["source_label"] or "Unlabeled",
            "source_type": r["source_type"] or "Wallet",
            "target_address": r["target_address"],
            "target_label": r["target_label"] or "Unlabeled",
            "target_type": r["target_type"] or "Wallet",
        })
    return {"events": events, "total": len(events)}

@app.on_event("startup")
async def startup_event():
    load_known_entities_from_github()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)