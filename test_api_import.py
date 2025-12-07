#!/usr/bin/env python
"""
Test script to verify API imports and structure.

Validates that all API modules can be imported successfully.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all API modules can be imported."""
    print("Testing API imports...")

    try:
        # Test main app
        print("  Importing app...")
        from src.api.app import app, create_app
        print("    ✓ app.py")

        # Test dependencies
        print("  Importing dependencies...")
        from src.api.dependencies import (
            get_db_session,
            get_redis,
            verify_api_key,
            get_pagination,
        )
        print("    ✓ dependencies.py")

        # Test middleware
        print("  Importing middleware...")
        from src.api.middleware import (
            RateLimitMiddleware,
            RequestLoggingMiddleware,
            AuthenticationMiddleware,
            ErrorHandlingMiddleware,
        )
        print("    ✓ middleware.py")

        # Test routes
        print("  Importing routes...")
        from src.api.routes import companies, predictions, reports, alerts
        print("    ✓ companies.py")
        print("    ✓ predictions.py")
        print("    ✓ reports.py")
        print("    ✓ alerts.py")

        print("\n✅ All imports successful!")
        print(f"\nApp title: {app.title}")
        print(f"App version: {app.version}")
        print(f"\nRegistered routes:")
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods) if route.methods else 'N/A'
                print(f"  {methods:10} {route.path}")

        return True

    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
