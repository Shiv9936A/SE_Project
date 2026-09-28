def create_project(client, payload):
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201
    return response.json()


def test_project_create_list_detail_update(client, project_payload):
    project = create_project(client, project_payload)
    project_id = project["id"]
    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == project_id
    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["project_name"] == project_payload["project_name"]
    assert detail.json()["questionnaire"] is None
    updated = client.put(f"/api/projects/{project_id}", json={"team_size": 14})
    assert updated.status_code == 200
    assert updated.json()["team_size"] == 14


def test_project_validation_and_not_found(client, project_payload):
    bad = {**project_payload, "team_size": 0}
    assert client.post("/api/projects", json=bad).status_code == 422
    assert client.get("/api/projects/missing-project").status_code == 404


def test_update_without_fields_returns_422(client, project_payload):
    project = create_project(client, project_payload)
    assert client.put(f"/api/projects/{project['id']}", json={}).status_code == 422
