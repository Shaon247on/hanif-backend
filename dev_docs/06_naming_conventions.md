# Naming Conventions

Consistent naming makes the project easy to read, maintain, and scale. All developers **must** follow these conventions.

## 1. Files and Folders

- **Format**: `snake_case`
- **App names**: Singular (`user`, `contact`, `product` — NOT `users`, `products`)
- **Examples**: `views.py`, `api_view.py`, `email_utils.py`

## 2. Classes

- **Format**: `PascalCase`
- **Models**: Singular noun → `User`, `Product`, `ContactMessage`
- **Serializers**: Model name + `Serializer` → `UserProfileSerializer`, `ProductCreateSerializer`
- **Views**: Descriptive + `APIView` → `ProductListCreateAPIView`, `ProfileUpdateAPIView`
- **Services**: Functions, not classes (see below)

## 3. Functions and Methods

- **Format**: `snake_case`
- **Rule**: Should sound like an action/verb
- **Examples**: `get_queryset()`, `register_user()`, `send_verification_email()`

## 4. Variables

- **Format**: `snake_case`
- **Rule**: Descriptive names. No single letters except loop iterators.
- **Booleans**: Prefix with `is_`, `has_`, `can_` → `is_verified`, `has_permission`
- **Examples**: `user_profile`, `product_list`, `is_active`

## 5. Constants and Enums

- **Constants**: `UPPER_SNAKE_CASE` → `MAX_LOGIN_ATTEMPTS`, `DEFAULT_PAGE_SIZE`
- **Enums**: `PascalCase` class name, `UPPER_SNAKE_CASE` values:
  ```python
  class UserRole(models.TextChoices):
      SUPER_ADMIN = "SUPER_ADMIN"
      ADMIN = "ADMIN"
      USER = "USER"
  ```

## 6. URLs and Endpoints

- **Format**: `kebab-case`, always with trailing slash `/`
- **Resources**: Pluralized nouns
- **Good**: `api/v1/products/`, `api/v1/auth/verify-email/`
- **Bad**: `api/v1/UserProfile`, `api/v1/products_list`

## 7. Model Fields

- **Format**: `snake_case`
- **No table-name prefix**: Use `title`, not `product_title`
- **Foreign keys**: Related model name → `user = models.ForeignKey(...)`
- **Booleans**: `is_active`, `is_verified`, `has_shipped`

## 8. Service Functions

- **Format**: `snake_case` verbs
- **Examples**: `register_user()`, `create_product()`, `notify_admin_of_contact()`
- **Private helpers**: Prefix with `_` → `_build_verification_link()`

## 9. Test Files and Methods

- **Files**: `test_<feature>.py` → `test_registration.py`, `test_product.py`
- **Classes**: `<Feature>Tests` → `RegistrationTests`, `ProductTests`
- **Methods**: `test_<description>` → `test_register_success`, `test_create_requires_admin`
