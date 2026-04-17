"""Generator configuration. Changing these regenerates a reproducibly different company."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SEED = 42

ORGS = [
    ("Engineering", 0.42),
    ("Product", 0.08),
    ("Design", 0.05),
    ("Sales", 0.18),
    ("Marketing", 0.07),
    ("Customer Success", 0.09),
    ("People", 0.04),
    ("Finance", 0.03),
    ("Legal", 0.02),
    ("IT", 0.02),
]

REGIONS = [
    ("AMER", 0.55),
    ("EMEA", 0.30),
    ("APAC", 0.15),
]

LEVELS = ["IC1", "IC2", "IC3", "IC4", "IC5", "IC6", "M1", "M2", "M3", "M4"]

JOB_FAMILIES = {
    "Engineering": ["Software Engineer", "SRE", "Data Engineer", "ML Engineer", "Security Engineer"],
    "Product": ["Product Manager", "Technical PM"],
    "Design": ["Product Designer", "UX Researcher"],
    "Sales": ["Account Executive", "Sales Engineer", "BDR"],
    "Marketing": ["Marketing Manager", "Content Marketer", "Growth"],
    "Customer Success": ["CSM", "Support Engineer"],
    "People": ["HRBP", "Recruiter", "People Ops"],
    "Finance": ["FP&A", "Accountant"],
    "Legal": ["Counsel", "Legal Ops"],
    "IT": ["IT Engineer", "IT Support"],
}

# Base comp bands by level (USD). Applied with regional multipliers.
BASE_COMP_BY_LEVEL = {
    "IC1": (70_000, 95_000),
    "IC2": (95_000, 130_000),
    "IC3": (130_000, 170_000),
    "IC4": (170_000, 220_000),
    "IC5": (220_000, 290_000),
    "IC6": (290_000, 380_000),
    "M1": (160_000, 210_000),
    "M2": (210_000, 280_000),
    "M3": (280_000, 370_000),
    "M4": (370_000, 480_000),
}

REGION_COMP_MULTIPLIER = {
    "AMER": 1.00,
    "EMEA": 0.82,
    "APAC": 0.74,
}


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = SEED
    n_employees: int = 2500
    n_former_employees: int = 600  # generated over a 3-year history window
    history_start: date = date(2023, 1, 1)
    today: date = date(2026, 4, 1)
    # Greenhouse
    n_open_reqs: int = 120
    n_closed_reqs: int = 340
    avg_candidates_per_req: int = 45
    # Docebo
    n_courses: int = 65
    completion_rate: float = 0.62

    orgs: list[tuple[str, float]] = field(default_factory=lambda: ORGS)
    regions: list[tuple[str, float]] = field(default_factory=lambda: REGIONS)
