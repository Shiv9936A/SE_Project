def test_health_includes_database_status(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "service": "requirements-studio-api"}


def test_openapi_documentation_is_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/projects/{project_id}/questionnaire" in paths
    assert "/api/projects/{project_id}/documents" in paths
