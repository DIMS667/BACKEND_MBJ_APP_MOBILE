"""A new account cannot reach child-data routes before opting in."""

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_authenticated_user, get_current_user
from app.modules.auth.router import router as auth_router


def test_child_routes_require_an_explicit_choice_and_can_be_disabled_again():
    user = SimpleNamespace(child_sync_enabled=False, child_sync_choice_at=None)
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    @app.post("/private-child-data")
    async def private_child_data(current_user=Depends(get_current_user)):
        return {"ok": True}

    @app.get("/public-content")
    async def public_content():
        return {"ok": True}

    app.dependency_overrides[get_authenticated_user] = lambda: user
    client = TestClient(app)

    assert client.get("/auth/child-sync").json() == {"enabled": False}
    assert client.get("/public-content").status_code == 200
    assert client.post("/private-child-data").status_code == 403

    assert client.put("/auth/child-sync", json={"enabled": True}).json() == {
        "enabled": True
    }
    assert user.child_sync_choice_at is not None
    assert client.post("/private-child-data").status_code == 200

    assert client.put("/auth/child-sync", json={"enabled": False}).json() == {
        "enabled": False
    }
    assert client.post("/private-child-data").status_code == 403
