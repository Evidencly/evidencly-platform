Evidencly
Open-source on-chain intelligence and investigative journalism platform.
Live at evidencly.com · MIT License · Built in public

What is Evidencly?
Evidencly is a self-hostable intelligence platform for tracing stolen crypto, exposing bad actors, and building evidentiary case files from on-chain data.
It does what Chainalysis and Arkham do — but open-source, self-hostable for free, and with an affordable hosted tier for investigators, journalists, and blockchain security researchers who can't afford $100K/yr enterprise licences.
The current live version is the lite foundation. With ecosystem funding, Evidencly migrates to a full OpenFoundry-backed intelligence layer with cross-chain tracing, actor fingerprinting across social and web data, and a shared global case file system.

The Problem
Over $7 billion in crypto was stolen in 2024 alone. The vast majority of that money moves through predictable patterns — mixers, bridges, high-risk exchanges — but the tools to trace it are locked behind expensive enterprise contracts.

Chainalysis Reactor — $50,000–$100,000+/yr
Arkham Intelligence — centralised, closed-source, ETH-only
Breadcrumbs / Metasleuth — limited hop depth, no social correlation, no self-hosting

Journalists at OCCRP, DFRLab, and independent blockchain investigators have no viable open-source alternative. Evidencly is that alternative.

Pricing Model
Evidencly is free to self-host, forever.
The hosted platform at evidencly.com operates on an affordable subscription model that covers the cost of multi-chain indexing, AI compute, and infrastructure at scale. No enterprise pricing walls. No $100K licences.
The open-source core — graph traversal engine, known entities database, ingestion pipelines, case file system — will always be publicly available under MIT licence.
TierWho it's forCostSelf-hostedDevelopers, researchers, security teamsFree foreverHosted — IndividualIndependent investigators, journalistsAffordable monthlyHosted — TeamDAOs, security firms, newsroomsAffordable monthlyHosted — InstitutionalExchanges, law firms, government agenciesContact us

What It Does Today
Graph Intelligence

Recursive multi-hop wallet tracing (up to 10 hops) via PostgreSQL recursive CTE
BFS radial canvas — seed wallet at centre, hops expand outward with visual distance
159 known entities: CEX hot wallets, OFAC SDN addresses, Lazarus Group subwallets, Tornado Cash contracts, Sinbad mixer, DeFi exploiters, bridge contracts, DEX routers

Multi-Source Ingestion

Etherscan V2 API — normal txs, internal txs, ERC-20 transfers
Brave Search API — web search correlated to addresses
Twitter/X search — social mentions tied to wallets
DeepSeek AI — automated entity classification and narrative generation

Investigation Tools

Node annotation — attach investigator notes to any wallet
Timeline panel — chronological transaction flow with Etherscan links
Case file system — save, load, and delete named investigations
PDF export — dark-themed professional report with cover, stats, entity table, timeline, annotations, AI narrative, and source integrity footer

Known Entity Database

159 labelled addresses across: OKX, Binance, Huobi, Kraken, Gemini, Coinbase, Bybit, Crypto.com, Lazarus Group (Ronin, Harmony, Atomic Wallet, Bybit, Stake.com, CoinEx, Alphapo hacks), OFAC SDN list, Tornado Cash pools and relayers, Sinbad.io, eXch, FixedFloat, Railgun, Euler/Curve/Nomad/Wormhole/Multichain exploiters


Roadmap
Phase 1 — Ethereum Foundation (live now)

 Recursive 10-hop graph tracing
 Known entity database (159 addresses)
 Multi-source ingestion (Etherscan, web, social)
 Case file system + PDF export
 Node annotation + timeline panel
 Self-hostable via Docker

Phase 2 — Cross-Chain Expansion (with funding)

 Tron — USDT laundering is predominantly Tron-based
 BSC — high volume of rug pulls and bridge exploits
 Solana — Lazarus Group primary chain post-2023
 Bitcoin — UTXO tracing via block explorer APIs
 Avalanche, Arbitrum, Optimism, Polygon, zkSync, Base

Phase 3 — Actor Fingerprinting (the moat)

 Cross-chain address correlation — same actor, different chains
 Social graph overlay — Twitter/Telegram accounts sharing the same addresses
 Web footprint matching — forums, paste sites, domains tied to wallets
 Actor profile builder — pseudonymous identity reconstruction across all data sources

Phase 4 — OpenFoundry Integration

 Migrate intelligence layer to OpenFoundry ontology engine
 Dataset pipelines for real-time chain indexing
 Shared global case file system — investigators worldwide contribute to one knowledge graph
 API access for OCCRP, DFRLab, and independent journalists
 Governance layer — community-maintained known entities database


Architecture
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  BFS Radial Canvas · Timeline · Cases · PDF Export   │
└────────────────────┬────────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────────┐
│              Backend (FastAPI / Python)              │
│  Graph Traversal · Ingestion Engine · AI Layer       │
│  DeepSeek · Etherscan V2 · Brave Search · Twitter    │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│           PostgreSQL · Known Entities DB             │
│  graph_nodes · graph_edges · node_annotations        │
│  investigations · known_entities                     │
└─────────────────────────────────────────────────────┘

Case Studies
Harmony Horizon Bridge Hack — $100M (June 2022)
The Lazarus Group exploited the Harmony Horizon Bridge, draining $100M in tokens across multiple assets. Evidencly traces the full fund flow from the exploiter wallet through Tornado Cash pools, Sinbad mixer, and onward to exchange deposit addresses — all flagged automatically via the known entities database.
→ Full case study (coming soon)
Bybit Exchange Hack — $1.5B (February 2025)
The largest crypto theft in history. North Korean Lazarus Group compromised Bybit's Safe multisig infrastructure. Evidencly maps the dispersion of funds across 50+ subwallets, eXch exchange, and Railgun privacy protocol.
→ Full case study (coming soon)

Self-Hosting
bashgit clone https://github.com/Evidencly/evidencly-platform
cd evidencly-platform
cp .env.example .env
# Add your API keys: Etherscan, DeepSeek, Brave Search
docker-compose up -d
Runs on any Linux VPS with 2GB+ RAM. No cloud dependencies.

Tech Stack
LayerTechnologyFrontendReact 18, Axios, Custom CanvasBackendPython 3.10, FastAPI, uvicornDatabasePostgreSQL 14AIDeepSeek API (swappable)Chain dataEtherscan V2, extensible to any block explorerWeb/SocialBrave Search APIExportReportLab PDF, NetworkXHostingSelf-hosted, Docker

Why Open Source?
Blockchain is public infrastructure. Intelligence about who is stealing from it, laundering through it, and exploiting it should be public too.
Closed-source tools with enterprise pricing walls mean that only the best-funded teams — governments, large exchanges, hedge funds — can trace illicit flows. Independent journalists, small DAOs, retail victims, and developing-world investigators get nothing.
Evidencly is built to change that. Every entity label, every case file structure, every graph traversal algorithm is open for the community to inspect, improve, and build on. The hosted service exists to cover the real costs of running multi-chain indexing at scale — not to create a paywall.

Contributing
See CONTRIBUTING.md. All contributions welcome — new chain integrations, known entity additions, UI improvements, documentation.
Known entities PRs especially welcomed — if you have a verified wallet label with a credible source, open a PR against backend/known_entities.sql.

Funding
Evidencly is seeking ecosystem grants from every major blockchain foundation to fund cross-chain expansion, the OpenFoundry integration, and infrastructure costs.
If you represent a chain ecosystem fund and want open-source on-chain intelligence tooling available to your community, get in touch: evidencly@gmail.com.com

License
MIT — free to self-host, fork, and build on.

Built by Nick Lowe · Dubai · 2026# evidencly-platform
Open-source on-chain intelligence and investigative journalism platform
