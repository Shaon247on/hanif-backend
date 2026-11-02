# DRF Generic Views Guide

Django REST Framework provides built-in "Generic Views" for common CRUD operations. In this template, we override their methods to enforce the **standard response envelope**.

## 1. ListAPIView (GET — multiple records)

```python
from rest_framework import generics
from apps.core.responses import success_response

class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page else queryset, many=True)
        return success_response("Products retrieved.", data=serializer.data)
```

## 2. CreateAPIView (POST — create record)

```python
class ProductCreateAPIView(generics.CreateAPIView):
    serializer_class = ProductCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Auto-handled by exception handler
        serializer.save()
        return success_response("Product created.", data=serializer.data, status_code=201)
```

## 3. RetrieveAPIView (GET — single record)

```python
class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response("Product retrieved.", data=serializer.data)
```

## 4. UpdateAPIView (PATCH — update record)

```python
class ProductUpdateAPIView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    http_method_names = ["patch"]  # Only allow PATCH, not PUT

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Product updated.", data=serializer.data)
```

## 5. DestroyAPIView (DELETE)

```python
class ProductDeleteAPIView(generics.DestroyAPIView):
    queryset = Product.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Soft delete (recommended)
        instance.status = 3  # Status.DELETED
        instance.save(update_fields=["status"])
        return success_response("Product deleted.", status_code=204)
```

## 6. Combined Views

### ListCreateAPIView (GET + POST)
```python
class ProductListCreateAPIView(generics.ListCreateAPIView):
    # Combine list() and create() from above
    pass
```

### RetrieveUpdateDestroyAPIView (GET + PATCH + DELETE)
```python
class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    # Combine retrieve(), partial_update(), destroy() from above
    pass
```

## Advanced Patterns

### Dynamic Queryset
```python
def get_queryset(self):
    return Product.objects.filter(user=self.request.user)
```

### Dynamic Serializer
```python
def get_serializer_class(self):
    if self.request.method == "POST":
        return ProductCreateSerializer
    return ProductSerializer
```

### Dynamic Permissions
```python
def get_permissions(self):
    if self.request.method in ("GET", "HEAD", "OPTIONS"):
        return [AllowAny()]
    return [IsAdmin()]
```

### Using QueryParamsMixin
```python
from apps.core.views import QueryParamsMixin

class ProductFilterSerializer(serializers.Serializer):
    category = serializers.CharField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

class FilteredProductListAPIView(QueryParamsMixin, generics.ListAPIView):
    serializer_class = ProductSerializer
    params_serializer = ProductFilterSerializer

    def get_queryset(self):
        query = self.get_query()
        return Product.objects.filter(**query)
```

## Key Rule

> **Never use `try/except` in views for validation errors.** Use `raise_exception=True` on serializer validation. The centralized exception handler in `apps/core/exceptions.py` handles ALL errors automatically.
