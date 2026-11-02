# Testing Guide

## Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest apps/user/tests/test_registration.py -v

# Run with coverage report
pytest --cov=apps --cov-report=html
```

## Test Structure

Each app has a `tests/` directory:
```
apps/user/tests/
├── __init__.py
├── test_registration.py
├── test_login.py
└── test_profile.py
```

## BaseAPITestCase

All API tests should inherit from `BaseAPITestCase`:

```python
from apps.core.test_utils import BaseAPITestCase

class MyTests(BaseAPITestCase):
    pass
```

### Available Helpers

| Method | Description |
|--------|-------------|
| `create_user(email, password, **kwargs)` | Create a test user |
| `authenticate(user=None, email=None)` | Set JWT auth on test client |
| `assert_success(response, status_code=200)` | Assert success envelope |
| `assert_error(response, status_code=400)` | Assert error envelope |

## Example Test

```python
from rest_framework import status
from apps.core.test_utils import BaseAPITestCase

class ProductTests(BaseAPITestCase):
    url = "/api/v1/products/"

    def setUp(self):
        super().setUp()
        self.admin = self.create_user(
            email="admin@example.com",
            role="ADMIN",
            is_staff=True,
        )

    def test_list_products_public(self):
        """Anyone can list products."""
        response = self.client.get(self.url)
        self.assert_success(response)

    def test_create_product_as_admin(self):
        """Admins can create products."""
        self.authenticate(user=self.admin)
        response = self.client.post(self.url, {
            "name": "Widget",
            "price": "19.99",
        })
        self.assert_success(response, status.HTTP_201_CREATED)

    def test_create_product_unauthorized(self):
        """Regular users cannot create products."""
        self.authenticate()
        response = self.client.post(self.url, {
            "name": "Widget",
            "price": "19.99",
        })
        self.assert_error(response, status.HTTP_403_FORBIDDEN)
```

## Testing Celery Tasks

Use `CELERY_TASK_ALWAYS_EAGER=True` to run tasks synchronously in tests:

```python
from django.test import override_settings

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class EmailTests(BaseAPITestCase):
    def test_registration_sends_email(self):
        # Email task runs synchronously
        response = self.client.post("/api/v1/auth/register/", {...})
        self.assert_success(response, 201)
```

## Rules

1. Every app must have tests
2. Test file names start with `test_`
3. Test class names end with `Tests`
4. Test method names start with `test_` and describe the behavior
5. Use `assert_success`/`assert_error` for response assertions
6. Test both success and error paths
