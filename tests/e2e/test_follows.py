"""cuentas privadas y solicitudes de seguimiento."""

import httpx

from conftest import SERVERS

API = f"{SERVERS['a']}/api"


def private(user):
    client = user()
    resp = client.http.patch("/me", json={"locked": True})
    assert resp.status_code == 200 and resp.json()["locked"] is True
    return client


def usernames(resp: httpx.Response) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [u["username"] for u in resp.json()]


def test_user_representation(user):
    ana = user()
    me = ana.http.get("/me").json()
    assert me["handle"] == f"{ana.username}@{me['domain']}"
    assert me["is_local"] is True and me["locked"] is False


def test_patch_me_changes_only_given_fields(user):
    ana = user()
    resp = ana.http.patch("/me", json={"display_name": "Ana"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Ana" and resp.json()["locked"] is False
    assert ana.http.patch("/me", json={"display_name": ""}).status_code == 422


def test_follow_public_account_is_accepted(user):
    ana, beto = user(), user()
    resp = ana.http.post(f"/users/{beto.username}/follow")
    assert resp.status_code == 200 and resp.json() == {"state": "accepted"}


def test_private_account_needs_approval(user):
    ana, beto = user(), private(user)
    secret = f"secreto-{beto.username}"
    beto.post(secret, "followers")
    assert ana.http.post(f"/users/{beto.username}/follow").json() == {"state": "pending"}

    assert usernames(httpx.get(f"{API}/users/{beto.username}/followers")) == []
    assert usernames(beto.http.get("/me/follow-requests")) == [ana.username]
    assert secret not in ana.home()
    assert ana.http.get(f"/users/{beto.username}/notes").json() == []

    assert beto.http.post(f"/me/follow-requests/{ana.username}/accept").status_code == 204
    assert beto.http.post(f"/me/follow-requests/{ana.username}/accept").status_code == 204
    assert usernames(httpx.get(f"{API}/users/{beto.username}/followers")) == [ana.username]
    assert usernames(beto.http.get("/me/follow-requests")) == []
    assert ana.home() == [secret]


def test_reject_request_is_idempotent(user):
    ana, beto = user(), private(user)
    ana.http.post(f"/users/{beto.username}/follow")
    assert beto.http.post(f"/me/follow-requests/{ana.username}/reject").status_code == 204
    assert beto.http.post(f"/me/follow-requests/{ana.username}/reject").status_code == 204
    assert usernames(beto.http.get("/me/follow-requests")) == []
    assert usernames(httpx.get(f"{API}/users/{beto.username}/followers")) == []


def test_accept_without_request_or_unknown_user_is_404(user):
    ana, beto = user(), private(user)
    assert beto.http.post(f"/me/follow-requests/{ana.username}/accept").status_code == 404
    assert beto.http.post("/me/follow-requests/nadie_existe/accept").status_code == 404
    assert beto.http.post("/me/follow-requests/nadie_existe/reject").status_code == 404


def test_unlocking_accepts_pending_requests(user):
    ana, beto = user(), private(user)
    ana.http.post(f"/users/{beto.username}/follow")
    assert beto.http.patch("/me", json={"locked": False}).json()["locked"] is False
    assert usernames(httpx.get(f"{API}/users/{beto.username}/followers")) == [ana.username]
    assert ana.http.post(f"/users/{beto.username}/follow").json() == {"state": "accepted"}


def test_unfollow_cancels_request(user):
    ana, beto = user(), private(user)
    ana.http.post(f"/users/{beto.username}/follow")
    assert ana.http.delete(f"/users/{beto.username}/follow").status_code == 204
    assert usernames(beto.http.get("/me/follow-requests")) == []
