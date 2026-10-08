"""
Who a deal counterparty is, from its name (spec §65, §69.2). NSE's bulk and block deal files carry
only the client's name as the broker typed it — no category, no owner, no PAN — so the type is
inferred from the name: an ordered set of rules, foreign cues before 'fund' (Norges Bank's
"Government Pension Fund Global" is a sovereign investor, not a mutual fund), plus a list of known
houses whose names say nothing (proprietary trading firms). Every classification carries the rule
that made it, so the page can show why. Ownership of a vehicle (who is behind an ODI note, which
family owns a private company) is not knowable from these filings and is never guessed.
"""

import re
from typing import Any

MUTUAL_FUND, FII, INSURANCE, BANK, AIF_PMS, PROP_TRADER, BROKER, CORPORATE, TRUST, INDIVIDUAL, UNKNOWN = (
    "MUTUAL_FUND",
    "FII",
    "INSURANCE",
    "BANK",
    "AIF_PMS",
    "PROP_TRADER",
    "BROKER",
    "CORPORATE",
    "TRUST",
    "INDIVIDUAL",
    "UNKNOWN",
)
LABEL = {
    MUTUAL_FUND: "Mutual fund",
    FII: "FII / FPI",
    INSURANCE: "Insurance (DII)",
    BANK: "Bank",
    AIF_PMS: "AIF / PMS",
    PROP_TRADER: "Prop / HFT",
    BROKER: "Broker",
    CORPORATE: "Company",
    TRUST: "Trust / estate",
    INDIVIDUAL: "Individual",
    UNKNOWN: "Unclassified",
}
# DII in SEBI's sense = domestic institutions: mutual funds, insurers, banks, AIFs and pension money.
DII_TYPES = {MUTUAL_FUND, INSURANCE, BANK, AIF_PMS}
BADGE = {
    MUTUAL_FUND: "badge-primary",
    FII: "badge-secondary",
    INSURANCE: "badge-accent",
    BANK: "badge-accent badge-outline",
    AIF_PMS: "badge-primary badge-outline",
    PROP_TRADER: "badge-warning",
    BROKER: "badge-warning badge-outline",
    CORPORATE: "badge-neutral badge-outline",
    TRUST: "badge-ghost",
    INDIVIDUAL: "badge-ghost",
    UNKNOWN: "badge-ghost",
}

# Houses whose names do not say what they are. Proprietary / high-frequency trading firms appear
# on both sides of the tape daily and their flow carries no investment view.
KNOWN_PROP = (
    "GRAVITON RESEARCH",
    "HRTI",
    "TOWER RESEARCH",
    "JUMP TRADING",
    "XTX MARKETS",
    "NK SECURITIES RESEARCH",
    "QE SECURITIES",
    "ALPHAGREP",
    "QUADEYE",
    "OPTIVER",
    "CITADEL SECURITIES",
    "SUSQUEHANNA",
    "HUDSON RIVER",
    "IMC ",
    "DRW ",
    "FLOW TRADERS",
    "MUSIGMA",
    "DOLAT",
    "KANCHAN SECURITIES",
    "CROSSLAND TRADING",
    "ESTEE ",
    "OPEN FUTURES",
)
KNOWN_FII = (
    "NORGES BANK",
    "GOVERNMENT OF SINGAPORE",
    "MONETARY AUTHORITY OF SINGAPORE",
    "ABU DHABI INVESTMENT",
    "KUWAIT INVESTMENT",
    "GOVERNMENT PENSION",
    "MTBJ",
    "VANGUARD",
    "ISHARES",
    "BLACKROCK",
    "FIDELITY",
    "CAPITAL GROUP",
    "SMALLCAP WORLD FUND",
    "NEW WORLD FUND",
    "T. ROWE",
    "T ROWE",
    "WELLINGTON",
    "SCHRODER",
    "ABERDEEN",
    "ABRDN",
    "INVESCO",
    "POWERSHARES",
    "WISDOMTREE",
    "MARSHALL WACE",
    "MILLENNIUM",
    "SEGANTII",
    "NOMURA",
    "MORGAN STANLEY",
    "GOLDMAN SACHS",
    "CITIGROUP",
    "BOFA SECURITIES",
    "MERRILL LYNCH",
    "JPMORGAN",
    "JP MORGAN",
    "BNP PARIBAS",
    "SOCIETE GENERALE",
    "UBS ",
    "CREDIT SUISSE",
    "BARCLAYS",
    "HSBC",
    "DEUTSCHE BANK",
    "MACQUARIE",
    "CLSA",
    "KAMEHAMEHA",
    "BERNICE PAUAHI",
    "RELIANCE TRUST INSTITUTIONAL",
    "WF ASIAN",
    "MATTHEWS",
    "FRANKLIN TEMPLETON INVESTMENT FUNDS",
    "COPTHALL",
    "ELARA",
    "NALANDA",
    "WESTBRIDGE",
    "STEADVIEW",
    "THINK INDIA",
    "AMANSA",
    "SMALLCAP WORLD",
)
_RULES: tuple[tuple[str, str, str], ...] = (
    (INSURANCE, r"INSURANCE|ASSURANCE|\bLIC\b|LIFE INS", "insurance in the name"),
    (
        FII,
        r"\bODI\b|\bFPI\b|MAURITIUS|SINGAPORE|LUXEMBOURG|CAYMAN|IRELAND|NETHERLANDS|\bPTE\b|\bPLC\b|\bINC\b|\bLLC\b|\bL\.?P\.?$|\bSA$|\bSE\b|\bN\.?V\.?\b|\bAG\b|\bETF\b|\bUCITS\b|\bSICAV\b|OFFSHORE|EMERGING MARKETS?|GLOBAL FUND|INTERNATIONAL FUND|ASIA (PACIFIC )?FUND|INDIA FUND|FOREIGN PORTFOLIO",
        "foreign domicile or vehicle in the name",
    ),
    (
        MUTUAL_FUND,
        r"MUTUAL FUND|\bMF\b|ASSET MANAGEMENT|\bAMC\b|TRUSTEE.*(SCHEME|MUTUAL)|PRUDENTIAL|NIPPON LIFE INDIA|AXIS BANK LIMITED A/C|SBI (FUNDS|EQUITY|SMALL|FOCUSED|BLUECHIP|FLEXI|MAGNUM|LONG|CONTRA|TECHNOLOGY)",
        "Indian mutual fund in the name",
    ),
    (BANK, r"\bBANK\b(?!.*\bON ACCOUNT OF\b)", "bank in the name"),
    (
        AIF_PMS,
        r"\bAIF\b|ALTERNATIVE INVESTMENT|\bPMS\b|PORTFOLIO MANAGE|CATEGORY (I|II|III)|OPPORTUNITIES FUND|VENTURE|CAPITAL PARTNERS|INVESTMENT MANAGERS|ADVISORS (PRIVATE|PVT)|\bFUND\b.*(SCHEME|SERIES|I\b|II\b|III\b)|SMALLCAP FUND|MICROCAP FUND|GROWTH FUND|EQUITY FUND|VALUE FUND|DISCOVERY FUND|SPECIAL SITUATIONS|\bTRUST\b.*\bFUND\b",
        "alternative or managed fund in the name",
    ),
    (
        BROKER,
        r"SECURITIES|STOCK ?BROK|SHAREBROK|BROKING|COMMODITIES|CAPITAL MARKETS|FINVEST|FINSERV|SHARE (AND|&) STOCK|INVESTMENT SERVICES",
        "broking firm in the name",
    ),
    (TRUST, r"\bTRUST\b|\bESTATE\b|ENDOWMENT|FOUNDATION|\bTRUSTEES?\b", "trust or estate in the name"),
    (
        CORPORATE,
        r"PRIVATE LIMITED|PVT\.? ?LTD|\bLIMITED\b|\bLTD\b|\bLLP\b|\bCO\.?$|CORPORATION|HOLDINGS?|ENTERPRISES?|ENTREPRENEURS?|INDUSTRIES|TRADERS|AGRO|TEXTILES?|MILLS?|STEELS?|CHEMICALS?|PHARMA|VENTURES|FINANCE|CAPITAL\b|INVESTMENTS?\b|TRADING|AGENCIES|EXPORTS?|\bINFRA",
        "company suffix in the name",
    ),
)
_PERSON_SUFFIX = re.compile(r"\b(HUF)\b")


def classify(name: str) -> dict[str, Any]:
    """Category, label, badge class and the rule that decided it, for one client name."""
    upper = " ".join(name.upper().replace(".", ". ").split())
    for house in KNOWN_PROP:
        if house.strip() in upper:
            return _result(PROP_TRADER, f"known proprietary trading house ({house.strip().title()})")
    for house in KNOWN_FII:
        if house.strip() in upper:
            return _result(FII, f"known foreign investor ({house.strip().title()})")
    for category, pattern, basis in _RULES:
        if re.search(pattern, upper):
            return _result(category, basis)
    words = [w for w in re.split(r"[^A-Z]+", upper) if w]
    if _PERSON_SUFFIX.search(upper) or (2 <= len(words) <= 4 and all(len(w) >= 2 for w in words)):
        return _result(
            INDIVIDUAL, "a personal name (no corporate suffix)" + (" — HUF" if "HUF" in words else "")
        )
    return _result(UNKNOWN, "no rule matched")


def _result(category: str, basis: str) -> dict[str, Any]:
    return {
        "type": category,
        "label": LABEL[category],
        "badge": BADGE[category],
        "basis": basis,
        "dii": category in DII_TYPES,
    }
