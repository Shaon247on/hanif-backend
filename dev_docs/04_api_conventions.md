# API Conventions

## Response Format

Every API response follows this standard envelope:

### Success Response
```json
{
    "success": true,
    "details": "Products retrieved successfully.",
    "code": "SUCCESS",
    "status_code": 200,
    "data": [...]
}
```

### Error Response
```json
{
    "success": false,
    "details": "Invalid email or password.",
    "code": "VALIDATION_ERROR",
    "status_code": 400
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | `true` for 2xx, `false` for 4xx/5xx |
| `details` | string | Human-readable message |
| `code` | string | Machine-readable error code |
| `status_code` | integer | HTTP status code |
| `data` | object/array | Response payload (only on success) |

## Standard Error Codes

| Code | HTTP Status | When |
|------|-------------|------|
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `NOT_AUTHENTICATED` | 401 | Missing or invalid token |
| `AUTHENTICATION_FAILED` | 401 | Wrong credentials |
| `PERMISSION_DENIED` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `THROTTLED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Using Response Helpers

```python
from apps.core.responses import success_response, error_response

# Success
return success_response("Created.", data=serializer.data, status_code=201)

# Error (rare — centralized handler catches most errors automatically)
return error_response("Custom error.", code="CUSTOM_ERROR", status_code=400)
```

## Pagination

All list endpoints are paginated by default (20 items per page).

### Query Parameters
- `page` — Page number (default: 1)
- `page_size` — Items per page (default: 20, max: 100)

### Disable Pagination for a View
```python
from apps.core.pagination import NoPagination

class MyView(generics.ListAPIView):
    pagination_class = NoPagination
```

## API Versioning

All endpoints are prefixed with `/api/v1/`. When breaking changes are needed, create `/api/v2/` routes.

## Rate Limiting

| Scope | Limit | Applied To |
|-------|-------|------------|
| Anonymous burst | 30/minute | All anonymous requests |
| Anonymous sustained | 500/day | All anonymous requests |
| Authenticated burst | 60/minute | All authenticated requests |
| Auth login | 5/minute | Login/register endpoints |
