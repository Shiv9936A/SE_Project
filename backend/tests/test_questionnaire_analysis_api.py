def create_project(client, payload):
    return client.post("/api/projects", json=payload).json()


def test_save_questionnaire_and_generate_recommendation(client, project_payload, questionnaire_payload):
    project = create_project(client, project_payload)
    project_id = project["id"]
    answer = client.post(f"/api/projects/{project_id}/questionnaire", json=questionnaire_payload)
    assert answer.status_code == 200
    assert answer.json()["formal_verification"] == "Yes"
    analysis = client.post(f"/api/projects/{project_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["recommended_sdlc"] in {
        "Waterfall", "V-Model", "Incremental", "Iterative", "Spiral", "Agile Scrum", "RAD"
    }
    assert 0 <= analysis.json()["confidence_score"] <= 100
    assert len(analysis.json()["alternatives"]) == 3
    assert analysis.json()["scoring_method"] == "rule_based_v2"
    latest = client.get(f"/api/projects/{project_id}/recommendation")
    assert latest.status_code == 200
    assert latest.json()["id"] == analysis.json()["id"]
    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["questionnaire"]["project_id"] == project_id
    assert detail["recommendation"]["id"] == analysis.json()["id"]


def test_analyze_without_questionnaire_conflicts(client, project_payload):
    project = create_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/analyze")
    assert response.status_code == 409


def test_questionnaire_enums_are_validated(client, project_payload, questionnaire_payload):
    project = create_project(client, project_payload)
    bad_answers = {**questionnaire_payload, "risk_level": "Severe"}
    assert client.post(f"/api/projects/{project['id']}/questionnaire", json=bad_answers).status_code == 422
