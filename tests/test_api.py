from fastapi.testclient import TestClient

from mqlbot_demo.app import app

client = TestClient(app)


def test_health_and_ui():
    assert client.get("/health").json() == {"status": "ok", "mode": "demo"}
    assert "MQL_PLMate" in client.get("/").text


def test_find_sme_contract():
    data = client.post("/api/find-sme", json={"query": "wifi", "top_k": "all"}).json()
    assert data["total_count"] == len(data["candidates"]) >= 1
    assert data["candidate1_name"] == data["candidates"][0]["name"]
    assert data["formatted_result"].startswith("🔍 SME Search Results")


def test_find_sme_validation():
    assert client.post("/api/find-sme", json={"query": "  "}).status_code == 400
    assert client.post("/api/find-sme", json={"query": "wifi", "top_k": 0}).status_code == 422


def test_find_sme_uses_expander_only_when_no_results():
    calls = []

    async def expander(query):
        calls.append(query)
        return ["wifi"]

    app.state.sme_expander = expander
    try:
        client.post("/api/find-sme", json={"query": "wifi"})
        assert calls == []
        data = client.post("/api/find-sme", json={"query": "airlink"}).json()
        assert calls == ["airlink"] and data["expanded_keywords"] == ["wifi"] and data["total_count"] > 0
    finally:
        del app.state.sme_expander


def test_query_log_records_searches():
    client.post("/api/find-sme", json={"query": "gps"})
    assert client.get("/api/query-log").json()["logs"][0]["query"] == "gps"


def test_issue_lookup_post_and_get():
    post = client.post("/api/aibuilder/issue-lookup", json={"userInput": {"issueNumber": "demo-000101"}}).json()
    get = client.get("/api/aibuilder/issue-lookup", params={"issueNumber": "DEMO-000101"}).json()
    assert post["output"]["found"] and get["output"]["found"]
    assert post["output"]["issueNumber"] == "DEMO-000101"


def test_issue_lookup_tolerates_invalid_json():
    resp = client.post("/api/aibuilder/issue-lookup", content=b"{broken", headers={"Content-Type": "application/json"})
    assert resp.status_code == 200 and resp.json()["output"]["found"] is False


def test_ai_summary_endpoint(monkeypatch):
    monkeypatch.delenv("OLLAMA_SUMMARY_MODEL", raising=False)
    text = "Camera preview freezes about 30 seconds into 4K HDR recording and recovers only after force close."
    data = client.post("/api/aibuilder/ai-summary", json={"text": text}).json()
    assert data["success"] and data["summary_en"] and data["summary_ko"]
