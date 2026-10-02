"""Persistence and API coverage for versioned multi-agent analysis runs."""
from datetime import datetime, timedelta, timezone

import pytest

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.models import AnalysisRun, Project, RequirementsAnalysis
from app.repositories import analysis_runs


def _db():
    generator = __import__("app.main", fromlist=["app"]).app.dependency_overrides[get_db]()
    return next(generator), generator


def _project(client, project_payload):
    response = client.post("/api/projects", json=project_payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_run_versions_history_detail_and_active_run_conflict(client, project_payload):
    project_id = _project(client, project_payload)
    db, generator = _db()
    first = analysis_runs.create(db, project_id)
    assert first.version == 1
    with pytest.raises(AppError) as conflict:
        analysis_runs.create(db, project_id)
    assert conflict.value.status_code == 409
    analysis_runs.finish(db, first.id, "completed", ["review evidence"], [])

    req_json = {
        "summary": "Application needs review.", "requirements": [], "ambiguities": [], "conflicts": [],
        "completeness": [], "clarification_questions": [], "quality_assessment": {}, "evidence_sources": [],
    }
    req = RequirementsAnalysis(project_id=project_id, version=1, status="needs_review", provider="test", model="test", result_json=req_json)
    db.add(req)
    db.commit()
    analysis_runs.attach_requirements(db, first.id, req.id)
    second = analysis_runs.create(db, project_id)
    assert second.version == 2
    analysis_runs.finish(db, second.id, "partial", [], [{"code": "AGENT_PARTIAL", "message": "Review fallback.", "recoverable": True}])
    db.close()
    generator.close()

    history = client.get(f"/api/projects/{project_id}/analysis-runs")
    assert history.status_code == 200
    rows = history.json()
    assert [row["version"] for row in rows] == [2, 1]
    assert rows[0]["status"] == "partial"
    assert rows[0]["errors"][0]["code"] == "AGENT_PARTIAL"
    assert rows[1]["requirements_analysis_id"] == req.id
    assert rows[1]["requirement_count"] == 0

    detail = client.get(f"/api/projects/{project_id}/analysis-runs/{first.id}")
    assert detail.status_code == 200
    assert detail.json()["requirements_analysis"]["analysis_id"] == req.id
    assert detail.json()["requirements_analysis"]["summary"] == "Application needs review."
    assert detail.json()["agents"][0]["status"] == "completed"
    assert client.get(f"/api/projects/{project_id}/analysis-runs/missing").status_code == 404
    assert client.get("/api/projects/missing/analysis-runs").status_code == 404


def test_stale_running_run_is_released_and_reported_failed(client, project_payload, monkeypatch):
    project_id = _project(client, project_payload)
    db, generator = _db()
    run = analysis_runs.create(db, project_id)
    run.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    monkeypatch.setattr(settings, "analysis_run_stale_after_minutes", 5)
    rows = analysis_runs.list_for_project(db, project_id)
    assert rows[0].status == "failed"
    assert rows[0].active_project_id is None
    assert rows[0].errors_json[0]["code"] == "ANALYSIS_RUN_ABANDONED"
    again = analysis_runs.create(db, project_id)
    assert again.version == 2
    db.close()
    generator.close()
