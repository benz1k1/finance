# Indian Equity AI/ML Opportunity & Market Intelligence Engine --- Product Specification

## Index

**Part A --- Product Specification**

-   [1. Purpose](#1-purpose)
-   [2. Design Principles](#2-design-principles)
-   [3. Data Universe](#3-data-universe)
-   [4. Company Master](#4-company-master)
-   [5. Financial Statement Engine](#5-financial-statement-engine)
-   [6. Profitability Inflection Engine](#6-profitability-inflection-engine)
-   [7. Earnings Acceleration Engine](#7-earnings-acceleration-engine)
-   [8. Margin Inflection Engine](#8-margin-inflection-engine)
-   [9. Operating Leverage Engine](#9-operating-leverage-engine)
-   [10. ROCE / ROIC Inflection Engine](#10-roce--roic-inflection-engine)
-   [11. Cash-Flow Inflection Engine](#11-cash-flow-inflection-engine)
-   [12. Debt & Deleveraging Engine](#12-debt--deleveraging-engine)
-   [13. Valuation Engine](#13-valuation-engine)
-   [14. Earnings Expectations / Implied Growth Engine](#14-earnings-expectations--implied-growth-engine)
-   [15. Undervalued Growth Engine](#15-undervalued-growth-engine)
-   [16. Value Trap Detector](#16-value-trap-detector)
-   [17. Deep Value Engine](#17-deep-value-engine)
-   [18. SOTP / Hidden Asset Engine](#18-sotp--hidden-asset-engine)
-   [19. Turnaround Engine](#19-turnaround-engine)
-   [20. Capacity Utilisation Engine](#20-capacity-utilisation-engine)
-   [21. Order Book Engine](#21-order-book-engine)
-   [22. Investor / Shareholding Intelligence](#22-investor--shareholding-intelligence)
-   [23. Investor Holding History](#23-investor-holding-history)
-   [24. Smart Money / Price Divergence Engine](#24-smart-money--price-divergence-engine)
-   [25. Technical / Price Engine](#25-technical--price-engine)
-   [26. Relative Strength Engine](#26-relative-strength-engine)
-   [27. Volume & Delivery Intelligence](#27-volume--delivery-intelligence)
-   [28. Sector Rotation Engine](#28-sector-rotation-engine)
-   [29. Market Regime Engine](#29-market-regime-engine)
-   [30. Corporate Event Engine](#30-corporate-event-engine)
-   [31. Historical Update / Company Timeline Engine](#31-historical-update--company-timeline-engine)
-   [32. Management Commentary Engine](#32-management-commentary-engine)
-   [33. Narrative vs Numbers Engine](#33-narrative-vs-numbers-engine)
-   [34. Accounting Quality Engine](#34-accounting-quality-engine)
-   [35. Corporate Governance Engine](#35-corporate-governance-engine)
-   [36. IPO / Newly Listed Stock Engine](#36-ipo--newly-listed-stock-engine)
-   [37. Catalyst Engine](#37-catalyst-engine)
-   [38. Underpriced Stock Discovery Engine](#38-underpriced-stock-discovery-engine)
-   [39. Opportunity Score](#39-opportunity-score)
-   [40. AI / ML Architecture](#40-ai--ml-architecture)
-   [41. Historical Winner Pattern Engine](#41-historical-winner-pattern-engine)
-   [42. Point-in-Time Backtesting](#42-point-in-time-backtesting)
-   [43. Backtest Metrics](#43-backtest-metrics)
-   [44. Dashboard](#44-dashboard)
-   [45. Company Detail Page](#45-company-detail-page)
-   [46. Historical Update View](#46-historical-update-view)
-   [47. Alerts](#47-alerts)
-   [48. Data Quality Layer](#48-data-quality-layer)
-   [49. Data Model](#49-data-model)
-   [50. Feature Store](#50-feature-store)
-   [51. Research Output](#51-research-output)
-   [52. Core Rule](#52-core-rule)
-   [53. MVP Priority](#53-mvp-priority)
-   [54. Final Objective](#54-final-objective)

**[Part B --- Additional Components](#part-b-----additional-components)**

-   [55. Sector-Specific Financial Templates](#55-sector-specific-financial-templates)
-   [56. Operating KPI Engine](#56-operating-kpi-engine)
-   [57. Reporting-Basis and Normalisation Rules](#57-reporting-basis-and-normalisation-rules)
-   [58. Consensus, Revisions and Results-Reaction Engine](#58-consensus-revisions-and-results-reaction-engine)
-   [59. Forensic Score Pack](#59-forensic-score-pack)
-   [60. Capital Allocation Engine](#60-capital-allocation-engine)
-   [61. Cyclical and Commodity Linkage Engine](#61-cyclical-and-commodity-linkage-engine)
-   [62. High-Frequency and Alternative Data Engine](#62-high-frequency-and-alternative-data-engine)
-   [63. Relationship Graph and Read-Through Engine](#63-relationship-graph-and-read-through-engine)
-   [64. Policy, Regulation and Theme Engine](#64-policy-regulation-and-theme-engine)
-   [65. Insider, Deal and Monthly Fund-Holding Engine](#65-insider-deal-and-monthly-fund-holding-engine)
-   [66. Supply Overhang and Forced-Flow Engine](#66-supply-overhang-and-forced-flow-engine)
-   [67. Special Situations Engine](#67-special-situations-engine)
-   [68. Credit and Distress Engine](#68-credit-and-distress-engine)
-   [69. Investability, Liquidity and Surveillance Filter](#69-investability-liquidity-and-surveillance-filter)
    -   [69.1 Hard exclusions by exchange series and group](#691-hard-exclusions-by-exchange-series-and-group)
    -   [69.2 Scam and manipulation detector](#692-scam-and-manipulation-detector)
-   [70. Derivatives Signal Engine](#70-derivatives-signal-engine)
-   [71. Document Diff and Language-Change Engine](#71-document-diff-and-language-change-engine)
-   [72. Signal Ledger and Outcome Tracking](#72-signal-ledger-and-outcome-tracking)
-   [73. Thesis Lifecycle and Monitoring](#73-thesis-lifecycle-and-monitoring)
-   [74. Portfolio Construction and Risk Layer](#74-portfolio-construction-and-risk-layer)
-   [75. Research Workbench](#75-research-workbench)
-   [76. Model Governance](#76-model-governance)
-   [77. Compliance, Licensing and Disclaimers](#77-compliance-licensing-and-disclaimers)
-   [78. Extensions to Existing Sections](#78-extensions-to-existing-sections)

**[Part C --- Technical Implementation Plan](#part-c-----technical-implementation-plan)**

-   [79. Architecture](#79-architecture)
-   [80. Technology Stack](#80-technology-stack)
-   [81. Repository Layout](#81-repository-layout)
-   [82. Data Sourcing Plan](#82-data-sourcing-plan)
    -   [82.1 Primary exchange: NSE](#821-primary-exchange-nse)
    -   [82.2 Index membership history](#822-index-membership-history)
-   [83. Ingestion and Document Pipeline](#83-ingestion-and-document-pipeline)
-   [84. Bitemporal Fact Store and the AsOf Gateway](#84-bitemporal-fact-store-and-the-asof-gateway)
-   [85. Engine Framework, Scoring and ML](#85-engine-framework-scoring-and-ml)
-   [86. Backtester](#86-backtester)
-   [87. API and UI](#87-api-and-ui)
-   [88. Schedule (IST)](#88-schedule-ist)
-   [89. Testing and Data Quality](#89-testing-and-data-quality)
-   [90. Delivery Roadmap](#90-delivery-roadmap)
-   [91. Risks and Open Decisions](#91-risks-and-open-decisions)

**[Part D --- Institutional (Buy-Side) Requirements](#part-d-----institutional-buy-side-requirements)**

-   [92. Personas and Jobs to Be Done](#92-personas-and-jobs-to-be-done)
-   [93. Coverage and Research Management](#93-coverage-and-research-management)
-   [94. House Estimates, Scenarios and Price Targets](#94-house-estimates-scenarios-and-price-targets)
-   [95. Idea Pipeline and Investment Committee Workflow](#95-idea-pipeline-and-investment-committee-workflow)
-   [96. Mandate, Limits and Pre-Trade Compliance](#96-mandate-limits-and-pre-trade-compliance)
-   [97. Benchmark-Relative Analytics and Attribution](#97-benchmark-relative-analytics-and-attribution)
-   [98. Factor and Risk Model](#98-factor-and-risk-model)
-   [99. Crowding and Peer Positioning](#99-crowding-and-peer-positioning)
-   [100. Capacity and Liquidity at Fund Scale](#100-capacity-and-liquidity-at-fund-scale)
-   [101. Stewardship, Voting and ESG](#101-stewardship-voting-and-esg)
-   [102. Management and Board Quality Scorecard](#102-management-and-board-quality-scorecard)
-   [103. Competitive Position and Industry Structure](#103-competitive-position-and-industry-structure)
-   [104. Unit Economics and Cash Runway Engine](#104-unit-economics-and-cash-runway-engine)
-   [105. Macro and Earnings Sensitivity Engine](#105-macro-and-earnings-sensitivity-engine)
-   [106. Pre-IPO and Offer-Document Pipeline](#106-pre-ipo-and-offer-document-pipeline)
-   [107. Primary Research and Channel-Check Log](#107-primary-research-and-channel-check-log)
-   [108. Analyst and Idea Performance Scorecard](#108-analyst-and-idea-performance-scorecard)
-   [109. Reporting and Distribution](#109-reporting-and-distribution)
-   [110. Data Governance and Reference Data](#110-data-governance-and-reference-data)
-   [111. Access Control, Audit and Records Retention](#111-access-control-audit-and-records-retention)
-   [112. Integrations](#112-integrations)
-   [113. Non-Functional Requirements](#113-non-functional-requirements)
-   [114. Success Metrics](#114-success-metrics)
-   [115. Prioritisation and Traceability](#115-prioritisation-and-traceability)
-   [116. Impact on the Technical Plan](#116-impact-on-the-technical-plan)

**[Part E --- Additions After the First Build](#part-e-----additions-after-the-first-build)**

-   [117. Company Profile: Products, Website, Brands, Ownership and Deals](#117-company-profile-products-website-brands-ownership-and-deals)
-   [118. Engines on the UI: Radar, Signal Feed, Engine Catalogue and the Company Stance Panel](#118-engines-on-the-ui-radar-signal-feed-engine-catalogue-and-the-company-stance-panel)
-   [118.1 Stance v2 and engine-output tests, 4 October 2026](#1181-stance-v2-and-engine-output-tests-4-october-2026)

------------------------------------------------------------------------

## 1. Purpose

Build an expert-level Indian equity research and opportunity-detection
platform that combines:

-   Market regime analysis
-   Company fundamentals
-   Quarterly and annual historical financials
-   Investor/shareholding intelligence
-   Valuation
-   Earnings and profitability inflection detection
-   Cash-flow quality
-   Technical/price behaviour
-   Sector rotation
-   Corporate actions
-   News and corporate-event intelligence
-   Management commentary
-   Order-book/capacity intelligence
-   ML-based anomaly and opportunity detection
-   LLM-based explanation and research
-   Point-in-time historical reconstruction
-   Backtesting without look-ahead bias

The system is intended to identify companies where the relationship
between **business fundamentals, valuation, expectations and market
price** is changing materially.

It must distinguish:

1.  Good business
2.  Good business at a reasonable valuation
3.  Underpriced improving business
4.  Turnaround
5.  Deep value
6.  Momentum without fundamental support
7.  Value trap
8.  Deteriorating business
9.  Overpriced growth
10. Event-driven situations

The system must never treat an AI score as a guaranteed prediction or
return.

------------------------------------------------------------------------

# 2. Design Principles

## 2.1 Point-in-time correctness

Every metric must have:

-   `period_end`
-   `announcement_date`
-   `available_from`
-   `source`
-   `source_document`
-   `revision_date`
-   `is_restated`
-   `data_version`

Historical models must only consume information whose `available_from`
is earlier than or equal to the simulated decision timestamp.

This prevents look-ahead bias.

## 2.2 Separate business quality from valuation

A company can be:

-   excellent but expensive
-   mediocre but cheap
-   improving and underpriced
-   deteriorating and apparently cheap

Never collapse these into one opaque score.

## 2.3 Explainability first

Every opportunity must show:

-   What changed?
-   When did it change?
-   Why does it matter?
-   What is already priced in?
-   What could invalidate the thesis?
-   Which data supports the conclusion?
-   What should be monitored next?

## 2.4 Avoid survivorship bias

Historical universes must include:

-   companies subsequently delisted
-   companies that failed
-   bankrupt/insolvent companies where historical data is available
-   companies that moved between indices
-   companies that changed names
-   corporate-action-adjusted securities

Do not construct historical universes using today's NIFTY 500
membership.

------------------------------------------------------------------------

# 3. Data Universe

## 3.1 Equity universe

Support:

-   NSE listed equities
-   BSE listed equities
-   Mainboard
-   SME as a separate universe
-   REIT/InvIT as separate asset classes
-   IPOs
-   recently listed companies
-   suspended securities
-   delisted historical securities

Default research universe:

> NSE/BSE mainboard equities excluding instruments with insufficient
> data quality.

## 3.2 Market data

Required:

-   OHLCV
-   adjusted OHLC
-   raw OHLC
-   traded value
-   number of trades
-   delivery quantity
-   delivery percentage
-   market capitalisation
-   free-float market capitalisation
-   52-week high/low
-   all-time high/low
-   VWAP
-   ATR
-   volatility
-   beta
-   relative strength
-   gap statistics
-   price-volume distribution

Frequency:

-   daily
-   weekly
-   monthly

Intraday can be added separately.

------------------------------------------------------------------------

# 4. Company Master

Each company needs a canonical identity.

Fields:

-   `company_id`
-   legal name
-   common name
-   NSE symbol
-   BSE code
-   ISIN
-   CIN
-   sector
-   industry
-   sub-industry
-   market-cap bucket
-   listing date
-   delisting date
-   registered office
-   website
-   promoter group
-   subsidiaries
-   associates
-   joint ventures
-   holding company
-   former names
-   ticker history

Corporate actions must preserve identity across:

-   mergers
-   demergers
-   name changes
-   stock splits
-   bonus issues
-   rights issues
-   preferential allotments

------------------------------------------------------------------------

# 5. Financial Statement Engine

Store historical:

## Income statement

-   revenue
-   other income
-   EBITDA
-   EBIT
-   PBT
-   PAT
-   minority interest
-   EPS
-   diluted EPS
-   exceptional items
-   tax rate

## Balance sheet

-   cash
-   investments
-   receivables
-   inventory
-   working capital
-   gross debt
-   net debt
-   equity
-   goodwill
-   intangible assets
-   fixed assets
-   CWIP

## Cash flow

-   CFO
-   capex
-   FCF
-   acquisitions
-   financing cash flow
-   dividend
-   buybacks

## Ratios

-   gross margin
-   EBITDA margin
-   EBIT margin
-   PAT margin
-   ROE
-   ROCE
-   ROIC
-   ROA
-   asset turnover
-   working-capital days
-   receivable days
-   inventory days
-   payable days
-   CFO/PAT
-   FCF/PAT
-   debt/equity
-   net debt/EBITDA
-   interest coverage

Every metric must support:

-   QoQ
-   YoY
-   3Y CAGR
-   5Y CAGR
-   10Y CAGR
-   rolling 4-quarter
-   rolling 8-quarter
-   rolling 12-quarter

------------------------------------------------------------------------

# 6. Profitability Inflection Engine

This is a first-class engine.

Detect transitions:

-   loss → smaller loss
-   smaller loss → breakeven
-   breakeven → profit
-   profit → accelerating profit
-   negative EBITDA → positive EBITDA
-   EBITDA margin expansion
-   gross-margin expansion
-   operating leverage

Example:

Revenue:

`+12% → +18% → +29%`

EBITDA:

`-20% → -5% → +32%`

Flag:

> PROFITABILITY INFLECTION

Signals:

-   revenue acceleration
-   gross-margin expansion
-   employee-cost leverage
-   fixed-cost absorption
-   EBITDA margin expansion
-   PAT margin expansion
-   CFO improvement
-   FCF improvement

Use confidence levels:

-   Early
-   Emerging
-   Confirmed
-   Mature
-   Reversing

------------------------------------------------------------------------

# 7. Earnings Acceleration Engine

Track:

-   revenue growth acceleration
-   EBITDA growth acceleration
-   PAT growth acceleration
-   EPS growth acceleration
-   quarterly sequential acceleration
-   annual acceleration
-   earnings surprise
-   earnings downgrade
-   earnings revision

Example:

`EPS growth: 8% → 14% → 27% → 41%`

Flag:

> EARNINGS ACCELERATION

Also detect:

> Earnings deceleration

This is equally important.

------------------------------------------------------------------------

# 8. Margin Inflection Engine

Track:

-   gross margin
-   EBITDA margin
-   EBIT margin
-   PAT margin
-   contribution margin
-   segment margins

Detect:

-   sustained expansion
-   temporary expansion
-   commodity-led expansion
-   pricing-led expansion
-   mix-led expansion
-   operating-leverage expansion

Avoid treating one-quarter margin spikes as structural.

------------------------------------------------------------------------

# 9. Operating Leverage Engine

Calculate:

`Δ EBITDA / Δ Revenue`

and:

`Δ EBIT / Δ Revenue`

Flag:

> Revenue +20%, EBITDA +60%

as a strong operating-leverage event.

Also detect negative operating leverage.

------------------------------------------------------------------------

# 10. ROCE / ROIC Inflection Engine

Track:

-   ROCE
-   ROIC
-   incremental ROCE
-   incremental ROIC
-   asset turnover
-   capital employed

Detect:

`ROCE 8% → 12% → 18% → 23%`

Also distinguish:

-   improving ROCE from genuine operating improvement
-   improving ROCE caused by shrinking capital base
-   artificially high ROCE caused by underinvestment

------------------------------------------------------------------------

# 11. Cash-Flow Inflection Engine

Detect:

-   CFO turning positive
-   FCF turning positive
-   FCF margin expansion
-   CFO/PAT divergence
-   capex cycle
-   working-capital release
-   cash conversion

Important alerts:

-   PAT rising but CFO falling
-   PAT rising but FCF negative
-   receivables rising faster than revenue
-   inventory rising faster than revenue

Classify:

-   High-quality earnings
-   Cash-flow questionable
-   Cash-flow inflection
-   Cash-flow deterioration

------------------------------------------------------------------------

# 12. Debt & Deleveraging Engine

Track:

-   gross debt
-   net debt
-   debt/equity
-   net debt/EBITDA
-   interest coverage
-   maturity profile
-   refinancing risk

Detect:

`D/E 1.8 → 1.2 → 0.7 → 0.3`

Flag:

> DELEVERAGING INFLECTION

Also flag:

> Debt-funded growth risk

------------------------------------------------------------------------

# 13. Valuation Engine

Support:

-   P/E
-   forward P/E
-   PEG
-   EV/EBITDA
-   EV/EBIT
-   P/B
-   P/S
-   FCF yield
-   dividend yield
-   EV/FCF
-   market-cap/revenue
-   market-cap/FCF

Compare against:

-   own 3Y history
-   own 5Y history
-   own 10Y history
-   sector
-   industry
-   comparable companies
-   market

Use percentile rather than only absolute multiples.

Example:

`Current PE = 18x`

`5Y PE percentile = 22%`

Flag:

> Valuation below historical range

------------------------------------------------------------------------

# 14. Earnings Expectations / Implied Growth Engine

Reverse-engineer what the current price appears to require.

Estimate:

-   implied EPS CAGR
-   implied revenue CAGR
-   implied margin
-   implied terminal growth
-   implied ROCE

Compare:

`Market-implied FY29 EPS growth = 30%`

versus:

`Fundamental model = 18%`

Flag:

> EXPECTATIONS RISK

Conversely:

`Market implied growth = 10%`

`Fundamental model = 25%`

Flag:

> EXPECTATION GAP / POTENTIAL MISPRICING

------------------------------------------------------------------------

# 15. Undervalued Growth Engine

Identify:

-   earnings growth \> valuation growth
-   EPS CAGR \> PE multiple
-   PEG \< configurable threshold
-   ROCE improving
-   FCF positive
-   balance sheet healthy
-   price below historical valuation range

Output:

> UNDERPRICED GROWTH CANDIDATE

Do not automatically label it a buy.

------------------------------------------------------------------------

# 16. Value Trap Detector

Cheap valuation is not sufficient.

Red flags:

-   declining revenue
-   declining margins
-   falling ROCE
-   rising debt
-   negative FCF
-   receivables spike
-   inventory spike
-   promoter pledge
-   promoter selling
-   customer concentration
-   market-share loss
-   repeated exceptional items
-   auditor qualifications
-   related-party concerns
-   contingent liabilities
-   governance events
-   dilution
-   shrinking industry

Output:

> CHEAP BUT DETERIORATING

or:

> POSSIBLE VALUE TRAP

------------------------------------------------------------------------

# 17. Deep Value Engine

Find:

-   low PE
-   low EV/EBITDA
-   high FCF yield
-   low P/B
-   net-cash companies
-   asset-rich companies
-   subsidiaries whose value may exceed market cap
-   holding-company discounts
-   replacement-value opportunities

But apply the Value Trap Detector before classification.

------------------------------------------------------------------------

# 18. SOTP / Hidden Asset Engine

Support:

-   listed subsidiaries
-   unlisted subsidiaries
-   investment portfolio
-   land
-   cash
-   strategic stakes
-   brands
-   IP
-   infrastructure assets

Calculate:

`Estimated SOTP NAV`

versus:

`Market Capitalisation`

Output:

> SOTP DISCOUNT: 38%

with a full component breakdown.

------------------------------------------------------------------------

# 19. Turnaround Engine

Detect:

-   revenue stabilization
-   cost reduction
-   gross-margin recovery
-   EBITDA recovery
-   PAT recovery
-   debt reduction
-   asset utilization improvement
-   management change
-   capacity restart
-   product-cycle recovery

Stages:

1.  Deterioration
2.  Bottoming
3.  Early turnaround
4.  Confirmed turnaround
5.  Recovery
6.  Mature recovery
7.  Reversal risk

Ather Energy is an example of a company where this engine would be
particularly relevant.

------------------------------------------------------------------------

# 20. Capacity Utilisation Engine

Track:

-   installed capacity
-   current production
-   utilization %
-   expansion
-   commissioning dates
-   capex
-   expected capacity
-   incremental revenue potential

Detect:

`Utilisation 55% → 73% → 88%`

Flag:

> OPERATING LEVERAGE / CAPACITY INFLECTION

Also detect:

> Capacity added but demand not keeping pace.

------------------------------------------------------------------------

# 21. Order Book Engine

Track:

-   order book
-   order inflow
-   order book/revenue
-   order conversion
-   order cancellations
-   customer concentration
-   book-to-bill ratio

Detect:

`Order book +60%`

while:

`Revenue +15%`

Flag:

> FUTURE REVENUE VISIBILITY

------------------------------------------------------------------------

# 22. Investor / Shareholding Intelligence

This is mandatory.

Use quarterly shareholding patterns and corporate disclosures.

SEBI's current LODR framework requires listed entities to submit
shareholding patterns quarterly, generally within 21 days of
quarter-end, with additional disclosure requirements around capital
restructuring. NSE exposes promoter/public categories and detailed
shareholder information.

Track:

## Promoters

-   promoter %
-   promoter group %
-   promoter change QoQ
-   promoter buying
-   promoter selling
-   promoter pledge %
-   pledge change
-   encumbrance
-   promoter lock-in
-   promoter reclassification

## Foreign investors

-   FII/FPI %
-   QoQ change
-   absolute shares
-   concentration
-   new entrants
-   exits

## Domestic institutions

-   mutual funds
-   insurance companies
-   banks
-   PMS/AIF where disclosed
-   other institutional holders

## Public

-   retail
-   HNI
-   non-institutional investors
-   employee trusts

## Significant holders

Track individual disclosed holders:

-   name
-   ownership %
-   change
-   first appearance
-   disappearance
-   cumulative accumulation

## Shareholder concentration

Calculate:

-   top 5 holders
-   top 10 holders
-   promoter concentration
-   institutional concentration
-   free-float concentration

## Shareholding intelligence signals

Examples:

`Promoter +1.2%`

`FII +2.4%`

`Mutual funds +1.1%`

Flag:

> OWNERSHIP ACCUMULATION

But distinguish:

-   genuine buying
-   denominator change
-   bonus/split
-   conversion
-   merger
-   preferential issue

Never interpret percentage changes without corporate-action adjustment.

------------------------------------------------------------------------

# 23. Investor Holding History

For every quarter create a timeline:

  Quarter     Promoter    FII     MF   Retail   Other
  --------- ---------- ------ ------ -------- -------
  Q1             51.2%   8.1%   6.2%    18.4%   16.1%
  Q2               ...    ...    ...      ...     ...

Then show:

-   4-quarter trend
-   8-quarter trend
-   12-quarter trend
-   3-year trend

Detect:

> Institutional accumulation while price is flat

> Promoter accumulation during correction

> Institutional exit despite rising price

> Retail ownership spike

------------------------------------------------------------------------

# 24. Smart Money / Price Divergence Engine

Compare:

-   institutional ownership
-   promoter ownership
-   price
-   volume
-   delivery
-   fundamentals

Important pattern:

`Fundamentals ↑`

`Institutional ownership ↑`

`Price →`

Flag:

> POTENTIAL UNDER-RECOGNITION

Opposite:

`Price ↑`

`Fundamentals →/↓`

`Institutional ownership ↓`

Flag:

> DISTRIBUTION / FUNDAMENTAL DIVERGENCE

------------------------------------------------------------------------

# 25. Technical / Price Engine

Indicators:

-   20/50/100/200 DMA
-   EMA
-   RSI
-   MACD
-   ATR
-   ADX
-   Bollinger Bands
-   volume
-   delivery
-   relative strength
-   price percentile
-   drawdown
-   breakout
-   base formation

Do not let technical indicators dominate fundamental opportunity
detection.

Use them primarily for:

-   confirmation
-   entry timing
-   accumulation/distribution
-   regime detection

------------------------------------------------------------------------

# 26. Relative Strength Engine

Compare stock against:

-   NIFTY 50
-   NIFTY 500
-   sector index
-   industry peers
-   relevant thematic index

Detect:

-   relative-strength inflection
-   long-term outperformance
-   short-term weakness
-   price/fundamental divergence

------------------------------------------------------------------------

# 27. Volume & Delivery Intelligence

Track:

-   volume vs 20D average
-   volume vs 50D average
-   delivery %
-   delivery quantity
-   traded value
-   price-volume relationship

Patterns:

-   price ↑ + volume ↑ + delivery ↑
-   price ↓ + volume ↑ + delivery ↑
-   price ↑ + volume ↓
-   price flat + accumulation

Use multiple-day confirmation to avoid false signals.

------------------------------------------------------------------------

# 28. Sector Rotation Engine

For every sector:

-   revenue growth
-   EPS growth
-   margins
-   ROCE
-   valuations
-   relative strength
-   FII/DII exposure
-   earnings revisions
-   breadth

Output:

-   emerging sectors
-   accelerating sectors
-   expensive sectors
-   deteriorating sectors
-   recovery sectors

Then rank stocks relative to their sector rather than only against the
whole market.

------------------------------------------------------------------------

# 29. Market Regime Engine

Track:

-   NIFTY trend
-   NIFTY 500 breadth
-   advance/decline
-   new highs/lows
-   VIX
-   FII flows
-   DII flows
-   sector breadth
-   market valuation
-   earnings breadth
-   credit conditions
-   INR
-   crude
-   bond yields

Classify:

-   Risk-on
-   Neutral
-   Risk-off
-   Panic
-   Recovery
-   Late-cycle/overheated

Stock signals should be interpreted differently under each regime.

------------------------------------------------------------------------

# 30. Corporate Event Engine

Track:

-   results
-   earnings calls
-   investor presentations
-   annual reports
-   credit-rating changes
-   acquisitions
-   divestitures
-   mergers
-   demergers
-   fund raising
-   QIP
-   preferential allotment
-   rights issue
-   buyback
-   dividend
-   bonus
-   split
-   warrants
-   ESOPs
-   management changes
-   auditor changes
-   resignation of directors
-   regulatory actions
-   legal disputes
-   plant shutdowns
-   fires
-   strikes
-   new factories
-   commissioning
-   major contracts

NSE provides corporate-announcement and financial-results filing
interfaces; the engine should ingest these as primary event sources.

------------------------------------------------------------------------

# 31. Historical Update / Company Timeline Engine

Every company needs a chronological event timeline.

Example:

``` text
2022
IPO
↓
2023
Revenue acceleration
↓
2024
Capacity disruption
↓
2025
Margin recovery
↓
2026
New capacity commissioned
↓
Q3 FY27
Profitability inflection
```

Each event must contain:

-   date
-   event type
-   source
-   affected metric
-   expected impact
-   subsequent observed impact

This is essential for AI training and historical reconstruction.

------------------------------------------------------------------------

# 32. Management Commentary Engine

Process:

-   earnings-call transcripts
-   investor presentations
-   annual reports
-   interviews
-   management guidance

Extract:

-   revenue guidance
-   margin guidance
-   capex guidance
-   capacity guidance
-   order-book guidance
-   demand commentary
-   pricing commentary
-   competition commentary
-   customer commentary

Then compare:

> Management guidance vs actual result

Calculate management guidance accuracy over time.

------------------------------------------------------------------------

# 33. Narrative vs Numbers Engine

Compare the market narrative with measurable data.

Example:

Narrative:

> "Company is struggling."

Numbers:

-   revenue +30%
-   EBITDA +70%
-   FCF positive
-   debt down 50%

Flag:

> NARRATIVE / FUNDAMENTAL DIVERGENCE

Opposite:

Narrative:

> "Fast-growing company."

Numbers:

-   revenue +8%
-   receivables +40%
-   EBITDA -20%
-   FCF negative

Flag:

> NARRATIVE / FUNDAMENTAL WARNING

------------------------------------------------------------------------

# 34. Accounting Quality Engine

Detect:

-   CFO/PAT divergence
-   receivable anomalies
-   inventory anomalies
-   unusual other income
-   exceptional items
-   related-party transactions
-   contingent liabilities
-   auditor qualifications
-   tax anomalies
-   capitalized expenses
-   goodwill growth
-   depreciation anomalies

Output:

-   Clean
-   Watch
-   High accounting risk

This should be an independent risk module.

------------------------------------------------------------------------

# 35. Corporate Governance Engine

Track:

-   promoter pledging
-   auditor resignation
-   independent-director resignation
-   related-party transactions
-   regulatory investigations
-   litigation
-   governance controversies
-   remuneration
-   promoter transactions
-   preferential allotments
-   warrants
-   dilution

Governance risks should reduce opportunity confidence.

------------------------------------------------------------------------

# 36. IPO / Newly Listed Stock Engine

For new listings:

Track:

-   IPO price
-   issue size
-   OFS vs fresh issue
-   promoter dilution
-   anchor investors
-   subscription
-   listing premium/discount
-   post-IPO shareholding
-   lock-ins
-   use of proceeds
-   valuation
-   IPO financial history

Run:

-   30-day
-   90-day
-   180-day
-   1-year
-   2-year

post-listing analysis.

------------------------------------------------------------------------

# 37. Catalyst Engine

Identify future catalysts:

-   capacity commissioning
-   new product
-   new customer
-   order conversion
-   margin recovery
-   debt repayment
-   subsidiary IPO
-   regulatory approval
-   export expansion
-   commodity-price normalization
-   restructuring
-   asset monetization

For each catalyst:

-   expected date
-   probability
-   potential financial impact
-   evidence
-   risk
-   whether already priced in

------------------------------------------------------------------------

# 38. Underpriced Stock Discovery Engine

Create separate opportunity buckets:

## A. Undervalued Growth

Growth ↑ Quality ↑ Valuation reasonable

## B. Profitability Inflection

Loss ↓ Margins ↑ Revenue ↑

## C. Earnings Acceleration

EPS growth accelerating

## D. FCF Inflection

Cash flow turning positive

## E. Deleveraging

Debt falling rapidly

## F. ROCE Inflection

Capital efficiency improving

## G. Capacity Inflection

Utilisation rising

## H. Institutional Accumulation

FII/MF/DII ownership rising

## I. Price/Fundamental Divergence

Fundamentals ↑ Price →

## J. Deep Value

Very low valuation + asset support

## K. Turnaround

Deterioration → stabilization → recovery

## L. SOTP Discount

Asset value \> market value

## M. Cyclical Recovery

Earnings at cyclical bottom

## N. Expectation Gap

Fundamental growth \> market-implied growth

------------------------------------------------------------------------

# 39. Opportunity Score

Do NOT use one score as a trading signal.

Instead calculate independent scores:

``` text
Business Quality              0–100
Growth                        0–100
Earnings Acceleration         0–100
Profitability Inflection      0–100
Margin Inflection             0–100
ROCE Inflection               0–100
Cash Flow Quality             0–100
Balance Sheet                 0–100
Valuation Attractiveness      0–100
Shareholding Intelligence     0–100
Institutional Accumulation    0–100
Relative Strength             0–100
Catalyst Strength              0–100
Governance Quality            0–100
Accounting Quality             0–100
```

Then create profiles rather than a universal winner:

``` text
UNDERVALUED GROWTH
TURNAROUND
PROFITABILITY INFLECTION
DEEP VALUE
QUALITY AT REASONABLE PRICE
EARNINGS ACCELERATOR
FCF INFLECTION
CYCLICAL RECOVERY
```

------------------------------------------------------------------------

# 40. AI / ML Architecture

Use different models for different tasks.

## Supervised ML

Candidates:

-   LightGBM
-   XGBoost
-   CatBoost

Tasks:

-   probability of earnings acceleration
-   probability of margin expansion
-   probability of profitability inflection
-   probability of positive 6/12-month excess return
-   probability of drawdown
-   classification of value traps

## Unsupervised ML

Use:

-   clustering
-   anomaly detection
-   regime clustering

Tasks:

-   identify unusual financial transitions
-   find companies behaving like historical winners
-   detect unusual shareholding changes
-   detect unusual accounting patterns

## Time-series models

Use for:

-   revenue
-   EPS
-   margins
-   capacity
-   cash flow

Candidate models:

-   statistical baselines
-   gradient boosting with lag features
-   temporal deep-learning models only if they demonstrably outperform
    simpler models

## LLM

Use the LLM for:

-   annual-report analysis
-   earnings-call analysis
-   news interpretation
-   management-commentary extraction
-   event classification
-   thesis generation
-   contradiction detection
-   explaining quantitative signals

Do NOT let the LLM directly determine position size or bypass risk
controls.

------------------------------------------------------------------------

# 41. Historical Winner Pattern Engine

Build a historical database of companies that experienced:

-   2x revenue
-   2x EBITDA
-   3x EPS
-   major ROCE improvement
-   debt reduction
-   margin expansion
-   turnaround
-   capacity-led growth

Examples can include companies from different sectors and market-cap
ranges.

For each historical company calculate:

> What did the financial and market data look like 3, 6, 12 and 24
> months before the major rerating?

Then search the current universe for similar patterns.

------------------------------------------------------------------------

# 42. Point-in-Time Backtesting

Every historical simulation must recreate the information set available
at the time.

Example:

``` text
Decision date:
30 Sep 2024

Allowed:
FY24 results available by then
Q1 FY25 results available by then
shareholding available by then
prices through 30 Sep 2024
announcements before 30 Sep 2024

Forbidden:
Q2 FY25 results
FY25 annual report
future share price
later corporate events
future shareholding
```

This is mandatory.

------------------------------------------------------------------------

# 43. Backtest Metrics

Evaluate:

-   CAGR
-   excess return vs NIFTY 50
-   excess return vs NIFTY 500
-   hit rate
-   average winner
-   average loser
-   maximum drawdown
-   Sharpe
-   Sortino
-   turnover
-   transaction costs
-   slippage
-   tax assumptions
-   exposure
-   sector concentration
-   market-cap concentration

Also measure:

-   precision of opportunity detection
-   recall of historical winners
-   false-positive rate
-   value-trap detection rate
-   profitability-inflection detection accuracy

------------------------------------------------------------------------

# 44. Dashboard

## Main dashboard

``` text
MARKET REGIME
NIFTY / NIFTY 500
Breadth
FII/DII
VIX
Sector rotation

OPPORTUNITY RADAR

Profitability Inflection
Earnings Acceleration
Undervalued Growth
FCF Inflection
ROCE Inflection
Turnaround
Deep Value
SOTP Discount
Institutional Accumulation
Expectation Gap

RISK RADAR

Value Traps
Debt Spikes
Accounting Risk
Governance Risk
Earnings Deterioration
Promoter Selling
Institutional Distribution
```

------------------------------------------------------------------------

# 45. Company Detail Page

## Header

-   price
-   market cap
-   sector
-   industry
-   52W high/low
-   valuation
-   liquidity

## Business

-   business description
-   segments
-   competitive position
-   customers
-   geography

## Financial trend

10-year:

-   revenue
-   EBITDA
-   PAT
-   EPS
-   ROCE
-   ROE
-   FCF
-   debt

## Inflection dashboard

-   profitability
-   margins
-   earnings
-   ROCE
-   FCF
-   debt
-   capacity

## Shareholding

-   promoter
-   FII
-   MF
-   DII
-   retail
-   top holders
-   pledge
-   12-quarter trend

## Valuation

-   PE
-   EV/EBITDA
-   P/B
-   FCF yield
-   historical percentile
-   peer comparison
-   implied-growth analysis

## Technical

-   20/50/100/200 DMA
-   RS
-   volume
-   delivery
-   accumulation/distribution

## Events

Chronological company timeline.

## AI thesis

Three sections:

### Why interesting

### What could go wrong

### What to monitor next

------------------------------------------------------------------------

# 46. Historical Update View

For any company allow:

> "What did the engine know on this date?"

Example:

`Aether Industries — 30 Sep 2022`

Show:

-   available financials
-   available shareholding
-   available price
-   available announcements
-   AI signals
-   valuation
-   risks
-   next catalysts

Then allow:

> Compare the historical thesis with what actually happened.

This is extremely important for auditing the AI.

------------------------------------------------------------------------

# 47. Alerts

Generate alerts when:

### Fundamental

-   revenue acceleration
-   EBITDA acceleration
-   PAT acceleration
-   margin expansion
-   ROCE inflection
-   FCF inflection

### Ownership

-   promoter buying
-   promoter selling
-   promoter pledge change
-   FII accumulation
-   MF accumulation

### Valuation

-   PE below historical percentile
-   PEG compression
-   FCF yield expansion
-   valuation below sector

### Price

-   200DMA breakout
-   relative-strength breakout
-   accumulation
-   abnormal volume

### Risk

-   earnings deterioration
-   debt spike
-   promoter pledge
-   auditor issue
-   governance event

------------------------------------------------------------------------

# 48. Data Quality Layer

Every data point must have:

-   source
-   timestamp
-   period
-   original value
-   normalized value
-   adjustment
-   confidence
-   revision history

Priority:

1.  NSE/BSE filings
2.  SEBI/MCA/regulatory filings
3.  Company annual reports
4.  Company investor presentations
5.  Earnings-call transcripts
6.  Exchange announcements
7.  Reliable market-data providers
8.  News sources
9.  Third-party aggregators

Never allow a third-party estimate to overwrite an official reported
number without preserving both.

------------------------------------------------------------------------

# 49. Data Model

Core tables:

``` text
companies
securities
prices_daily
financial_periods
income_statement
balance_sheet
cash_flow
financial_ratios
shareholding_quarterly
shareholders
promoter_transactions
institutional_holdings
corporate_actions
corporate_events
announcements
annual_reports
investor_presentations
earnings_calls
management_guidance
orders
capacity
segments
subsidiaries
valuations
sector_metrics
market_regimes
technical_features
ml_features
ml_predictions
ai_theses
risk_flags
historical_snapshots
backtest_runs
```

------------------------------------------------------------------------

# 50. Feature Store

Create point-in-time features such as:

``` text
revenue_growth_1q
revenue_growth_4q
revenue_cagr_3y
ebitda_growth_4q
pat_growth_4q
eps_acceleration
ebitda_margin_change
roce_change
roic_change
fcf_yield
fcf_growth
net_debt_ebitda
receivable_growth_vs_revenue
inventory_growth_vs_revenue
promoter_change_qoq
fii_change_qoq
mf_change_qoq
institutional_accumulation
pe_percentile_5y
ev_ebitda_percentile_5y
relative_strength_6m
volume_accumulation
capacity_utilization
order_book_growth
earnings_revision
```

------------------------------------------------------------------------

# 51. Research Output

For every detected opportunity generate:

``` text
Company:
Ticker:
Sector:

OPPORTUNITY TYPE:
Profitability Inflection

WHAT CHANGED:
...

WHY IT MATTERS:
...

VALUATION:
...

SHAREHOLDING:
...

PRICE CONFIRMATION:
...

CATALYSTS:
...

RISKS:
...

VALUE-TRAP CHECK:
PASS / FAIL

CONFIDENCE:
Early / Emerging / Confirmed

NEXT DATA POINT:
Q2 FY27 results

INVALIDATION CONDITIONS:
...
```

------------------------------------------------------------------------

# 52. Core Rule

The engine must never output:

> "This stock will go up."

It should output:

> "These measurable conditions have changed, this is how unusual the
> change is historically, this is what the current valuation assumes,
> these are the supporting and contradictory signals, and these are the
> next conditions to monitor."

The final investment decision remains with the investor.

------------------------------------------------------------------------

# 53. MVP Priority

## Phase 1

Build first:

1.  NSE/BSE price data
2.  Financial statements
3.  10-year historical ratios
4.  Valuation engine
5.  Profitability Inflection
6.  Earnings Acceleration
7.  Margin Inflection
8.  ROCE Inflection
9.  FCF Inflection
10. Debt/Deleveraging
11. Shareholding
12. Promoter pledge
13. FII/MF/DII changes
14. Sector comparison
15. Value Trap Detector
16. Historical company timeline

## Phase 2

Add:

17. Order book
18. Capacity
19. Corporate events
20. management guidance
21. earnings-call NLP
22. institutional accumulation
23. expectation-gap model
24. SOTP
25. catalyst engine

## Phase 3

Add:

26. ML prediction models
27. historical pattern matching
28. point-in-time backtesting
29. portfolio simulator
30. regime-aware models
31. LLM research agent
32. automated research reports

------------------------------------------------------------------------

# 54. Final Objective

The system should be exceptionally good at finding situations like:

``` text
                 PRICE
                   │
                   │
                   │       ← market hasn't fully reacted
                   │
FUNDAMENTALS ──────┼─────────────── ↑
                   │
                   │
                   ▼

Revenue            ↑
EBITDA             ↑↑
EPS                ↑↑↑
Margins            ↑
ROCE               ↑
FCF                ↑
Debt               ↓
Institutional      ↑
Valuation          reasonable
```

The highest-value discovery pattern is:

> **Fundamental improvement begins → multiple independent indicators
> confirm it → ownership/price begins confirming → valuation remains
> reasonable → market recognition follows.**

The system should also be equally capable of detecting the opposite:

> **Price rises → fundamentals deteriorate → cash flow weakens →
> institutions exit → valuation expands → value-trap/overvaluation
> risk.**

That symmetry is essential for a robust Indian equity intelligence
platform.

------------------------------------------------------------------------

# Part B --- Additional Components

Sections 55--78 fill gaps in sections 1--54. Each states which existing
section it extends. Regulatory timelines, tax rates and thresholds quoted
below change by circular; store them as dated configuration and verify
against the current circular before relying on them.

------------------------------------------------------------------------

# 55. Sector-Specific Financial Templates

Extends §5. The generic template (EBITDA, ROCE, net debt/EBITDA,
working-capital days, CFO/PAT) is meaningless for lenders and insurers,
which are roughly a third of index weight. Without this, every bank
looks like a "debt spike" and a "cash-flow questionable" company.

Each company is assigned one template; engines read the template to
decide which metrics apply.

| Template | Core metrics | Valuation anchor |
|---|---|---|
| Bank | NII, NIM, PPOP, credit cost, GNPA, NNPA, provision coverage, slippage ratio, restructured book, CASA, credit/deposit ratio, CET1/CRAR, cost/income, ROA | P/B vs ROE, P/adjusted book |
| NBFC / HFC | AUM growth, spread, stage 2/3 assets, ECL coverage, collection efficiency, borrowing mix, ALM gaps, leverage, ROA | P/B vs ROE |
| Life insurance | APE, VNB, VNB margin, persistency (13M/61M), embedded value, RoEV, solvency | P/EV |
| General insurance | GWP, loss ratio, combined ratio, investment yield, solvency | P/B, P/E |
| AMC / broker / exchange | AUM and mix, yield on AUM, active clients, ADTO, operating margin | P/E, % of AUM |
| Non-financial (default) | §5 as written | §13 as written |

Rules:

-   §6--§12 inflection engines run only on metrics the template declares.
-   Lenders get their own inflections: **asset-quality inflection**
    (slippages and credit cost falling), **NIM inflection**, **ROA
    inflection**, **capital-raise risk** (CET1 near regulatory minimum).
-   Holding companies and conglomerates are routed to §18 SOTP first.

------------------------------------------------------------------------

# 56. Operating KPI Engine

Extends §20--§21. Capacity and order book are two instances of a general
problem: each industry has non-financial KPIs that lead the P&L.

| Industry | Leading KPIs |
|---|---|
| IT services | deal TCV, constant-currency growth, headcount, attrition, utilisation |
| Autos | monthly wholesale volumes, retail registrations, mix, discounts |
| Cement / metals | volume, realisation per tonne, EBITDA per tonne, fuel cost |
| Retail / QSR | same-store sales growth, store count, revenue per sq ft |
| Telecom | ARPU, subscribers, churn, data usage |
| Pharma | US generics revenue, ANDA approvals, USFDA inspection status |
| Real estate | pre-sales, collections, launches, net debt |
| Hotels / aviation | RevPAR, occupancy, load factor, yield |
| Capital goods | order inflow, order book, execution rate (§21) |
| Manufacturing | capacity and utilisation (§20) |

Store as a generic `operating_kpi(company_id, kpi, period, value, unit,
available_from, source_doc)` table rather than one table per KPI. KPIs
come from investor presentations and monthly business updates, so most
are extracted by the document pipeline (§83), not from XBRL.

------------------------------------------------------------------------

# 57. Reporting-Basis and Normalisation Rules

Extends §5 and §48. These are the rules where Indian filings quietly
break naive pipelines.

-   **Consolidated vs standalone.** Store both; consolidated is the
    default for analysis, standalone only where consolidated is not
    filed. Never mix bases inside one time series.
-   **Units.** Filings report in lakh, crore or million, sometimes
    changing between years. Normalise to ₹ crore at ingestion and keep
    the original value and unit.
-   **Fiscal year.** Apr--Mar is default but not universal (Dec and Jun
    year-ends exist). Key everything by `period_end`, never by
    "Q1/Q2" labels.
-   **Q4 is a balancing figure** (full year minus nine months) and
    absorbs year-end adjustments; flag Q4 anomalies separately.
-   **Balance sheet and cash flow are half-yearly** for most companies.
    Quarterly CFO/FCF does not exist; §11 must run on half-year and TTM
    periods. SME-board companies report results half-yearly only.
-   **TTM construction** from quarterly P&L; for half-yearly reporters
    from H1 + H2.
-   **Exceptional and one-off items.** Keep reported PAT and an
    `adjusted_pat` that strips exceptionals, one-off tax items and
    discontinued operations. Growth and inflection engines use adjusted
    figures; both are displayed.
-   **Accounting-regime breaks.** Ind AS adoption, Ind AS 116 (leases
    inflate EBITDA and debt), and demerger/merger restatements create
    series breaks. Mark the break; do not compute growth across it
    without a restated comparable.
-   **Share count.** EPS, market cap and per-share values use the share
    count as of the decision date, adjusted for splits/bonuses, with
    dilution from warrants, convertibles and ESOPs tracked separately.
-   **Filing deadlines** (currently 45 days after quarter-end, 60 days
    for the audited annual result) define the expected-by date; a late
    filing is itself a governance signal for §35.

------------------------------------------------------------------------

# 58. Consensus, Revisions and Results-Reaction Engine

Extends §7 and §14. §7 lists "earnings surprise" and "earnings revision"
but neither exists without an expectations dataset.

Track:

-   consensus revenue / EBITDA / EPS by fiscal year, with number of
    estimates and dispersion
-   revision breadth (upgrades ÷ downgrades) and magnitude over 1M / 3M
-   target-price and rating changes
-   surprise vs consensus; where no coverage exists, surprise vs a
    statistical baseline (seasonal random walk on YoY growth)
-   **results-day reaction**: 1-day and 3-day excess return and volume
    after the result
-   **post-earnings drift**: excess return over the following 20 / 60
    days
-   pre-result run-up (was the result already priced in?)

Flags:

> POSITIVE SURPRISE, MUTED REACTION

> BEAT BUT SOLD (the market is reading something the headline misses)

> UNCOVERED COMPANY WITH ACCELERATING RESULTS

Coverage itself is a feature: analyst count, and first-time initiation
of coverage, are strong under-recognition indicators for §24.

------------------------------------------------------------------------

# 59. Forensic Score Pack

Extends §34. Adds standard, backtestable scores and India-specific
checks so "Clean / Watch / High risk" is computed, not judged.

Standard scores:

-   Beneish M-score (earnings manipulation)
-   Piotroski F-score (fundamental strength, 0--9)
-   Altman Z-score, emerging-market variant (distress)
-   Sloan accruals ratio
-   cash-conversion over rolling 3 and 5 years (smooths working-capital
    timing)

India-specific checks:

-   interest income ÷ average cash and investments implausibly low
    (cash may not be real)
-   cash taxes paid ÷ P&L tax persistently low
-   CWIP ageing and capitalised interest rising without commissioning
-   loans, advances and guarantees to related parties and group
    companies; inter-corporate deposits
-   royalty, brand fees and management fees paid to promoter entities
    as % of PAT
-   managerial remuneration as % of PAT
-   contingent liabilities ÷ net worth
-   receivables older than six months; unbilled revenue growth
-   audit fee size and growth, auditor tenure and standing, material
    subsidiaries audited by other firms
-   CARO remarks, key audit matters, emphasis-of-matter paragraphs
-   frequent changes in accounting policy, useful lives or segment
    definitions
-   mid-term auditor, CFO or company-secretary resignation

Output per check: value, peer percentile, 5-year trend, and the source
page. Lender-specific forensics (evergreening, divergence vs regulator
assessment, low provision coverage) live in the §55 templates.

------------------------------------------------------------------------

# 60. Capital Allocation Engine

New. Long-run returns depend on what management does with cash; nothing
in §1--§54 measures it.

Track over rolling 5 and 10 years:

-   cumulative CFO split into capex, acquisitions, dividends, buybacks,
    debt repayment, cash build-up
-   reinvestment rate and incremental ROIC on that reinvestment
-   acquisition record: price paid, subsequent goodwill impairment,
    ROCE before and after
-   equity dilution history: QIPs, preferential issues, warrants, ESOP
    burn; price of issue vs later price
-   unrelated diversification
-   payout consistency

Classify:

-   Compounder (high reinvestment at high incremental ROIC)
-   Cash returner
-   Empire builder
-   Serial diluter
-   Cash hoarder

------------------------------------------------------------------------

# 61. Cyclical and Commodity Linkage Engine

Supplies the missing engine behind bucket M (Cyclical Recovery) and the
"commodity-led expansion" distinction in §8.

-   Map each company to its input and output commodities and macro
    drivers (crude, gas, steel, copper, aluminium, palm oil, cotton,
    sugar, USD/INR, interest rates, monsoon, government capex), with
    estimated sensitivity.
-   Track product spreads where they exist (refining cracks, steel
    spreads, chemical spreads, cement price less fuel cost).
-   Compute **normalised (mid-cycle) earnings**: average margin and ROCE
    over a full cycle applied to current capacity.
-   Locate the cycle position: margin percentile vs own 10-year range,
    industry capacity additions, industry utilisation.

Rules:

-   For cyclicals, a low P/E at peak margins is a warning and a high P/E
    at trough margins can be an opportunity. The §13 percentile logic
    must use normalised earnings for companies tagged cyclical.
-   Attribute each margin change into price, input cost, mix and
    operating leverage where disclosures allow.

Flag:

> CYCLICAL TROUGH: margins in bottom quintile, spreads turning, balance
> sheet survives the downturn

> PEAK-EARNINGS RISK

------------------------------------------------------------------------

# 62. High-Frequency and Alternative Data Engine

New. Quarterly results arrive 30--60 days late; these series move
monthly or faster and lead them.

-   monthly auto dispatches (company releases) and vehicle
    registrations (VAHAN), including EV registrations by maker
-   quarterly business updates published before results (banks,
    retailers, some consumer companies)
-   GST collections, e-way bills, power demand, rail freight, port
    volumes, air traffic
-   bank credit and deposit growth by sector
-   cement, steel and fuel price trackers
-   USFDA inspection outcomes, warning letters, import alerts, ANDA
    approvals
-   government tender awards and order announcements
-   trade data and anti-dumping / safeguard duty investigations
-   commodity and FX prices (feeds §61)

Each series maps to the companies or industries it informs, with a
measured historical lead/lag correlation to reported revenue. A series
with no demonstrated relationship is displayed but not scored.

------------------------------------------------------------------------

# 63. Relationship Graph and Read-Through Engine

New. Extends the Company Master (§4).

Edges:

-   competitor / peer (classification plus business-description
    similarity)
-   customer / supplier
-   promoter group and common-promoter entities
-   parent / subsidiary / associate / JV
-   common directors, common auditor
-   global peers and global customers

Uses:

-   **Read-through.** When a company reports, generate expectations for
    unreported peers, customers and suppliers. Peers reporting early in
    the season inform those reporting late.
-   **Peer sets** for every relative comparison in §13, §26 and §28.
-   **Group contagion.** A governance or credit event at one group
    entity raises risk at the others.
-   **Hidden exposure.** Customer concentration and single-supplier
    dependence for §16.

------------------------------------------------------------------------

# 64. Policy, Regulation and Theme Engine

New. A large share of Indian sector reratings are policy-driven.

Track:

-   Union Budget allocations and tax changes
-   production-linked incentive schemes: eligibility, thresholds,
    disbursements
-   import duties, anti-dumping duties, quality-control orders, export
    restrictions
-   sector regulators: RBI (lender norms, risk weights), SEBI (market
    intermediaries), TRAI, NPPA (drug price caps), CERC/SERC (tariffs),
    IRDAI, PNGRB
-   GST rate changes
-   government capex and defence-indigenisation lists
-   state-level policy where material (excise, mining, real estate)

Each policy event is linked to affected industries and companies with a
direction and an estimated earnings impact, and becomes a §37 catalyst
or a §16 risk.

Themes are maintained as explicit, versioned company baskets so that
theme breadth, relative strength and valuation can be tracked like a
sector in §28.

------------------------------------------------------------------------

# 65. Insider, Deal and Monthly Fund-Holding Engine

Extends §22--§24. Quarterly shareholding is up to 111 days stale; these
sources are days or weeks old.

-   **Insider-trading disclosures** (promoters, directors, designated
    persons): buyer, quantity, value, mode (market, off-market, ESOP,
    pledge invocation). Open-market purchases by promoters are the
    signal; ESOP exercises and inter-se transfers are noise.
-   **Substantial-acquisition disclosures**: crossings of 5 % and
    subsequent 2 % changes.
-   **Pledge creation, release and invocation** as events, not only the
    quarterly percentage.
-   **Bulk and block deals** daily, with counterparty names resolved to
    canonical investor entities.
-   **Mutual-fund monthly portfolios**: scheme-level holdings, giving a
    monthly institutional-ownership series, number of schemes holding,
    new entries and complete exits.
-   **Named-investor tracking**: holders above 1 % appear by name in the
    quarterly pattern; maintain a canonical investor entity so a holder
    can be followed across companies.
-   **FPI sector allocation** (fortnightly) for §28.

Signals:

> CLUSTER INSIDER BUYING (several insiders, open market, during a
> drawdown)

> FIRST-TIME FUND ENTRY (scheme count rising from a low base)

> PLEDGE INVOCATION

Entity resolution is the hard part: the same investor appears under
many spellings and vehicles. Maintain an alias table; never match on raw
strings.

------------------------------------------------------------------------

# 66. Supply Overhang and Forced-Flow Engine

Extends §36. Price is often driven by known, dated, non-fundamental
supply and demand.

Supply:

-   lock-in expiries after listing (anchor investors, pre-IPO
    shareholders, promoters), with shares unlocked as % of free float
-   private-equity / venture holders past their typical holding period
-   promoter stake above the minimum-public-shareholding limit
    (a forced sale is coming)
-   pending warrant conversions, convertible conversions, QIP and OFS
    announcements, ESOP vesting

Demand:

-   index inclusion and exclusion (NSE, BSE, MSCI, FTSE) with estimated
    passive flow as multiples of average daily volume
-   half-yearly large/mid/small-cap reclassification used by mutual
    funds, which forces scheme-level buying and selling
-   F&O segment inclusion and exclusion
-   open buybacks and open offers

Output: a dated calendar per company, and a flag on any opportunity
where a large unlock falls inside the thesis horizon.

------------------------------------------------------------------------

# 67. Special Situations Engine

Supplies the missing engine for category 10 (event-driven) in §1.

-   demergers: parent and spun-off entity, record date, expected listing,
    forced selling in the smaller entity
-   mergers and schemes of arrangement: swap ratio, spread to implied
    value, approval stage
-   buybacks: tender vs open-market, price, size, acceptance-ratio
    estimate
-   open offers and delisting offers: offer price, floor price,
    reverse-book-building status
-   rights issues: terms, promoter participation
-   insolvency resolutions and post-resolution relistings
-   holding-company simplifications and subsidiary IPOs (links §18)

Each situation is a structured record with a timeline of regulatory
steps, an implied return if completed, and the break risk.

------------------------------------------------------------------------

# 68. Credit and Distress Engine

Extends §12. Credit markets and rating agencies usually see trouble
before equity does.

-   rating actions and outlook changes from all agencies, per
    instrument; "issuer not cooperating" status
-   rating rationales parsed for liquidity, covenant and refinancing
    language
-   disclosed defaults and delays on loans and debt securities
-   short-term debt and commercial-paper dependence vs liquid assets
-   debt maturing within 12 months ÷ (cash + expected CFO)
-   implied cost of debt (finance cost ÷ average borrowings) rising
-   promoter pledge with falling price (margin-call spiral)
-   Altman Z from §59

Output: distress probability band, and a hard gate that prevents a
company in the top distress band from appearing in any opportunity
bucket except Turnaround, where it is labelled explicitly.

------------------------------------------------------------------------

# 69. Investability, Liquidity and Surveillance Filter

New. An opportunity that cannot be bought in size is not one.

Per company, per day:

-   median traded value over 20 / 60 days, and days-to-build a position
    of a configured size at a configured participation rate
-   free float and free-float market cap
-   impact-cost proxy (spread, or Amihud illiquidity)
-   price band (circuit limit), and frequency of circuit-locked days
-   surveillance status: ASM / GSM / ESM stage, trade-for-trade segment
-   suspension history
-   F&O eligibility and ban status

Use:

-   every opportunity displays an investability grade
-   the default radar hides names failing a configurable liquidity floor;
    they remain reachable in a separate "illiquid" view
-   surveillance-list entry is an alert and a risk flag
-   the backtester (§86) uses the same data to refuse untradeable fills

## 69.1 Hard exclusions by NSE series and surveillance list

Some securities are removed before any engine runs. They never appear
in the radar, in an opportunity bucket or in a backtest universe; they
stay visible only in the risk radar, marked "excluded" with the reason.

The exclusion list is data (`exclusion_rule`: NSE series and NSE
surveillance lists), dated like every other rule so the backtest applies
the list that was in force on each date. **NSE data only**; no BSE feed
is used.

| NSE label | Meaning | Default | Count on 2026-10-01 |
|---|---|---|---|
| NSE series `BE`, `BZ` | Trade-for-trade; `BZ` is trade-for-trade for non-compliance | **Exclude** | 234 + 27 |
| NSE series `ST`, `SZ` | SME trade-for-trade equivalents | **Exclude** | 86 + 1 |
| NSE ESM list, any stage | Enhanced Surveillance Measure (micro-caps) | **Exclude** | 256 |
| NSE GSM list, any stage | Graded Surveillance Measure | **Exclude** | 77 |
| NSE ASM list (long and short term) | Additional Surveillance Measure | Keep; input to §69.2 | 139 + 84 |
| NSE series `SM` | SME platform | Separate universe (§3.1) | 391 |

Together these exclude 433 NSE securities on 2026-10-01 (a security
can match several rules).

NSE has no group literally named "B", "C" or "E"; those are BSE-style
labels, and BSE is not used. "E group" is implemented as NSE's `BE`
series plus the ESM list. Nothing is lost by dropping BSE's groups:
when BSE's trade-for-trade and non-compliant groups were applied as
well, the NSE exclusion count stayed at 433, because every NSE-listed
stock in those groups was already in `BE`/`BZ` or under ESM/GSM.
Everything else is judged by the detector in §69.2 on its own
behaviour rather than by a group label.

Series, price band and surveillance stage are stored per
security per day as bitemporal facts. The surveillance lists and
`sec_list.csv` (price bands) are current-only files, so they are
snapshotted daily from day one; their history starts when ingestion
starts.

## 69.2 Scam and manipulation detector

New. Purpose: keep operator-driven and pump-and-dump stocks out of the
opportunity set, where a rising price and "improving" numbers would
otherwise score well. Runs nightly on every security that survives
§69.1. It is a gate applied after bucketing, alongside risk (§16, §59,
§68) and investability.

**Price and volume signals** (daily bhavcopy, price bands)

-   share of days closing locked at the band limit over 60 and 250 days;
    longest run of consecutive upper-circuit days
-   price multiple over 6 and 12 months against the change in reported
    revenue and operating profit over the same period
-   traded value as a fraction of market cap, and number of trades per
    day: a large market cap moving on a handful of trades
-   delivery percentage through the run-up versus the stock's own
    history
-   the reversal shape: a run of lower circuits following the run-up
-   market cap divided by trailing revenue and by net worth, flagged
    when extreme and revenue is negligible

**Ownership signals** (shareholding, insider, pledge, takeover filings)

-   promoter holding low, or falling while the price rises; promoter
    reclassified as public
-   no institutional holders; public float concentrated in a few
    non-institutional names
-   number of shareholders rising sharply while large holders reduce
-   preferential allotments or warrants to non-promoter entities well
    below market price, and the lock-in expiry date (§66)
-   promoter pledge created or raised during the run-up

**Counterparty network** (bulk and block deals, §63 graph)

-   client names that recur as bulk-deal buyers or sellers across
    several flagged stocks; a stock inherits risk from the entities
    trading it
-   the same names appearing as preferential allottees and later as
    bulk-deal sellers

**Corporate-behaviour signals** (announcements, corporate actions)

-   company name or object-clause change into a fashionable theme
    without a matching change in revenue mix
-   splits and bonus issues in quick succession on a small company
-   a stream of order-win, MoU and tie-up announcements whose stated
    value never appears in later reported revenue
-   exchange queries on price movement or volume spurt, and the
    company's replies
-   auditor, CFO, company-secretary or independent-director
    resignations; a very small audit firm for the reported scale
-   late or missed results and shareholding filings

**Financial-reality signals** (results; extends §59)

-   revenue, employee cost and fixed assets negligible against market
    cap
-   revenue that is mostly low-margin trading, with receivables about
    equal to revenue and operating cash flow persistently negative
-   other income exceeding operating income; loans and advances the
    largest asset

**Regulatory signals**

-   ASM stage, and any prior ESM, GSM or trade-for-trade episode
-   SEBI interim and final orders naming the company, promoters or
    counterparties
-   past suspension

**Output**

-   `scam_risk_score` 0--100 with class **Clean / Watch / Suspect /
    Avoid**, plus every fired signal with its value, peer percentile and
    source document.
-   **Suspect** and **Avoid** are removed from the radar and from every
    opportunity bucket regardless of other scores. **Watch** is shown
    with the flag attached.
-   A class change is an alert. For a name already held or under
    research it is also a mandatory review trigger (§73).

**Method**

-   Rules first, each with an explicit threshold; this is the baseline.
-   A supervised model later (§85), trained on point-in-time labels:
    SEBI orders, GSM entry, suspension, and a fall of more than 80%
    within 24 months of a flagged run-up.
-   Judged in the backtester (§86) on whether flags fired **before** the
    collapse: lead time, precision and recall, and the number of
    legitimate multi-baggers wrongly flagged.

Additional tables:

``` text
security_group_history   -- series, group, band, surveillance stage per day
scam_signals             -- one row per security, signal, date
scam_scores              -- score and class per security per day
deal_counterparties      -- normalised client names from bulk/block deals
regulatory_orders        -- SEBI and exchange orders, linked entities
```

Data status: every exchange input above was confirmed available from
NSE on 2026-10-01 (§82.1). The SEBI orders feed has not been probed
yet, and deal client names are free text that needs normalisation
before the network signals are reliable.

Delivery: §69.1 and the rule-based detector ship with the §69 filter in
Phase 2 (§90); the network signals and the model follow in Phase 5.

------------------------------------------------------------------------

# 70. Derivatives Signal Engine

Extends §25, for the F&O-eligible subset only.

-   futures open-interest change vs price: long build-up, short
    build-up, long unwinding, short covering
-   implied volatility rank, and straddle-implied move into results
    compared with the stock's historical results-day moves
-   put/call skew
-   market-wide position limit utilisation

Confirmation and timing only, on the same footing as §25.

------------------------------------------------------------------------

# 71. Document Diff and Language-Change Engine

Extends §32--§33. What changed between two documents is more
informative than either document.

-   **Annual report diff, year on year:** risk factors added or removed,
    changes in accounting policies, auditor's report wording, key audit
    matters, related-party schedule, contingent liabilities, segment
    definitions, director and KMP changes.
-   **Concall language change, quarter on quarter:** topics that
    appeared or disappeared, guidance that was dropped rather than
    revised, hedging language, share of analyst questions deflected.
-   **Guidance ledger:** every forward-looking statement stored with
    its date, metric, value/range and horizon, then scored against
    actuals (feeds the accuracy measure in §32).
-   **Presentation KPI continuity:** a KPI that management stops
    disclosing is a signal.

Flag:

> GUIDANCE QUIETLY WITHDRAWN

> NEW KEY AUDIT MATTER

> DISCLOSURE DISCONTINUED

------------------------------------------------------------------------

# 72. Signal Ledger and Outcome Tracking

New, and required from the first day any engine runs. Backtests can be
overfitted; a live record cannot.

-   Every signal, score and thesis is written once to an append-only
    ledger with timestamp, engine version, inputs and price at
    emission. Nothing is edited or deleted.
-   Each record is automatically marked to outcome at 1 / 3 / 6 / 12 /
    24 months: absolute return, excess return vs sector and size
    benchmark, maximum drawdown, and whether its invalidation condition
    fired.
-   Per engine and per bucket: live hit rate, average excess return,
    time-to-payoff, decay curve, compared against the backtest
    expectation.
-   An engine whose live performance falls outside its backtest
    confidence band is flagged for review.

This is what makes §46 ("what did the engine know") trustworthy for the
live period, and it cannot be backfilled later.

------------------------------------------------------------------------

# 73. Thesis Lifecycle and Monitoring

Extends §51. A thesis is a tracked object, not a generated report.

States:

`Candidate → Watching → Active → Confirmed → Closed (played out /
invalidated / expired)`

Each thesis holds:

-   the claims, each tied to a measurable metric and threshold
-   invalidation conditions, encoded as machine-checkable rules
-   the next expected data point and its expected-by date
-   the user's own notes and decision (acted / passed / why)

On every new data point the engine re-evaluates each open thesis and
reports: claim confirmed, claim weakened, invalidation fired, or
overdue data. Closed theses feed a post-mortem view: which claim types
and which engines were right.

------------------------------------------------------------------------

# 74. Portfolio Construction and Risk Layer

Specifies item 29 of §53 (portfolio simulator).

-   position sizing from conviction, liquidity (§69) and volatility,
    with hard caps per stock, sector, promoter group and market-cap
    bucket
-   exposure report: sector, size, factor (value, quality, momentum,
    low-volatility), opportunity-bucket mix
-   correlation and concentration (top-5 weight, HHI)
-   drawdown and stress scenarios replayed from history
-   regime overlay (§29): gross exposure and bucket mix guidance per
    regime, as a suggestion
-   tax-lot awareness: holding-period status and the tax cost of an
    exit
-   overlap check of a new candidate against existing holdings

Consistent with §40 and §52, this layer suggests and constrains; it
does not place orders.

------------------------------------------------------------------------

# 75. Research Workbench

Extends §44--§45.

-   **Screener / query builder** over any feature in the store, with
    saved screens, and "as of date" so a screen can be replayed
    historically.
-   **Natural-language query** ("mid-caps with ROCE inflection and
    falling pledge where mutual funds entered in the last two
    quarters") translated to a structured filter that is shown to the
    user and editable; the model never returns numbers it did not read
    from the database.
-   **Compare view**: two to five companies side by side across every
    panel.
-   **Document Q&A** per company with page-level citations.
-   **Watchlists, notes and tags**, and export of any table to CSV /
    Excel.
-   **Results-season console**: who reports today, flash summary within
    minutes of filing, changes to open theses.
-   **Daily digest**: new signals, changed stages, fired invalidations,
    upcoming events for watched names.

------------------------------------------------------------------------

# 76. Model Governance

Extends §40.

ML:

-   every model has a model card: target, features, training window,
    validation scheme, metrics, known weaknesses
-   a model ships only if it beats the rule-based engine and a simple
    factor composite out of sample
-   probabilities are calibrated and shown with the base rate
-   per-prediction feature attributions are stored with the prediction
-   feature and prediction drift monitored; scheduled retraining
-   count and record every experiment so backtest results can be
    discounted for multiple testing

LLM:

-   every extraction and thesis records model, prompt version, input
    document hashes and output
-   numbers shown to the user come from the database; generated text is
    checked so that every figure in it matches a supplied fact
-   a hand-labelled evaluation set per task; a prompt or model change
    must pass it before deployment
-   extracted values carry a confidence and are cross-checked against
    structured filings where both exist

------------------------------------------------------------------------

# 77. Compliance, Licensing and Disclaimers

New.

-   **Personal research vs distribution.** Sharing stock-specific
    views or scores with others can fall under SEBI's research-analyst
    and investment-adviser regulations. Decide the intended audience
    before building any sharing feature and take advice if it is
    anything other than personal use.
-   **Data licensing.** Exchange data, vendor fundamentals and
    consensus estimates carry redistribution limits. Record the licence
    for each source in the source registry; anything not licensed for
    redistribution must not leave the system.
-   **Scraping.** Unofficial exchange endpoints are rate-limited and
    change without notice; build on published archive files and
    licensed feeds, and treat scraped sources as replaceable.
-   **Only public information.** The system ingests published
    disclosures only.
-   **Disclaimer** on every output, consistent with §52.
-   **Audit trail**: §72 doubles as the record of what was shown and
    when.

------------------------------------------------------------------------

# 78. Extensions to Existing Sections

Changes implied by §55--§77.

**§38 opportunity buckets --- add:**

-   O. Asset-Quality Inflection (lenders)
-   P. Special Situation
-   Q. Policy / Theme Beneficiary
-   R. Under-Covered Accelerator (no or thin analyst coverage)
-   S. Capital-Allocation Change (first buyback, debt-free, payout
    step-up)

**§39 scores --- add:** Capital Allocation, Credit/Distress,
Investability, Cyclical Position, Expectations/Revisions, Insider
Activity.

**§47 alerts --- add:** insider cluster buying, pledge invocation,
rating action, surveillance-list entry/exit, lock-in expiry within 30
days, index/reclassification change, guidance withdrawn, new key audit
matter, thesis invalidation fired, late results filing, auditor/CFO
resignation.

**§49 tables --- add:**

``` text
source_registry
raw_documents
company_template
operating_kpi
consensus_estimates
estimate_revisions
results_reaction
forensic_scores
capital_allocation
commodity_map
commodity_prices
alt_data_series
alt_data_company_map
company_relationships
policy_events
theme_baskets
insider_trades
sast_disclosures
pledge_events
bulk_block_deals
mf_scheme_holdings
investors
investor_aliases
supply_events
index_membership_history
special_situations
credit_ratings
defaults_disclosures
liquidity_daily
surveillance_status
derivatives_daily
document_diffs
guidance_ledger
signal_ledger
signal_outcomes
theses
thesis_claims
portfolio_positions
model_registry
llm_runs
```

**§50 features --- add:**

``` text
gnpa_change_4q
credit_cost_change
nim_change
piotroski_f
beneish_m
altman_z
accruals_ratio
cash_yield_gap
incremental_roic_3y
dilution_3y
margin_percentile_10y
normalised_pe
eps_revision_3m
revision_breadth
surprise_vs_baseline
results_day_excess_return
analyst_count
insider_net_buy_6m
mf_scheme_count_change
pledge_change_event
unlock_pct_float_90d
passive_flow_adv_multiple
rating_change_12m
median_traded_value_60d
days_to_build
asm_stage
guidance_accuracy
concall_tone_change
peer_readthrough_surprise
policy_exposure
```

------------------------------------------------------------------------

# Part C --- Technical Implementation Plan

Assumptions, each changeable: a single-user research tool run by one
developer; daily frequency (no intraday); no order execution; one
Linux host; free exchange and public sources only, with no paid
fundamentals vendor (§82.1). If the platform is built for an
investment team rather than one person, §116 lists what changes.

------------------------------------------------------------------------

# 79. Architecture

``` text
 SOURCES            exchange archives · exchange filings/XBRL · public releases
                    fund portfolios · ratings · alt data · documents (PDF/audio)
                                         │
 BRONZE   raw/      immutable files, content-hashed, fetched_at, source_registry
                                         │  parse + validate (Pydantic)
 SILVER   Postgres  bitemporal facts, events, documents, identities   ◄── LLM extraction
                                         │  AsOf(t) gateway  ── the only read path
 GOLD     Parquet   point-in-time feature store (partitioned by as-of date)
                                         │
 ENGINES            rule engines → signals → scores → buckets      ML models
                                         │
 LEDGER   Postgres  append-only signals, theses, outcomes
                                         │
 SERVE              FastAPI + server-rendered UI · alerts · digest
```

Two rules shape everything else:

1.  **One read path.** Engines, models, the UI and the backtester all
    read through `AsOf(t)`. Production is a backtest with `t = now`.
    There is no separate "live" code path to drift from the tested one,
    and look-ahead becomes structurally impossible rather than a
    discipline.
2.  **Raw is immutable; everything else is rebuildable.** Any silver or
    gold table can be dropped and regenerated from bronze. Parsing bugs
    are fixed by re-running, not by patching rows.

------------------------------------------------------------------------

# 80. Technology Stack

The workspace's usual stack, kept short. One language, one process, one
database, no build step.

| Layer | Choice |
|---|---|
| Language and tooling | Python 3.12+, **uv**, ruff, mypy |
| Web server | **Granian** (Rust ASGI server), as in the `learn_*` projects |
| API | FastAPI, routes as one list in `pages/urls.py`; REST paths singular |
| UI | **htmx 2 + Alpine.js 3 + Tailwind + daisyUI**, vendored under `pages/static/`; Jinja templates; no bundler, no CDN |
| Database | PostgreSQL, raw SQL through SQLAlchemy Core + psycopg 3 (no ORM) |
| Validation | Pydantic v2 at every file and HTTP boundary |
| Dataframes | polars |
| JSON, logging, ids | orjson; loguru (f-strings only); nanoid |
| Config | Nested YAML env file read through `config._require()`; secrets Fernet-encrypted; helpers from `lr_lib` |
| HTTP client | httpx, paced per host |
| Raw files | Plain files under `raw/`, cached for good (§83) |
| Tests | pytest against the running app over httpx; never `TestClient` |

Added only when the phase that needs them starts, not before:

| Need | Choice | Phase |
|---|---|---|
| Scheduling | Celery + Redis beat, or a systemd timer on `ingest.py daily` | 2 |
| Feature store | Parquet files read with polars | 2 |
| Documents | PyMuPDF, OCR fallback | 3 |
| LLM | Claude API; model ids in config | 3 |
| Embeddings | pgvector | 3 |
| Charts | ECharts, vendored | 2 |
| ML | LightGBM, scikit-learn, SHAP | 5 |

Scale is small: about 3,400 securities × 8 years is under 7 million
daily price rows. No distributed system is needed.

------------------------------------------------------------------------

# 81. Repository Layout

As built in `finance/` (the same shape as `learn_mba`, with Postgres).

``` text
finance/
  start.py                 # granian on 5018; --load-data, --stop
  load_data.py             # schema bootstrap, seed, refill from raw/
  ingest.py                # daily | prices | snapshots | rebuild | status
  TODO.md                  # running state of the build
  schema/schema.sql        # the whole schema; migrations/ for later changes
  resources/env/dev/.env.yaml     # nested YAML; gitignored
  resources/seed/          # exclusion rules (§69.1)
  raw/                     # bronze: cached exchange files, never deleted
  api/
    pyproject.toml
    src/equity_engine/
      config.py  db.py  ids.py  main.py
      sources/             # registry (§82), bronze cache, paced HTTP client
      parsers/             # bytes → validated Pydantic records
      service/             # ingest pipeline, loaders, health, securities, exclusions
      pages/               # urls.py, controller/, templates/, static/
    tests/                 # parsers, cache rules, live API, data integrity
```

Later phases add `master/` (corporate actions, adjustment), `facts/`
(bitemporal store, `AsOf` gateway), `features/`, `engines/`, `scoring/`,
`documents/`, `ml/`, `backtest/` and `ledger/` beside `service/`.

------------------------------------------------------------------------

# 82. Data Sourcing Plan

| Data | Source | Access | Point-in-time handling |
|---|---|---|---|
| Daily prices, volume, delivery | NSE daily archive files (bhavcopy, delivery) | Free files | Known at close of trade date |
| Corporate actions | Exchange corporate-action files | Free files | Ex-date; adjustment factors computed in-house |
| Index membership history | Index provider announcements | Free, manual backfill | Effective date |
| Results (recent years) | Exchange filings in XBRL + PDF | Free | Exchange dissemination timestamp |
| Long history, delisted companies | Out of scope (§82.1) | --- | --- |
| Shareholding pattern | Exchange filings (XBRL) | Free | Dissemination timestamp |
| Insider, substantial-acquisition, pledge | Exchange disclosure feeds | Free | Dissemination timestamp |
| Bulk and block deals | Exchange daily files | Free | Trade date, after close |
| Mutual-fund portfolios | AMC monthly disclosures | Free, per-AMC formats | Publication date |
| Announcements, presentations, call transcripts | Exchange announcement feeds, company sites | Free | Dissemination timestamp |
| Credit ratings | Rating-agency press releases; exchange disclosures | Free | Release date |
| Consensus estimates | Licensed vendor | Paid; optional at start | Snapshot daily; history starts when you start |
| Commodities, FX, macro | Exchange, RBI, ministry releases | Free | Release date |
| Alternative data (§62) | Public portals and company releases | Free, fragile | Release date |

Order of work: free exchange archives first (prices, actions,
shareholding, announcements). No fundamentals vendor is planned; the
history NSE provides is the accepted scope (§82.1).

## 82.1 Primary exchange: NSE

**Decision: NSE is the only exchange source.** Wherever the table above
says "exchange", read NSE. No BSE feed of any kind is used: not prices,
not filings, not the scrip list.

Both sites were probed on 2026-10-01. Both serve every category; NSE
wins on format, not on coverage: its filing feeds return clean JSON with
a broadcast timestamp and a direct XBRL link, and one daily file carries
price and delivery together. BSE returns results and shareholding as
HTML fragments, splits delivery into a second file, and caps
announcement queries at 12 months per request.

| Data | NSE source (verified) | History seen |
|---|---|---|
| Prices + delivery | `nsearchives` `sec_bhavdata_full_DDMMYYYY.csv` | Current format |
| Prices, ISIN-keyed | `nsearchives` UDiFF `BhavCopy_NSE_CM_…_YYYYMMDD_F_0000.csv.zip` | Current format |
| Prices, old format | `nsearchives` `content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip` | 2005 file present |
| Delivery, old format | `nsearchives` `archives/equities/mto/MTO_DDMMYYYY.DAT` | 2016 file present |
| Market cap, shares outstanding | `nsearchives` `archives/equities/bhavcopy/pr/PRDDMMYY.zip`, member `mcap*.csv` | In the 2026 bundle; **absent from the 2019 bundle** |
| Corporate actions (ex-dates), circuit hits | Same bundle, members `bc*.csv`, `bh*.csv` | Present in the 2019 bundle |
| Security master | `EQUITY_L.csv` (2,593 rows), `SME_EQUITY_L.csv` (575 rows) | Current only; no delisted names |
| Index membership | `content/indices/ind_nifty500list.csv`; history in §82.2 | 1996 onwards, from four sources |
| Bulk / block deals | `bulk.csv`, `block.csv`; `api/historicalOR/bulk-block-short-deals` | 2016 query returned rows |
| Corporate actions | `api/corporates-corporateActions` | Reliance back to 2005 |
| Results | `api/corporates-financial-results` | Rows back to 2005; **XBRL only from Dec-2018 quarter** |
| Results, new format | `api/integrated-filing-results` (XBRL + iXBRL) | 2025 onwards |
| Shareholding | `api/corporate-share-holdings-master` (XBRL link) | **Only from Sep-2021** on the query tried |
| Insider trades | `api/corporates-pit` (per symbol) | Reliance back to Nov-2015 |
| SAST, pledge | `api/corporate-sast-reg29`, `api/corporate-pledgedata` | Not depth-tested |
| Announcements | `api/corporate-announcements` (PDF link) | Reliance back to Jan-2008 |
| Annual reports | `api/annual-reports` | TCS back to FY2009-10 |
| Credit ratings | `api/corporate-credit-rating` | Not depth-tested |
| Surveillance | `api/reportASM`, `api/reportGSM` | Current only |

Constraints this puts on the build:

-   The `api/` feeds are the website's own undocumented endpoints. They
    need a session cookie from a normal page load and browser-like
    headers, and can change without notice. The archive files need only
    a user agent. Keep request rates low and check NSE's terms of use
    before any redistribution.
-   The market-wide insider query (no symbol) returned nothing; only the
    per-symbol form was confirmed. Plan on per-symbol fetches.
-   **Accepted scope:** structured results from the Dec-2018 quarter,
    shareholding from Sep-2021, and no delisted companies. The data
    does not need to be exhaustive, so no fundamentals vendor is bought.
    Backtests start in 2019 and carry survivorship bias; every backtest
    report states both.
-   Surveillance lists and price bands are current-only at NSE; they
    are snapshotted daily and their history starts when ingestion
    starts. Index membership history is recoverable (§82.2).
-   **Market cap** is not in NSE's daily price file. It comes from the
    market-cap member of NSE's daily reports bundle, which also gives
    shares outstanding. Older bundles lack that member, so market cap
    is empty for those dates until it is derived from shares
    outstanding in the shareholding filings.
-   **No yearly dump.** NSE publishes one file per trading day; no
    yearly or monthly archive of the daily files was found. NSE sells
    historical data as a paid product.
-   **Blocking is a real risk on the filing feeds.** After roughly sixty
    quick requests in one afternoon of probing, `nseindia.com/api`
    briefly returned "Access Denied". The archive host
    (`nsearchives`) has not refused anything, including a parallel
    download at about three requests a second. Every file is still
    fetched once and cached for good (§83).

**Zerodha Kite Connect is not a substitute.** The paid plan (₹500 per
month) provides live ticks and historical OHLCV candles only --- no
results, shareholding, corporate actions, announcements, delivery or
surveillance data --- and its terms prohibit displaying or
redistributing the data on another platform. It is optional, useful
only if intraday or live prices are wanted later (§3.2).

**What an NSE-only universe misses.** Companies listed only on BSE.
By market value this is small (under 2% of BSE's total when measured on
2026-10-01), and the two large names are structural: **National Stock
Exchange of India Ltd** and **NSDL**, which cannot list on NSE itself.
They are out of scope.

## 82.2 Index membership history

Verified on 2026-10-01. No single file covers the whole period, but four
free sources together do.

| Source | What it holds | Period | Format |
|---|---|---|---|
| `nsearchives` `content/indices/IndexInclExcl.xls` | Inclusion and exclusion events, 37 indices, 9,141 rows | 1996 to Sep-2020 (Nifty 500 from Aug-1998) | Excel; company **names**, no symbol or ISIN |
| `niftyindices.com` `Indices_-_Market_Capitalisation_and_Weightage/indices_data<Mon><YYYY>.zip` | Full month-end constituents with weights, about 40 indices including Nifty 500 | Apr-2013 to at least Mar-2022 | CSV in 2013, PDF afterwards; has symbols |
| Same monthly zip, later years | Only 5--7 indices (Nifty 50, Next 50, Bank, IT, Financial Services); **no Nifty 500** | By Mar-2023 onwards | PDF |
| `niftyindices.com` `Press_Release/ind_prs<DDMMYYYY>.pdf` | "Replacements in indices": every inclusion and exclusion per index, with symbol and effective date | Sampled 2024--2025 | PDF, text-extractable |
| Wayback Machine copies of `ind_nifty500list.csv` | Full Nifty 500 list on the snapshot date | About 14 distinct versions, 2018--2026 | CSV with ISIN |
| `nsearchives` `content/indices/ind_close_all_<DDMMYYYY>.csv` | Daily index values, P/E, P/B, dividend yield (not membership) | 2015 file present | CSV |

Build order for a backtest that starts in 2019:

1.  Seed membership from the Mar-2019 monthly constituents file.
2.  Roll forward with the monthly files to the last month that includes
    Nifty 500, cross-checking against the event workbook to Sep-2020.
3.  From there to today, apply the press-release events; reconcile at
    each Wayback snapshot and against the live constituent file.
4.  From ingestion start, snapshot the live file daily.

Known weaknesses: the event workbook identifies companies by name
only, so it needs a name-to-ISIN mapping that handles renames; the
press-release filenames carry the announcement date, which has to be
discovered from the listing page; and the exact month the monthly zip
stopped carrying Nifty 500 (between Mar-2022 and Mar-2023) is not yet
pinned down.

Every source gets one row in `source_registry`: owner, licence terms,
expected cadence, fetch method, and a staleness threshold that drives
monitoring.

------------------------------------------------------------------------

# 83. Ingestion and Document Pipeline

**Structured sources**

1.  Fetch to `raw/<source>/<yyyy>/<file>` with content hash and
    `fetched_at`. **A file is fetched once and kept for good**: the
    cache on disk is checked before any request, a cached file is never
    downloaded again, overwritten or deleted, and a weekday with no file
    (a market holiday) is remembered with a marker. Dropping the
    database loses nothing; it is refilled from disk with no network.
2.  Parse into Pydantic models. A row that fails validation stops the
    run for that source; it is not skipped or defaulted.
3.  Upsert into silver as new bitemporal versions.

**Documents**

1.  Store the original; record dissemination timestamp and hash.
2.  Extract text with layout; fall back to OCR for scanned pages;
    transcribe call audio where no transcript is filed.
3.  Classify the document type and event type (small model).
4.  Extract to a strict schema per task --- guidance, capacity, order
    book, KPIs, rating rationale, auditor remarks --- with the page
    number and quoted span for every value.
5.  Validate: units normalised; values cross-checked against structured
    filings where both exist; disagreements go to a review queue rather
    than into the facts table.
6.  Embed chunks into pgvector for retrieval and peer-similarity.
7.  Record the run in `llm_runs` (model, prompt version, input hashes).

Historical backfills go through the batch interface with prompt caching
on the shared instructions; only results-season flashes need the
synchronous path.

------------------------------------------------------------------------

# 84. Bitemporal Fact Store and the AsOf Gateway

``` sql
create table fin_fact (
    company_id      text        not null,
    metric          text        not null,   -- canonical line item
    period_end      date        not null,
    period_type     text        not null,   -- Q | H | FY
    basis           text        not null,   -- consolidated | standalone
    value           numeric,
    original_value  numeric,
    original_unit   text        not null,
    available_from  timestamptz not null,   -- when the market could know it
    superseded_at   timestamptz,            -- available_from of the next version
    is_restated     boolean     not null,
    source_doc_id   text        not null,
    primary key (company_id, metric, period_end, period_type, basis, available_from)
);

-- what was believed at decision time :t
select * from fin_fact
where available_from <= :t
  and (superseded_at is null or superseded_at > :t);
```

The same pattern (valid period + `available_from` + `superseded_at`)
applies to shareholding, ratings, estimates, KPIs and index membership.

`available_from` rules:

-   Exchange dissemination timestamp where one exists. A filing
    disseminated after the market close becomes available at the next
    trading day's open.
-   Vendor history without timestamps: period end plus the statutory
    filing deadline (the latest it could legally have been known). This
    is conservative by design and is recorded as `available_from_basis
    = 'assumed'` so such rows can be excluded from sensitive tests.
-   Restatements are new versions; the original stays queryable.

The gateway:

``` python
snap = AsOf("2024-09-30")
snap.facts(metrics=[...], periods=12)      # polars frame, whole universe
snap.prices(adjusted=True, lookback=750)   # adjusted using actions known at t
snap.universe()                            # listed and tradeable on that date
snap.shareholding(), snap.events(), snap.documents()
```

Engines receive a snapshot and nothing else; they hold no database
handle. Price adjustment is computed as of `t`, so a split announced
after `t` does not alter the series the model sees.

------------------------------------------------------------------------

# 85. Engine Framework, Scoring and ML

**Engines.** One interface for §6--§37 and §55--§71:

``` python
class Engine(Protocol):
    name: str
    version: str
    requires: set[str]                      # metrics / templates needed
    def evaluate(self, snap: Snapshot) -> pl.DataFrame: ...   # one row per signal
```

A signal row carries: company, engine and version, signal type, stage
(Early / Emerging / Confirmed / Mature / Reversing), strength,
historical percentile of the change, evidence (references to the exact
fact rows), and invalidation rules.

-   Vectorised across the universe; no per-company loops.
-   Stages move through a state machine with hysteresis: promotion
    needs N consecutive confirming periods, demotion one clear break.
    This implements "avoid treating one-quarter spikes as structural"
    (§8) once, for every engine.
-   "How unusual" is measured empirically: the percentile of the
    observed change against the full point-in-time history of the same
    metric in the same sector.
-   Engines are pure functions of the snapshot, so each is unit-tested
    on frozen historical snapshots of known cases.

**Scoring.** Scores (§39, §78) are transparent weighted combinations of
sector-relative percentiles, with the inputs stored. Buckets (§38) are
rule profiles over scores and signals. Value-trap (§16), distress (§68)
and investability (§69) are gates applied after bucketing, and the
reason a name was gated out is kept and shown.

**ML**, built only after the rule engines have a ledger history:

-   **Labels:** forward 6- and 12-month excess return vs a sector- and
    size-matched benchmark, ranked within date; plus event labels
    (margin expansion, inflection confirmed, drawdown beyond a
    threshold). Delisted and failed companies keep their terminal
    returns.
-   **Features:** from gold, rank-normalised within date and sector,
    winsorised; missingness kept as information, not imputed away.
-   **Validation:** walk-forward with purging and an embargo at least as
    long as the label horizon; overlapping labels down-weighted.
-   **Objective:** learning-to-rank or calibrated classification;
    judged on rank IC, top-decile minus bottom-decile spread after
    costs, and stability across years and regimes.
-   **Acceptance:** §76 --- beats the rule baseline out of sample, or it
    does not ship.
-   **Similarity search (§41):** nearest neighbours in standardised
    feature space to pre-rerating snapshots of historical winners, with
    the matched precedents shown, and the same search run for
    historical losers to estimate the false-positive rate.

------------------------------------------------------------------------

# 86. Backtester

-   Iterates decision dates; at each date builds `AsOf(t)` and runs the
    production engines unchanged.
-   Universe is whatever was listed and passed §69 on that date.
-   Execution: decision on close of `t`, fill on `t+1`; no fill on a
    circuit-locked or suspended day; participation capped as a fraction
    of traded volume; impact cost scaled by liquidity.
-   Costs and taxes come from dated configuration tables (brokerage,
    securities transaction tax, exchange and regulatory fees, stamp
    duty, GST, capital-gains rates), so each simulated year uses the
    rules then in force.
-   Corporate actions are applied to holdings as events (demerged
    shares received, merger swaps, delisting proceeds).
-   Outputs the §43 metrics, by bucket, by regime (§29), by market-cap
    band and by year, with the number of configurations tried recorded
    against each result.
-   Every run stores its code version, configuration and data-version
    watermark in `backtest_runs` and is reproducible from them.

------------------------------------------------------------------------

# 87. API and UI

-   FastAPI, singular resource paths: `/api/company/{id}`,
    `/api/signal`, `/api/thesis`, `/api/screen`, `/api/snapshot`. Every
    read endpoint accepts `as_of`, which is how §46 is delivered ---
    the historical view is the normal view with a different date.
-   Server-rendered pages: Radar (§44), Company (§45), Timeline (§31),
    Screener and Compare (§75), Thesis board (§73), Ledger performance
    (§72), Data health (§89).
-   Every number on a page links to its source fact and document page.
-   Alerts and the daily digest are generated from the ledger after the
    nightly run; delivery by email or messaging webhook.

------------------------------------------------------------------------

# 88. Schedule (IST)

| When | Job |
|---|---|
| Continuous, 07:00--23:00 | Poll exchange announcements; classify; results flash for watched names |
| ~19:00--21:00, trading days | Prices, delivery, deals, corporate actions, surveillance lists |
| Nightly | Rebuild features for the day; run engines; write ledger; alerts and digest |
| Weekly | Re-fetch recent archives for corrections; outcome marking; data-health report |
| Monthly | Fund portfolios; alt-data series; index and reclassification calendars |
| Quarterly, after season | Shareholding; full fundamentals reconciliation; model retraining and review |

------------------------------------------------------------------------

# 89. Testing and Data Quality

-   **Leak tests.** For sampled dates, assert that no row returned by
    `AsOf(t)` has `available_from > t`; and that running an engine at
    `t` yields the same output before and after later data is loaded.
    These run on every change.
-   **Reconciliation.** Computed ratios for a fixed panel of companies
    are checked against published annual-report figures; adjusted price
    series against total-return index behaviour around known actions.
-   **Identity tests.** A fixed list of historical mergers, demergers
    and renames must resolve correctly (for example the 2023 HDFC
    merger and the Jio Financial demerger).
-   **Accounting invariants.** Assets equal liabilities plus equity;
    quarters sum to the year; TTM equals the sum of four quarters.
    Violations quarantine the filing.
-   **Golden cases.** Known historical inflections, turnarounds, value
    traps and frauds, each asserting which engine should have fired and
    by when.
-   **LLM evaluation sets** per extraction task (§76).
-   **Monitoring.** Per-source freshness against the registry cadence,
    row-count and null-rate drift, parse-failure rate, and a visible
    stale-data marker in the UI. A source that fails fails loudly; no
    silent fallback to yesterday's data.

------------------------------------------------------------------------

# 90. Delivery Roadmap

This refines §53. The main change: point-in-time storage and the signal
ledger move from Phase 3 to the foundation, because neither can be
retrofitted --- history not captured with timestamps is lost.

Durations are rough estimates for one developer and depend heavily on
the fundamentals source.

| Phase | Scope | Exit criterion | Estimate |
|---|---|---|---|
| 0. Foundation | Repo, bronze store, source registry, company master, prices, corporate actions, adjustment, `AsOf` gateway, leak tests, scheduled daily ingest | Adjusted prices and identities pass §89 tests for the full universe | 3--4 weeks |
| 1. Fundamentals slice | Financial facts (recent years from XBRL), §57 rules, non-financial template, §6--§12 engines, §13 valuation, company page, ledger | One sector end to end: signals in the ledger, every number traceable to a filing | 6--8 weeks |
| 2. Breadth and risk | All sectors and §55 templates, shareholding §22--§24, §65 feeds, §59 forensics, §16 value trap, §68 distress, §69 filter, radar, alerts | Nightly unattended run over the whole universe; radar and risk radar live | 5--7 weeks |
| 3. Documents and LLM | Announcement classification, §30 events, §31 timeline, §32 guidance, §56 KPIs, §71 diffs, §51 thesis output, §73 lifecycle | Extraction evaluation sets pass; theses contain only database-sourced figures | 6--8 weeks |
| 4. History and backtest | NSE backfill to the Dec-2018 quarter (no vendor, no delisted names), §86 backtester, §43 metrics, §41 pattern search, §46 historical view | Rule engines backtested from 2019 with leak tests green | 5--7 weeks |
| 5. ML and expectations | §85 ML, §58 consensus and reaction, §14 implied growth, §76 governance | A model beats the rule baseline out of sample, or the finding that none does is recorded | 6--8 weeks |
| 6. Depth | §18 SOTP, §60--§64, §66--§67, §70, §74 portfolio layer, §75 workbench extras | Incremental; each ships behind its own golden cases | ongoing |

Sequencing rules:

-   Each phase delivers a usable vertical slice, not a layer.
-   No engine is built before its data passes reconciliation.
-   Rule engines precede ML for the same signal; the rule is the
    baseline the model must beat.
-   The ledger records from Phase 1 so that by Phase 5 there is more
    than a year of live outcomes to judge the backtests against.

------------------------------------------------------------------------

# 91. Risks and Open Decisions

| Risk | Mitigation |
|---|---|
| Long-history point-in-time fundamentals are hard to obtain | Conservative assumed-lag rule (§84); mark assumed rows; trust live-ledger results most |
| Free sources change format or block access | Bronze is immutable; parsers versioned; per-source monitoring; no engine depends on one scraped source |
| XBRL and vendor numbers disagree | Keep both with provenance (§48); reconciliation report; official filing wins |
| Overfitting across many engines and thresholds | Experiment count logged; walk-forward only; live ledger as the final judge (§72) |
| Small-cap noise, illiquidity and manipulation | §69 filter; liquidity-aware labels and costs; surveillance flags |
| LLM extraction errors entering facts | Schema validation, cross-checks, citations, review queue, evaluation sets |
| Scope: over a hundred sections | Vertical slices; a section is not started until the phase before it meets its exit criterion |

Decisions needed before Phase 1:

1.  **Fundamentals source and budget.** This sets how far back
    backtests can credibly go and whether delisted companies are
    covered.
2.  **Audience.** Personal use only, or shared? This determines the
    §77 obligations and whether multi-user access is built.
3.  **Universe floor.** The minimum liquidity and market cap for the
    default universe; it drives data-cleaning effort more than anything
    else.
4.  **Consensus data.** Licence it, or run §58 on statistical baselines
    until the rest proves its worth.

------------------------------------------------------------------------

# Part D --- Institutional (Buy-Side) Requirements

Parts A--C describe an engine that finds and explains opportunities.
An investment firm also needs the process around it: who covers what,
how an idea becomes a position, what the mandate allows, how the result
is measured against a benchmark, and what must be recorded for the
regulator. Sections 92--116 add those requirements. Priorities use
MoSCoW (Must / Should / Could) and are consolidated in §115.

Regulatory limits and obligations named here are summaries; the
compliance function owns the authoritative rule set, held as dated
configuration.

------------------------------------------------------------------------

# 92. Personas and Jobs to Be Done

| Persona | Primary job | Key screens |
|---|---|---|
| Sector analyst | Maintain coverage, find and defend ideas, update models after results | Company, Results console, Thesis board |
| Portfolio manager | Decide what to own and how much, relative to benchmark and mandate | Radar, Portfolio, Attribution |
| Head of research / CIO | Allocate analyst time, judge idea quality, run the committee | Pipeline, Scorecards, IC pack |
| Risk manager | Monitor exposures, liquidity, concentration and limits | Risk, Liquidity, Crowding |
| Compliance officer | Enforce restricted lists, limits, information barriers, records | Compliance console, Audit |
| Dealer / trader | Know what can be executed, in what size, over how long | Liquidity, Supply calendar |
| Data steward | Keep reference data and overrides correct | Data health, Override log |
| Stewardship / ESG lead | Vote, engage, and report on both | Voting, Engagement log |

Every feature below names the persona it serves; a feature with no
owning persona is out of scope.

------------------------------------------------------------------------

# 93. Coverage and Research Management

**Must.** Serves analyst, head of research.

-   Coverage universe: each company assigned a primary and a backup
    analyst, a coverage status (active / monitored / uncovered) and a
    house rating with history.
-   Research notes: initiation, results update, event note, meeting
    note --- typed, versioned, linked to the company, the thesis (§73)
    and the facts they cite.
-   Management-meeting and conference log: date, attendees, topics,
    takeaways, follow-ups.
-   Sell-side research ingestion: broker reports stored with broker,
    analyst, rating, target and estimate changes, feeding §58.
-   Model library: the analyst's spreadsheet model stored per version
    with its key outputs extracted (§94).
-   Coverage-gap report: engine-flagged opportunities in uncovered
    names, ranked --- the engine's main contribution to a research
    team's agenda.
-   Stale-coverage report: covered names with no note since the last
    result.

------------------------------------------------------------------------

# 94. House Estimates, Scenarios and Price Targets

**Must.** Extends §14 and §58. Serves analyst, PM.

-   Driver-based forecasts per company: volume, price, mix, margin,
    capex, working capital → revenue, EBITDA, EPS, FCF for three
    forward years.
-   **House vs consensus vs market-implied (§14)** side by side; the
    gap between house and consensus is the variant view and must be
    stated explicitly in every thesis.
-   Bull / base / bear scenarios with probabilities, each with its own
    drivers, earnings and valuation; probability-weighted value and
    upside/downside ratio.
-   Price target with method, multiple and horizon; full history of
    target and rating changes with the reason.
-   Sensitivity tables: value against the two drivers that matter most.
-   Estimate-change log after each result: what changed, by how much,
    and why.
-   Forecast-accuracy tracking per analyst and per company (§108).

------------------------------------------------------------------------

# 95. Idea Pipeline and Investment Committee Workflow

**Must.** Serves analyst, PM, CIO.

Stages:

`Screened → Under research → Pitched → Accepted / Rejected / Deferred
→ In portfolio → Under review → Exited`

-   Each stage change records who, when and why. There is no approver
    and no maker-checker step: whoever owns the idea moves it.
-   IC memo assembled from the system: thesis, variant view, scenarios,
    valuation, forensic and governance checks, liquidity, mandate fit,
    risks and invalidation conditions. The analyst edits; the facts are
    locked to the database.
-   A fixed **pre-mortem checklist** must be completed before a pitch:
    value-trap check (§16), forensic pack (§59), distress (§68),
    supply overhang (§66), liquidity at fund size (§100), governance
    (§35, §102).
-   Decision log: intended size range, conditions, review date.
    Rejected and deferred ideas are kept and tracked to outcome ---
    errors of omission are measured as well as errors of commission.
-   Mandatory review triggers: invalidation fired, price beyond a
    configured drawdown, target reached, review date passed.

------------------------------------------------------------------------

# 96. Mandate, Limits and Pre-Trade Compliance

**Must.** Serves compliance, PM, risk.

-   **Restricted and watch lists** with reason, start and end dates;
    restricted names are blocked from pitches and flagged everywhere.
-   **Information barriers:** when a team is brought over the wall on
    unpublished price-sensitive information, the name is restricted,
    the event logged with persons and time, and research access to
    related notes is limited. The system never stores such information
    in the research database.
-   **Regulatory limits** as rules: single-issuer and group exposure
    caps per scheme, ownership caps across all schemes of the house,
    sector caps, unlisted and illiquid limits, derivative exposure.
-   **Mandate limits** per fund: benchmark, market-cap ranges,
    tracking-error budget, stock and sector active-weight bands, cash
    limits, exclusions.
-   **Aggregate-holding thresholds:** house-wide ownership in each
    company monitored against the levels that trigger the firm's own
    disclosure obligations, with an early-warning band.
-   **Foreign-ownership headroom** for foreign-domiciled mandates.
-   Hypothetical-trade check: "can fund X add N % of this stock?"
    answered against every rule before the idea reaches the dealer.
-   Breach log: passive and active breaches, cure deadline, resolution.

------------------------------------------------------------------------

# 97. Benchmark-Relative Analytics and Attribution

**Must.** Serves PM, CIO, risk.

-   Benchmark constituents and weights stored historically; active
    weight per stock, sector and market-cap band.
-   Ex-ante tracking error and its decomposition by stock and factor.
-   Performance attribution: allocation, selection and interaction by
    sector; stock-level contribution; factor attribution (§98).
-   **Decision attribution:** return split by idea source (engine
    bucket, analyst, PM), by entry timing, by sizing, and by exit ---
    did selling add or destroy value?
-   **Engine attribution:** performance of positions that originated
    from each §38 bucket versus those that did not. This is the
    business case for the platform, measured on real capital.
-   "Not-owned" analysis: largest benchmark names not held and their
    contribution to relative return.

------------------------------------------------------------------------

# 98. Factor and Risk Model

**Should.** Serves risk, PM.

-   India-specific factor set: value, quality, momentum, size, low
    volatility, growth, leverage, liquidity, plus sector factors.
-   Daily factor returns, factor valuations (spread between cheap and
    expensive quintiles) and factor crowding.
-   Portfolio and benchmark exposures; risk split into factor and
    stock-specific.
-   Each §38 bucket profiled by its factor exposure, so that an
    "opportunity" that is merely a factor bet is recognised as one.
-   Stress tests: historical episodes and hypothetical shocks (rates,
    crude, currency, foreign outflow) applied through §105.

------------------------------------------------------------------------

# 99. Crowding and Peer Positioning

**Should.** Extends §65. Serves PM, risk.

-   From monthly fund portfolios: number of funds holding, aggregate
    institutional ownership as % of free float, and its change.
-   **Days-to-exit for the crowd:** aggregate institutional holding ÷
    average traded volume. High values mean the exit is narrow.
-   Overlap of the house portfolio with each competitor fund and with
    the peer-group aggregate.
-   Peer-group over- and under-weights by stock and sector relative to
    the benchmark; consensus longs and consensus avoids.
-   Flags:

> CROWDED LONG: ownership at multi-year high, valuation stretched,
> revisions rolling over

> UNDER-OWNED IMPROVER: ownership at multi-year low, fundamentals
> inflecting

------------------------------------------------------------------------

# 100. Capacity and Liquidity at Fund Scale

**Must.** Extends §69. Serves PM, risk, dealer.

-   Position size as % of free float and as multiples of average daily
    volume, for the house in aggregate and per fund.
-   Liquidation ladder: % of each fund that can be sold in 1 / 5 / 20 /
    60 days at a configured participation rate, in normal and stressed
    volume.
-   Entry-cost estimate for a target position: days to build, expected
    impact.
-   Strategy capacity: the assets at which a bucket's backtested alpha
    is consumed by impact cost.
-   Redemption stress: liquidity available against assumed outflows.
-   Every engine-generated idea shows the largest position each fund
    could hold within its liquidity rules; ideas too small to matter
    for a fund are filtered from that fund's radar.

------------------------------------------------------------------------

# 101. Stewardship, Voting and ESG

**Should.** Extends §35. Serves stewardship lead, analyst, compliance.

-   Meeting and resolution calendar: AGMs, EGMs, postal ballots; each
    resolution typed (related-party transaction, remuneration,
    director appointment, auditor, fund raise, scheme).
-   Proxy-adviser recommendations where licensed, house voting policy,
    proposed vote, rationale and final vote --- with the
    record needed for periodic voting disclosure.
-   Voting outcomes, including the share of public and institutional
    votes cast against; a resolution passed over heavy institutional
    dissent is a governance signal for §35.
-   Engagement log: issue raised, with whom, response, escalation,
    outcome.
-   Sustainability data from business-responsibility reports: emissions,
    energy and water intensity, safety, workforce, board composition
    --- sector-relative and trended.
-   Controversy tracking: regulatory orders, pollution-board actions,
    accidents, labour disputes, product recalls.
-   Material ESG issues mapped by industry; only material ones feed
    scores.

------------------------------------------------------------------------

# 102. Management and Board Quality Scorecard

**Should.** Extends §35 and §60. Serves analyst, PM.

-   Promoter and KMP background, tenure, prior ventures and any
    regulatory history; succession visibility.
-   KMP and senior-management turnover; unexplained exits.
-   Board: independence in substance (tenure, interlocks, relationships
    with the promoter), attendance, committee composition, relevant
    expertise.
-   Pay alignment: remuneration vs profit and vs shareholder return;
    ESOP breadth; promoter-family roles and pay.
-   Guidance accuracy (§32) and capital-allocation class (§60).
-   Treatment of minority shareholders: history of related-party
    structures, merger ratios, royalty increases, delisting attempts.
-   Disclosure quality: segment detail, concall regularity, consistency
    of KPIs (§71).

Output: a scorecard with evidence for each item, sector-relative, with
analyst override allowed but recorded.

------------------------------------------------------------------------

# 103. Competitive Position and Industry Structure

**Should.** Serves analyst.

-   Industry revenue and profit pool built bottom-up from constituents;
    each company's share and its trend.
-   Concentration (HHI), entry and exit of players, announced capacity
    additions across the industry against demand growth.
-   Relative margin and ROCE vs peers through the cycle as evidence of
    pricing power.
-   Import share and landed-cost parity where relevant.
-   Customer and supplier concentration (§63).

Flags:

> SHARE GAINER WITH EXPANDING MARGINS

> INDUSTRY CAPACITY GLUT AHEAD

------------------------------------------------------------------------

# 104. Unit Economics and Cash Runway Engine

**Should.** Extends §6 for loss-making and recently listed companies.

-   contribution margin per unit / order / customer, and its trend
-   customer-acquisition cost, payback, retention or repeat rates where
    disclosed
-   take rate, average order value, and adjusted-EBITDA reconciliation
    to reported EBITDA (ESOP cost and other add-backs shown, never
    accepted at face value)
-   cash burn, cash and liquid investments, **runway in quarters**
-   funding dependence: next likely raise and implied dilution
-   path to breakeven: scale needed at current unit economics

Flag:

> BURN FALLING FASTER THAN GROWTH --- runway extending

> RUNWAY UNDER FOUR QUARTERS --- dilution risk

------------------------------------------------------------------------

# 105. Macro and Earnings Sensitivity Engine

**Should.** Extends §61. Serves PM, risk, analyst.

-   Per-company exposure: export share and currency mix, imported input
    share, hedging policy, floating-rate debt share, commodity
    intensity, government-revenue dependence, rural / urban mix.
-   Sensitivity of EPS to a unit move in each driver, from disclosures
    and from the house model (§94).
-   Scenario runner: a shock (currency, crude, rates, a tariff) → EPS
    change per company → portfolio and benchmark impact.
-   India-relative context: valuation and earnings growth vs other
    emerging markets, as an input to foreign-flow expectations in §29.

------------------------------------------------------------------------

# 106. Pre-IPO and Offer-Document Pipeline

**Should.** Extends §36. Serves analyst, PM.

-   Tracker of draft and final offer documents: status, expected
    timing, size, fresh issue vs offer for sale, selling shareholders.
-   Structured extraction from the offer document: restated
    financials, KPIs, peer set named by the issuer, objects of the
    issue, risk factors, litigation, related-party transactions,
    pre-IPO placements and their prices.
-   Valuation against listed peers at the price band; anchor
    participation decision support.
-   Financial history from the offer document enters the fact store so
    a newly listed company has a multi-year record on day one.

------------------------------------------------------------------------

# 107. Primary Research and Channel-Check Log

**Could.** Serves analyst, compliance.

-   Structured notes from dealer and distributor checks, site and plant
    visits, industry-expert calls, customer and supplier conversations.
-   Each note tagged to companies and KPIs, with source type and
    reliability.
-   Compliance attestation on every expert interaction that no
    unpublished price-sensitive information was received; a flagged
    note is quarantined and routed to compliance (§96).
-   Recurring surveys stored as time series and treated as an
    alternative-data series in §62.

------------------------------------------------------------------------

# 108. Analyst and Idea Performance Scorecard

**Should.** Extends §72. Serves head of research, CIO.

-   Per analyst: rating hit rate, excess return of recommendations,
    forecast accuracy vs consensus, timeliness after results, coverage
    productivity.
-   Per idea: outcome vs the base case, which scenario played out,
    which thesis claims held.
-   Per source: engine-originated vs analyst-originated vs externally
    sourced.
-   Behavioural diagnostics for the portfolio: winners sold early,
    losers held, added-to losers, sizing vs stated conviction.

Used for process improvement and reported in aggregate; the measures
and their use should be agreed with the research head before launch.

------------------------------------------------------------------------

# 109. Reporting and Distribution

**Should.** Serves PM, CIO, compliance.

-   Investment-committee pack, generated: pipeline, decisions due,
    review triggers, portfolio changes, attribution.
-   Monthly and quarterly portfolio review: performance, attribution,
    risk, top changes, thesis status per holding.
-   Results-season summary per sector: aggregate growth, margin
    direction, surprise breadth, guidance changes.
-   Commentary drafts for fund factsheets and client reviews, generated
    from attribution and theses; drafts are never sent automatically.
-   Stewardship and voting reports (§101).
-   Scheduled delivery, PDF / Excel export, and a record of exactly
    what was sent to whom.

------------------------------------------------------------------------

# 110. Data Governance and Reference Data

**Must.** Extends §48. Serves data steward, everyone.

-   **Golden security master:** one identity per issuer and security,
    mapped to every vendor identifier; changes are logged.
-   **Data dictionary:** every metric with its definition, formula,
    unit, template applicability and owner. A number on a screen links
    to its definition as well as its source.
-   **Lineage:** from any displayed value back through feature, fact,
    parsed record and raw document.
-   **Manual overrides:** applied directly, with reason, author and
    expiry recorded; the original value is retained and
    the override is visible wherever the number appears.
-   **Vendor management:** contract, entitlements, permitted uses,
    renewal date, delivery SLA and measured adherence per source.
-   **Issue workflow:** a user can flag any number; flags are triaged,
    resolved and reported.
-   **Data-quality scorecard** per source and per company, published
    weekly.

------------------------------------------------------------------------

# 111. Access Control, Audit and Records Retention

**Must.** Serves compliance.

-   Single sign-on; role-based access by persona (§92) and by fund.
-   Entitlement-aware data access: content licensed to named users is
    visible only to them.
-   Information-barrier enforcement (§96) at the data layer, not only
    in the UI.
-   Immutable audit trail of every view of restricted content, every
    workflow action, override, rating change and export.
-   Retention schedules for research notes, IC records, voting records
    and communications, with legal hold.
-   Recorded rationale for every investment decision, retrievable by
    security and date.

------------------------------------------------------------------------

# 112. Integrations

**Should.**

-   **Portfolio accounting / order management:** holdings, transactions
    and cash in daily; accepted ideas and size ranges out. The platform
    remains decision-support and does not send orders (§52).
-   **Risk system:** exposures out, or factor model in, depending on
    which is the system of record.
-   **Market-data terminals and vendor feeds:** identifiers mapped
    through the security master.
-   **Spreadsheet add-in:** pull any point-in-time series into an
    analyst model; push model outputs back (§94).
-   **Messaging and email:** alerts, digests, and one-click "discuss
    this signal" links.
-   **Document management** for research notes if one already exists.
-   Open, documented API so the quantitative team can use the feature
    store directly.

------------------------------------------------------------------------

# 113. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Timeliness | End-of-day data and signals ready before the morning meeting; results flash within minutes of filing during the season |
| Availability | Business-hours availability target agreed with the desk; degraded mode shows last good data with a visible stale marker |
| Performance | Company page and radar interactive in about two seconds; universe-wide screen in seconds |
| Accuracy | Reconciliation tolerance per metric class defined and reported (§89) |
| Reproducibility | Any historical screen, signal or report regenerable exactly from stored versions |
| Recoverability | Backups with tested restore; raw store replicated; stated recovery point and recovery time |
| Security | Encryption in transit and at rest; secrets in configuration, never in code; periodic access review |
| Auditability | §111 |
| Scalability | Whole listed universe; tens of users; full history |
| Change control | Engine, model and prompt changes versioned, reviewed and released with a change note |
| Model risk | Independent validation of ML models before use in decisions (§76) |

------------------------------------------------------------------------

# 114. Success Metrics

The platform is judged on outcomes, measured from the ledger (§72) and
attribution (§97).

| Dimension | Metric |
|---|---|
| Idea generation | Share of new portfolio ideas first surfaced by the engine; lead time ahead of sell-side coverage |
| Idea quality | Excess return and hit rate of engine-sourced positions vs others |
| Risk avoidance | Flagged-before-event rate for holdings that later suffered large drawdowns or governance events |
| Analyst productivity | Time from result filing to updated note; companies monitored per analyst |
| Coverage | Share of the investable universe with a current signal set and data-quality pass |
| Trust | Data issues raised per month and time to resolve; overrides outstanding |
| Adoption | Weekly active users by persona; share of IC memos generated from the system |
| Discipline | Share of positions with a live thesis, invalidation rules and a current review |

------------------------------------------------------------------------

# 115. Prioritisation and Traceability

| Priority | Sections |
|---|---|
| Must | §93 coverage, §94 house estimates, §95 pipeline and IC, §96 compliance, §97 attribution, §100 liquidity at scale, §110 governance, §111 access and audit |
| Should | §98 factor model, §99 crowding, §101 stewardship, §102 management, §103 competitive, §104 unit economics, §105 sensitivity, §106 pre-IPO, §108 scorecards, §109 reporting, §112 integrations |
| Could | §107 primary-research log |

Traceability: each requirement is recorded with an identifier, owning
persona, source section, priority, acceptance criterion and the test
that proves it. Example:

``` text
ID:          REQ-096-03
Section:     §96 Mandate, Limits and Pre-Trade Compliance
Persona:     Compliance officer
Statement:   A restricted name cannot be moved to "Pitched".
Acceptance:  Given a company on the restricted list,
             when an analyst submits a pitch,
             then the action is refused, the reason shown,
             and the attempt written to the audit trail.
Test:        tests/compliance/test_restricted_pitch.py
```

------------------------------------------------------------------------

# 116. Impact on the Technical Plan

Part C assumed a single user. Part D changes the following and nothing
else; the fact store, `AsOf` gateway, engines and ledger are unchanged.

-   **Identity and access:** single sign-on, roles, fund scoping and
    entitlements enforced in the API layer and in row-level policies in
    the database.
-   **Workflow:** none. There is no approval service; stage changes,
    overrides, security-master changes and votes are direct actions
    recorded in the audit log.
-   **Audit:** append-only audit table written by middleware for every
    state-changing request and for reads of restricted content.
-   **Portfolio data:** daily holdings, transactions and benchmark
    weights ingested as bitemporal facts, so attribution and compliance
    checks are also reproducible as of any date.
-   **Rules engine:** mandate and regulatory limits expressed as dated,
    data-driven rules evaluated against actual or hypothetical
    portfolios.
-   **Deployment:** at least two application instances behind a load
    balancer, managed database with replication and backups, separate
    test and production environments.

Additional tables:

``` text
users, roles, funds, entitlements
coverage, research_notes, meeting_log, broker_reports
house_estimates, scenarios, price_targets, analyst_models
ideas, idea_stage_history, ic_memos, ic_decisions
restricted_list, barrier_events, limit_rules, limit_breaches
holdings, transactions, benchmark_weights
attribution_results, factor_returns, factor_exposures
fund_peer_holdings, crowding_metrics, liquidity_ladder
resolutions, votes, engagements, esg_metrics, controversies
management_scorecard, industry_structure, unit_economics
macro_sensitivities, offer_documents, channel_checks
data_dictionary, overrides, data_issues, vendor_contracts
audit_log, report_runs
```

Roadmap insertion (§90):

| Phase | Institutional additions |
|---|---|
| 0 | Access control, audit log, security master, data dictionary |
| 1 | Coverage and research notes (§93); holdings and benchmark ingestion |
| 2 | Restricted list and limit rules (§96); liquidity at fund scale (§100); crowding (§99) |
| 3 | Idea pipeline and IC workflow (§95); house estimates and scenarios (§94) |
| 4 | Attribution (§97); scorecards (§108); factor model (§98) |
| 5 | Stewardship (§101); reporting (§109); integrations (§112) |
| 6 | Remaining Should and Could items |

Compliance, access control and audit are placed first deliberately:
they are cheap to build into the foundation and expensive to add once
research content exists without them.

------------------------------------------------------------------------

# Part E --- Additions After the First Build

# 117. Company Profile: Products, Website, Brands, Ownership and Deals

Extends §4 (company master), §22--§24 (shareholding) and §65 (deals).
One page per company answers four questions: what does it sell, where
is it on the web, who owns it, and who has been dealing in it. NSE data
only.

| Item | NSE source (verified 2026-10-01) | Coverage |
|---|---|---|
| Official website, e-mail, CIN, incorporation date, registered office | Sustainability report (BRSR) XBRL, from `api/corporate-bussiness-sustainabilitiy` | About 1,260 companies (the largest by market cap must file); FY2025-26 |
| Business activities with % of turnover | Same XBRL, "activities accounting for 90% of turnover" | Same |
| Products and services with NIC code and % of turnover | Same XBRL | Same |
| Markets (states, countries), employees, workers | Same XBRL | Same |
| **Brands** | **Not in any structured NSE filing** | None yet |
| Promoter and public % | Shareholding filing list, `api/corporate-share-holdings-master` (one request per month of filings) | Every listed company, from the Sep-2021 quarter |
| FII %, DII %, mutual funds, insurance, pension funds, banks, AIFs, retail, HNI, NRI | Shareholding XBRL, one file per filing | Same; older filings use an earlier format and may lack the split |
| Number of shareholders, total shares | Same XBRL | Same |
| Bulk and block deals | `api/historicalOR/bulk-block-short-deals` with `csv=true`, one request per month | From 2019 |

Definitions used on the page:

-   **FII** is the filing's "Institutions (Foreign)" total. Foreign
    portfolio investors (categories I and II) are shown within it.
-   **DII** is the filing's "Institutions (Domestic)" total: mutual
    funds, insurers, banks, pension funds, alternative investment funds
    and other financial institutions.
-   **Retail** is resident individuals holding nominal share capital up
    to ₹2 lakh.
-   A company may file more than once for a quarter. Every filing is
    kept with its broadcast time; the newest one is what the page shows,
    and the older ones remain what was known before it (§84).

What it produces:

-   Company page: website link, business activities and products with
    their share of turnover; ownership bar and breakdown for the newest
    quarter; ownership by quarter; bulk and block deals, newest first.
-   Ownership screen: every company's newest breakdown, sortable by
    promoter, FII, DII, mutual-fund, insurance or retail holding.
-   Inputs to other engines: quarter-on-quarter change in FII and DII
    holding (§22--§24), shareholder-count jumps and repeat deal
    counterparties (§69.2).

Limits to state on the page, not hide:

-   **Brands are not available.** They are named only in free text
    (annual reports, investor presentations, company websites). They are
    extracted in the documents phase (§83) from annual-report PDFs,
    which the BRSR filing list already links, with page and quoted span
    for each brand. Until then the page says so.
-   Companies that do not file a BRSR have no website, activity or
    product data here.
-   The JSON form of the deal-history feed stops at 70 rows; only the
    CSV form returns a whole month.
-   ISINs in shareholding filings are typed by the company and are
    sometimes malformed, so filings are matched to securities by NSE
    symbol.

Tables: `shareholding_filing`, `shareholding_pattern`,
`company_profile`, `company_activity`, `company_product`, `deal`.

------------------------------------------------------------------------

# 118. Engines on the UI: Radar, Signal Feed, Engine Catalogue and the Company Stance Panel

Decided 2026-10-03. Engines are not pages. Sixty sidebar entries would be
unusable and most engines emit nothing on most days, so the UI shows the
*signals* the engines emit, organised three ways, plus one page that says
what each engine is and whether it runs. Sidebar group **Signals** with
three entries: Radar, Signals, Engines. Data health moves to the Data
group once the Radar exists and becomes the landing page.

**Radar** (§44). Opportunity Radar and Risk Radar panels; one tile per
engine with the count of companies in each stage (Early / Emerging /
Confirmed / Reversing) and the change since the previous run. A tile
opens that engine's signal list. Market Regime strip on top.

**Signal feed.** One chronological stream from the ledger (§72) across
all engines, filtered by engine, stage, sector and watchlist. A row is
company, engine, stage transition, strength, historical percentile, with
the evidence facts expandable inline. Stance changes (below) are rows of
their own. This is the source of the daily digest.

**Engine catalogue.** One row per engine from a registry in code: name,
spec section, phase, required tables, status (*not built* / *blocked on
data* / *live*), last run, coverage, and the live hit rate from the
ledger. Status is derived by checking whether the required tables hold
data, so the page is honest from day one and becomes the §76 governance
view later. An engine's page shows its definition, stage rules and §72
performance.

**Company stance panel.** Every company page opens with the result of
all engines summarised to a bottom line. §39 and §52 stand: the stance
is not a score sold as advice, it is a transparent summary of what the
engines say, shown together with the tally that produced it.

-   **Stance:** Long / Lean long / Neutral / Lean short / Short /
    **Avoid**. Avoid is a gate, not a direction: the investability
    filter (§69), distress (§68) or the scam detector (§69.2) fired. The
    panel names the gate and the reason first, and the tally is shown
    greyed beneath it.
-   **Conviction:** Low / Medium / High, from how many engines agree
    and at what stage. Confirmed signals count, Early ones only hint.
    One Confirmed signal with nothing against it is Medium at most;
    three Confirmed in one direction with no Confirmed contradiction is
    High. Short needs the same standard as Long plus the liquidity
    check, since an illiquid short is not actionable.
-   **Engine tally:** a single bar, bullish signals left, bearish right,
    stage as shade. The stance is computed from this bar and nothing
    else, so the arithmetic is visible.
-   **Strongest for / strongest against:** two or three signals each
    side with engine, stage, percentile and the triggering fact linked
    to its source. The contradicting side is always shown.
-   **Engine grid:** every engine as a card, grouped Fundamentals /
    Valuation / Ownership and flows / Price / Events and documents /
    Risk gates, showing stage, direction, last change and a sparkline.
    An engine that has not run shows *no data* and the reason, never a
    blank, so all engines are always visible.
-   **What would change this:** invalidation conditions and the next
    expected data point (§73).
-   **Horizon:** 6--12 months, matching the ledger outcome windows.

Rules: the stance is a deterministic, versioned function of engine
stages and gates, written to the ledger on every emission like any
engine, so it is backtested and its live hit rate appears in the
catalogue. Wording is "signals lean long", never "buy". The §77
disclaimer stays on the panel. The stance is a sortable column on the
Securities and Ownership screens and a filter on the Radar.

**Built 2026-10-03.** All of the above exists for review. Implementation notes that are
decisions in their own right:

-   Application tables (`exclusion_rule`, `engine`, `engine_run`, `signal`, `stance`) live in a
    second Postgres schema, `<data schema>_app`, managed by `load_data.py` and seeded from
    `resources/seed/*.csv`. No script drops the data schema. The two can change independently.
-   The engine catalogue is a seeded table (`engine.csv`, one row per engine here), and the code
    registry (`engines.IMPLEMENTED`) says which rows run. Status on the page is derived from
    whether the tables an engine `requires` hold rows.
-   The stance is written for every priced security on every run, and also for any security a
    gate fired on outside the EQ/SM series, so a trade-for-trade name shows its gate.
-   Stance v1: stage weights early 0.3 / emerging 0.6 / confirmed 1.0 times strength; lean at
    a net 0.6, full at 1.5; conviction counts CONFIRMED signals (HIGH needs three unopposed).
    These are first guesses to be reviewed against known names.
-   Market regime is computed directly on the Radar from the same price features (share above
    the 200-day average, median 3-month return, 1-month breadth); it is not an engine yet.

------------------------------------------------------------------------

# 118.1 Stance v2 and engine-output tests, 4 October 2026

-   **Stance v2** multiplies each signal's stage weight × strength by a per-engine, per-direction
    weight (`service/stance.py: ENGINE_WEIGHT`). The table was derived from the 2019–2024 backtest
    runs at the 12-month horizon (≥ 200 marked signals: 1.5 above a 57% hit rate, 1.0 at 52–57%,
    0.5 at 47–52%, 0 below 47%) and held out on 2025–2026, where long stances improved from 50.8% to
    54.2% hit (+5.5% to +11.3% mean excess) and short from 52.9% to 55.5%. `ingest.py retune`
    recomputes every backtest stance offline from the stored signals under equal and current
    weights and prints both, so the next revision is judged the same way. The ledger is
    survivor-biased for past dates (TODO.md), which the weights inherit.
-   **Engine outputs are tested against the tables they came from** (`tests/test_engine_outputs.py`):
    price distances and returns against `price_daily`, catalyst and governance counts against
    `document`, growth series and operating leverage against `fin_quarter`, ownership changes against
    `shareholding_pattern`, every stored stance against `stance.compute`, plus ledger-shape rules (one
    signal per security-engine-type, price_at = the as-of close, no identical evidence across
    securities for security-level engines, no float noise). Catalyst v2 lists the announcements it
    counted; sector rotation v2 signals only counted members.
-   **Colours (user rule):** long = green, short = blue, avoid = grey. Red stays for risk and gates.

------------------------------------------------------------------------

# 119. Build Notes, 3 October 2026: Phases 1–6 in One Pass

What was built when the instruction was "implement all the phases", and the decisions it forced.
TODO.md carries the open items.

-   **Results XBRL contexts.** NSE's four results taxonomies (Ind-AS, integrated-filing
    `in-capmkt`, NBFC, banking, pre-Ind-AS) all name the plain contexts the same way: `OneD`
    is the quarter, `FourD` the financial year to date, `OneI` the balance sheet at period end.
    `FourD`'s own period dates are often wrong in the file and are not trusted. Every numeric
    fact in those three contexts is stored as filed (`fin_fact`); dimensional contexts
    (segments, OCI items) are not. Canonical line items are mapped per taxonomy at load time
    into `fin_quarter`; banks have no EBITDA and lenders' finance costs are operating costs.
-   **Two results feeds.** The old feed stopped after the Dec-2024 quarter; integrated filings
    start with Mar-2025 and are paginated (`size=10000&page=1` returns a month whole; a
    response shorter than `totalCount` is refused, not loaded).
-   **Market-wide insider and pledge queries return nothing** (confirmed again); they are
    registered as `per_symbol` sources and not yet fetched.
-   **Corporate actions come from the bundle**, not the API: `bc*.csv` is cached for every
    trade date since 2019, so adjustment factors (bonus `n:m` → `m/(m+n)`, face-value split
    `a→b` → `b/a`) needed no download. Capital reductions get no factor (share-count effect is
    not in the text). Prices stay raw; the engine snapshot adjusts as of its date.
-   **Outcome benchmark** is the priced universe's median return over the same window, not an
    index, until index history (§82.2) is loaded.
-   **LLM extraction** uses Claude structured outputs behind `llm.enabled`; rule-based
    classification of announcements stands on its own and is what the catalyst and
    governance engines read.
-   **Universe narrowed to the Nifty 500** (user decision, later the same day; §69.1's hard
    exclusions still apply inside it). BSE group A (702 scrips, 700 on NSE) was considered and
    rejected in favour of the NSE definition. Market-wide files keep being ingested; engines,
    stances, lists and the results download read only constituents. Membership history (§82.2)
    becomes the first backtest-integrity item.
