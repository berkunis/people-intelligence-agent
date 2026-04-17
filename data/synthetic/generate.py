"""Synthetic People data generator. Faker + fixed seed = reproducible fake company.

Produces parquet files under data/synthetic/:
  - workday_employees.parquet
  - workday_comp.parquet
  - workday_org.parquet
  - greenhouse_requisitions.parquet
  - greenhouse_candidates.parquet
  - greenhouse_applications.parquet
  - docebo_courses.parquet
  - docebo_completions.parquet

No real names, no real companies, no scraped data. Everything is Faker.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from faker import Faker

from data.synthetic.config import (
    BASE_COMP_BY_LEVEL,
    JOB_FAMILIES,
    LEVELS,
    REGION_COMP_MULTIPLIER,
    GeneratorConfig,
)

OUTPUT_DIR = Path(__file__).parent


@dataclass
class GenerationArtifacts:
    employees: list[dict]
    comp: list[dict]
    orgs: list[dict]
    requisitions: list[dict]
    candidates: list[dict]
    applications: list[dict]
    courses: list[dict]
    completions: list[dict]


def _weighted_choice(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    choices, weights = zip(*pairs, strict=True)
    return rng.choices(choices, weights=weights, k=1)[0]


def _level_from_tenure_years(rng: random.Random, tenure_years: float, is_manager: bool) -> str:
    if is_manager:
        if tenure_years < 2:
            return "M1"
        if tenure_years < 5:
            return rng.choices(["M1", "M2"], weights=[0.4, 0.6])[0]
        if tenure_years < 8:
            return rng.choices(["M2", "M3"], weights=[0.5, 0.5])[0]
        return rng.choices(["M3", "M4"], weights=[0.7, 0.3])[0]
    # IC progression
    if tenure_years < 1:
        return rng.choices(["IC1", "IC2"], weights=[0.6, 0.4])[0]
    if tenure_years < 3:
        return rng.choices(["IC2", "IC3"], weights=[0.4, 0.6])[0]
    if tenure_years < 6:
        return rng.choices(["IC3", "IC4"], weights=[0.4, 0.6])[0]
    if tenure_years < 10:
        return rng.choices(["IC4", "IC5"], weights=[0.5, 0.5])[0]
    return rng.choices(["IC5", "IC6"], weights=[0.6, 0.4])[0]


def _comp_for(rng: random.Random, level: str, region: str) -> int:
    lo, hi = BASE_COMP_BY_LEVEL[level]
    base = rng.randint(lo, hi)
    return int(base * REGION_COMP_MULTIPLIER[region])


def generate(cfg: GeneratorConfig = GeneratorConfig()) -> GenerationArtifacts:
    rng = random.Random(cfg.seed)
    fake = Faker()
    Faker.seed(cfg.seed)

    employees: list[dict] = []
    orgs_seen: set[str] = set()

    total = cfg.n_employees + cfg.n_former_employees
    for i in range(total):
        is_former = i >= cfg.n_employees
        org = _weighted_choice(rng, cfg.orgs)
        region = _weighted_choice(rng, cfg.regions)
        orgs_seen.add(org)
        is_manager = rng.random() < 0.12
        job_family = rng.choice(JOB_FAMILIES[org])
        if is_former:
            # Former employees need room for a tenure window; cap hire_date at today-60d.
            hire_end = cfg.today - timedelta(days=60)
            hire_date = fake.date_between(start_date=cfg.history_start, end_date=hire_end)
            term_range_start = hire_date + timedelta(days=30)
            term_date = fake.date_between(start_date=term_range_start, end_date=cfg.today)
            term_reason = rng.choices(
                ["voluntary", "involuntary", "retirement"],
                weights=[0.72, 0.23, 0.05],
            )[0]
        else:
            hire_date = fake.date_between(start_date=cfg.history_start, end_date=cfg.today)
            term_date = None
            term_reason = None
        reference_date = term_date or cfg.today
        tenure_years = max(0.0, (reference_date - hire_date).days / 365.25)
        level = _level_from_tenure_years(rng, tenure_years, is_manager)
        emp_id = f"emp_{i:06d}"
        employees.append(
            {
                "employee_id": emp_id,
                "full_name": fake.name(),
                "work_email": f"{emp_id}@company.example",
                "hire_date": hire_date,
                "termination_date": term_date,
                "termination_reason": term_reason,
                "is_active": not is_former,
                "org": org,
                "region": region,
                "country": fake.country_code(),
                "level": level,
                "is_manager": is_manager,
                "job_family": job_family,
                "job_title": f"{level} {job_family}" if not is_manager else f"{job_family} Manager",
            }
        )

    # Assign managers (~1 per 8 ICs within same org)
    by_org: dict[str, list[dict]] = {}
    for e in employees:
        by_org.setdefault(e["org"], []).append(e)
    emp_by_id = {e["employee_id"]: e for e in employees}
    for org_emps in by_org.values():
        managers = [e for e in org_emps if e["is_manager"] and e["is_active"]]
        ics = [e for e in org_emps if not e["is_manager"]]
        if not managers:
            # Promote someone
            if ics:
                promoted = rng.choice(ics)
                promoted["is_manager"] = True
                promoted["level"] = "M2"
                managers = [promoted]
        for ic in ics:
            ic["manager_id"] = rng.choice(managers)["employee_id"] if managers else None
        for m in managers:
            m["manager_id"] = None

    for e in employees:
        if "manager_id" not in e:
            e["manager_id"] = None

    # Comp rows
    comp_rows: list[dict] = []
    for e in employees:
        salary = _comp_for(rng, e["level"], e["region"])
        band_lo = int(salary * 0.9 / 10_000) * 10_000
        band_hi = int(salary * 1.1 / 10_000) * 10_000
        comp_rows.append(
            {
                "employee_id": e["employee_id"],
                "effective_date": e["hire_date"],
                "base_salary_usd": salary,
                "salary_band": f"${band_lo // 1000}k-${band_hi // 1000}k",
                "currency": "USD",
                "region": e["region"],
            }
        )

    # Org dim
    org_rows = [
        {"org_id": f"org_{i:03d}", "org_name": name, "parent_org_id": None}
        for i, name in enumerate(sorted(orgs_seen))
    ]

    # Greenhouse
    requisitions: list[dict] = []
    candidates: list[dict] = []
    applications: list[dict] = []

    total_reqs = cfg.n_open_reqs + cfg.n_closed_reqs
    for r in range(total_reqs):
        is_open = r < cfg.n_open_reqs
        org = _weighted_choice(rng, cfg.orgs)
        opened_at = fake.date_between(start_date=cfg.history_start, end_date=cfg.today)
        closed_at = None if is_open else fake.date_between(start_date=opened_at, end_date=cfg.today)
        level = rng.choice(LEVELS)
        req_id = f"req_{r:05d}"
        hiring_manager = rng.choice([e for e in employees if e["is_manager"] and e["is_active"]])
        requisitions.append(
            {
                "req_id": req_id,
                "title": f"{level} {rng.choice(JOB_FAMILIES[org])}",
                "org": org,
                "region": _weighted_choice(rng, cfg.regions),
                "level": level,
                "status": "open" if is_open else "closed",
                "opened_at": opened_at,
                "closed_at": closed_at,
                "hiring_manager_id": hiring_manager["employee_id"],
            }
        )

    stages = [
        "applied",
        "recruiter_screen",
        "hiring_manager_screen",
        "technical_interview",
        "onsite",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
    ]
    for req in requisitions:
        n_cands = max(5, int(rng.gauss(cfg.avg_candidates_per_req, 12)))
        for _ in range(n_cands):
            cand_id = f"cand_{len(candidates):07d}"
            source = rng.choices(
                ["inbound", "referral", "sourced", "agency"],
                weights=[0.45, 0.22, 0.28, 0.05],
            )[0]
            candidates.append(
                {
                    "candidate_id": cand_id,
                    "first_seen_at": req["opened_at"],
                    "source": source,
                    "external_email": f"{cand_id}@external.example",
                }
            )
            # Applications — each candidate on this req gets one application
            applied_at = fake.date_between(
                start_date=req["opened_at"],
                end_date=req["closed_at"] or cfg.today,
            )
            # Walk stages with realistic drop-off
            current_stage = "applied"
            for stage in stages[1:-2]:
                if rng.random() < 0.55:
                    current_stage = stage
                else:
                    break
            if current_stage == "onsite" and rng.random() < 0.35:
                current_stage = rng.choice(["offer", "hired"])
            if current_stage not in {"hired", "offer"} and rng.random() < 0.6:
                current_stage = rng.choice(["rejected", "withdrawn"])
            applications.append(
                {
                    "application_id": f"app_{len(applications):08d}",
                    "candidate_id": cand_id,
                    "req_id": req["req_id"],
                    "applied_at": applied_at,
                    "current_stage": current_stage,
                    "source": source,
                    "is_active": req["status"] == "open"
                    and current_stage not in {"hired", "rejected", "withdrawn"},
                }
            )

    # Docebo
    course_catalog = [
        ("Security Awareness", "compliance"),
        ("Code of Conduct", "compliance"),
        ("Anti-Harassment", "compliance"),
        ("Data Privacy (GDPR)", "compliance"),
        ("Manager Fundamentals", "leadership"),
        ("Giving Feedback", "leadership"),
        ("SQL for Analysts", "technical"),
        ("Python for Data", "technical"),
        ("Cloud Fundamentals", "technical"),
        ("Customer Empathy", "soft_skills"),
    ]
    courses: list[dict] = []
    for i in range(cfg.n_courses):
        title, category = course_catalog[i % len(course_catalog)]
        courses.append(
            {
                "course_id": f"course_{i:04d}",
                "title": f"{title} v{(i // len(course_catalog)) + 1}",
                "category": category,
                "required": category == "compliance",
                "duration_minutes": rng.choice([15, 30, 45, 60, 90, 120]),
            }
        )

    completions: list[dict] = []
    for e in employees:
        if not e["is_active"]:
            continue
        for course in courses:
            if course["required"] or rng.random() < cfg.completion_rate:
                assigned_at = fake.date_between(
                    start_date=max(e["hire_date"], cfg.history_start),
                    end_date=cfg.today,
                )
                if rng.random() < cfg.completion_rate:
                    completed_at = assigned_at + timedelta(days=rng.randint(1, 45))
                    if completed_at > cfg.today:
                        completed_at = None
                else:
                    completed_at = None
                completions.append(
                    {
                        "completion_id": f"comp_{len(completions):08d}",
                        "employee_id": e["employee_id"],
                        "course_id": course["course_id"],
                        "assigned_at": assigned_at,
                        "completed_at": completed_at,
                        "status": "completed" if completed_at else "in_progress",
                    }
                )

    return GenerationArtifacts(
        employees=employees,
        comp=comp_rows,
        orgs=org_rows,
        requisitions=requisitions,
        candidates=candidates,
        applications=applications,
        courses=courses,
        completions=completions,
    )


def _write_parquet(rows: list[dict], filename: str) -> Path:
    path = OUTPUT_DIR / filename
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path


def write(artifacts: GenerationArtifacts) -> dict[str, Path]:
    mapping = {
        "workday_employees.parquet": artifacts.employees,
        "workday_comp.parquet": artifacts.comp,
        "workday_org.parquet": artifacts.orgs,
        "greenhouse_requisitions.parquet": artifacts.requisitions,
        "greenhouse_candidates.parquet": artifacts.candidates,
        "greenhouse_applications.parquet": artifacts.applications,
        "docebo_courses.parquet": artifacts.courses,
        "docebo_completions.parquet": artifacts.completions,
    }
    return {name: _write_parquet(rows, name) for name, rows in mapping.items()}


def main() -> None:
    cfg = GeneratorConfig()
    artifacts = generate(cfg)
    paths = write(artifacts)
    print(f"Generated synthetic data with seed={cfg.seed}:")
    for name, path in paths.items():
        count = {
            "workday_employees.parquet": len(artifacts.employees),
            "workday_comp.parquet": len(artifacts.comp),
            "workday_org.parquet": len(artifacts.orgs),
            "greenhouse_requisitions.parquet": len(artifacts.requisitions),
            "greenhouse_candidates.parquet": len(artifacts.candidates),
            "greenhouse_applications.parquet": len(artifacts.applications),
            "docebo_courses.parquet": len(artifacts.courses),
            "docebo_completions.parquet": len(artifacts.completions),
        }[name]
        print(f"  {path.name}  —  {count:,} rows")


if __name__ == "__main__":
    main()
