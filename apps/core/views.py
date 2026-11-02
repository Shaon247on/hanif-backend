"""
Base view mixins.

Provides:
    - QueryParamsMixin — validate and extract query parameters via a serializer
"""

from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request


class QueryParamsMixin(GenericAPIView):
    """
    Mixin to validate GET query parameters using a serializer.

    Usage:
        class MyFilterSerializer(serializers.Serializer):
            category = serializers.CharField(required=False)
            min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

        class MyListView(QueryParamsMixin, generics.ListAPIView):
            params_serializer = MyFilterSerializer

            def get_queryset(self):
                query = self.get_query()
                return MyModel.objects.filter(**query)
    """

    params_serializer: type[serializers.Serializer] = None
    _params_validated_data: dict | None = None

    def get_params(self, partial: bool = True) -> dict:
        """Validate and return query parameters."""
        if self._params_validated_data is None:
            assert self.params_serializer is not None, f"{self.__class__.__name__} must set 'params_serializer'."
            request: Request = self.request
            serializer = self.params_serializer(
                data=request.query_params,
                partial=partial,
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            self._params_validated_data = serializer.validated_data
        return self._params_validated_data

    def get_query(self, partial: bool = True) -> dict:
        """
        Return validated query params, filtering out None and empty strings.

        Useful for passing directly to .filter(**query).
        """
        params = self.get_params(partial=partial)
        return {key: value for key, value in params.items() if value is not None and value != ""}
