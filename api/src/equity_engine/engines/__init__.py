"""The engines implemented in code, keyed as in resources/seed/engine.csv. The catalogue (the
``engine`` table) lists every engine in the spec; this map says which of them run."""

from equity_engine.engines.base import Engine
from equity_engine.engines.documents import Catalyst, CorporateGovernance, DerivativesSignal, RatingAction
from equity_engine.engines.events import CorporateEvent, IpoNewlyListed, SupplyOverhang
from equity_engine.engines.flows import (
    InsiderDealFlow,
    InstitutionalAccumulation,
    PromoterActivity,
    SmartMoneyDivergence,
)
from equity_engine.engines.fundamentals import (
    AccountingQuality,
    CapitalAllocation,
    CashFlowInflection,
    CreditDistress,
    DeepValue,
    Deleveraging,
    EarningsAcceleration,
    ForensicScorePack,
    ImpliedGrowth,
    MarginInflection,
    OperatingLeverage,
    ProfitabilityInflection,
    ResultsReaction,
    RoceInflection,
    Turnaround,
    UndervaluedGrowth,
    UnitEconomics,
    Valuation,
    ValueTrap,
)
from equity_engine.engines.gates import Investability, ManipulationRisk
from equity_engine.engines.global_context import GlobalResilience, HistoricalPE
from equity_engine.engines.market import MarketRegime, SectorRotation
from equity_engine.engines.narrative import (
    DocumentDiff,
    ManagementCommentary,
    NarrativeVsNumbers,
    OperatingKpi,
)
from equity_engine.engines.price import RelativeStrength, TechnicalPrice, VolumeDelivery

IMPLEMENTED: dict[str, Engine] = {
    engine.key: engine
    for engine in (
        GlobalResilience(),
        HistoricalPE(),
        Investability(),
        ManipulationRisk(),
        RelativeStrength(),
        TechnicalPrice(),
        VolumeDelivery(),
        InstitutionalAccumulation(),
        PromoterActivity(),
        SmartMoneyDivergence(),
        InsiderDealFlow(),
        CorporateEvent(),
        IpoNewlyListed(),
        SupplyOverhang(),
        SectorRotation(),
        MarketRegime(),
        ProfitabilityInflection(),
        EarningsAcceleration(),
        MarginInflection(),
        OperatingLeverage(),
        RoceInflection(),
        CashFlowInflection(),
        Deleveraging(),
        Valuation(),
        UndervaluedGrowth(),
        ValueTrap(),
        DeepValue(),
        Turnaround(),
        AccountingQuality(),
        ForensicScorePack(),
        CreditDistress(),
        ImpliedGrowth(),
        ResultsReaction(),
        CapitalAllocation(),
        UnitEconomics(),
        Catalyst(),
        CorporateGovernance(),
        RatingAction(),
        DerivativesSignal(),
        ManagementCommentary(),
        NarrativeVsNumbers(),
        OperatingKpi(),
        DocumentDiff(),
    )
}
