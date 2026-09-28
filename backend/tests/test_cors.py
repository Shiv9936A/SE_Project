def test_delete_cors_preflight_allows_frontend_origin(client):
    response = client.options(
        "/api/projects/example-project/documents/example-document",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "DELETE" in response.headers["access-control-allow-methods"]
