"""Governance and SDLC planning agent layered over the existing deterministic scorecard."""
import json
import logging
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models import GovernanceAnalysis, Project, QuestionnaireResponse
from app.repositories import governance_analyses as governance_repo
from app.repositories import requirements_analyses as requirements_repo
from app.schemas.governance_analysis import (
    GovernanceAnalysisRead, GovernanceAnalysisResult, GovernanceEvidence,
    GovernanceRisk, MethodologyRecommendation, ProjectAssessment, ReasoningFactor,
)
from app.schemas.requirements_analysis import RequirementsAnalysisResult
from app.services.agents.requirements_agent import _json_from_text, _norm
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import retrieval_service
from app.services.sdlc_recommendation_service import SDLC_MODELS, score_sdlc_models

logger = logging.getLogger(__name__)

METHODOLOGIES = {"Agile", "Waterfall", "Iterative", "Spiral", "Hybrid", *SDLC_MODELS}


class GovernanceAgent:
    def __init__(self, retriever=None, llm=None):
        self.retriever = retriever or retrieval_service
        self.llm = llm or get_llm_service()

    def analyze(self, db: Session, project_id: str, top_k: int = 5) -> dict:
        project = db.get(Project, project_id)
        if project is None:
            raise AppError("Project not found.", 404)
        analysis = requirements_repo.latest(db, project_id)
        if analysis is None:
            raise AppError("Generate a Phase 11 requirements analysis before requesting governance analysis.", 409)
        try:
            requirements = RequirementsAnalysisResult.model_validate(analysis.result_json)
        except ValidationError as exc:
            raise AppError("The saved requirements analysis is invalid. Regenerate it before continuing.", 409) from exc

        questionnaire = project.questionnaire
        questionnaire_data = self._questionnaire_dict(questionnaire)
        chunks = self._retrieve(db, project, top_k)
        baseline = score_sdlc_models(questionnaire_data, chunks)
        project_context = self._project_dict(project)
        refs = self._source_map(requirements, questionnaire_data, chunks)
        for key, value in project_context.items():
            if value is not None and str(value).strip():
                refs[f"project:{key}"] = str(value)
        request_data = {
            "project": project_context,
            "questionnaire": questionnaire_data,
            "requirements_analysis": requirements.model_dump(mode="json"),
            "deterministic_sdlc_baseline": baseline,
            "retrieved_document_context": [
                {"chunk_id": str(row.get("chunk_id")), "filename": row.get("filename"),
                 "page_number": row.get("page_number"), "text": str(row.get("text", ""))[:3000]}
                for row in chunks
            ],
            "allowed_evidence_reference_ids": sorted(refs),
            "output_schema": GovernanceAnalysisResult.model_json_schema(),
        }
        failure_category = None
        started = perf_counter()
        try:
            draft = self._generate(project_id, analysis.id, request_data, refs, requirements,
                                   questionnaire_data, baseline, chunks)
            status = "partial" if analysis.status == "partial" else "needs_review"
            if status == "partial":
                draft.fallback_reason = "requirements_analysis_partial"
        except Exception as exc:
            failure_category = self._failure_category(exc)
            failure_location = self._failure_location(exc)
            logger.warning("Governance generation falling back to deterministic SDLC baseline: %s (%s at %s)", failure_category, type(exc).__name__, failure_location, extra={
                "project_id": project_id,
                "requirements_analysis_id": analysis.id,
                "provider": settings.llm_provider.lower(),
                "model": self._model_name(),
                "failure_category": failure_category,
                "failure_type": type(exc).__name__,
                "failure_location": failure_location,
            })
            draft = self._fallback(project_id, analysis.id, project_context,
                                   questionnaire_data, requirements, baseline, chunks,
                                   failure_category)
            status = "partial"

        version = governance_repo.next_version(db, project_id)
        provider = settings.llm_provider.lower()
        record = governance_repo.create(db, GovernanceAnalysis(
            project_id=project_id,
            requirements_analysis_id=analysis.id,
            version=version,
            methodology=draft.methodology.name,
            status=status,
            provider=provider,
            model=self._model_name(),
            result_json=draft.model_dump(mode="json"),
        ))
        logger.info("Governance analysis persisted", extra={
            "project_id": project_id, "analysis_id": record.id,
            "requirements_analysis_id": analysis.id, "methodology": record.methodology,
            "provider": provider, "model": record.model,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "requirement_count": len(requirements.requirements), "risk_count": len(draft.risks),
            "fallback_status": status == "partial", "failure_category": failure_category,
        })
        return self._serialize(record)

    def latest(self, db: Session, project_id: str) -> dict:
        if db.get(Project, project_id) is None:
            raise AppError("Project not found.", 404)
        record = governance_repo.latest(db, project_id)
        if record is None:
            raise AppError("No governance analysis is available for this project.", 404)
        return self._serialize(record)

    def _retrieve(self, db, project, top_k):
        if not project.documents:
            return []
        query = f"{project.project_name} {project.description} security compliance integrations performance delivery requirements"
        try:
            return self.retriever.search(db, project.id, query, top_k=top_k, score_threshold=0.15)
        except Exception as exc:
            logger.warning("Governance document retrieval unavailable", extra={
                "project_id": project.id, "failure_category": self._failure_category(exc),
            })
            return []

    @staticmethod
    def _questionnaire_dict(questionnaire: QuestionnaireResponse | None) -> dict:
        if questionnaire is None:
            return {}
        return {
            column.name: getattr(questionnaire, column.name)
            for column in questionnaire.__table__.columns
            if column.name not in {"id", "project_id", "created_at"}
        }

    @staticmethod
    def _project_dict(project: Project) -> dict:
        return {
            "project_name": project.project_name, "description": project.description,
            "domain": project.domain, "organization_type": project.organization_type,
            "team_size": project.team_size, "stakeholders": project.stakeholders,
            "initial_requirements": project.initial_requirements,
        }

    @staticmethod
    def _source_map(requirements, questionnaire, chunks):
        refs = {row.requirement_id: f"{row.title}. {row.description}. Evidence: {row.evidence}"
                for row in requirements.requirements}
        for key, value in questionnaire.items():
            refs[f"questionnaire:{key}"] = str(value)
        for index, item in enumerate(requirements.ambiguities, start=1):
            refs[f"analysis:ambiguity:{index}"] = f"{item.description} Clarification: {item.clarification_question}"
        for index, item in enumerate(requirements.conflicts, start=1):
            refs[f"analysis:conflict:{index}"] = item.description
        for item in requirements.completeness:
            if item.status != "covered":
                refs[f"analysis:missing:{item.area}"] = f"{item.area}: {item.note}"
        for index, question in enumerate(requirements.clarification_questions, start=1):
            refs[f"analysis:question:{index}"] = question
        for row in requirements.evidence_sources:
            refs[row.source_reference] = row.evidence
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            if chunk_id and chunk.get("text"):
                refs[chunk_id] = str(chunk["text"])
        return refs

    def _generate(self, project_id, analysis_id, request_data, refs, requirements,
                  questionnaire, baseline, chunks) -> GovernanceAnalysisResult:
        system = (
            "You are a software governance and SDLC planning specialist. Return a single JSON object matching the supplied schema. "
            "Use the structured Requirements Analysis as the primary source and the supplied deterministic SDLC scorecard as the baseline. "
            "Recommend an allowed methodology based on observed characteristics; do not choose randomly or ignore the scorecard without "
            "citing project evidence. Do not regenerate or add requirements. Do not invent integrations, regulatory obligations, facts, "
            "risk controls, or requirement IDs. Reference only IDs in allowed_evidence_reference_ids and requirement_references must be "
            "actual REQ-* IDs. Identify recommendations as recommendations, and potential risks as potential. If evidence is missing, "
            "surface it as a prerequisite or unresolved question instead of resolving it. Do not expose chain-of-thought; give concise, "
            "user-safe reasoning factors. All phase names, methodology names, severity, likelihood, and assessment values must exactly match "
            "the schema enums. Do not include a fallback_reason. Output JSON only, no markdown."
        )
        raw = _json_from_text(self.llm.generate(system, json.dumps(request_data, ensure_ascii=False)))
        if not isinstance(raw, dict):
            raise ValueError("invalid_json_shape")
        # Validate the provider's categorical assessment before replacing it with
        # the deterministic values derived from saved questionnaire/analysis data.
        ProjectAssessment.model_validate(raw.get("project_assessment"))
        raw["project_id"] = project_id
        raw["requirements_analysis_id"] = analysis_id
        raw["baseline_scores"] = baseline
        raw["project_assessment"] = self._assessment(questionnaire, requirements)
        raw["risks"] = self._risk_ids(raw.get("risks", []))
        raw["fallback_reason"] = None
        result = GovernanceAnalysisResult.model_validate(raw)
        self._validate_result(result, refs, requirements)
        # The output assessment is a deterministic view of saved inputs, never an LLM fact.
        result.project_assessment = self._assessment(questionnaire, requirements)
        result.evidence = self._validated_evidence(result, refs, requirements, questionnaire, chunks)
        return result

    @staticmethod
    def _risk_ids(risks):
        if not isinstance(risks, list):
            raise ValueError("invalid_risks")
        return [{**risk, "risk_id": f"RISK-{index:03d}"} for index, risk in enumerate(risks, start=1)]

    @staticmethod
    def _validate_result(result, refs, requirements):
        requirement_ids = {item.requirement_id for item in requirements.requirements}
        allowed_refs = set(refs)
        if result.methodology.name not in METHODOLOGIES:
            raise ValueError("invalid_methodology")
        for item in result.methodology.reasoning:
            if not item.source_references or any(ref not in allowed_refs for ref in item.source_references):
                raise ValueError("invalid_reasoning_reference")
        for phase in result.development_lifecycle:
            if any(ref not in requirement_ids for ref in phase.requirement_references):
                raise ValueError("invalid_phase_requirement_reference")
        for group in (
            result.testing_strategy.unit_testing, result.testing_strategy.integration_testing,
            result.testing_strategy.system_testing, result.testing_strategy.acceptance_testing,
            result.testing_strategy.security_testing, result.testing_strategy.performance_testing,
        ):
            if any(ref not in requirement_ids for row in group for ref in row.requirement_references):
                raise ValueError("invalid_test_requirement_reference")
        for item in result.security_governance + result.documentation_requirements:
            if any(ref not in requirement_ids for ref in item.requirement_references):
                raise ValueError("invalid_governance_requirement_reference")
        for risk in result.risks:
            if any(ref not in allowed_refs for ref in risk.source_references):
                raise ValueError("invalid_risk_reference")
        for gate in result.quality_gates:
            if any(ref not in requirement_ids for ref in gate.requirement_references):
                raise ValueError("invalid_quality_gate_reference")
        for evidence in result.evidence:
            if evidence.source_reference not in allowed_refs:
                raise ValueError("invalid_evidence_reference")
            expected_type = GovernanceAgent._evidence_source_type(evidence.source_reference)
            if evidence.source_type != expected_type:
                raise ValueError("invalid_evidence_source_type")
            if _norm(evidence.observation) not in _norm(refs[evidence.source_reference]):
                raise ValueError("evidence_observation_mismatch")

    @staticmethod
    def _evidence_source_type(reference):
        if reference.startswith("project:"):
            return "project_profile"
        if reference.startswith("questionnaire:"):
            return "questionnaire"
        if reference.startswith(("REQ-", "analysis:", "interview:")):
            return "requirements_analysis"
        return "rag_evidence"

    @staticmethod
    def _validated_evidence(result, refs, requirements, questionnaire, chunks):
        evidence = []
        for item in result.methodology.reasoning:
            reference = item.source_references[0]
            source_type = GovernanceAgent._evidence_source_type(reference)
            # Emit a quoted observation from the cited source rather than model-authored evidence.
            observation = refs[reference][:500]
            evidence.append(GovernanceEvidence(source_type=source_type,
                                               source_reference=reference,
                                               observation=observation))
        seen = {(item.source_reference, item.observation) for item in evidence}
        for risk in result.risks:
            for reference in risk.source_references:
                pair = (reference, refs[reference][:500])
                if pair in seen:
                    continue
                source_type = GovernanceAgent._evidence_source_type(reference)
                evidence.append(GovernanceEvidence(source_type=source_type,
                                                   source_reference=reference,
                                                   observation=pair[1]))
                seen.add(pair)
        return evidence[:100]

    @staticmethod
    def _assessment(questionnaire, requirements):
        def level(value):
            clean = str(value or "").casefold()
            return clean if clean in {"low", "medium", "high"} else "unknown"

        stability_value = str(questionnaire.get("requirement_stability", "")).casefold()
        stability = {
            "stable": "stable", "moderately changing": "moderate",
            "frequently changing": "volatile",
        }.get(stability_value, "unknown")
        integration = {"yes": "high", "no": "low"}.get(
            str(questionnaire.get("legacy_integration", "")).casefold(), "unknown",
        )
        if integration == "unknown" and any(req.category == "integration" for req in requirements.requirements):
            integration = "medium"
        return ProjectAssessment(
            complexity=level(questionnaire.get("complexity")),
            risk_level=level(questionnaire.get("risk_level")),
            requirements_stability=stability,
            integration_complexity=integration,
            security_sensitivity=level(questionnaire.get("security_criticality")),
            compliance_impact=level(questionnaire.get("compliance_criticality")),
        )

    def _fallback(self, project_id, analysis_id, project, questionnaire, requirements,
                  baseline, chunks, failure_category):
        winner = baseline[0]
        runner_up = baseline[1] if len(baseline) > 1 else winner
        gap = max(0, int(winner["score"]) - int(runner_up["score"]))
        confidence = min(95.0, round(55.0 + gap * 0.8, 1)) / 100
        ref_for_baseline = next((f"questionnaire:{key}" for key in (
            "requirement_stability", "complexity", "risk_level", "expected_changes",
        ) if f"questionnaire:{key}" in self._source_map(requirements, questionnaire, chunks)), None)
        if not ref_for_baseline:
            ref_for_baseline = requirements.requirements[0].requirement_id if requirements.requirements else "analysis:missing:testing and verification"
        reasoning = [ReasoningFactor(
            factor="deterministic_scorecard",
            observation=f"The existing rule-based scorecard ranks {winner['model']} first ({winner['score']}/100), followed by {runner_up['model']} ({runner_up['score']}/100).",
            impact="Use the scorecard leader as a provisional lifecycle baseline and validate it with stakeholders.",
            source_references=[ref_for_baseline],
        )]
        methodology = MethodologyRecommendation(name=winner["model"], confidence=confidence, reasoning=reasoning)
        risks = self._deterministic_risks(requirements, questionnaire)
        req_ids = [item.requirement_id for item in requirements.requirements]
        relevant_security = [item.requirement_id for item in requirements.requirements
                             if item.category == "security_privacy_compliance"]
        security_signal = str(questionnaire.get("security_criticality", "")).casefold()
        compliance_signal = str(questionnaire.get("compliance_criticality", "")).casefold()
        integration_ids = [item.requirement_id for item in requirements.requirements
                           if item.category == "integration"]
        functional_ids = [item.requirement_id for item in requirements.requirements
                          if item.category == "functional"]
        nfr_ids = [item.requirement_id for item in requirements.requirements
                   if item.category == "non_functional"]

        def rec(text, ids=()):
            return {"recommendation": text, "requirement_references": list(ids)}

        testing = {
            "unit_testing": [rec("Add unit tests for each accepted functional requirement.", functional_ids)] if functional_ids else [],
            "integration_testing": [rec("Verify declared interfaces and integration behavior against their agreed contracts.", integration_ids)] if integration_ids else [],
            "system_testing": [rec("Validate end-to-end behavior against approved acceptance criteria.", req_ids)] if req_ids else [],
            "acceptance_testing": [rec("Have stakeholder representatives review the implemented scope and acceptance criteria.", req_ids)] if req_ids else [],
            "security_testing": ([rec("Validate the stated security requirements during security testing.", relevant_security)]
                                 if relevant_security else
                                 [rec("Confirm explicit security controls before defining security tests; the questionnaire marks security as a project concern.")]
                                 if security_signal in {"medium", "high"} else []),
            "performance_testing": [rec("Define measurable performance targets before selecting and running load tests.", nfr_ids)] if nfr_ids else [],
        }
        phases = [
            {"phase": "Requirements", "activities": ["Review and approve the current requirements draft.", "Resolve critical ambiguities and conflicts."],
             "deliverables": ["Reviewed requirements baseline", "Traceability updates"],
             "exit_criteria": ["Critical open questions have an owner and resolution plan."], "requirement_references": req_ids},
            {"phase": "Architecture & Design", "activities": ["Review architecture, data boundaries, and declared integrations."],
             "deliverables": ["Architecture decision record", "Interface and data design"],
             "exit_criteria": ["Architecture and integration assumptions are reviewed."], "requirement_references": integration_ids + relevant_security},
            {"phase": "Implementation", "activities": [f"Deliver work using the {winner['model']} baseline and maintain requirement traceability."],
             "deliverables": ["Implementation increments", "Updated technical documentation"],
             "exit_criteria": ["Changes are reviewed and linked to accepted requirements."], "requirement_references": req_ids},
            {"phase": "Testing", "activities": ["Run the test levels applicable to accepted requirements.", "Record defects and verification results."],
             "deliverables": ["Test results", "Defect disposition"],
             "exit_criteria": ["Required tests have results and release-blocking defects are dispositioned."], "requirement_references": req_ids},
            {"phase": "Deployment", "activities": ["Review deployment readiness and rollback arrangements."],
             "deliverables": ["Release plan", "Rollback plan"],
             "exit_criteria": ["Release owner and operational support are identified."], "requirement_references": []},
            {"phase": "Monitoring & Maintenance", "activities": ["Monitor operation and review incidents and change requests."],
             "deliverables": ["Operational runbook", "Monitoring and incident records"],
             "exit_criteria": ["Operational ownership and issue escalation are agreed."], "requirement_references": []},
        ]
        security = ([{"activity": "Review each explicit security, privacy, or compliance requirement and record implementation and verification evidence.",
                      "requirement_references": relevant_security}] if relevant_security else [])
        if not security and (security_signal in {"medium", "high"} or compliance_signal in {"medium", "high"}):
            security.append({"activity": "Confirm which security, privacy, and compliance controls apply; no specific regulation or control is assumed.",
                             "requirement_references": []})
        docs = [
            {"document": "Software Requirements Specification", "rationale": "Maintain the reviewed scope, requirement IDs, and acceptance criteria.", "requirement_references": req_ids},
            {"document": "Architecture and Interface Documentation", "rationale": "Record design decisions and integration assumptions for review.", "requirement_references": integration_ids},
            {"document": "Test Plan and Results", "rationale": "Show how accepted requirements were verified.", "requirement_references": req_ids},
            {"document": "Deployment and Operations Guide", "rationale": "Support release, rollback, monitoring, and ongoing ownership.", "requirement_references": []},
        ]
        checkpoints = [
            {"checkpoint": "Requirements review", "purpose": "Confirm scope, traceability, ambiguity resolution, and acceptance criteria.",
             "entry_conditions": ["Requirements draft is available."], "exit_conditions": ["Open issues are resolved or explicitly owned."],
             "required_artifacts": ["Requirements Analysis", "Decision and clarification log"]},
            {"checkpoint": "Architecture review", "purpose": "Review design decisions, security topics, and declared integrations.",
             "entry_conditions": ["Architecture proposal and integration list are available."], "exit_conditions": ["Assumptions and risks have owners."],
             "required_artifacts": ["Architecture document", "Interface inventory"]},
            {"checkpoint": "Test readiness review", "purpose": "Confirm test scope, environments, and evidence collection.",
             "entry_conditions": ["Approved requirements and test plan are available."], "exit_conditions": ["Required test levels and acceptance owners are agreed."],
             "required_artifacts": ["Test plan", "Acceptance criteria"]},
            {"checkpoint": "Release readiness review", "purpose": "Review acceptance, release risks, operational support, and rollback planning.",
             "entry_conditions": ["Test results and release plan are available."], "exit_conditions": ["Release decision and accountable owner are recorded."],
             "required_artifacts": ["Test results", "Deployment and rollback plan"]},
        ]
        gates = [
            {"gate": "Requirements gate", "checks": ["Critical ambiguities and conflicts are resolved or accepted as open risks.", "Requirements and acceptance criteria are traceable."], "requirement_references": req_ids},
            {"gate": "Architecture gate", "checks": ["Architecture has been reviewed.", "Declared interfaces and security requirements have an owner."], "requirement_references": integration_ids + relevant_security},
            {"gate": "Testing gate", "checks": ["Applicable test levels have recorded results.", "Critical defects have a documented disposition."], "requirement_references": req_ids},
            {"gate": "Release gate", "checks": ["Stakeholder acceptance and release ownership are recorded.", "Deployment and rollback plans are available."], "requirement_references": []},
        ]
        prerequisites = list(dict.fromkeys(
            [f"Resolve or explicitly accept: {item.clarification_question}" for item in requirements.ambiguities
             if item.severity in {"critical", "high"}]
            + [f"Resolve or explicitly accept conflict: {item.description}" for item in requirements.conflicts
               if item.severity in {"critical", "high"}]
            + [f"Confirm missing or incomplete area before the relevant design or release decision: {item.area}." for item in requirements.completeness
               if item.status != "covered" and item.area in {"security and privacy", "compliance and audit", "performance and scale", "integrations"}]
        ))
        evidence = []
        for reason in reasoning:
            reference = reason.source_references[0]
            text = self._source_map(requirements, questionnaire, chunks).get(reference, "")
            evidence.append({"source_type": "questionnaire" if reference.startswith("questionnaire:") else "requirements_analysis",
                             "source_reference": reference, "observation": text[:500]})
        return GovernanceAnalysisResult(
            project_id=project_id, requirements_analysis_id=analysis_id,
            methodology=methodology, project_assessment=self._assessment(questionnaire, requirements),
            baseline_scores=baseline, development_lifecycle=phases,
            testing_strategy=testing, security_governance=security,
            documentation_requirements=docs, governance_checkpoints=checkpoints,
            risks=risks, quality_gates=gates, prerequisites=prerequisites,
            evidence=evidence, unresolved_questions=list(requirements.clarification_questions),
            fallback_reason=failure_category,
        )

    @staticmethod
    def _deterministic_risks(requirements, questionnaire):
        risks = []

        def add(title, description, severity, likelihood, mitigation, refs, basis="potential"):
            risks.append({"risk_id": f"RISK-{len(risks) + 1:03d}", "title": title,
                          "description": description, "severity": severity,
                          "likelihood": likelihood, "mitigation": mitigation,
                          "source_references": refs, "basis": basis})

        for index, item in enumerate(requirements.ambiguities, start=1):
            ref = item.related_requirement_id or f"analysis:ambiguity:{index}"
            if ref not in {r.requirement_id for r in requirements.requirements}:
                ref = f"analysis:ambiguity:{index}"
            severity = "high" if item.severity == "critical" else item.severity
            add("Unresolved requirement ambiguity", item.description, severity,
                "medium", "Ask the listed clarification question and record the decision before baselining the affected scope.", [ref], "observed")
        for index, item in enumerate(requirements.conflicts, start=1):
            severity = "high" if item.severity == "critical" else item.severity
            add("Conflicting project evidence", item.description, severity,
                "medium", "Have the source owners reconcile the conflicting statements and update the requirement baseline.",
                [f"analysis:conflict:{index}"], "observed")
        for item in requirements.completeness:
            if item.status == "missing" and item.area in {"security and privacy", "compliance and audit", "performance and scale", "integrations", "operations and recovery"}:
                add(f"Unspecified {item.area}", f"Potential risk: the requirements analysis reports no supporting evidence for {item.area}.",
                    "medium", "medium", f"Confirm {item.area} with the accountable stakeholders and document applicable requirements.",
                    [f"analysis:missing:{item.area}"])
        q_risk = str(questionnaire.get("risk_level", "")).casefold()
        if q_risk in {"high", "medium"}:
            add("Project risk exposure", f"The questionnaire records project risk as {q_risk}.", q_risk, q_risk,
                "Assign risk owners, agree mitigations, and review open risks at governance checkpoints.", ["questionnaire:risk_level"], "observed")
        return risks[:40]

    @staticmethod
    def _failure_category(exc):
        if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError, TypeError)):
            return "invalid_output"
        if isinstance(exc, AppError):
            if exc.status_code == 502:
                return "provider_unavailable"
            if exc.status_code == 429:
                return "rate_limited"
            if exc.status_code == 504:
                return "timeout"
            return "provider_error"
        name = type(exc).__name__.casefold()
        if "timeout" in name or "deadline" in name:
            return "timeout"
        if "quota" in name or "rate" in name:
            return "rate_limited"
        return "generation_error"

    @staticmethod
    def _failure_location(exc):
        traceback = exc.__traceback__
        while traceback and traceback.tb_next:
            traceback = traceback.tb_next
        if traceback is None:
            return "unknown"
        return f"{traceback.tb_frame.f_code.co_name}:{traceback.tb_lineno}"

    @staticmethod
    def _model_name():
        return settings.gemini_model if settings.llm_provider.lower() == "gemini" else settings.llm_model

    @staticmethod
    def _serialize(record: GovernanceAnalysis) -> dict:
        return GovernanceAnalysisRead(
            id=record.id, project_id=record.project_id,
            requirements_analysis_id=record.requirements_analysis_id,
            version=record.version, status=record.status,
            provider=record.provider, model=record.model,
            created_at=record.created_at, updated_at=record.updated_at,
            result=record.result_json,
        ).model_dump(mode="json")


governance_agent = GovernanceAgent()
