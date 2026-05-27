Architecture
This document describes the technical architecture of Evidencly v0.1.0 (the live lite platform) and the target architecture for the OpenFoundry-backed v2.0.

Overview
Evidencly is a three-layer application: a React frontend, a FastAPI backend, and a PostgreSQL database. All three run on a single VPS for the lite version. The OpenFoundry migration in Phase 4 distributes these across a microservices architecture.

Current Architecture (v0.1.0)
┌─────────────────────────────────────────────────────────────────┐
│                        Browser Client                           │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ BFS Radial  │  │   Timeline   │  │  Cases / PDF Export    │ │
│  │   Canvas    │  │    Panel     │  │  Node Annotations      │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
│                     React 18 + Axios                            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / REST
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Nginx Reverse Proxy                        │
│                  evidencly.com → :8004                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend (:8004)                       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    API Routes                            │  │
│  │  POST /api/search        GET /api/search/{addr}/status   │  │
│  │  GET  /api/graph/{id}    POST /api/annotate              │  │
│  │  POST /api/cases         GET  /api/cases                 │  │
│  │  POST /api/export/pdf    GET  /api/known_entities        │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                           │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │                Ingestion Engine                          │  │
│  │                                                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │  Etherscan  │  │ Brave Search│  │   Twitter/X     │  │  │
│  │  │   V2 API    │  │    API      │  │    Search       │  │  │
│  │  │             │  │             │  │                 │  │  │
│  │  │ Normal txs  │  │ Web results │  │ Social mentions │  │  │
│  │  │ Internal txs│  │ correlated  │  │ correlated to   │  │  │
│  │  │ ERC-20 txs  │  │ to address  │  │ address         │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  │                                                          │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │              DeepSeek AI Layer                      │ │  │
│  │  │  Entity classification · Risk scoring               │ │  │
│  │  │  Investigation narrative generation                 │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                           │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │               Graph Traversal Engine                     │  │
│  │                                                          │  │
│  │  PostgreSQL Recursive CTE — up to 10 hops                │  │
│  │  Cycle-safe path tracking via visited node array         │  │
│  │  Directional BFS from seed wallet                        │  │
│  │  750 edge cap per traversal                              │  │
│  │  hop_level returned on every edge                        │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                           │
└─────────────────────┼───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                      PostgreSQL Database                        │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ graph_nodes │  │ graph_edges │  │   node_annotations   │   │
│  │             │  │             │  │                      │   │
│  │ id (uuid)   │  │ source_id   │  │ node_id              │   │
│  │ address     │  │ target_id   │  │ annotation_text      │   │
│  │ label       │  │ edge_type   │  │ created_at           │   │
│  │ entity_type │  │ tx_hash     │  └──────────────────────┘   │
│  │ risk_level  │  │ amount_eth  │                              │
│  │ confidence  │  │ block_ts    │  ┌──────────────────────┐   │
│  │ metadata    │  │ hop_level   │  │    investigations    │   │
│  └─────────────┘  └─────────────┘  │                      │   │
│                                    │ id, name, address    │   │
│  ┌─────────────────────────────┐   │ graph snapshot       │   │
│  │       known_entities        │   │ created_at           │   │
│  │                             │   └──────────────────────┘   │
│  │ 159 labelled addresses      │                              │
│  │ CEX · Mixers · Sanctioned   │                              │
│  │ Exploiters · Bridges · DEX  │                              │
│  └─────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘

Data Flow — Wallet Investigation
User enters wallet address
        │
        ▼
POST /api/search
        │
        ├─── Address already in DB?
        │         │
        │         ├── YES → traverse_graph() immediately
        │         │         Returns nodes + edges to frontend
        │         │
        │         └── NO  → Add stub node
        │                   Trigger background ingestion
        │                   Return empty graph
        │                   Frontend polls /status every 3s
        │
        ▼
Background Ingestion (parallel threads)
        │
        ├── Etherscan V2 → normal + internal + ERC-20 txs
        │       │
        │       └── Each counterparty → add_node_if_not_exists()
        │                             → insert graph_edge
        │                             → enrich from known_entities
        │
        ├── Brave Search → web results mentioning address
        │       └── Add web_* nodes with source_type=web
        │
        ├── Twitter/X → social mentions
        │       └── Add tweet_* nodes with source_type=social
        │
        └── DeepSeek AI → classify entity type + generate narrative
                └── Update graph_node label + entity_subtype
        │
        ▼
Frontend polls /status → ingestion_status = "complete"
        │
        ▼
traverse_graph(node_id, depth)
        │
        └── PostgreSQL recursive CTE
            Returns nodes + edges + hop_level
            Frontend renders BFS radial canvas

Frontend Canvas
The graph is rendered on an HTML5 Canvas using a custom BFS radial layout algorithm — no third-party graph library.
Seed wallet → centre (0,0)
Hop 1 nodes → inner ring, evenly distributed
Hop 2 nodes → second ring
...up to 10 hops
Node colouring by risk level:

Critical (OFAC, Lazarus) → red
High (mixers, high-risk CEX) → orange
Medium → yellow
Low (known CEX, bridges) → green
Unknown → grey

Edge weight by transaction volume. Node size by number of connections.

Ingestion Pipeline — Chain Adapters
Each supported chain implements the same adapter interface:
pythonclass ChainAdapter:
    def fetch_transactions(self, address: str) -> list[Transaction]
    def fetch_token_transfers(self, address: str) -> list[Transfer]
    def normalize(self, raw: dict) -> NormalizedTx
Currently implemented:

EtherscanAdapter — Ethereum mainnet via Etherscan V2

Planned (Phase 2):

TronGridAdapter — Tron / TRC-20
BscScanAdapter — BNB Smart Chain / BEP-20
HeliusAdapter — Solana / SPL tokens (API key held)
BlockstreamAdapter — Bitcoin UTXO model
PolygonAdapter, ArbitrumAdapter, OptimismAdapter — EVM extensions


Security

Admin endpoints protected by X-Admin-Token header
Rate limiting on all public endpoints
Input sanitisation on all address fields
No private keys stored anywhere in the system
Read-only chain data access (no transaction signing)
VPS hardened: dedicated system user, bcrypt auth, audit logging, daily backups


Deployment
Current production deployment:
Hostinger VPS (srv1274971)
├── Ubuntu 24.04
├── 16GB RAM / 4 CPUs
├── Nginx (reverse proxy + static frontend)
├── uvicorn (FastAPI backend, systemd service)
└── PostgreSQL 14 (local)
Self-hosted deployment via Docker:
bashdocker-compose up -d
# Services: nginx, fastapi, postgres
# Ports: 80/443 external, 8004 internal

Target Architecture — v2.0 (OpenFoundry)
Phase 4 migrates the intelligence layer onto OpenFoundry — a Go microservices platform modelled on Palantir Foundry's capability architecture.
┌──────────────────────────────────────────────────────────────┐
│                     Evidencly v2.0                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              OpenFoundry Core                       │    │
│  │                                                     │    │
│  │  Ontology Engine  │  Dataset Pipelines              │    │
│  │  AI/ML Layer      │  Governance + Audit             │    │
│  │  RBAC Workspaces  │  API Gateway                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Chain       │  │  Social +    │  │  Actor           │  │
│  │  Indexers    │  │  Web         │  │  Fingerprinting  │  │
│  │              │  │  Crawlers    │  │  Engine          │  │
│  │  ETH/Tron    │  │              │  │                  │  │
│  │  BSC/SOL/BTC │  │  Twitter     │  │  Cross-chain     │  │
│  │  ARB/OP/POLY │  │  Telegram    │  │  correlation     │  │
│  │  AVAX/BASE   │  │  Web/Paste   │  │  Identity graph  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Shared Global Case File System            │    │
│  │   Community-contributed · Cryptographically signed  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘

Contributing
See CONTRIBUTING.md for how to add chain adapters, known entities, or frontend improvements.
Architecture questions and proposals: open an issue tagged architecture.
Contact: evidencly@gmail.com

Last updated: May 2026
