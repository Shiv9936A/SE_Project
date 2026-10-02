def test_list_projects_returns_200_with_empty_database(client):
    response = client.get("/api/projects")

    assert response.status_code == 200
    assert response.json() == []


def test_analytics_summary_returns_200_with_empty_database(client):
    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    assert response.json() == {
        "project_count": 0,
        "document_count": 0,
        "embedded_document_count": 0,
        "recommendation_count": 0,
        "conversation_count": 0,
    }
