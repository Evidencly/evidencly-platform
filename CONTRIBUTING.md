Contributing to Evidencly
First — thank you. Evidencly is built on the belief that on-chain intelligence should be a public good, and every contribution moves that forward.
This document covers how to contribute code, known entity data, documentation, and chain integrations.

Ways to Contribute
1. Known Entity Labels
The highest-impact contribution with the lowest technical barrier.
If you have a verified wallet address with a credible source — an exchange hot wallet, a sanctioned address, a confirmed exploiter, a mixer contract — open a PR adding it to the known entities database.
File: backend/known_entities.sql
Format:
sql('0xaddress', 'Label', 'entity_type', 'entity_subtype', 'risk_level', 'source', 'notes'),
Entity types: Exchange, Mixer, Sanctioned, Wallet, Contract, Bridge
Risk levels: low, medium, high, critical
Source examples: OFAC SDN, Chainalysis, ZachXBT, manual, FBI advisory, on-chain analysis
Every label must have a credible source. Unverified labels will not be merged.

2. Chain Adapters
Phase 2 of the roadmap adds Tron, BSC, Solana, Bitcoin, and additional EVM chains. Each chain needs an adapter that implements the standard ingestion interface.
Interface to implement:
pythonclass ChainAdapter:
    def fetch_transactions(self, address: str) -> list[Transaction]
    def fetch_token_transfers(self, address: str) -> list[Transfer]
    def normalize(self, raw: dict) -> NormalizedTx
Location: backend/adapters/<chain_name>.py
If you want to claim a chain integration, open an issue tagged chain-adapter so work isn't duplicated.
Priority order:

Tron (TronGrid API)
BNB Smart Chain (BscScan API)
Solana (Helius API)
Bitcoin (Blockstream API)
Arbitrum / Optimism / Polygon (EVM extensions of existing Etherscan adapter)


3. Frontend Improvements
The canvas renderer, timeline panel, and case file UI are all open for improvement.
Stack: React 18, plain CSS, HTML5 Canvas
Key files:

frontend/src/App.js — main application
frontend/src/App.css — styling

Current frontend improvement wishlist:

Hop-level ring colouring on the canvas
Search across saved case files
Mini-map for large graphs
Keyboard shortcuts for investigation workflow
Mobile-responsive layout


4. Documentation
Case studies are the most valuable documentation Evidencly can have. If you have investigated a hack or exploit and want to write it up as a case study using Evidencly, open a PR against docs/case-studies/.
Format: Markdown, following the template at docs/case-studies/template.md
Include:

Incident summary (what happened, when, how much)
Seed wallet address(es)
Fund flow narrative
Screenshots of the Evidencly graph (optional but encouraged)
Sources


5. Bug Reports and Feature Requests
Open an issue. Use the following tags:

bug — something is broken
enhancement — new feature request
chain-adapter — new chain integration
known-entity — entity label addition or correction
roadmap — roadmap discussion
architecture — architectural proposal
documentation — docs improvement


Development Setup
Prerequisites

Python 3.10+
Node.js 18+
PostgreSQL 14+
API keys: Etherscan V2, DeepSeek, Brave Search

Backend
bashcd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys
uvicorn main:app --reload --port 8004
Frontend
bashcd frontend
npm install
npm start
# Development server on :3000
# Proxies API calls to :8004
Database
bashpsql -U postgres -c "CREATE DATABASE evidencly;"
psql -U postgres -c "CREATE USER evidencly_user WITH PASSWORD 'yourpassword';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE evidencly TO evidencly_user;"
# Tables are created automatically on first backend start
Docker (recommended)
bashcp .env.example .env
# Fill in your API keys
docker-compose up -d
# Frontend: http://localhost
# API: http://localhost:8004

Pull Request Process

Fork the repository
Create a branch: git checkout -b feature/your-feature-name
Make your changes
Test locally
Commit with a clear message: git commit -m "Add Tron chain adapter"
Push and open a PR against main
Describe what you changed and why

PRs are reviewed and merged by the maintainer. For large changes, open an issue first to discuss the approach.

Code Style
Python (backend)

PEP 8
Type hints on all function signatures
Docstrings on public functions
No hardcoded API keys — use environment variables

JavaScript (frontend)

Functional components, React hooks
No external graph libraries — canvas rendering is custom
CSS variables for theming


Entity Label Standards
Known entity labels must meet these standards to be merged:
FieldRequirementAddressLowercase, checksummed where applicableLabelClear, concise, human-readableSourceMust be cited — OFAC SDN, Chainalysis blog post, ZachXBT thread, FBI advisory, etc.Risk levelConservative — when in doubt, go higherNotesInclude the incident name and date where relevant
Disputed labels (e.g. a wallet incorrectly attributed) can be flagged via issue tagged entity-dispute.

Community
Questions, ideas, and discussion: open an issue or reach out directly.
Contact: evidencly@gmail.com

Recognition
Contributors who add verified entity labels, chain adapters, or significant features will be listed in the project README under Contributors.
On-chain attribution for significant contributors is planned as part of the Phase 4 governance layer.

Thank you for helping make on-chain intelligence a public good.
