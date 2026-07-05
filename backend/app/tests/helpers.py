"""Shared test helpers."""


def process_and_wait(client, admin_token: str, act_id: str) -> dict:
    """Trigger processing and return the finalized job.

    Processing runs as a FastAPI BackgroundTask, so the POST response body
    reflects the just-created QUEUED job (serialized before the background task
    runs). Starlette's TestClient executes background tasks synchronously as
    part of handling the request, so by the time the POST call returns, the job
    has already finished; a single follow-up GET reflects its final state.
    """
    response = client.post(
        f"/api/v1/acts/{act_id}/process",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    queued_job = response.json()
    assert queued_job["status"] == "QUEUED"

    jobs_response = client.get(
        f"/api/v1/acts/{act_id}/processing-jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    finalized = next(job for job in jobs if job["id"] == queued_job["id"])
    assert finalized["status"] in {"COMPLETED", "FAILED"}
    return finalized
