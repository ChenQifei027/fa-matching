import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")

from core.database import (
    init_db, get_project, get_institution,
    list_institutions, list_projects, list_investment_records,
)
from core.matcher import match_project_to_institutions, match_institution_to_projects, analyze_investment_records

init_db(DB_PATH)
router = APIRouter(prefix="/api/matching")


class ProjectMatchReq(BaseModel):
    project_id: int


class InstitutionMatchReq(BaseModel):
    institution_id: int


@router.post("/project-to-institutions")
def project_to_institutions(body: ProjectMatchReq):
    project = get_project(DB_PATH, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    institutions = list_institutions(DB_PATH)
    if not institutions:
        return []
    enriched = []
    for inst in institutions:
        records = list_investment_records(DB_PATH, inst["id"])
        sample = "；".join(
            f"{r['company_name']}/{r.get('sector','')}/{r.get('stage','')}/{r.get('amount','')}"
            for r in records[:20]
        )
        enriched.append({**inst,
            "portfolio_analysis": analyze_investment_records(records),
            "investment_records_sample": sample,
        })
    return match_project_to_institutions(project, enriched)


@router.post("/institution-to-projects")
def institution_to_projects(body: InstitutionMatchReq):
    institution = get_institution(DB_PATH, body.institution_id)
    if not institution:
        raise HTTPException(404, "Institution not found")
    records = list_investment_records(DB_PATH, body.institution_id)
    projects = list_projects(DB_PATH)
    if not projects:
        return []
    return match_institution_to_projects(
        {**institution, "portfolio_analysis": analyze_investment_records(records)},
        projects,
    )
