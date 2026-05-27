Case Study: Harmony Horizon Bridge Hack
Date: June 23, 2022
Amount stolen: $100,000,000
Attacker: Lazarus Group (North Korea / DPRK)
Chain: Ethereum, Binance Smart Chain, Harmony (ONE)
Status: Funds partially traced, majority laundered through Tornado Cash and Sinbad

Incident Summary
On June 23 2022, the Lazarus Group compromised two of the five validator private keys controlling the Harmony Horizon Bridge — a cross-chain bridge connecting Harmony's ONE blockchain to Ethereum and Binance Smart Chain.
With two of five multisig keys compromised, the attacker had sufficient signing authority to drain the bridge's liquidity. Over the course of 11 transactions, $100M in tokens was extracted: ETH, USDC, USDT, WBTC, BNB, and several smaller assets.
The FBI formally attributed the attack to Lazarus Group in January 2023. OFAC subsequently sanctioned the primary exploiter addresses.

Attacker Wallets
Primary Exploiter
0x5d4b2a02c59197eb2cae95a6df9fe27af60459d4
Labelled in Evidencly known entities database as: Lazarus - Harmony Bridge Exploiter · risk: critical
Subwallets (fund dispersion)
0x0d043128146654c7683fbf30ac98d7b2285ded00
0x4acc04a0d7f03e81cded33f7c5f0ba3c6ee92be8
0x85b931a32a0725be14285b66f1a22178c672d69b
All three labelled in Evidencly known entities database as: Lazarus - Harmony Subwallet · risk: critical

Fund Flow
Harmony Horizon Bridge (drained)
        │
        │  $100M in ETH/USDC/USDT/WBTC/BNB
        ▼
0x5d4b2a02c59197eb2cae95a6df9fe27af60459d4
(Primary Exploiter — Lazarus)
        │
        ├──────────────────────────────────────┐
        │                                      │
        ▼                                      ▼
Tornado Cash 100 ETH Pool            Tornado Cash 10 ETH Pool
0x910cbd523d972eb0a6f4cae4618ad62622b39dbf   0xd90e2f925da726b50c4ed8d0fb90ad053324f31b
(OFAC sanctioned)                    (OFAC sanctioned)
        │
        ▼
Subwallets (dispersion)
0x0d043128146654c7683fbf30ac98d7b2285ded00
0x4acc04a0d7f03e81cded33f7c5f0ba3c6ee92be8
0x85b931a32a0725be14285b66f1a22178c672d69b
        │
        ▼
Sinbad.io Mixer
0x2f389ce8bd8ff92de3402ffce4691d17fc4f6f6d
(OFAC sanctioned Nov 2023)
        │
        ▼
Exchange deposit addresses
(Binance, Huobi — flagged in known entities)

How Evidencly Traces This
Step 1 — Seed the primary exploiter wallet
Enter 0x5d4b2a02c59197eb2cae95a6df9fe27af60459d4 into Evidencly and hit Investigate.
The ingestion engine pulls all transactions from Etherscan V2 across three tx types: normal, internal, and ERC-20 transfers. Every counterparty wallet is added to the graph as a node. Every transaction becomes a directed edge.
Known entity matching runs automatically on every node. Within seconds the graph lights up:

The Tornado Cash pool addresses are flagged red — OFAC sanctioned, risk: critical
The Sinbad mixer address is flagged red — OFAC sanctioned, risk: critical
Exchange deposit addresses at Binance and Huobi are flagged green — known CEX

Step 2 — Expand hops
Set depth to 5 hops and re-investigate. The recursive CTE traversal expands outward from the exploiter wallet through the mixer layers and into the subwallet dispersion pattern. The full laundering topology becomes visible in a single graph.
Step 3 — Annotate nodes
Click any node to open the Entity Details panel. Add investigator annotations — timestamps, source links, confidence notes. These persist in the case file.
Step 4 — Timeline panel
Switch to the Timeline tab. All transactions are displayed in chronological order with Etherscan links. The 11 drain transactions from the bridge are visible at the top, followed by the dispersion to Tornado Cash pools, then the subwallet movements.
The timeline confirms the attack sequence:

23 Jun 2022 06:08 UTC — first drain transaction
23 Jun 2022 06:26 UTC — last drain transaction
24 Jun 2022 onward — Tornado Cash cycling begins

Step 5 — Save the case file and export
Save the investigation as a named case file: Harmony Bridge Hack — Lazarus 2022
Export as PDF. The report includes:

Cover page with investigation name and date
Stats panel: node count, edge count, risk distribution
Full entity table with risk levels
Chronological timeline
All investigator annotations
AI-generated narrative summary
Source integrity footer

The PDF is court-presentable and journalist-ready.

What Evidencly Automatically Flagged
AddressLabelRiskSource0x5d4b2a0...Lazarus - Harmony Bridge ExploiterCriticalChainalysis/OFAC0x910cbd5...Tornado Cash 100 ETHHighOFAC SDN0xd90e2f9...Tornado Cash 10 ETHHighOFAC SDN0x2f389ce...Sinbad.io MixerCriticalOFAC SDN0x0d04312...Lazarus - Harmony SubwalletCriticalChainalysis0x4acc04a...Lazarus - Harmony Subwallet 2CriticalChainalysis0x85b931a...Lazarus - Harmony Subwallet 3CriticalChainalysis
7 of the key addresses in this attack are automatically labelled on first contact — no manual research required.

What Funding Enables
This case study demonstrates Evidencly's current capability on Ethereum. The Harmony hack also involved:

Binance Smart Chain — a portion of funds moved through BSC bridges
Bitcoin — final conversion destination for a portion of proceeds
Tron — USDT portion moved through Tron for near-zero fee transfers

With Phase 2 cross-chain funding, the complete multi-chain fund flow becomes traceable in a single investigation — seed one address, follow the money across every chain it touches.

Sources

FBI Attribution — January 2023
OFAC Sanctions Notice
Chainalysis Harmony Hack Analysis
Rekt.news Incident Report
Etherscan transaction data — publicly verifiable


Case study prepared using Evidencly v0.1.0 · evidencly.com
All wallet addresses cited are publicly documented in FBI advisories and OFAC SDN list
