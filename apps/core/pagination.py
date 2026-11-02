"""
Standard pagination classes.

Set as default in REST_FRAMEWORK settings:
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination"
"""

from rest_framework.pagination import PageNumberPagination

from apps.core.responses import success_response


class StandardPagination(PageNumberPagination):
    """Default pagination: 20 items per page, max 100."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return success_response(
            details="Retrieved successfully.",
            code="PAGINATED_SUCCESS",
            data={
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            },
        )


class LargePagination(StandardPagination):
    """For endpoints that need more items per page (e.g., dropdowns)."""

    page_size = 100
    max_page_size = 500


class NoPagination(PageNumberPagination):
    """Explicitly disable pagination for specific views."""

    page_size = None
