"""The 30-question stratified eval set.

Each case is anchored to calls that ACTUALLY exist in the corpus (verified
against the chunks table). Cases come in three buckets:

- single_call: pinned to one ticker + year + quarter. Tests metadata
  pre-filtering + precise retrieval inside a single call.
- multi_quarter: one company, range of quarters. Tests temporal synthesis
  and consistent ticker filtering.
- cross_company: comparison across 2-3 tickers. Tests breadth of retrieval.

Every case carries:
- `question`: the user prompt
- `expected_filters`: what filters a realistic UI would apply
- `expected_themes`: keywords/concepts the answer should mention
- `expected_chunk_signals`: at minimum which tickers MUST appear in top-K
- `expected_min_citations`: lower bound on parsed citations
- `difficulty`: easy / medium / hard (for stratification audits)

Reference chunk IDs are deliberately omitted. They drift as the corpus
re-chunks; using filter-based scoring keeps the eval stable across
chunker changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.retrieve.filters import RetrievalFilters


QueryType = Literal["single_call", "multi_quarter", "cross_company"]
Difficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    query_type: QueryType
    question: str
    expected_filters: RetrievalFilters
    expected_themes: list[str]
    expected_tickers: list[str]     # any retrieved chunk's ticker must be in this set
    expected_min_citations: int = 1
    difficulty: Difficulty = "medium"
    notes: str = ""


# ---------------------------------------------------------------------------
# Single-call (10) — pin to one ticker + year + quarter
# ---------------------------------------------------------------------------

SINGLE_CALL_CASES: list[EvalCase] = [
    EvalCase(
        case_id="sc01_aapl_q4_2024_apple_intelligence",
        query_type="single_call",
        question=(
            "On Apple's Q4 2024 earnings call, what did Tim Cook say about the "
            "rollout of Apple Intelligence and its impact on customer behavior?"
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL"], year=2024, quarter="Q4"),
        expected_themes=["apple intelligence", "rollout", "iphone", "customer"],
        expected_tickers=["AAPL"],
        expected_min_citations=1,
        difficulty="easy",
    ),
    EvalCase(
        case_id="sc02_msft_q4_2024_ai_capex_flexibility",
        query_type="single_call",
        question=(
            "How did Amy Hood describe the flexibility and monetization horizon of "
            "Microsoft's AI infrastructure spend on the Q4 2024 fiscal call?"
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT"], year=2024, quarter="Q4"),
        expected_themes=["flexible", "long-lived", "infrastructure", "monetize"],
        expected_tickers=["MSFT"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc03_googl_q1_2024_capex_guidance",
        query_type="single_call",
        question=(
            "What did Ruth Porat say about Alphabet's capital expenditures and "
            "guidance for the rest of 2024 on the Q1 2024 call?"
        ),
        expected_filters=RetrievalFilters(tickers=["GOOGL"], year=2024, quarter="Q1"),
        expected_themes=["capex", "capital expenditure", "infrastructure", "2024"],
        expected_tickers=["GOOGL"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc04_amzn_q2_2024_aws_growth",
        query_type="single_call",
        question=(
            "On Amazon's Q2 2024 call, how was AWS growth described and what was the AI "
            "contribution to it?"
        ),
        expected_filters=RetrievalFilters(tickers=["AMZN"], year=2024, quarter="Q2"),
        expected_themes=["aws", "growth", "generative ai", "demand"],
        expected_tickers=["AMZN"],
        expected_min_citations=1,
        difficulty="easy",
    ),
    EvalCase(
        case_id="sc05_meta_q3_2024_reality_labs_spend",
        query_type="single_call",
        question=(
            "How did Susan Li frame Meta's Reality Labs spending and 2025 outlook on "
            "the Q3 2024 earnings call?"
        ),
        expected_filters=RetrievalFilters(tickers=["META"], year=2024, quarter="Q3"),
        expected_themes=["reality labs", "losses", "infrastructure", "ai"],
        expected_tickers=["META"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc06_nvda_q2_2025_blackwell_ramp",
        query_type="single_call",
        question=(
            "What did NVIDIA say about Blackwell production ramp and Hopper demand on "
            "the FQ2 2025 earnings call?"
        ),
        expected_filters=RetrievalFilters(tickers=["NVDA"], year=2025, quarter="Q2"),
        expected_themes=["blackwell", "hopper", "ramp", "production"],
        expected_tickers=["NVDA"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc07_tsla_q3_2024_fsd_robotaxi",
        query_type="single_call",
        question=(
            "What did Elon Musk say about FSD progress and the robotaxi timeline on "
            "Tesla's Q3 2024 call?"
        ),
        expected_filters=RetrievalFilters(tickers=["TSLA"], year=2024, quarter="Q3"),
        expected_themes=["fsd", "robotaxi", "autonomous", "supervised"],
        expected_tickers=["TSLA"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc08_aapl_q1_2025_services_revenue",
        query_type="single_call",
        question=(
            "How did Apple describe Services revenue on the Q1 2025 earnings call?"
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL"], year=2025, quarter="Q1"),
        expected_themes=["services", "revenue", "all-time", "record"],
        expected_tickers=["AAPL"],
        expected_min_citations=1,
        difficulty="easy",
    ),
    EvalCase(
        case_id="sc09_nvda_q4_2025_blackwell_supply",
        query_type="single_call",
        question=(
            "What did NVIDIA executives say about Blackwell shipments, supply, and "
            "data-center revenue mix on the FQ4 2025 earnings call?"
        ),
        expected_filters=RetrievalFilters(tickers=["NVDA"], year=2025, quarter="Q4"),
        expected_themes=["blackwell", "supply", "data center", "shipments"],
        expected_tickers=["NVDA"],
        expected_min_citations=1,
        difficulty="medium",
    ),
    EvalCase(
        case_id="sc10_msft_q2_2025_copilot_adoption",
        query_type="single_call",
        question=(
            "What did Satya Nadella say about Copilot adoption and enterprise AI "
            "monetization on the Microsoft FQ2 2025 earnings call?"
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT"], year=2025, quarter="Q2"),
        expected_themes=["copilot", "enterprise", "adoption", "monetization"],
        expected_tickers=["MSFT"],
        expected_min_citations=1,
        difficulty="medium",
    ),
]


# ---------------------------------------------------------------------------
# Multi-quarter (10) — one company, range of quarters
# ---------------------------------------------------------------------------

MULTI_QUARTER_CASES: list[EvalCase] = [
    EvalCase(
        case_id="mq01_msft_ai_capex_evolution",
        query_type="multi_quarter",
        question=(
            "How did Microsoft's framing of AI capital expenditure evolve from "
            "fiscal Q3 2024 through fiscal Q2 2026? What changed and what stayed "
            "constant?"
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT"]),
        expected_themes=["capex", "infrastructure", "long-lived", "demand"],
        expected_tickers=["MSFT"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq02_aapl_apple_intelligence_messaging",
        query_type="multi_quarter",
        question=(
            "How did Apple's messaging around Apple Intelligence evolve from Q4 2024 "
            "through Q1 2026? Did Tim Cook's tone become more or less confident?"
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL"]),
        expected_themes=["apple intelligence", "rollout", "iphone", "adoption"],
        expected_tickers=["AAPL"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq03_amzn_aws_growth_2024",
        query_type="multi_quarter",
        question=(
            "How did the AWS growth narrative evolve across Amazon's Q1, Q2, Q3, and "
            "Q4 2024 earnings calls?"
        ),
        expected_filters=RetrievalFilters(tickers=["AMZN"], year=2024),
        expected_themes=["aws", "growth", "demand", "ai"],
        expected_tickers=["AMZN"],
        expected_min_citations=3,
        difficulty="medium",
    ),
    EvalCase(
        case_id="mq04_meta_reality_labs_losses",
        query_type="multi_quarter",
        question=(
            "Track Meta's commentary on Reality Labs losses and AI infrastructure "
            "investment from Q3 2024 through Q4 2025. How did the framing shift?"
        ),
        expected_filters=RetrievalFilters(tickers=["META"]),
        expected_themes=["reality labs", "ai infrastructure", "losses", "capex"],
        expected_tickers=["META"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq05_nvda_blackwell_ramp_arc",
        query_type="multi_quarter",
        question=(
            "Trace NVIDIA's Blackwell ramp narrative from the FQ2 2025 call through "
            "the FQ4 2026 call. How did supply, customer demand, and revenue "
            "contribution evolve?"
        ),
        expected_filters=RetrievalFilters(tickers=["NVDA"]),
        expected_themes=["blackwell", "ramp", "supply", "demand", "data center"],
        expected_tickers=["NVDA"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq06_tsla_fsd_progress_arc",
        query_type="multi_quarter",
        question=(
            "How did Tesla's narrative on FSD progress and unsupervised autonomy evolve "
            "across the Q1 2024 to Q4 2025 calls?"
        ),
        expected_filters=RetrievalFilters(tickers=["TSLA"]),
        expected_themes=["fsd", "unsupervised", "autonomy", "robotaxi"],
        expected_tickers=["TSLA"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq07_googl_search_ai_overviews",
        query_type="multi_quarter",
        question=(
            "How did Google describe the impact of AI Overviews and generative AI on "
            "Search across 2024 and 2025 earnings calls?"
        ),
        expected_filters=RetrievalFilters(tickers=["GOOGL", "GOOG"]),
        expected_themes=["search", "ai overviews", "generative", "engagement"],
        expected_tickers=["GOOGL", "GOOG"],
        expected_min_citations=3,
        difficulty="medium",
    ),
    EvalCase(
        case_id="mq08_tsla_robotaxi_timeline_shifts",
        query_type="multi_quarter",
        question=(
            "How did Tesla's stated robotaxi timeline shift across the 2024 and 2025 "
            "earnings calls? Where did Elon Musk hedge most?"
        ),
        expected_filters=RetrievalFilters(tickers=["TSLA"], min_hedging_score=0.3),
        expected_themes=["robotaxi", "timeline", "launch", "supervised"],
        expected_tickers=["TSLA"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="mq09_aapl_services_trajectory",
        query_type="multi_quarter",
        question=(
            "Track Apple's Services revenue trajectory and what the company said about "
            "drivers across Q4 2024, Q1 2025, Q3 2025, and Q1 2026."
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL"]),
        expected_themes=["services", "revenue", "growth", "all-time"],
        expected_tickers=["AAPL"],
        expected_min_citations=3,
        difficulty="medium",
    ),
    EvalCase(
        case_id="mq10_msft_azure_growth_arc",
        query_type="multi_quarter",
        question=(
            "How did Azure growth and AI contribution evolve across Microsoft's fiscal "
            "Q3 2024 to fiscal Q2 2026 earnings calls?"
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT"]),
        expected_themes=["azure", "growth", "ai contribution", "demand"],
        expected_tickers=["MSFT"],
        expected_min_citations=3,
        difficulty="hard",
    ),
]


# ---------------------------------------------------------------------------
# Cross-company (10) — comparisons across 2-3 tickers
# ---------------------------------------------------------------------------

CROSS_COMPANY_CASES: list[EvalCase] = [
    EvalCase(
        case_id="cc01_aapl_googl_china_risk",
        query_type="cross_company",
        question=(
            "Compare how Apple and Alphabet talk about China exposure and risk on "
            "their 2024 and 2025 earnings calls."
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL", "GOOGL", "GOOG"]),
        expected_themes=["china", "exposure", "risk", "tariff"],
        expected_tickers=["AAPL", "GOOGL", "GOOG"],
        expected_min_citations=2,
        difficulty="hard",
    ),
    EvalCase(
        case_id="cc02_msft_googl_ai_capex",
        query_type="cross_company",
        question=(
            "Compare how Microsoft and Alphabet describe AI capital expenditure in "
            "2024 and 2025. Which company is more numerically explicit?"
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT", "GOOGL", "GOOG"]),
        expected_themes=["capex", "infrastructure", "billion", "investment"],
        expected_tickers=["MSFT", "GOOGL", "GOOG"],
        expected_min_citations=2,
        difficulty="medium",
    ),
    EvalCase(
        case_id="cc03_aapl_msft_ai_integration",
        query_type="cross_company",
        question=(
            "Compare how Apple and Microsoft describe AI integration into their core "
            "products. Apple Intelligence vs Copilot — what's the strategic framing "
            "for each?"
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL", "MSFT"]),
        expected_themes=["apple intelligence", "copilot", "integration", "platform"],
        expected_tickers=["AAPL", "MSFT"],
        expected_min_citations=2,
        difficulty="medium",
    ),
    EvalCase(
        case_id="cc04_amzn_msft_cloud_growth",
        query_type="cross_company",
        question=(
            "Compare AWS and Azure growth narratives across 2024 and 2025. How do the "
            "two companies talk about AI's contribution to cloud growth?"
        ),
        expected_filters=RetrievalFilters(tickers=["AMZN", "MSFT"]),
        expected_themes=["aws", "azure", "growth", "ai", "cloud"],
        expected_tickers=["AMZN", "MSFT"],
        expected_min_citations=2,
        difficulty="medium",
    ),
    EvalCase(
        case_id="cc05_nvda_msft_ai_infra",
        query_type="cross_company",
        question=(
            "Compare how NVIDIA and Microsoft talk about AI infrastructure demand "
            "and supply constraints in 2024 and 2025."
        ),
        expected_filters=RetrievalFilters(tickers=["NVDA", "MSFT"]),
        expected_themes=["ai infrastructure", "supply", "demand", "data center"],
        expected_tickers=["NVDA", "MSFT"],
        expected_min_citations=2,
        difficulty="medium",
    ),
    EvalCase(
        case_id="cc06_meta_googl_advertising_ai",
        query_type="cross_company",
        question=(
            "Compare how Meta and Alphabet describe AI's contribution to advertising "
            "performance in 2024 and 2025."
        ),
        expected_filters=RetrievalFilters(tickers=["META", "GOOGL", "GOOG"]),
        expected_themes=["advertising", "ai", "performance", "advertiser"],
        expected_tickers=["META", "GOOGL", "GOOG"],
        expected_min_citations=2,
        difficulty="medium",
    ),
    EvalCase(
        case_id="cc07_aapl_meta_ai_device_strategy",
        query_type="cross_company",
        question=(
            "Compare Apple's and Meta's AI device strategies (Apple Intelligence on "
            "iPhone vs Ray-Ban Meta and Quest)."
        ),
        expected_filters=RetrievalFilters(tickers=["AAPL", "META"]),
        expected_themes=["apple intelligence", "ray-ban", "meta", "quest", "device"],
        expected_tickers=["AAPL", "META"],
        expected_min_citations=2,
        difficulty="hard",
    ),
    EvalCase(
        case_id="cc08_msft_googl_amzn_2025_capex",
        query_type="cross_company",
        question=(
            "Compare 2025 capex guidance and rationale across Microsoft, Alphabet, "
            "and Amazon."
        ),
        expected_filters=RetrievalFilters(tickers=["MSFT", "GOOGL", "GOOG", "AMZN"]),
        expected_themes=["capex", "guidance", "2025", "billion"],
        expected_tickers=["MSFT", "GOOGL", "GOOG", "AMZN"],
        expected_min_citations=3,
        difficulty="hard",
    ),
    EvalCase(
        case_id="cc09_evasive_ceo_responses_2024",
        query_type="cross_company",
        question=(
            "Across all Mag 7 calls from 2024, which CEO responses on forward guidance "
            "or AI monetization timelines contained the most hedging language?"
        ),
        expected_filters=RetrievalFilters(
            year=2024, speaker_roles=["CEO"], section="qa", min_hedging_score=0.4
        ),
        expected_themes=["guidance", "monetization", "uncertain", "depends"],
        expected_tickers=["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"],
        expected_min_citations=2,
        difficulty="hard",
        notes="Tests the hedging_score + role + section metadata filter combination.",
    ),
    EvalCase(
        case_id="cc10_nvda_tsla_ai_chip_strategy",
        query_type="cross_company",
        question=(
            "Compare NVIDIA's data-center GPU strategy with Tesla's Dojo / inference "
            "compute strategy across 2024 and 2025."
        ),
        expected_filters=RetrievalFilters(tickers=["NVDA", "TSLA"]),
        expected_themes=["data center", "gpu", "dojo", "inference", "training"],
        expected_tickers=["NVDA", "TSLA"],
        expected_min_citations=2,
        difficulty="hard",
    ),
]


def all_cases() -> list[EvalCase]:
    """All 30 stratified cases."""
    return [*SINGLE_CALL_CASES, *MULTI_QUARTER_CASES, *CROSS_COMPANY_CASES]


def cases_by_type(query_type: QueryType) -> list[EvalCase]:
    return [c for c in all_cases() if c.query_type == query_type]
