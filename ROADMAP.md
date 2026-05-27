Evidencly Roadmap
This document tracks the full development trajectory of Evidencly — from the current Ethereum-focused lite platform through to the full cross-chain OpenFoundry-backed intelligence layer.
Progress is updated as milestones are completed. Community contributions accelerate every phase.

Current Status — v0.1.0 (Live)
Evidencly is live at evidencly.com with a working Ethereum intelligence stack:

Recursive 10-hop graph tracing via PostgreSQL recursive CTE
159 known entities across exchanges, mixers, sanctioned wallets, exploiters, and bridges
Multi-source ingestion: Etherscan V2, Brave Search, Twitter/X, DeepSeek AI
BFS radial canvas with hop-distance visualisation
Node annotation, timeline panel, case file system, PDF export
Self-hostable via Docker


Phase 2 — Cross-Chain Expansion
Target: Q3 2026
Funding dependency: Ecosystem grants
The single biggest limitation of every existing on-chain intelligence tool is that bad actors don't stay on one chain. Lazarus Group moves ETH → Tron → BSC → Solana in a single laundering cycle. Tracing stops the moment funds cross a bridge.
Phase 2 breaks that wall.
Tron
Priority chain. The majority of USDT-denominated money laundering runs through Tron due to near-zero fees. TRC-20 transfers, USDT flows, and Tron Energy market abuse all become traceable.

TronGrid API integration
TRC-20 transfer ingestion
Known entities expansion: Tron CEX deposits, sanctioned Tron addresses

BNB Smart Chain
High volume of rug pulls, pig butchering operations, and bridge exploit proceeds move through BSC.

BscScan API integration
BEP-20 transfer ingestion
PancakeSwap router and known BSC mixer contracts added to entity database

Solana
Lazarus Group's primary chain for post-2023 operations. Atomic Wallet, Stake.com, and Alphapo hack proceeds all moved through Solana.

Helius API integration (already have API key)
SPL token transfer ingestion
Known Solana entities: Lazarus-linked addresses, high-risk Solana DEXs

Bitcoin
UTXO-based tracing requires a different graph model — inputs and outputs rather than sender/receiver. Bitcoin is the final destination for a significant portion of state-sponsored theft.

BlockCypher / Blockstream API integration
UTXO graph model alongside existing account model
Known BTC entities: OFAC-sanctioned BTC addresses, mixing service outputs

Additional EVM Chains
Once the cross-chain ingestion pattern is established, adding further EVM chains is low marginal effort:

Arbitrum — bridge exploit proceeds
Optimism — OP ecosystem exploits
Polygon — gaming and NFT fraud
zkSync / Starknet / Base — emerging L2 activity
Avalanche — DeFi exploit proceeds


Phase 3 — Actor Fingerprinting
Target: Q4 2026
This is the moat. No existing tool does this.
On-chain tracing tells you where money went. Actor fingerprinting tells you who moved it.
The insight: bad actors are pseudonymous on-chain but they leak identity signals everywhere else. The same wallet address appears in a Telegram group, a forum post, a Twitter thread, and a paste site. The same person controls wallets on three different chains. The same infrastructure hosts a phishing site and a mixer frontend.
Evidencly's actor fingerprinting layer correlates all of these signals into a unified actor profile.
Cross-Chain Address Correlation

Detect same actor operating wallets across ETH, Tron, Solana, BSC by timing patterns, bridge usage, and shared intermediaries
Probabilistic scoring: "85% confidence these three wallets are controlled by the same entity"

Social Graph Overlay

Index Twitter/X, Telegram public groups, and Discord servers for address mentions
Build a graph of which accounts are promoting, sharing, or warning about the same addresses
Detect coordinated behaviour: multiple accounts all posting the same contract address = likely shill operation or scam coordination

Web Footprint Matching

Correlate wallet addresses with domains, hosting infrastructure, WHOIS data
Match paste site drops (Pastebin, GitHub Gist) containing addresses to on-chain activity timing
Forum post history (Bitcointalk, Reddit) linked to wallet activity

Actor Profile Builder

Unified profile page per suspected actor: all chains, all social handles, all web mentions, all known associates
Confidence scoring on each attribution
Export as PDF evidence package for law enforcement or journalism


Phase 4 — OpenFoundry Integration
Target: H1 2027
Transforms Evidencly from a tool into an intelligence platform
OpenFoundry is the open-source Palantir Foundry alternative — a full operational data platform built in Go with ontology management, dataset pipelines, AI/ML integration, and governance. Evidencly's current Python/FastAPI stack is the proof of concept. Phase 4 migrates the intelligence layer onto OpenFoundry's architecture.
Ontology Engine

Wallets, actors, transactions, and social entities become first-class ontology objects
Relationships between objects are typed, versioned, and auditable
The known entities database becomes a community-governed ontology

Dataset Pipelines

Real-time chain indexing pipelines replace on-demand Etherscan calls
Each supported chain has a dedicated indexing pipeline
Historical backfill for all major hack events

Shared Global Case File System

Investigators worldwide contribute to a shared knowledge graph
Case files are cryptographically signed and attributable
Community can validate, dispute, or extend any attribution

API Layer

Public API for verified journalists, OCCRP members, and academic researchers
Rate-limited free tier, affordable paid tier
Webhook support for real-time alerts on watched addresses

Governance

Community-maintained known entities database via GitHub PRs
On-chain governance for entity dispute resolution
Transparency log: every entity label has a source, a date, and a contributor


Phase 5 — Institutional and Government Layer
Target: 2027+

Law enforcement API with evidentiary-standard export formats
Integration with FATF travel rule compliance tools
Court-ready PDF reports with chain-of-custody documentation
Partnerships with OCCRP, DFRLab, Chainalysis academic programme
White-label deployment for exchange compliance teams


Funding Targets
Evidencly is actively seeking ecosystem grants from blockchain foundations to fund Phase 2 and Phase 3 development. Every chain we add is a direct contribution to that chain's security and investigative infrastructure.
Current outreach:
FoundationStatusChain relevanceEthereum Foundation ESPApplyingETH core chainSolana FoundationApplyingLazarus primary chainOptimism RPGFApplyingL2 bridge exploitsArbitrum FoundationApplyingL2 bridge exploitsUniswap FoundationApplyingDeFi exploit tracingAave Grants DAOApplyingDeFi exploit tracingPolygon FoundationApplyingGaming/NFT fraudAvalanche FoundationApplyingDeFi exploitsNear FoundationApplyingCross-chain expansionKnight FoundationApplyingInvestigative journalismOmidyar NetworkApplyingOpen-source public good
Contact for grant enquiries: evidencly@gmail.com

Contributing to the Roadmap
Have a chain integration, entity label, or feature you want to see prioritised? Open an issue tagged roadmap or submit a PR.
The roadmap is community-influenced. If a chain's community wants to fund or contribute their own integration, that moves it up the queue.

Last updated: May 2026
