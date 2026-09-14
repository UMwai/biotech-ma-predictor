"""Smoke test for the supported local application; import errors must fail pytest."""


def test_imports():
    from src.local_app import app

    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/predictions/watchlist" in paths


if __name__ == "__main__":
    test_imports()
    print("Local application import passed")
