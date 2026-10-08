"""
The terminology page's content: every piece of finance and exchange jargon the app prints,
with a one-paragraph meaning, a worked example in the units the app shows, and the engines or
pages where the term appears. Plain data, no database — edit here and the page changes.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Term:
    term: str
    group: str
    meaning: str
    example: str
    engines: tuple[str, ...] = field(default=())  # engine keys, linked to /engine/{key}
    aliases: tuple[str, ...] = field(default=())


GROUPS = (
    "Profit and loss",
    "Balance sheet and cash flow",
    "Valuation",
    "Ownership and flows",
    "Price and volume",
    "Derivatives",
    "Corporate actions and events",
    "Exchange and regulation",
    "How the app scores",
)

TERMS: tuple[Term, ...] = (
    Term(
        "PAT (profit after tax)",
        "Profit and loss",
        "The bottom line of the quarter: revenue minus every cost, interest and tax. Indian results report it per quarter; the app sums the last four quarters for a trailing figure.",
        """A cement company's Jun-2026 quarter, ₹ crore: revenue 2,400 · operating costs 1,980 → EBITDA 420 · depreciation 110 → EBIT 310 · finance costs 40 → PBT 270 · tax 68 → PAT 202.
Owners' PAT is 196 after the 6 that belongs to minority holders of a part-owned subsidiary; the app uses the total (q_pat) for growth and the owners' line for EPS.
TTM PAT = Sep-25 170 + Dec-25 185 + Mar-26 190 + Jun-26 202 = 747. A year earlier the four quarters summed to 610, so TTM PAT growth is +22%.
An exceptional ₹90 crore land-sale gain inside the 202 would make underlying PAT 112: always read the exceptional line before trusting a jump.""",
        ("earnings_acceleration", "profitability_inflection", "turnaround", "operating_leverage"),
        aliases=("net profit",),
    ),
    Term(
        "TTM (trailing twelve months)",
        "Profit and loss",
        "The sum of the last four reported quarters, so a company is compared on a full year regardless of where it is in its financial year. It removes seasonality from a single quarter.",
        """A hotel chain earns most of its profit in the Dec quarter (wedding and holiday season):
Quarterly PAT, ₹ crore — Sep-25 40 · Dec-25 160 · Mar-26 90 · Jun-26 50. Comparing Jun-26 (50) with Mar-26 (90) looks like a 44% collapse; it is seasonality.
TTM PAT as of Jun-26 = 40 + 160 + 90 + 50 = 340. TTM a quarter earlier = Jun-25 45 + 40 + 160 + 90 = 335. The business grew 1.5%, which is the honest reading.
Every multiple here (P/E, EV/EBITDA) and every growth rate for operating leverage, implied growth and value trap uses TTM, so a seasonal quarter cannot distort them.""",
        ("margin_inflection", "operating_leverage", "valuation", "implied_growth"),
    ),
    Term(
        "YoY (year on year)",
        "Profit and loss",
        "A quarter compared with the same quarter a year earlier, so festive or monsoon seasonality cancels. QoQ (quarter on quarter) compares with the previous quarter instead.",
        """An air-conditioner maker, quarterly PAT in ₹ crore:
Jun-25 120 · Sep-25 30 · Dec-25 25 · Mar-26 70 · Jun-26 150.
QoQ: Jun-26 against Mar-26 is +114%, which says nothing except that summer sells ACs.
YoY: Jun-26 against Jun-25 is +25%, the real growth. Sep-26 will be judged against Sep-25's 30, not against Jun-26's 150.
Earnings acceleration looks at three consecutive YoY rates: +25% (Jun-26), +18% (Mar-26), +12% (Dec-25) — rising each quarter and all positive, so it fires EARNINGS_ACCELERATING.""",
        ("earnings_acceleration",),
        aliases=("QoQ",),
    ),
    Term(
        "EBITDA and EBITDA margin",
        "Profit and loss",
        "Earnings before interest, tax, depreciation and amortisation: operating profit before financing and accounting charges. The margin is EBITDA as a share of revenue. Meaningless for banks, whose interest is their revenue.",
        """A paint maker's June-2026 quarter, consolidated, in ₹ crore:
Revenue 1,000 · raw materials 520 · employees 90 · other operating costs 170 → EBITDA 220, a 22.0% margin.
Below EBITDA: depreciation 45 → EBIT 175; finance costs 15 → PBT 160; tax 40 → PAT 120.
A year earlier the same quarter had revenue 850 and EBITDA 153, an 18.0% margin. The margin expanded 400 basis points (4 percentage points) while revenue grew 18%, so EBITDA grew 44%: that gap between revenue growth and profit growth is operating leverage.
The app works on TTM figures: the last four quarters' EBITDA summed over the last four quarters' revenue, so one strong quarter cannot fake a trend. Margin inflection fires when the TTM margin has risen for consecutive quarters after a trough at least 200 bp below its 3-year peak — here, if the TTM margin had slid from 24% to 17% through 2024–25 and has since climbed 17.0 → 18.5 → 20.1 → 22.0, that is three rising quarters, CONFIRMED.
Why it is meaningless for banks: a bank's 'interest' is its revenue and its cost of goods, so stripping it out leaves nothing; lenders are read on net interest margin and ROA instead.""",
        ("margin_inflection", "operating_leverage"),
    ),
    Term(
        "Basis points (bp)",
        "Profit and loss",
        "One hundredth of a percentage point. Margins and rates move in basis points so a change is not confused with a percentage change of the figure itself.",
        """A lender's net interest margin moved from 3.40% to 3.65%.
In percentage points that is +0.25; in basis points +25 bp. Saying "up 7%" would be the relative change of the margin itself (0.25 / 3.40) and invites confusion, so margins and rates are always quoted in bp.
In the app: margin inflection needs a trough at least 200 bp (2 percentage points) below the 3-year peak; ROCE inflection needs +200 bp on a year ago; a bond yield going from 7.10% to 7.35% is +25 bp.""",
        ("margin_inflection", "roce_inflection"),
    ),
    Term(
        "Operating leverage",
        "Profit and loss",
        "When costs are largely fixed, a small rise in revenue produces a much larger rise in profit. The ratio of profit growth to revenue growth measures it.",
        """A multiplex chain has rent, staff and depreciation of ₹400 crore a quarter whatever the footfall, and variable costs of 30% of ticket and food sales.
Quarter A: revenue 600 → variable 180 → fixed 400 → profit 20.
Quarter B: revenue 720 (+20%) → variable 216 → fixed 400 → profit 104 (+420%).
Revenue +20% produced profit +420%: that ratio, 21×, is operating leverage, and it cuts both ways — a 20% fall in revenue would wipe the profit out entirely.
The engine fires on TTM PAT growth at least 1.5× TTM revenue growth with revenue growing 5%+; CONFIRMED when the ratio is 3× or more on revenue growth of 10%+. The 4.6× example on the engine page (PAT +124% on revenue +27%) is a chemicals company past its break-even volume.""",
        ("operating_leverage",),
    ),
    Term(
        "Consolidated vs standalone",
        "Profit and loss",
        "Consolidated results include subsidiaries; standalone cover only the parent entity. The app prefers consolidated when a company files both, and says which it used.",
        """A listed holding company owns 100% of a power producer and 60% of a cement subsidiary, and itself only collects dividends.
Standalone: revenue ₹900 crore (dividends and fees), PAT ₹850 crore, margin 94% — meaningless.
Consolidated: revenue ₹18,000 crore, PAT ₹1,500 crore of which ₹300 crore belongs to the 40% minority in cement, so owners' PAT is ₹1,200 crore.
The app prefers consolidated when both are filed for the same quarter and marks every figure with which one it used, so the margin and P/E shown are the group's.
A company that files only standalone (no subsidiaries, or a bank's quarterly results) is compared with itself on the same basis each quarter.""",
        ("valuation", "margin_inflection"),
    ),
    Term(
        "Exceptional items",
        "Profit and loss",
        "One-off gains or losses (asset sales, write-offs, settlements) reported separately so the underlying run rate can be read. A profit made of exceptionals is not repeatable.",
        """A pharma company reports Mar-2026 PAT of ₹620 crore against ₹240 crore a year earlier: +158%.
The results note shows an exceptional gain of ₹410 crore from selling a US plant. Underlying PAT is 620 − 410 = 210, actually down 12%.
The mirror case: a ₹300 crore write-off of a failed drug makes a profitable quarter look like a loss, and the next year's comparison looks heroic.
The app carries q_exceptional separately; accounting quality and earnings acceleration should be read with it, and the company page shows it on the results card so a jump can be checked in one glance.""",
        ("accounting_quality",),
    ),
    Term(
        "CFO (cash flow from operations)",
        "Balance sheet and cash flow",
        "Cash actually generated by the business in the year, before investment and financing. Profit is an accounting opinion; CFO is what arrived in the bank. Indian companies report it half-yearly and at year end.",
        """An infrastructure contractor, FY2026, ₹ crore: PAT 500. Cash flow statement: PAT 500 + depreciation 180 (non-cash) − increase in receivables 520 (customers have not paid) − increase in inventory 90 + increase in payables 60 → CFO 130.
₹500 crore of profit produced ₹130 crore of cash; ₹370 crore is tied up in unpaid bills. If a government client delays further, next year's CFO can be negative while PAT still grows.
Indian companies publish the cash flow statement only half-yearly and at year end, so the app reads the year-end (ytd_cfo) figures for cash flow inflection, accounting quality, capital allocation and deep value.
The healthy pattern is CFO close to or above PAT over a cycle, like a consumer company with CFO 1,050 on PAT 1,000.""",
        ("cash_flow_inflection", "accounting_quality", "deep_value"),
    ),
    Term(
        "Accruals",
        "Balance sheet and cash flow",
        "The gap between reported profit and operating cash flow, scaled by total assets. High accruals mean earnings are being booked ahead of cash and tend to reverse.",
        """FY2026 for a wealth manager, ₹ crore: PAT 1,216 · CFO −2,921 · total assets 27,000.
Accrual ratio = (PAT − CFO) / assets = (1,216 + 2,921) / 27,000 = 15.3%: profit ran ₹4,137 crore ahead of cash.
For an NBFC or broker a negative CFO can be loans and margin funding growing, so the engine skips lenders; for an industrial the same figure means receivables or inventory ballooning.
Thresholds: the engine flags HIGH_ACCRUALS above 10% of assets, EMERGING; the strength rises with the ratio. The historical pattern is that high-accrual years are followed by weaker profit as the accruals reverse.""",
        ("accounting_quality",),
    ),
    Term(
        "Capex and free cash flow (FCF)",
        "Balance sheet and cash flow",
        "Capital expenditure is cash spent on plant, equipment and acquisitions of fixed assets. Free cash flow is CFO minus capex: what is left for debt, dividends and buybacks.",
        """A steel producer, FY2026, ₹ crore: CFO 6,200 · capex 9,800 on a new blast furnace → FCF −3,600, funded by ₹4,000 crore of new borrowing.
Same company FY2023, before the project: CFO 5,100 · maintenance capex 1,400 → FCF 3,700, of which 1,900 went to dividends and 1,500 to repaying debt.
The engine's two readings: capex above 2× CFO at ROCE under 10% is CAPEX_BINGE (the FY2026 picture if the furnace is not earning yet); positive FCF with 20–80% of profit returned and ROCE ≥ 15% is DISCIPLINED_ALLOCATOR (the FY2023 picture).
Capex is not bad in itself: the question the engine asks is whether the capital already deployed earns its keep (ROCE) before more is poured in.""",
        ("capital_allocation",),
    ),
    Term(
        "Payout ratio",
        "Balance sheet and cash flow",
        "Dividends plus buybacks as a share of profit. Very low payout with high cash hoards and very high payout funded by debt are both warnings; 20–80% is the disciplined range here.",
        """Three FY2026 pictures, ₹ crore:
An FMCG company: PAT 2,000 · dividends 1,600 · buyback 0 → 80% payout, with ROCE 60% and no debt — it genuinely has nothing better to do with the cash.
A software services company: PAT 1,000 · dividends 300 · buyback 300 → 60% payout; a tender buyback at a premium also signals the board thinks the stock is cheap.
A capital-goods company: PAT 400 · dividends 400 · new borrowing 350 → 100% payout funded by debt, a warning.
The engine's disciplined band is 20–80%: under 20% with a cash pile and no growth is hoarding; above 80% sustained is usually borrowed or starving the business.""",
        ("capital_allocation",),
    ),
    Term(
        "ROCE (return on capital employed)",
        "Balance sheet and cash flow",
        "TTM EBIT divided by equity plus borrowings: how much operating profit each rupee of long-term capital earns. Above 15% is good for an Indian industrial; it is not computed for lenders, whose capital is the business.",
        """An auto-ancillary maker, TTM to Jun-2026, ₹ crore: EBIT 300. Balance sheet: equity 1,500 · borrowings 500 → capital employed 2,000.
ROCE = 300 / 2,000 = 15%. Its cost of capital is about 11–12%, so each rupee invested earns more than it costs: the business creates value as it grows.
A year earlier EBIT was 220 on capital of 1,950 → 11.3%; the +370 bp move fires ROCE_RISING.
Why not for lenders: a bank's 'capital employed' includes deposits it lends out, so ROCE collapses to a few percent by construction; banks are read on ROA and ROE. Capital allocation uses ROCE ≥ 15% as its quality bar; undervalued growth needs ≥ 12%.""",
        ("roce_inflection", "capital_allocation", "undervalued_growth"),
    ),
    Term(
        "Debt-to-equity",
        "Balance sheet and cash flow",
        "Total borrowings divided by shareholders' equity. Above 1.5× is highly geared for a non-financial company; lenders run far higher by design and are excluded.",
        """A solar developer, Jun-2026 balance sheet, ₹ crore: borrowings 18,988 · equity 5,063 → D/E 3.75×. A year earlier borrowings were 10,422 on equity 4,900 → 2.13×.
Borrowings grew 82% in a year and the ratio jumped 1.6 turns: the engine fires LEVERAGE_SPIKE. Project developers do run high gearing, but the speed of the rise is the point.
The mirror: a hotel company that took borrowings from 4,000 to 3,300 (−17.5%) while equity grew, D/E 1.4× → 1.0×, fires DELEVERAGING.
Context matters: 0.3× is conservative for a manufacturer, 1.5× is high, and an NBFC at 5× is normal, which is why lenders are excluded from both engines.""",
        ("deleveraging", "credit_distress"),
    ),
    Term(
        "Interest cover",
        "Balance sheet and cash flow",
        "TTM EBIT divided by TTM finance costs: how many times operating profit covers the interest bill. Below 1× the company cannot pay interest from operations.",
        """A conglomerate's finance arm, TTM to Jun-2026, ₹ crore: EBIT 17,499 · finance costs 12,275 → cover 1.43×.
Each rupee of interest is covered 1.43 times by operating profit. A 15% fall in EBIT, or a 1 percentage-point rise in borrowing cost on its debt, takes cover under 1.2×; under 1× it must borrow to pay interest.
Engine rules: cover below 1.5× is THIN_INTEREST_COVER, a risk signal; cover below 1× with debt-to-equity above 1.5× is DISTRESS, a gate that makes the stance Avoid regardless of every other signal.
A healthy industrial runs 5–10×; a utility with regulated returns can live at 2.5–3× because its EBIT is predictable.""",
        ("credit_distress",),
    ),
    Term(
        "Altman Z''-score",
        "Balance sheet and cash flow",
        "A bankruptcy-risk score from four balance-sheet ratios (working capital, retained earnings, EBIT and equity, each over assets or liabilities). The non-manufacturer form reads below 1.1 as the distress zone and above 2.6 as safe.",
        """The non-manufacturer form: Z'' = 6.56 × (working capital / assets) + 3.26 × (retained earnings / assets) + 6.72 × (EBIT / assets) + 1.05 × (equity / liabilities).
A telecom operator with assets ₹20,000 crore: working capital −₹8,000 crore (−0.40) · retained earnings −₹30,000 crore of accumulated losses (−1.50) · EBIT ₹600 crore (0.03) · equity ₹1,000 crore against liabilities ₹19,000 crore (0.05).
Z'' = 6.56 × −0.40 + 3.26 × −1.50 + 6.72 × 0.03 + 1.05 × 0.05 = −2.62 − 4.89 + 0.20 + 0.05 = −7.3: far below the 1.1 distress line.
A paint company: 0.15 · 0.55 · 0.22 · 2.0 → 0.98 + 1.79 + 1.48 + 2.10 = 6.4, deep in the safe zone (above 2.6).
The engine fires ALTMAN_DISTRESS_ZONE below 1.1; it was the strongest short-side engine in the backtest, 76% hit at 12 months.""",
        ("forensic_score_pack",),
    ),
    Term(
        "Cash runway",
        "Balance sheet and cash flow",
        "For a loss-making company, cash and bank balances divided by the quarterly cash loss: how many quarters it can survive without raising money.",
        """A two-wheeler EV maker, Jun-2026 quarter, ₹ crore: cash and bank balances 112 · quarterly loss 97 (PAT −97, roughly the cash burn once non-cash depreciation of 20 and working-capital swings are netted).
Runway = 112 / 97 ≈ 1.1 quarters: without a fund-raise it runs out of cash before the Dec quarter ends.
Engine rules: under 4 quarters is CASH_RUNWAY_SHORT (risk); under 2 quarters CASH_RUNWAY_CRITICAL (confirmed, and in the stance it behaves like a gate).
Why it matters for the price: the next move is almost always a QIP or rights issue at a discount, diluting holders, or a promoter infusion at a price the promoter chooses.""",
        ("unit_economics",),
    ),
    Term(
        "Book value and P/B",
        "Valuation",
        "Book value is shareholders' equity per share; P/B is the price divided by it. Below 1 means the market values the company at less than its net assets, common for weak banks and asset-heavy cyclicals.",
        """A public-sector bank: equity ₹1,52,000 crore · 517 crore shares → book value ₹294 per share. Price ₹260 → P/B 0.88.
The market says the bank's assets are worth less than stated — it expects bad loans not yet provided for, or returns below the cost of equity. If the bank earns a 15% ROE on that book, 0.88× is cheap; if 6%, it is fair.
A software company: book value ₹120, price ₹1,500 → P/B 12.5 — normal when the assets that matter (people, contracts) are not on the balance sheet.
Deep value fires below 1× book with positive operating cash flow; valuation reads P/B within the industry so a bank at 0.9× is compared with banks, not with software.""",
        ("deep_value", "valuation"),
    ),
    Term(
        "Market capitalisation",
        "Valuation",
        "Share price times shares outstanding: what the whole company is priced at. Nifty 500 companies run from a few thousand crore to over ₹15 lakh crore.",
        """A cement company: 18.78 crore shares × ₹1,182.80 close = ₹22,214 crore market cap.
A 1:1 bonus doubles the shares to 37.56 crore and halves the price to ₹591: market cap unchanged at ₹22,214 crore. Price per share means nothing without the share count.
Free-float market cap counts only shares not held by promoters: with promoters at 56.7%, free float is 43.3% × 22,214 = ₹9,618 crore, which is what index weights use.
In the app: insider deal flow measures net deal value against market cap (₹775 crore of buying on ₹36,000 crore = 2.15%); the screener's floor is in crore of market cap; P/E is market cap over TTM PAT.""",
        ("insider_deal_flow", "valuation"),
        aliases=("mcap",),
    ),
    Term(
        "P/E (price to earnings)",
        "Valuation",
        "Market cap divided by TTM PAT, or price per share over earnings per share: how many years of current profit the price represents. Only meaningful with positive earnings.",
        """A cement company: market cap ₹22,214 crore · TTM PAT ₹1,909 crore → P/E 11.6. Equivalently price ₹1,183 / EPS ₹101.6.
Read it as a payback: at today's profit the price is 11.6 years of earnings. The inverse, 8.6%, is the earnings yield against a 7% bond.
Context: the construction-materials industry's P/E runs 25–40, so 11.6 is its 0th percentile — CHEAP_ON_EARNINGS. The same 11.6 for a public-sector bank would be the median.
Traps: a loss makes P/E meaningless (the engines skip it); a one-off gain shrinks it artificially (check exceptionals); a cyclical at peak earnings shows a low P/E right before profit halves. Value trap and implied growth exist to catch the last two.""",
        ("valuation", "undervalued_growth", "value_trap", "implied_growth"),
    ),
    Term(
        "EV/EBITDA",
        "Valuation",
        "Enterprise value (market cap plus debt minus cash) over TTM EBITDA. It compares companies regardless of how they are financed; under 5× is cheap, over 20× rich for most industries.",
        """Two cement companies with the same ₹8,000 crore market cap:
A: debt ₹3,000 crore · cash ₹1,000 crore → EV 10,000 · EBITDA 1,230 → 8.1×.
B: no debt · cash ₹2,500 crore → EV 5,500 · EBITDA 1,230 → 4.5×.
Same price for the equity, but a buyer of the whole of A also takes on its net debt, so A is nearly twice as expensive per rupee of operating profit. P/E would hide this because B's interest income flatters its PAT.
Reading: under 5× is cheap (deep value uses it with positive cash flow), 8–12× normal for industrials, 20×+ rich. Not computed for banks and NBFCs, whose debt is their raw material.""",
        ("valuation", "deep_value"),
        aliases=("enterprise value",),
    ),
    Term(
        "Percentile within industry",
        "Valuation",
        "Where a multiple ranks among peers in the same NSE industry, 0 cheapest to 100 dearest. Used instead of absolute cut-offs because a fair P/E for IT is not a fair P/E for steel.",
        """P/E across the 25 Nifty 500 IT services companies on 1-Oct-2026 ranges from 17 to 62. A company at P/E 17.2 has 85% of its peers dearer: 15th percentile.
The same 17.2 in construction materials (range 11–40) would be the 35th percentile; in public-sector banks (range 5–12) the 100th.
Rule: the industry is used when it has at least five members with a valid multiple; otherwise the whole priced universe is the yardstick, and the evidence says which (percentile_basis).
Engine use: valuation fires CHEAP_ON_EARNINGS in the bottom quintile (≤ 20th) and RICH above the 80th; undervalued growth needs below-median P/E; value trap needs bottom quintile with shrinking revenue and profit.""",
        ("valuation", "undervalued_growth", "value_trap"),
    ),
    Term(
        "Implied growth (PEG = 1)",
        "Valuation",
        "Reading the P/E as the annual growth rate the market is paying for. If delivered growth is far above it the stock is under-appreciated; a high P/E with falling profit is priced for a recovery that has not come.",
        """The rough convention: a stock at P/E 25 is priced as if profit will grow about 25% a year for the next few years (PEG = P/E ÷ growth = 1).
A liquor company at P/E 86: implied growth 86%. Delivered TTM PAT growth is −12%. The gap of 98 points is PRICE_NEEDS_GROWTH — the price only makes sense if profit explodes, and it is shrinking.
The mirror: a hospital chain at P/E 28 that grew TTM PAT 55%. Delivered 55% against implied 28% is GROWTH_EXCEEDS_IMPLIED — either the market expects the growth to fade or it has not noticed.
It is a heuristic, not a valuation: it ignores ROCE and duration. Its job is to flag where price and delivered growth disagree most, for a human to look at.""",
        ("implied_growth",),
    ),
    Term(
        "Value trap",
        "Valuation",
        "A stock that looks cheap on multiples because the business is shrinking. The low P/E is the market being right, not an opportunity.",
        """An engineering company at P/E 12.8 when its industry trades at 30. Cheap?
TTM revenue ₹3,400 crore, down 34% as a large order book ran off; TTM PAT ₹210 crore, down 49%. Next year's PAT at this run rate is ₹110 crore, which makes the real forward P/E 24 — not cheap at all.
The engine fires VALUE_TRAP on bottom-quintile P/E with both TTM revenue and PAT shrinking; strength rises with the fall.
The distinguishing question for a human: is the decline cyclical (steel in a downturn, likely to revert) or structural (a print-media company losing readers)? The engine cannot tell; it only stops 'cheap' from being read as 'opportunity' on its own.""",
        ("value_trap",),
    ),
    Term(
        "Deep value",
        "Valuation",
        "Priced below the value of its assets or at a very low multiple of cash earnings while still generating cash, the classic contrarian setup.",
        """A public-sector bank at P/B 0.88 with ₹33,400 crore of operating cash flow in FY2026, or a shipping company at EV/EBITDA 3.2× after a freight boom, both with cash coming in.
The engine fires DEEP_VALUE below 1× book or under 5× EV/EBITDA when the latest year's CFO is positive — the cash-flow condition separates 'cheap and alive' from 'cheap and dying'.
Why it can work: book value anchors the downside, cash keeps the lights on, and any improvement in return on equity rerates the stock toward 1× book.
Why it often does not: the market may be right about hidden bad assets. In the backtest it hit 70% at 12 months, but on only 504 signals and mostly from 2024 on, so the stance gives it a default weight of 1.0 rather than a bonus.""",
        ("deep_value",),
    ),
    Term(
        "Promoter",
        "Ownership and flows",
        "India's term for the controlling shareholder group, the founders or parent that run the company, disclosed separately in every shareholding pattern. Promoter buying is read as confidence; selling as supply or a signal of trouble. Many banks and MNC-free companies have no promoter.",
        """A listed hospital chain: founder family 48.2%, their family trust 6.5%, a group company 4.1% → promoter group 58.8%; FII 18%, DII 12%, public 11%.
Jun-2026 filing shows promoters at 57.5%: a 1.3-point cut. A block deal on 12-Aug shows the family trust selling ₹620 crore to three mutual funds — the cut is explained, and the buyers are long-only institutions, a benign exit.
The engine fires PROMOTER_SELLING on a 1-point quarterly fall (PROMOTER_BUYING on a 1-point rise). Three consecutive quarters of selling is CONFIRMED.
Companies with no promoter (HDFC Bank, ICICI Bank, ITC, L&T, Infosys) show NULL and the engine stays silent. A promoter *pledging* rather than selling is a different and more dangerous signal.""",
        ("promoter_activity", "supply_overhang"),
    ),
    Term(
        "FII / FPI and DII",
        "Ownership and flows",
        "Foreign institutional (portfolio) investors and domestic institutional investors (mutual funds, insurers, pension funds, banks). Together they are 'institutions'; their quarterly change is the clearest footprint of professional money.",
        """A private bank's Jun-2026 shareholding pattern: FPI 22.1% (foreign funds and sovereign wealth funds), mutual funds 24.8%, insurance companies 18.6%, other DII 11.8% → DII 55.2%, institutions 77.3%; promoter none; public 22.7%.
A quarter earlier institutions held 76.1%. The 1.2-point rise fires INSTITUTIONAL_ACCUMULATION, EARLY; if next quarter adds another point it becomes EMERGING, three in a row CONFIRMED.
Reading the two sides: FPIs sold Indian equities heavily through 2025 while DIIs (SIP money) absorbed it. A stock where both are buying is rare and strong; where FPIs sell and DIIs buy is the market's current norm.
The parser derives FII as FPI plus foreign venture capital and DII as the remaining institutions, because older filings did not split them.""",
        ("institutional_accumulation", "smart_money_divergence"),
    ),
    Term(
        "Shareholding pattern",
        "Ownership and flows",
        "The quarterly filing (within 21 days of quarter end) listing holdings by promoter, institution and public category. Occasionally filed on an event date, such as after a QIP, which is why a 'quarter' can show an odd date.",
        """Timeline for the Jun-2026 quarter: quarter ends 30-Jun; SEBI deadline 21-Jul; a cement company broadcasts on 16-Jul at 18:42.
The app assigns the filing to period_end 30-Jun but lets engines see it only from 17-Jul: for a backtest run as of 10-Jul the ownership table still shows March's numbers, as it did for anyone trading that day.
What it carries: promoter / FII / DII / mutual fund / insurance / retail percentages, number of shareholders (retail participation), pledged promoter shares.
Oddities you will see: an event-based filing after a QIP dated 30-Jul appears as its own 'quarter'; companies with no promoter show a NULL promoter column; a few older XBRLs do not split FII from DII.""",
        ("promoter_activity", "institutional_accumulation"),
    ),
    Term(
        "Pledge",
        "Ownership and flows",
        "Promoters borrowing against their shares. If the price falls the lender can sell the collateral, so a large pledge turns a price fall into forced supply. Disclosed per symbol on NSE; not yet loaded here.",
        """A promoter holds 70% of a company worth ₹10,000 crore and has pledged 60% of that stake (42% of the company, ₹4,200 crore of shares) to borrow ₹2,000 crore for another venture, at a 2:1 collateral cover.
The stock falls 30%: the pledged shares are now worth ₹2,940 crore, under the 1.5:1 trigger. The lender asks for more shares or cash; failing that, it sells in the open market — forced supply into a falling price, which pushes it lower and triggers the next lender.
This is how several mid-caps lost 70–90% in 2019: the fall was mechanical, not a judgement about the business.
The source is registered (NSE answers per symbol) but not loaded yet; when it is, supply overhang will add pledge changes to its lock-in and promoter-selling reads, and corporate governance already counts pledge disclosures among its flags.""",
        ("supply_overhang", "corporate_governance"),
    ),
    Term(
        "Bulk and block deals",
        "Ownership and flows",
        "Trades NSE publishes with the counterparty's name: a bulk deal is over 0.5% of shares in a day, a block deal a single negotiated trade in a special window. Net buying by named parties over 90 days is read against market cap.",
        """Bulk: on 15-Sep-2026 a fund buys 0.7% of a mid-cap's shares across the day; crossing 0.5% in one session obliges NSE to publish 'client name, buy, 42 lakh shares at ₹386.20' after the close.
Block: a promoter and three mutual funds agree a price and the trade prints in the block window (8:45–9:00 or 14:05–14:20) — ₹620 crore in one line.
A client's deals over 90 days: buys ₹7,807 crore, sells ₹61 crore → net ₹7,746 crore, 2.15% of market cap, two distinct buyers. Insider deal flow fires NET_DEAL_BUYING; above 5% of market cap it is CONFIRMED.
Caveats: a market-maker like Graviton appears on both sides every day with net flows near zero; a mutual fund's name on the buy side is informative, an HFT's is not. The client page sums each name's disclosed book.""",
        ("insider_deal_flow", "supply_overhang"),
    ),
    Term(
        "Lock-in",
        "Ownership and flows",
        "After an IPO, SEBI bars pre-IPO holders from selling for 6 months and promoters for 18 months (anchor investors 90 days). Expiry dates are known supply events.",
        """A company lists on 6-May-2025 after a ₹5,000 crore IPO.
Anchor investors (allotted the day before the issue opened) are locked for 90 days on half their shares and 30 days on the rest: free from early August 2025.
Pre-IPO investors (venture and private equity) are locked for 6 months: free 6-Nov-2025 — the classic first wave of selling in a new listing.
Promoters must keep 20% of post-issue capital locked for 18 months (free 6-Nov-2026) and the remainder for 6 months.
Supply overhang fires LOCKIN_EXPIRY_AHEAD when a 6- or 18-month date falls in the next 30 days. The price often weakens into the date and stabilises once the overhang has actually sold, so the window after expiry is also worth watching.""",
        ("supply_overhang", "ipo_newly_listed"),
    ),
    Term(
        "OFS (offer for sale) vs fresh issue",
        "Ownership and flows",
        "In an IPO, a fresh issue raises money for the company; an OFS is existing holders cashing out. A mostly-OFS IPO funds nothing and signals the insiders wanted an exit.",
        """IPO A, ₹5,000 crore: fresh issue ₹800 crore (goes to the company for a new plant), OFS ₹4,200 crore (goes to the private-equity holder selling 84% of its stake). The company is worth exactly what it was the day before; insiders cashed out at the price they set.
IPO B, ₹1,200 crore: fresh issue ₹1,100 crore to repay ₹900 crore of debt, OFS ₹100 crore so the promoter can meet the 25% public-float rule. The balance sheet transforms; the promoter stays at 65%.
The prospectus 'objects of the issue' and the OFS share are the first things to read in a new listing; with the lock-in calendar they say who will want to sell and when.
Not yet parsed by the app (the IPO engine reads only price); listed in TODO.md as the input a promoter-exit read would need.""",
        ("ipo_newly_listed",),
    ),
    Term(
        "QIP and preferential issue",
        "Ownership and flows",
        "Ways a listed company raises equity: a qualified institutional placement sells new shares to institutions quickly; a preferential issue to named investors, often the promoter. Both dilute existing holders.",
        """A real-estate developer with 50 crore shares at ₹400 raises ₹2,000 crore by QIP: 5.26 crore new shares to institutions at ₹380 (SEBI's floor is the two-week average price, less a permitted 5% discount). Every existing holder now owns 9.5% less of the company; the stock usually trades toward the issue price for a while.
A preferential issue: the promoter is allotted 2 crore shares at ₹410 (the regulatory floor) to fund a stake increase — dilutive to others but a strong vote of confidence, and locked in for 6 months.
Watch the sequence: a QIP a few months after a sharp run-up is management selling the company's shares high; a preferential issue to the promoter after a fall is the promoter buying low.
The catalyst engine reads 'fund raising' and 'preferential' board-meeting purposes as upcoming events; corporate event tracks the ex-dates.""",
        ("catalyst", "corporate_event"),
    ),
    Term(
        "Close, adjusted close",
        "Price and volume",
        "The closing price NSE prints. After a bonus or split the share count changes, so older closes are scaled onto today's share basis before any average or return is computed; otherwise a 1:1 bonus looks like a 50% crash.",
        """A company closes at ₹2,000 on Friday. A 1:1 bonus goes ex on Monday: holders now have two shares each and the stock opens around ₹1,000.
Raw closes: … 1,980, 2,000, 1,000, 1,010 … A 200-day average computed on these shows the price 'crashing' 50% through a rising average, and the 52-week high of ₹2,000 is never approached again — three engines would fire nonsense (TREND_DOWN, RS_LAGGARD, a −50% results reaction).
Adjusted: every close before the ex-date is multiplied by the factor 0.5 → … 990, 1,000, 1,000, 1,010 …, a continuous series. Splits (₹10 face to ₹1: factor 0.1) and bonus 5:1 (factor 1/6) work the same way.
The app stores raw closes and applies the factors from the corporate-action table at query time, as of the date being computed, so the same rows serve a 2021 backtest and today. Dividends are not adjusted for (total-return series would), a known simplification.""",
        ("technical_price", "relative_strength"),
    ),
    Term(
        "Turnover",
        "Price and volume",
        "Value traded in the day (shares × price), in rupees. The app's liquidity floor is ₹1 crore a day; below it a stock cannot be entered or exited at the printed price.",
        """A small-cap trades 2 lakh shares at an average ₹450 → ₹9 crore turnover for the day. Its 20-day average is ₹6 crore and its 120-day average ₹3 crore: today is 3× normal.
The investability floor is ₹1 crore a day: below it, buying ₹50 lakh of stock moves the price against you and selling it in a hurry is impossible. 433 NSE securities fail it; they are gated out before any engine runs.
Volume delivery compares the 20-day average turnover with the 120-day: at 2× or more, with delivery also rising, it fires DELIVERY_VOLUME_SURGE.
Manipulation risk reads the opposite: a +134% move in six months on a 60-day median turnover of ₹1.3 crore is a run-up nobody of size could have participated in.""",
        ("investability", "volume_delivery", "manipulation_risk"),
    ),
    Term(
        "Delivery percentage",
        "Price and volume",
        "The share of traded quantity that actually changed hands into demat accounts rather than being squared off the same day. High delivery means buyers are keeping the stock; low delivery on a run-up means speculation or an operator churning.",
        """On 1-Oct-2026 a stock trades 10 lakh shares; at day end 3.4 lakh move between demat accounts (the rest were bought and sold intraday by the same hands) → delivery 34%.
A large-cap bank normally runs 50–65% delivery; an F&O-heavy counter 25–40%; a sleepy mid-cap 60–80%.
Reading it with price: a stock up 134% in six months with a 60-day median delivery of 34% and tiny turnover is being churned, not accumulated — SUSPECT_RUN_UP (manipulation risk). The same move on 70% delivery and rising turnover is real buying — DELIVERY_VOLUME_SURGE.
Data notes: NSE publishes delivery in a separate file; trade-for-trade series (BE, BZ) are 100% delivery by rule and are excluded; the app keeps the medians over 20, 60 and 120 sessions.""",
        ("volume_delivery", "manipulation_risk"),
    ),
    Term(
        "50-day and 200-day moving averages",
        "Price and volume",
        "The average close over the last 50 or 200 trading sessions. Price above a rising 50-day that is above the 200-day is an uptrend; the 200-day's slope says whether the long trend is turning.",
        """A housing financier on 1-Oct-2026: close ₹448.40 · 50-day average ₹476.74 · 200-day ₹481.69 · 200-day a month ago ₹484.50 (slope −0.6%).
Price below the 50-day, 50-day below the 200-day, 200-day falling: every layer of the trend points down → TREND_DOWN. It sits 3.7% above its 52-week low, so the stage is CONFIRMED (within 5% of the extreme).
The mirror, an auto-parts maker: close ₹1,010 · 50-day ₹940 · 200-day ₹860 rising, 3% below its 52-week high → TREND_UP, CONFIRMED.
Averages lag by construction, so these engines never catch a turn early; they confirm one. Market regime counts how many of the 494 are above their 200-day: 181 (38%) on 1-Oct-2026, a RISK_OFF reading.""",
        ("technical_price", "market_regime"),
        aliases=("DMA", "SMA"),
    ),
    Term(
        "52-week high and low",
        "Price and volume",
        "The highest and lowest adjusted close over the last 252 sessions. Distance from them is given in percent; 'at its 52-week low' means today is the low.",
        """A cement stock: highest adjusted close in the last 252 sessions ₹1,913.70 (Nov-2025), lowest ₹1,182.80 — which is today's close. It is at its 52-week low, 38% below the high.
On 1-Oct-2026, 59 of 478 universe stocks closed at a 52-week low; on 29-Sep it was 53. That cluster is what a broad downtrend looks like at the stock level, and why the regime reads risk off.
Engine use: TREND_UP is CONFIRMED within 5% of the high, TREND_DOWN within 5% of the low; the IPO engine's leader case needs the price near its high.
Why adjusted: without bonus/split adjustment a 1:1 bonus would set a fake 52-week high that the stock can never revisit.""",
        ("technical_price", "ipo_newly_listed"),
    ),
    Term(
        "Relative strength",
        "Price and volume",
        "A stock's return ranked against every other priced stock over the same window, as a percentile. A leader is in the top quintile on both 6 and 12 months; it says nothing about value, only persistence.",
        """Returns over the last 6 months across the 480 priced universe stocks range from −55% to +140%. A liquor company at +68% has 451 stocks below it: 94th percentile. Over 12 months it is +27%, 81st percentile.
Top quintile (≥ 80th) on both windows → RS_LEADER. Its 3-month return (+3.7%, 78th percentile) is still above median, so the stage is CONFIRMED; had the 3-month slipped below the 60th percentile the stage would drop to REVERSING.
The mirror: bottom quintile on both windows → RS_LAGGARD.
What it is not: a value judgement. Momentum persists over 6–12 months in most markets and then mean-reverts; in the backtest RS_LEADER longs hit only 48% at 12 months, which is why the stance weighs it at 0.5.""",
        ("relative_strength",),
    ),
    Term(
        "Breadth and market regime",
        "Price and volume",
        "How many stocks are participating: the share above their 200-day average and the share that advanced over a month. Most above with a positive median 3-month return is RISK_ON; both weak is RISK_OFF.",
        """1-Oct-2026: 181 of the 480 universe stocks with a 200-day history are above it (38%); the median stock is −7.9% over three months; 77 of 494 (16%) rose over the last month.
Rules: RISK_ON needs more than 60% above the 200-day *and* a positive median 3-month return; RISK_OFF needs under 40% *and* a negative median; anything else is MIXED. So this is RISK_OFF — a broad downtrend, not a few index heavyweights falling.
Contrast Jan-2024: 82% above the 200-day, median 3-month +11% → RISK_ON.
Why it matters: in RISK_OFF most long signals fail regardless of the company, so the Radar shows it first; the market-history page draws all three lines back to 2019.""",
        ("market_regime", "sector_rotation"),
    ),
    Term(
        "Drawdown",
        "Price and volume",
        "The largest fall from a peak to a later trough within a window, the pain an investor would have sat through even if the end-to-end return was fine.",
        """Bought at ₹100 on 1-Jan. Path: ₹140 by March (peak), ₹98 in June (trough), ₹125 at year end.
Return: +25%. Maximum drawdown: from 140 to 98 is −30% — the loss an investor actually sat through, and the point at which most people sell.
Two signals with the same +25% twelve-month return are not equal if one went there via −30% and the other via −8%; the outcome tables record mean drawdown per engine for exactly this reason.
In the stance outcomes, SHORT stances show positive excess returns with large drawdowns in 2020–21: the shorts were 'right' for weeks and then crushed by the market.""",
        (),
    ),
    Term(
        "Open interest (OI)",
        "Derivatives",
        "The number of futures or options contracts outstanding. Rising OI means new positions; falling OI means positions being closed. Read with price direction it tells who is adding.",
        """A stock future has 1,598,750 shares of open interest on 1-Oct-2026 (lot size 250 → 6,395 contracts). Five sessions earlier it was 1,780,000.
OI fell 10% while the price fell 3.2%: positions were closed, not opened, and since the price fell as they closed, it was longs giving up — LONG_UNWINDING (bearish, EARLY).
OI is not volume: 10,000 contracts can trade in a day and leave OI unchanged if every buyer of a new position met a seller closing one.
Only the ~190 stocks in the F&O segment have OI; the derivatives engine is silent elsewhere. Data comes from NSE's F&O bhavcopy, summed across expiries per underlying.""",
        ("derivatives_signal",),
    ),
    Term(
        "Long build-up, short covering and their mirrors",
        "Derivatives",
        "OI up with price up is a long build-up (bullish); OI down with price up is short covering (bullish, but weaker). OI up with price down is a short build-up; OI down with price down is long unwinding (both bearish).",
        """Four combinations of a week's change in futures OI and price, with an example each:
Long build-up: OI +18%, price +6% — new money buying futures, bullish and the strongest of the four.
Short covering: OI −12%, price +4% — shorts closing in a hurry push the price up, bullish but exhausted once they are done.
Short build-up: OI +15%, price −5% — new shorts opening, bearish.
Long unwinding: OI −10%, price −3.2% — longs giving up, bearish but often near the end of a fall.
The engine needs both moves to be material (about 5% OI and 2% price over five sessions) and grades the stage by size; it is a 1–3 week signal and sits at weight 0.5 in the stance for that reason.""",
        ("derivatives_signal",),
    ),
    Term(
        "Basis and put-call ratio (PCR)",
        "Derivatives",
        "Basis is the futures price minus the spot, in percent; a positive basis is normal, a negative one shows selling pressure. PCR is put OI over call OI; well below 1 means more bets on upside, well above 1 more on downside.",
        """Spot ₹1,000, near-month future ₹1,001.25 → basis +0.125%: normal, the cost of carry for a few weeks at 6–7% a year.
Future ₹994 → basis −0.6%: traders are paying to be short, or expecting a dividend; sustained negative basis in a falling stock is selling pressure.
PCR: put OI 450,000 against call OI 600,000 → 0.75. More bets (or hedges) on upside than downside, mildly bullish. Above 1.2 the crowd is defensive — which, at extremes, is contrarian bullish.
Both ride along as evidence in derivatives signals rather than firing on their own; the engine's call is made on OI and price together.""",
        ("derivatives_signal",),
    ),
    Term(
        "Ex-date and record date",
        "Corporate actions and events",
        "The record date is when the register is read to decide who receives a dividend, bonus or rights; the ex-date is the first trading day the stock trades without that entitlement, and the price adjusts that morning.",
        """A company announces a ₹5 interim dividend with record date Monday 10-Nov-2026. Under T+1 settlement a purchase settles the next business day, so the ex-date is also 10-Nov: buy by Friday 7-Nov to be on the register.
On 10-Nov the stock opens about ₹5 lower; the dividend has left the price. Buying on the ex-date for the dividend is buying nothing.
For a 1:1 bonus with record date 10-Nov, the ex-date is the day the price halves and the share count doubles; the bonus shares arrive in demat a few days later, so for a day or two a holder's portfolio shows half its value.
The corporate-event engine reads the ex-date from the daily reports bundle and fires BONUS_AHEAD / SPLIT_AHEAD / BUYBACK_AHEAD / RIGHTS_ISSUE_AHEAD while the date is still ahead.""",
        ("corporate_event",),
    ),
    Term(
        "Bonus and stock split",
        "Corporate actions and events",
        "A bonus issues free extra shares from reserves (1:1 doubles the count); a split cuts the face value (₹10 → ₹1 gives ten shares for one). Neither changes what you own; the price adjusts proportionally, hence adjusted closes.",
        """Bonus 1:1 on 100 shares at ₹2,000 (₹2 lakh): 200 shares at ₹1,000, still ₹2 lakh; reserves are capitalised into share capital. Bonus 5:1: 600 shares at ₹333.
Split ₹10 face value → ₹1: 100 shares at ₹2,000 become 1,000 at ₹200; nothing moves between reserves and capital.
Neither changes what anyone owns. Companies do it to make the share price 'affordable' and improve liquidity; a stock that announces a bonus after a 3× run-up is often also one whose promoters want to sell into a bigger retail crowd.
In the app: the adjustment factor (0.5, 1/6, 0.1) is parsed from the daily reports bundle's purpose text and applied to all earlier closes; the backtest showed BONUS/SPLIT_AHEAD longs hitting only 33%, so corporate-event longs weigh 0 in the stance.""",
        ("corporate_event", "technical_price"),
    ),
    Term(
        "Buyback",
        "Corporate actions and events",
        "The company purchasing its own shares, through a tender offer at a fixed price or in the open market. Cash returned to holders and a signal the board thinks the stock is cheap.",
        """Tender buyback: an IT services company offers to buy 2% of its shares at ₹1,500 when the stock is ₹1,300. Holders tender; small shareholders have a reserved 15% quota, so a holder of 100 shares might get 20 accepted at a 15% premium and keep the rest.
Open-market buyback: the company buys up to ₹1,000 crore on the exchange over six months, supporting the price day by day.
Why it matters: cash returned without dividend tax (the company pays buyback tax instead), fewer shares so EPS rises, and the board is saying the stock is cheap. A buyback funded by debt or at a 60× P/E says something else.
Catalyst reads an upcoming board meeting 'to consider buyback' (0.4 points) and a buyback announcement (0.5); corporate event fires BUYBACK_AHEAD before the record date; capital allocation counts the cash as returned to holders.""",
        ("corporate_event", "catalyst", "capital_allocation"),
    ),
    Term(
        "Rights issue",
        "Corporate actions and events",
        "Existing holders are offered new shares at a discount in proportion to their holding. It raises money but dilutes anyone who does not subscribe, so it reads as bearish supply.",
        """A company at ₹100 announces 1 rights share for every 4 held at ₹80, raising ₹2,000 crore. A holder of 400 shares (₹40,000) may buy 100 more for ₹8,000.
Theoretical ex-rights price: (4 × 100 + 1 × 80) / 5 = ₹96 — the stock drops about 4% on the ex-date just from the arithmetic.
Subscribe and you keep your 100% stake; ignore it and you own 20% less of the company and the right lapses (or you sell the entitlement, which trades briefly as a separate instrument).
It is the dilutive way to raise money — a QIP goes to institutions, a rights issue asks existing holders to pay up, and large rights issues (telecoms in 2019 and 2021) follow balance-sheet distress. Corporate event fires RIGHTS_ISSUE_AHEAD as a bearish signal.""",
        ("corporate_event",),
    ),
    Term(
        "Demerger",
        "Corporate actions and events",
        "Splitting a company so a division becomes a separately listed company whose shares are given to existing holders. Often unlocks value when the parts were hidden in the whole.",
        """A conglomerate (₹600 a share) separates its hotels business. Record date 15-Dec: each holder receives one share of the new hotels company per share held; the parent trades ex-demerger at about ₹500 and the hotels company lists weeks later at ₹100–130, found by price discovery.
Why it unlocks value: the parent traded at 12× earnings as a 'conglomerate' while listed hotel companies trade at 25×; separately listed, the hotels arm rerates and the parent's own business is easier to read.
Mechanics to watch: index funds must sell the piece that is not in their index on listing day, which creates a temporary selling wave and often a cheap entry.
Corporate event fires DEMERGER_AHEAD; the special-situations engine (§67) that would track the full timetable is not built.""",
        ("corporate_event",),
    ),
    Term(
        "Results broadcast and reaction",
        "Corporate actions and events",
        "Quarterly results are filed to the exchange within 45 days of quarter end (60 for Q4). The app reads the price from the close before the broadcast to three sessions after against the quarter's PAT change: a rerating.",
        """A chemicals company's Jun-2026 results are broadcast to NSE on 23-Jul at 16:10, after the close. Close on 23-Jul ₹1,340 (the 'before'); three sessions later, 28-Jul, ₹1,460: +9.0%.
The quarter: PAT +40% YoY. Profit up a lot and the stock rerated up — RESULTS_RERATED_UP, strength from the size of the move.
Other patterns: PAT +25% but the stock −6% (expectations were higher; RESULTS_RERATED_DOWN); PAT −30% but the stock +4% (the market feared worse).
Deadlines: 45 days after quarter end, 60 for the March quarter; a broadcast after 15:30 counts from the next session. The app has no analyst-consensus feed, so this engine reads the market's reaction as the consensus.""",
        ("consensus_reaction",),
    ),
    Term(
        "Catalyst",
        "Corporate actions and events",
        "A dated event that can change how the market values a company: a board meeting on a buyback or fund raise, order wins, acquisitions, approvals. Several in one window compound.",
        """A defence electronics company on 1-Oct-2026: board meeting on 11-Oct 'to consider buyback' (special purpose, 0.4 points); announcements in the last 45 days — two order wins (0.2 each) and one acquisition (0.3).
Score 1.1: EMERGING (CONFIRMED needs 1.2). The evidence lists the four filings by date with their summaries so each can be checked.
Why dated events matter: a buyback record date, an order conversion or a regulatory approval forces the market to reprice on a known day; a vague 'strong growth prospects' does not.
Two companies with the same score are not alike — the engine cannot weigh a ₹50 crore order against a ₹5,000 crore one — so the catalyst engine's longs sit at weight 0.5 in the stance, and the listed filings are the point.""",
        ("catalyst",),
    ),
    Term(
        "NSE series (EQ, BE, BZ, SM, ST)",
        "Exchange and regulation",
        "The segment suffix on every NSE scrip. EQ is normal rolling settlement; BE and BZ are trade-for-trade (no intraday squaring, delivery compulsory, usually a surveillance measure); SM and ST are the SME platform. The app keeps EQ and SM and excludes the rest.",
        """RELIANCE-EQ: normal rolling settlement; intraday buying and selling allowed, F&O available.
XYZ-BE: trade-for-trade — every purchase must be taken into delivery and every sale delivered; no intraday squaring. NSE moves a stock here as a surveillance step, often alongside a 5% band; liquidity collapses.
ABC-BZ: trade-for-trade for a company that has not complied with listing rules (unpaid fees, no results filed).
PQR-SM / -ST: SME platform, lot-based trading, small companies with lighter disclosure.
The app's universe keeps EQ and SM; BE, BZ and ST are excluded by rule, and a security's move into BE is visible in its history as a gap in the delivery data (trade-for-trade shows no delivery figure).""",
        ("investability",),
    ),
    Term(
        "ASM, GSM and ESM",
        "Exchange and regulation",
        "NSE and SEBI surveillance lists. Additional Surveillance Measure (long and short term, stages I–IV) raises margins on volatile stocks; Graded Surveillance Measure targets suspected manipulation with stricter stages; Enhanced Surveillance Measure covers small caps. GSM and ESM exclude a stock here; ASM is a warning.",
        """A logistics stock up 134% in six months lands on ASM long-term stage I: 100% margin on every trade (no leverage), a 5% price band. Stage IV adds a trade-for-trade move. The app shows SURVEILLANCE_ASM as a warning and keeps the stock investable.
A micro-cap that doubled on no news goes to GSM stage II: trade-for-trade, 100% margin, and a ₹1 lakh additional surveillance deposit per trade that is held for five months — designed to stop speculation outright. GSM excludes the stock from the universe.
ESM applies to companies under ₹500 crore market cap with abnormal moves: stage I is a 5% band, stage II periodic call auctions only. ESM also excludes.
The lists are refreshed daily from NSE and snapshotted, so the backtest knows which day a stock went on and came off (from Oct-2026; earlier it sees today's lists — a known leak in TODO.md).""",
        ("investability",),
    ),
    Term(
        "Price band and circuit",
        "Exchange and regulation",
        "The daily limit (2%, 5%, 10% or 20%) a stock may move before trading halts at that price. Hitting the upper circuit day after day on thin volume is an operator hallmark; the 'circuit hits' table records every band hit.",
        """A ₹50 stock with a 5% band can trade between ₹47.50 and ₹52.50 today; orders beyond that are rejected. Hitting ₹52.50 is an 'upper circuit' — buyers queue, nobody sells, no trades print.
Bands: 2%, 5%, 10% and 20% for stocks without derivatives; F&O stocks have no fixed band (a dynamic 10% that NSE can widen). The daily reports bundle lists every stock that touched its band, which the app stores as circuit hits.
The operator pattern: a ₹12 stock hits the 5% upper circuit 20 sessions in a row on a few hundred shares a day — the price has gone from 12 to 32 with almost nobody able to buy or sell. Manipulation risk counts serial circuit hits toward OPERATOR_PATTERN.
Market-wide circuits (10%, 15%, 20% on the Nifty) halt the whole exchange and are a different thing.""",
        ("manipulation_risk",),
    ),
    Term(
        "ISIN and symbol",
        "Exchange and regulation",
        "The ISIN (INE…) is the permanent 12-character identifier of a security; the NSE symbol is the ticker, which can change on a rename. The app keys everything on ISIN and shows the symbol.",
        """INE002A01018 is Reliance Industries: IN (country), E (equity), 002A (issuer), 0101 (security), 8 (check digit). It never changes while the share exists.
Symbols change: ZEEL → ZEE, MINDTREE → LTIM after a merger, ADANITRANS → ADANIENSOL after a rename. A table keyed on symbol would break every history at the rename; the app keys prices, signals and stances on ISIN and shows the current symbol.
Mutual fund units and ETFs carry INF… ISINs and trade in the EQ series; they are in the price table but not in the security master.
Related identifiers you may meet: BSE scrip code (500325 for Reliance) and the company's CIN; neither is used here since the app is NSE-only.""",
        (),
    ),
    Term(
        "XBRL",
        "Exchange and regulation",
        "The machine-readable format in which results, shareholding patterns and BRSR reports are filed to NSE. Every fundamental figure here is parsed from these files, by taxonomy (Ind AS, banking, NBFC).",
        """A June-quarter results filing arrives as an XBRL instance: hundreds of tagged facts such as RevenueFromOperations = 24000000000 for context 'Q1FY27 consolidated', ProfitLossForPeriod, FinanceCosts, and at year end the cash-flow and balance-sheet items.
The parser maps tags to the app's canonical columns per taxonomy — Ind AS for most companies, a banking taxonomy (interest earned, provisions, gross NPA %), an NBFC variant, a legacy non-Ind-AS one — into one fin_quarter row per company, period and consolidated/standalone.
Shareholding patterns and BRSR reports are XBRL too; older shareholding files (before 2025) use a different layout the parser also handles.
Why it matters: every fundamental figure in the app traces to a tagged fact in a cached file under raw/, which is what makes the numbers checkable and the tests possible (23,890 quarters loaded for the universe).""",
        (),
    ),
    Term(
        "BRSR",
        "Exchange and regulation",
        "Business Responsibility and Sustainability Report, the annual ESG filing of the top 1,000 listed companies. The app reads it for the company's website, business activities and products, not for scores.",
        """A diversified chemicals company's FY2025 BRSR, filed with the annual report: website, three business activities (specialty chemicals 62% of turnover, agrochemicals 28%, pharma intermediates 10%), nine named products, number of employees and plants, energy and water use, CSR spend.
The app reads the website, business lines and products into the company profile and the products list on the company page; it does not score ESG.
Mandatory for the top 1,000 listed companies by market cap, so about 1,900 smaller NSE companies file none and have no website on their page — a listed gap.
Three universe filings cannot be loaded (two links answer 404 at NSE, one file is truncated on NSE's server); they are kept in raw/_quarantine so nobody retries them blindly.""",
        (),
    ),
    Term(
        "Nifty 500 and index membership",
        "Exchange and regulation",
        "NSE's broad index of the 500 largest companies by free-float market cap, rebalanced half-yearly. It is this app's universe; membership history matters because the list in 2020 was not the list today.",
        """The Nifty 500 covers about 92% of NSE's free-float market cap; rebalanced each March and September. Nifty 50 ⊂ Nifty 100 ⊂ Nifty 200 ⊂ Nifty 500; the sidebar focus narrows pages to one of them.
A company joins in March 2024 after its market cap crosses the cut-off; another drops out in September 2025 after a 60% fall. Today's list says nothing about who was in it in 2020.
Why history matters: a backtest run as of June 2020 must use the June-2020 constituents, else it 'knows' which small companies would later grow into the index (future-member bias). The app stores yearly snapshots from 2013 and picks the newest one on or before the run date.
The remaining bias: companies that *left* the index since had their prices pruned in Oct-2026, so a 2020 run cannot price them — the survivors look better than the real list did. TODO.md records the fix and the decision pending.""",
        ("sector_rotation",),
    ),
    Term(
        "Crore and lakh",
        "Exchange and regulation",
        "Indian numbering. One lakh is 100,000; one crore is 10 million (100 lakh). Company results are filed in lakh or crore; the app prints crore throughout.",
        """1 lakh = 1,00,000 (10^5). 1 crore = 100 lakh = 1,00,00,000 (10^7). Written with Indian grouping: ₹12,34,56,789 is 12 crore 34 lakh 56 thousand 789.
₹1,216.2 crore = ₹12,162 million = ₹12.16 billion. ₹1 lakh crore = ₹1 trillion. At ₹84 to the dollar, ₹1,000 crore ≈ $119 million.
Results are filed in lakh or crore depending on the company (the XBRL carries the scale); the app normalises to rupees in the database and prints crore everywhere, with one decimal for figures under ₹100 crore.
A share price is in rupees, market cap in crore, a block deal in crore, a client's P&L in crore — if a number on a page looks a thousand times off, check which unit the source filing used.""",
        (),
    ),
    Term(
        "Signal, direction and stage",
        "How the app scores",
        "A signal is one engine's dated finding on one security. Direction is BULL, BEAR or GATE. Stage is how established it is: EARLY (first sighting), EMERGING (two periods), CONFIRMED (three or more), MATURE (long-running) and REVERSING (breaking down).",
        """One row in the ledger: 1-Oct-2026 · 360ONE · engine margin_inflection v1 · signal MARGIN_EXPANDING · direction BULL · stage CONFIRMED · strength 1.0 · headline 'EBITDA margin up 34.1 points from its trough over 9 quarters, to 62.0%' · evidence {the six TTM margins} · invalidation 'margin falls for two quarters' · price at emission ₹1,090.
Direction: BULL (for), BEAR (against), GATE (uninvestable, overrides).
Stage, the state machine: EARLY on first sighting, EMERGING after two periods, CONFIRMED after three or more, MATURE when long-running, REVERSING when the condition is breaking down. Promotion needs consecutive confirming periods; demotion takes one clear break (spec §85).
Strength (0–1) is how far past the threshold the measurement is. The stance weighs stage × engine weight × strength; the signal feed and the company panel show the headline and let you open the evidence.""",
        (),
    ),
    Term(
        "Gate",
        "How the app scores",
        "A signal that overrides everything else: the stock is uninvestable (excluded, illiquid, manipulated, in credit distress). Any gate makes the stance AVOID with the reason named.",
        """1-Oct-2026: a steel-pipe maker sits on NSE's GSM list (EXCLUDED), a textile company trades ₹40 lakh a day (ILLIQUID), a telecom has interest cover 0.8× at 4× debt-to-equity (DISTRESS), an EV maker has 1.1 quarters of cash (CASH_RUNWAY_CRITICAL), a micro-cap is up 300% on 20% delivery and 20 serial upper circuits (OPERATOR_PATTERN).
Each is a GATE signal. The stance becomes AVOID with the gate's headline shown, whatever the bullish engines say — a cheap P/E does not matter if you cannot sell the stock or the company may not survive.
Gates are not predictions of a fall (the backtest shows distressed survivors often rebounded); they are a statement that the position is not investable for a normal portfolio.
The screener's AVOID chip lists them; the company panel names the blocking table so you can see exactly which rule fired.""",
        ("investability", "credit_distress", "manipulation_risk", "unit_economics"),
    ),
    Term(
        "Stance and conviction",
        "How the app scores",
        "The stance tallies every signal: each adds stage weight × engine weight × strength to its side; the net decides Buy, Lean buy, Neutral, Lean sell or Sell (the ledger keys stay LONG / SHORT). Conviction counts CONFIRMED signals (HIGH needs three unopposed). It is a checkable tally, not advice.",
        """A specialty chemicals company's signals on 1-Oct-2026:
Bull: MARGIN_EXPANDING confirmed (1.0 × 0.5 engine weight × 1.0 strength = 0.50) · OPERATING_LEVERAGE confirmed (1.0 × 0.5 × 1.0 = 0.50) · UNDERVALUED_GROWTH emerging (0.6 × 1.0 × 0.34 = 0.20) · INSTITUTIONAL_ACCUMULATION early (0.3 × 1.0 × 0.24 = 0.07) → bull 1.27.
Bear: TREND_DOWN confirmed (1.0 × 1.0 × 0.14 = 0.14) → bear 0.14. Net +1.13.
Thresholds: net ≥ 0.6 is LEAN_LONG, ≥ 1.5 LONG (mirror for short). Net 1.13 → LEAN_LONG, shown as Lean buy.
Conviction counts CONFIRMED signals on the winning side: two for, one confirmed against → MEDIUM (HIGH needs three confirmed with none confirmed against; LOW is a lean built only on early/emerging signals).
Every number is on the company panel, so the tally can be checked by hand. It is a summary of what the engines measured, not advice.""",
        (),
    ),
    Term(
        "Engine weight (stance v2)",
        "How the app scores",
        "A per-engine multiplier learned from the backtest: engines whose signals paid off get 1.5, average ones 1.0, weak ones 0.5, and engines that were wrong more often than right 0. A zero-weight signal still shows on the panel; it just does not count.",
        """How the table was built: every backtest signal from 2019–2024 was marked at 12 months. Per engine and direction with at least 200 marks: hit rate above 57% → weight 1.5; 52–57% → 1.0; 47–52% → 0.5; below 47% → 0.
Turnaround longs hit 84% (636 marks) → 1.5. Technical-trend longs 49% (27,987 marks) → 0.5. Capital-allocation longs 40% → 0; corporate-event longs 31% → 0. Credit-distress shorts 40% → 0 (its DISTRESS gate still applies).
Effect on the tally: a confirmed TURNAROUND at strength 0.6 contributes 1.0 × 1.5 × 0.6 = 0.90; a confirmed TREND_UP at strength 0.5 contributes 1.0 × 0.5 × 0.5 = 0.25. A DISCIPLINED_ALLOCATOR signal still appears on the panel but adds 0.
Held out on 2025–26 the weights lifted long stances from 50.8% to 54.2% hit; `python ingest.py retune` reprints the table. The caveat: the training ledger is survivor-biased (see Backtest).""",
        ("turnaround", "corporate_event"),
    ),
    Term(
        "Excess return",
        "How the app scores",
        "A stock's return minus the universe median over the same window, so a signal is judged on whether it beat the market, not on whether the market rose.",
        """A signal fires on a hospital chain on 15-Jan-2025 at ₹620. 252 sessions later the stock is ₹694: +12.0%.
Over the same window the median Nifty 500 stock returned +7.0%. Excess return = 12.0 − 7.0 = +5.0 percentage points: the signal beat the market, modestly.
A short signal on a cement company over the same window: the stock −3% while the median was +7% → excess −10 points, a successful short even though the market rose.
Why the median and not an index: the Nifty 50 is dominated by a few banks and Reliance; the median stock is what a typical pick would have done. Every hit rate and mean-excess figure on the engine pages is in these terms; the raw return is shown beside it.""",
        (),
    ),
    Term(
        "Hit rate",
        "How the app scores",
        "The share of a signal's marked outcomes whose excess return went the way the signal pointed (positive for BULL, negative for BEAR). 50% is a coin toss.",
        """Turnaround signals in the backtest: 678 marked at 12 months, 548 with positive excess return → hit rate 80.8%. Mean excess +45.7%, median +31.1%.
Capital-allocation longs: 7,648 marked, 3,065 hits → 40.1%, mean excess −2.9%: wrong more often than right, so weight 0.
Read hit rate with the count and the mean together: 66% on 53 marks (IPO leaders) is noise; 57% on 2,277 marks (profitability inflection) is a real edge; 52% with +14% mean excess (results rerated up) means a few big winners carry many small losers.
50% is the coin toss for longs; for shorts the baseline is near 51% because the median return is positive more often than not. Live hit rates will accumulate under each engine from Oct-2026 and can be compared with these backtest figures (spec §72).""",
        (),
    ),
    Term(
        "Outcome marking and horizons",
        "How the app scores",
        "Every signal and stance is measured 21, 63, 126, 252 and 504 trading sessions later (1, 3, 6, 12 and 24 months): return, excess return and maximum drawdown. Nothing is ever re-marked, so the record cannot be flattered later.",
        """A signal emitted on 1-Oct-2026 at ₹448.40. The marker waits for trading sessions, not calendar days:
21 sessions → about 31-Oct-2026 (1 month) · 63 → late Dec (3 months) · 126 → early April 2027 (6 months) · 252 → October 2027 (12 months) · 504 → October 2028 (24 months).
At each date it writes the close, the return, the excess over the universe median for the same window, and the maximum drawdown in between; a stock suspended or delisted inside the window is left unmarked rather than guessed.
Nothing is ever re-marked or edited: a signal that looked right at 3 months and wrong at 12 keeps both records. The backtest (382 runs, 2019–2026) marked 308,000 signal outcomes at one month and 184,000 at two years, which is what the hit-rate tables are built on.""",
        (),
    ),
    Term(
        "Backtest and survivorship bias",
        "How the app scores",
        "Replaying the engines on past dates with only the data known then. Survivorship bias is the distortion when the past universe contains only companies that survived to today, which flatters long signals and punishes bear ones.",
        """The replay: every 5th trade date from Jan-2019 to Sep-2026 (394 runs), the engines run on a snapshot that contains only what was public that day — results by broadcast date, membership from the newest index snapshot on or before the date, prices to that date. 2.4 million signals; each marked at the five horizons.
Survivorship bias, concretely: in Oct-2026 prices of companies no longer in the Nifty 500 were pruned. A run as of June 2020 can therefore price only companies that are still in the index today. A company that was in distress in 2020 and *survived to stay in the index* recovered by definition; the ones that collapsed are invisible. Result: bear engines look worse than they were (credit distress shorts 'hit' 40%) and long signals look better.
The fix is to re-ingest the pruned prices from the cached market-wide files and rerun; it reverses part of the prune, so it waits for a decision (TODO.md).
Point-in-time filings are respected, so there is no look-ahead on fundamentals; the remaining known leak is surveillance lists, which exist only from Oct-2026.""",
        (),
    ),
    Term(
        "Point in time",
        "How the app scores",
        "Using each fact only from the moment it was public: a quarter's results from its broadcast date, not its period end. Without it a backtest knows the future and looks far better than it was.",
        """A cement company's June-2026 quarter: period ends 30-Jun; results broadcast 24-Jul at 17:05.
A run as of 10-Jul sees the March quarter as the newest; a run as of 24-Jul still sees March (the broadcast was after the close); a run as of 25-Jul sees June. The same rule governs shareholding patterns (broadcast date, not quarter end), ratings, announcements and index membership.
Why it is non-negotiable: a backtest that used June results on 1-Jul would 'know' three weeks early that profit jumped 40% and would buy before the rerating — a strategy that cannot be traded. Most published backtests that look too good fail here.
Where the app still leaks: exclusion and surveillance lists exist only from Oct-2026, so earlier runs see today's lists; and industry classification comes from today's snapshot. Both are recorded in TODO.md and shown where they apply.""",
        (),
    ),
)


def by_group() -> list[tuple[str, list[Term]]]:
    return [(group, [t for t in TERMS if t.group == group]) for group in GROUPS]
