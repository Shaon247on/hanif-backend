# Creating a New App

This guide walks through creating a new `product` app as an example.

## Step 1: Create the App Directory

```bash
mkdir -p apps/product/tests
```

Create these files:
- `apps/product/__init__.py`
- `apps/product/apps.py`
- `apps/product/models.py`
- `apps/product/serializers.py`
- `apps/product/services.py`
- `apps/product/views.py`
- `apps/product/admin.py`
- `apps/product/urls.py`
- `apps/product/tests/__init__.py`
- `apps/product/tests/test_product.py`

## Step 2: App Config (`apps.py`)

```python
from django.apps import AppConfig

class ProductConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.product"
    label = "product"
    verbose_name = "Products"
```

## Step 3: Register in Settings

Add to `INSTALLED_APPS` in `config/settings/base.py`:
```python
LOCAL_APPS = [
    "apps.core",
    "apps.common",
    "apps.user",
    "apps.contact",
    "apps.product",  # ← Add here
]
```

## Step 4: Create the Model

```python
# apps/product/models.py
from django.db import models
from apps.common.models import BaseModel

class Product(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
```

Run migrations:
```bash
make migrate
```

## Step 5: Create Serializers

```python
# apps/product/serializers.py
from rest_framework import serializers
from apps.product.models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "status", "created_at")
        read_only_fields = ("id", "created_at")

class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("name", "description", "price")
```

## Step 6: Create Services (Business Logic)

```python
# apps/product/services.py
from apps.product.models import Product

def create_product(validated_data: dict) -> Product:
    return Product.objects.create(**validated_data)

def get_active_products():
    return Product.objects.filter(status=1)
```

## Step 7: Create Views

```python
# apps/product/views.py
from rest_framework import generics, status
from apps.core.permissions import IsAdminOrReadOnly
from apps.core.responses import success_response
from apps.product.models import Product
from apps.product.serializers import ProductSerializer, ProductCreateSerializer
from apps.product import services as product_services

class ProductListCreateAPIView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductCreateSerializer
        return ProductSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page else queryset, many=True)
        return success_response("Products retrieved.", data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_services.create_product(serializer.validated_data)
        return success_response(
            "Product created.", data=serializer.data, status_code=status.HTTP_201_CREATED,
        )
```

## Step 8: Wire URLs

```python
# apps/product/urls.py
from django.urls import path
from apps.product import views

urlpatterns = [
    path("products/", views.ProductListCreateAPIView.as_view(), name="product-list"),
]
```

Include in `config/urls.py`:
```python
urlpatterns = [
    # ... existing routes
    path("api/v1/", include("apps.product.urls")),
]
```

## Step 9: Admin

```python
# apps/product/admin.py
from django.contrib import admin
from apps.product.models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)
```

## Step 10: Write Tests

```python
# apps/product/tests/test_product.py
from rest_framework import status
from apps.core.test_utils import BaseAPITestCase

class ProductTests(BaseAPITestCase):
    url = "/api/v1/products/"

    def test_list_products(self):
        response = self.client.get(self.url)
        self.assert_success(response)

    def test_create_product_requires_admin(self):
        self.authenticate()  # Regular user
        response = self.client.post(self.url, {"name": "Test", "price": "9.99"})
        self.assert_error(response, status.HTTP_403_FORBIDDEN)
```

Run tests:
```bash
make test
```

## Checklist

- [ ] `apps.py` with correct `name` and `label`
- [ ] Added to `INSTALLED_APPS` in `config/settings/base.py`
- [ ] Model inherits from `BaseModel`
- [ ] Business logic in `services.py`
- [ ] Serializers only validate data
- [ ] Views are thin (< 15 lines per method)
- [ ] URLs registered in `config/urls.py`
- [ ] Admin registered
- [ ] Tests written
- [ ] Migrations created and applied
