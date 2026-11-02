# BarberBay — Booking, Dashboard & Checkout API Documentation

This document provides complete, sequential API specifications mapped to the mobile application workflow (Calendar Timeline, Dashboard List, 3-Step New Booking, Category/Service Creation, Order Checkout, Tip/Discount, Payment Methods, and Checkout Completion).

---

## 🌐 General Configuration

- **Base URL:** `http://<your-domain>/api/v1/`
- **Default Content-Type:** `application/json`
- **Authentication:** `Bearer <JWT_ACCESS_TOKEN>` in headers:
  ```http
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```
- **Standard Response Structure:**
  ```json
  {
    "status": true,
    "code": "RESPONSE_CODE",
    "details": "Human readable message",
    "data": {}
  }
  ```

---

## 📑 Table of Contents (Sequential Flow)

0. [Auth & Login: Role-Based Shop List](#0-auth--login-role-based-shop-list)
1. [Screen 1: Calendar View (Barber Schedule Timeline)](#1-screen-1-calendar-view-barber-schedule-timeline)
2. [Screen 2: Dashboard Overview & Today Appointments List](#2-screen-2-dashboard-overview--today-appointments-list)
3. [Screen 3 & 4: New Booking — Step 1 (Select or Create Customer)](#3-screen-3--4-new-booking--step-1-select-or-create-customer)
4. [Screen 5 & Component 70: New Booking — Step 2 (Barber, Service & Slot Selection)](#4-screen-5--component-70-new-booking--step-2-barber-service--slot-selection)
5. [Screen 6: New Booking — Step 3 (Review & Confirm Booking)](#5-screen-6-new-booking--step-3-review--confirm-booking)
6. [Screen 7, 8 & 9: Checkout Screen (Order Breakdown, Notes, Tip & Update)](#6-screen-7-8--9-checkout-screen-order-breakdown-notes-tip--update)
7. [Screen 10 & 11: Payment Processing (Cash, Card, Mobile Banking, RevenueCat)](#7-screen-10--11-payment-processing-cash-card-mobile-banking-revenuecat)
8. [Screen 12: Checkout Complete & Post-Actions (Google Calendar Sync, Reviews)](#8-screen-12-checkout-complete--post-actions-google-calendar-sync-reviews)

---

## 0. Auth & Login: Role-Based Shop List

When a user logs in via `POST /api/v1/auth/login/`:
- **Regular Customers (`USER`)**: `shops` array is empty `[]`.
- **Admins (`ADMIN` / `SUPER_ADMIN`)**: Returns all shops in the system in the `shops` list.
- **Barbers / Staff (`barber` / `staff` / `manager`)**: Returns assigned and owned shop(s).

### `POST /auth/login/`
- **Content-Type:** `application/json`

#### Request Payload:
```json
{
  "email": "owner@barberbay.com",
  "password": "Password123!"
}
```

#### Response Example (Admin / Staff):
```json
{
  "status": true,
  "code": "LOGIN_SUCCESS",
  "details": "Login successful.",
  "data": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "user": {
      "id": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
      "email": "owner@barberbay.com",
      "username": "owner",
      "role": "ADMIN",
      "full_name": "Shop Owner",
      "image": null,
      "phone": "+1234567890",
      "address": "",
      "last_active_at": "2026-08-26T08:00:00Z",
      "date_joined": "2026-08-01T00:00:00Z",
      "shops": [
        {
          "id": 1,
          "name": "Downtown Barber Studio",
          "slug": "downtown-barber-studio",
          "logo": "http://api.barberbay.com/media/shop_logos/logo1.jpg",
          "cover_image": null,
          "location": "123 Main Street",
          "phone": "+1234567890",
          "email": "shop1@barberbay.com",
          "payment_gateway_enabled": true,
          "created_at": "2026-08-15T10:00:00Z"
        }
      ]
    },
    "shops": [
      {
        "id": 1,
        "name": "Downtown Barber Studio",
        "slug": "downtown-barber-studio",
        "logo": "http://api.barberbay.com/media/shop_logos/logo1.jpg",
        "cover_image": null,
        "location": "123 Main Street",
        "phone": "+1234567890",
        "email": "shop1@barberbay.com",
        "payment_gateway_enabled": true,
        "created_at": "2026-08-15T10:00:00Z"
      }
    ]
  }
}
```

---

## 1. Screen 1: Calendar View (Barber Schedule Timeline)

Retrieves all appointments for a given date grouped by barber/staff columns.

### `GET /booking/`
- **Headers:** `Authorization: Bearer <token>`
- **Query Parameters:**
  | Parameter | Type | Required | Description | Example |
  |---|---|---|---|---|
  | `view_type` | string | Yes | Set to `admin` or `staff` | `admin` |
  | `display_mode` | string | Yes | Set to `calendar` | `calendar` |
  | `shop_id` | integer | Yes | ID of the shop | `1` |
  | `date` | string (YYYY-MM-DD) | No | Target calendar date (defaults to today) | `2026-07-15` |

#### Request Example:
```http
GET /api/v1/booking/?view_type=admin&display_mode=calendar&shop_id=1&date=2026-07-15 HTTP/1.1
Host: api.barberbay.com
Authorization: Bearer <token>
```

#### Response Example:
```json
{
  "status": true,
  "code": "CALENDAR_VIEW",
  "details": "Calendar view data retrieved.",
  "data": [
    {
      "barber": {
        "id": 1,
        "name": "Mike Johnson",
        "avatar": "http://api.barberbay.com/media/barber_avatars/mike.jpg"
      },
      "appointments": [
        {
          "booking_id": 12,
          "appointment_id": 24,
          "customer_name": "John Doe",
          "service_name": "Haircut + Beard Trim",
          "start_time": "09:30",
          "end_time": "10:45",
          "status": "scheduled"
        }
      ]
    },
    {
      "barber": {
        "id": 2,
        "name": "Alex Turner",
        "avatar": "http://api.barberbay.com/media/barber_avatars/alex.jpg"
      },
      "appointments": [
        {
          "booking_id": 14,
          "appointment_id": 28,
          "customer_name": "David Smith",
          "service_name": "Shave & Facial",
          "start_time": "11:00",
          "end_time": "11:45",
          "status": "in_progress"
        }
      ]
    }
  ]
}
```

---

## 2. Screen 2: Dashboard Overview & Today Appointments List

Retrieves metrics summary (total sales value, appointment count, new client count) along with today's appointments list.

### `GET /booking/`
- **Headers:** `Authorization: Bearer <token>`
- **Query Parameters:**
  | Parameter | Type | Required | Description | Example |
  |---|---|---|---|---|
  | `view_type` | string | Yes | Set to `admin` or `staff` | `admin` |
  | `display_mode` | string | Yes | Set to `list` | `list` |
  | `shop_id` | integer | Yes | Shop ID | `1` |
  | `date` | string (YYYY-MM-DD) | No | Filter date | `2026-07-15` |

#### Request Example:
```http
GET /api/v1/booking/?view_type=admin&display_mode=list&shop_id=1&date=2026-07-15 HTTP/1.1
Authorization: Bearer <token>
```

#### Response Example:
```json
{
  "status": true,
  "code": "LIST_VIEW",
  "details": "List view data retrieved.",
  "data": {
    "2026-07-11": {
      "total_value": 0.0,
      "new_client": 0,
      "new_clients": 0,
      "appointment": [],
      "appointments": []
    },
    "2026-07-15": {
      "total_value": 35.0,
      "new_client": 1,
      "new_clients": 1,
      "appointment": [
        {
          "id": 12,
          "booking_code": "BB-2026-X99",
          "customer": "b98fa320-192a-4df0-9428-f6a9cba21200",
          "shop": 1,
          "shop_details": {
            "name": "Barberbay Studio",
            "location": "123 Main Street, Suite 4B",
            "phone": "+1-800-555-0199"
          },
          "total_amount": "35.00",
          "tip_amount": "0.00",
          "discount_amount": "0.00",
          "payment_method": "cash",
          "payment_status": "pending",
          "status": "pending",
          "created_at": "2026-07-15T08:00:00Z",
          "updated_at": "2026-07-15T08:00:00Z",
          "appointments_details": [
            {
              "id": 24,
              "service_id": 3,
              "service_name": "Haircut + Beard Trim",
              "barber_id": 1,
              "appointment_date": "2026-07-15",
              "start_time": "09:30:00",
              "end_time": "10:45:00"
            }
          ]
        }
      ],
      "appointments": [
        {
          "id": 12,
          "booking_code": "BB-2026-X99",
          "customer": "b98fa320-192a-4df0-9428-f6a9cba21200",
          "shop": 1,
          "shop_details": {
            "name": "Barberbay Studio",
            "location": "123 Main Street, Suite 4B",
            "phone": "+1-800-555-0199"
          },
          "total_amount": "35.00",
          "tip_amount": "0.00",
          "discount_amount": "0.00",
          "payment_method": "cash",
          "payment_status": "pending",
          "status": "pending",
          "created_at": "2026-07-15T08:00:00Z",
          "updated_at": "2026-07-15T08:00:00Z",
          "appointments_details": [
            {
              "id": 24,
              "service_id": 3,
              "service_name": "Haircut + Beard Trim",
              "barber_id": 1,
              "appointment_date": "2026-07-15",
              "start_time": "09:30:00",
              "end_time": "10:45:00"
            }
          ]
        }
      ]
    }
  }
}
```

---

## 3. Screen 3 & 4: New Booking — Step 1 (Select or Create Customer)

### 3.1 Get Existing Customers (Screen 3: Existing Customer Tab)
- **Endpoint:** `GET /dashboard/shops/<shop_id>/clients/` (or `GET /dashboard/clients/`)
- **Headers:** `Authorization: Bearer <token>`

#### Response Example:
```json
{
  "status": true,
  "code": "CLIENTS_RETRIEVED",
  "details": "Clients retrieved",
  "data": {
    "new_clients": [
      {
        "id": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
        "email": "andria@example.com",
        "full_name": "Andria Doe",
        "phone": "+1234567890",
        "avatar": "http://api.barberbay.com/media/profile/andria.jpg"
      }
    ],
    "all_clients": [
      {
        "id": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
        "email": "andria@example.com",
        "full_name": "Andria Doe",
        "phone": "+1234567890",
        "avatar": "http://api.barberbay.com/media/profile/andria.jpg"
      },
      {
        "id": "d2a8b12e-6df6-4df6-c214-7e92eadf2202",
        "email": "john@example.com",
        "full_name": "John Doe",
        "phone": "+1987654321",
        "avatar": null
      }
    ]
  }
}
```

### 3.2 Create New Customer (Screen 4: New Customer Tab)
- **Endpoint:** `POST /dashboard/shops/<shop_id>/clients/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json` or `multipart/form-data`

#### Payload:
```json
{
  "name": "Andria Doe",
  "email": "andria.doe@example.com",
  "phone": "+1234567890"
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "CLIENT_CREATED",
  "details": "Client created successfully",
  "data": {
    "id": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
    "email": "andria.doe@example.com",
    "full_name": "Andria Doe",
    "phone": "+1234567890",
    "avatar": null
  }
}
```

---

## 4. Screen 5 & Component 70: New Booking — Step 2 (Barber, Service & Slot Selection)

### 4.1 Get Staff/Barbers for the Shop
- **Endpoint:** `GET /barbers/?shop=<shop_id>`
- **Headers:** Public or `Authorization: Bearer <token>`

#### Response Example:
```json
{
  "status": true,
  "code": "BARBER_LIST_RETRIEVED",
  "details": "Barber list retrieved successfully.",
  "data": [
    {
      "id": 1,
      "user": {
        "id": "uuid-1",
        "username": "mike_johnson",
        "full_name": "Mike Johnson",
        "image": "http://api.barberbay.com/media/barbers/mike.jpg"
      },
      "shop": 1,
      "specialty": "Master Stylist",
      "experience_years": 8
    }
  ]
}
```

### 4.2 Get Services List
- **Endpoint:** `GET /services/?shop=<shop_id>&barber=<barber_id>`
- **Headers:** Public or `Authorization: Bearer <token>`

#### Response Example:
```json
{
  "status": true,
  "code": "SERVICES_RETRIEVED",
  "details": "Services retrieved successfully.",
  "data": [
    {
      "id": 1,
      "category": {
        "id": 1,
        "name": "Haircuts"
      },
      "name": "Dry Haircut",
      "price": "35.00",
      "duration_minutes": 30,
      "is_active": true
    },
    {
      "id": 2,
      "category": {
        "id": 2,
        "name": "Shaving & Beard"
      },
      "name": "Beard Trim",
      "price": "15.00",
      "duration_minutes": 15,
      "is_active": true
    }
  ]
}
```

### 4.3 Add Service Category / Service (Component 70: Add Category)
- **Endpoint:** `POST /services/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload:
```json
{
  "category": 1,
  "shop": 1,
  "name": "Hair Treatment & Spa",
  "price": "50.00",
  "duration_minutes": 45,
  "description": "Deep conditioning hair treatment"
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "SERVICE_CREATED",
  "details": "Service created successfully.",
  "data": {
    "id": 5,
    "name": "Hair Treatment & Spa",
    "price": "50.00",
    "duration_minutes": 45
  }
}
```

### 4.4 Calculate & Fetch Available Time Slots
Calculates valid available appointment start times based on barber shifts, breaks, time-offs, and existing bookings.

- **Endpoint:** `GET /bookings/available-slots/`
- **Query Parameters:**
  | Parameter | Type | Required | Description | Example |
  |---|---|---|---|---|
  | `barber_id` | integer or UUID | Yes | Barber ID or Barber's User ID | `1` |
  | `date` | string (YYYY-MM-DD) | Yes | Appointment date | `2026-07-15` |
  | `services` | string | Yes | Comma-separated Service IDs | `1,2` |

#### Request Example:
```http
GET /api/v1/bookings/available-slots/?barber_id=1&date=2026-07-15&services=1,2 HTTP/1.1
```

#### Response Example:
```json
{
  "status": true,
  "code": "AVAILABLE_SLOTS",
  "details": "Available slots retrieved.",
  "data": [
    "09:00:00",
    "09:30:00",
    "10:15:00",
    "11:00:00",
    "14:00:00",
    "15:30:00",
    "16:15:00"
  ]
}
```

---

## 5. Screen 6: New Booking — Step 3 (Review & Confirm Booking)

Creates the booking transaction and schedules each service appointment sequentially.

### `POST /bookings/create/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload:
```json
{
  "shop": 1,
  "barber": 1,
  "services": [1, 2],
  "appointment_date": "2026-07-15",
  "start_time": "09:30:00",
  "payment_method": "cash",
  "tip_amount": "0.00"
}
```

#### Field Specifications:
| Field | Type | Required | Description |
|---|---|---|---|
| `shop` | integer | Yes | Shop ID |
| `barber` | integer | Yes | Barber ID |
| `services` | array of int | Yes | List of service IDs selected |
| `appointment_date` | string (YYYY-MM-DD) | Yes | Appointment date |
| `start_time` | string (HH:MM:SS) | Yes | Slot start time |
| `payment_method` | string | Yes | `card`, `cash`, or `mobile_banking` |
| `tip_amount` | decimal string | No | Optional tip amount (defaults to 0.00) |

#### Response Example:
```json
{
  "status": true,
  "code": "BOOKING_CREATED",
  "details": "Booking created successfully.",
  "data": {
    "id": 15,
    "booking_code": "BB-2026-7A4B9F",
    "customer": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
    "shop": 1,
    "shop_details": {
      "name": "Barberbay Studio",
      "location": "123 Main Street, Suite 4B",
      "phone": "+1-800-555-0199"
    },
    "total_amount": "50.00",
    "tip_amount": "0.00",
    "payment_method": "cash",
    "payment_status": "pending",
    "status": "pending",
    "created_at": "2026-07-15T09:00:00Z",
    "updated_at": "2026-07-15T09:00:00Z",
    "appointments_details": [
      {
        "id": 31,
        "service_id": 1,
        "service_name": "Dry Haircut",
        "barber_id": 1,
        "appointment_date": "2026-07-15",
        "start_time": "09:30:00",
        "end_time": "10:00:00"
      },
      {
        "id": 32,
        "service_id": 2,
        "service_name": "Beard Trim",
        "barber_id": 1,
        "appointment_date": "2026-07-15",
        "start_time": "10:00:00",
        "end_time": "10:15:00"
      }
    ]
  }
}
```

---

## 6. Screen 7, 8 & 9: Checkout Screen (Order Breakdown, Notes, Tip & Update)

### 6.1 Update Booking (Add Tip / Change Staff / Update Service Selection)
- **Endpoint:** `PATCH /bookings/<booking_id>/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload (Add Tip):
```json
{
  "tip_amount": "5.00"
}
```

#### Payload (Change Staff or Services while pending):
```json
{
  "barber": 2,
  "services": [1, 2, 5],
  "appointment_date": "2026-07-15",
  "start_time": "10:00:00",
  "tip_amount": "5.00"
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "BOOKING_UPDATED",
  "details": "Booking updated successfully.",
  "data": {
    "id": 15,
    "booking_code": "BB-2026-7A4B9F",
    "customer": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
    "shop": 1,
    "total_amount": "55.00",
    "tip_amount": "5.00",
    "payment_method": "cash",
    "payment_status": "pending",
    "status": "pending",
    "appointments_details": [
      {
        "id": 31,
        "service_id": 1,
        "service_name": "Dry Haircut",
        "barber_id": 1,
        "appointment_date": "2026-07-15",
        "start_time": "09:30:00",
        "end_time": "10:00:00"
      },
      {
        "id": 32,
        "service_id": 2,
        "service_name": "Beard Trim",
        "barber_id": 1,
        "appointment_date": "2026-07-15",
        "start_time": "10:00:00",
        "end_time": "10:15:00"
      }
    ]
  }
}
```

### 6.2 Cancel Booking (Screen 7: Cancel Button)
- **Endpoint:** `POST /bookings/<booking_id>/cancel/`
- **Headers:** `Authorization: Bearer <token>`

#### Response Example:
```json
{
  "status": true,
  "code": "BOOKING_CANCELLED",
  "details": "Booking cancelled successfully.",
  "data": {
    "id": 15,
    "booking_code": "BB-2026-7A4B9F",
    "status": "cancelled",
    "payment_status": "pending"
  }
}
```

---

## 7. Screen 10 & 11: Payment Processing (Cash, Card, Mobile Banking, RevenueCat)

### 7.1 Manual / Counter Payment Logging (Cash, Card terminal, Mobile Pay)
Used when a customer pays at the counter via Cash, POS Card, or manual Mobile Banking.

- **Endpoint:** `POST /payments/manual/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload:
```json
{
  "booking_id": 15,
  "amount": "55.00",
  "method": "cash"
}
```
*(Valid `method` options: `"cash"`, `"card"`, `"mobile_banking"`)*

#### Response Example:
```json
{
  "status": true,
  "code": "MANUAL_PAYMENT_LOGGED",
  "details": "Manual payment logged.",
  "data": {
    "id": 8,
    "booking": 15,
    "amount": "55.00",
    "method": "cash",
    "transaction_id": null,
    "status": "completed",
    "created_at": "2026-07-15T10:15:00Z"
  }
}
```

### 7.2 In-App Purchases / Subscriptions Webhook (RevenueCat)
Used for Apple Pay / Google Pay transactions routed through RevenueCat.

- **Endpoint:** `POST /payments/webhook/revenuecat/`
- **Headers:** `Content-Type: application/json` (Public webhook)

#### Payload:
```json
{
  "event": {
    "app_user_id": "BB-2026-7A4B9F",
    "transaction_id": "rc_txn_987654321",
    "price": 55.00,
    "store": "app_store"
  }
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "WEBHOOK_RECEIVED",
  "details": "Webhook received.",
  "data": {}
}
```

---

## 8. Screen 12: Checkout Complete & Post-Actions (Google Calendar Sync, Reviews)

### 8.1 Sync to Google Calendar
Synchronizes the confirmed booking directly to the user's primary Google Calendar.

- **Endpoint:** `POST /bookings/<booking_id>/calendar/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload:
```json
{
  "access_token": "ya29.a0AfH6SM..."
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "EVENT_CREATED",
  "details": "Event created in Google Calendar.",
  "data": {
    "id": "google_event_id_12345",
    "status": "confirmed",
    "htmlLink": "https://www.google.com/calendar/event?eid=..."
  }
}
```

### 8.2 Customer Review & Rating
- **Endpoint:** `POST /bookings/reviews/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload:
```json
{
  "booking": 15,
  "rating": 5,
  "comment": "Best haircut experience! Mike was very attentive and skilled."
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "SHOP_REVIEW_CREATED",
  "details": "Shop review created successfully.",
  "data": {
    "id": 6,
    "shop": 1,
    "shop_name": "Barberbay Studio",
    "customer": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
    "customer_name": "Andria Doe",
    "booking": 15,
    "rating": 5,
    "comment": "Best haircut experience! Mike was very attentive and skilled.",
    "created_at": "2026-07-15T11:00:00Z"
  }
}
```

---

## 9. Shop Business Off & Barber Shifts Management

### 9.1 Shop Business Off (Holidays / Closed Period)
Sets days or time ranges where the whole shop/business is closed (e.g. Eid Holiday, Renovation, Christmas). When active on a date, customer availability check automatically returns `code: "SHOP_CLOSED"`.

#### List Business Off Records:
- **Endpoint:** `GET /schedule/business/off/?shop=<shop_id>`
- **Headers:** `Authorization: Bearer <token>`

#### Create Business Off Record:
- **Endpoint:** `POST /schedule/business/off/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

```json
{
  "shop": 1,
  "start_date": "2026-09-01",
  "end_date": "2026-09-05",
  "is_full_day": true,
  "reason": "Shop Renovation & Eid Holiday"
}
```

#### Update Business Off Record:
- **Endpoint:** `PUT /schedule/business/off/<id>/` (or `PATCH`)

#### Delete Business Off Record:
- **Endpoint:** `DELETE /schedule/business/off/<id>/`

---

### 9.2 Barber Shifts (Working Schedule)
Sets working hours / shifts for staff. Supports both single shift and bulk list.

#### List Shifts:
- **Endpoint:** `GET /schedule/shifts/?shop=<shop_id>&barber=<barber_id>`
- **Headers:** `Authorization: Bearer <token>`

#### Create Single Shift:
- **Endpoint:** `POST /schedule/shifts/`
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

```json
{
  "barber": 1,
  "day_of_week": "monday",
  "start_time": "09:00:00",
  "end_time": "18:00:00",
  "is_active": true
}
```

#### Create Bulk Shifts:
- **Endpoint:** `POST /schedule/shifts/`
```json
[
  {
    "barber": 1,
    "day_of_week": "monday",
    "start_time": "09:00:00",
    "end_time": "18:00:00"
  },
  {
    "barber": 1,
    "day_of_week": "tuesday",
    "start_time": "09:00:00",
    "end_time": "18:00:00"
  }
]
```

---

### 9.3 Barber Schedule & Date-Specific Shift Override
Overrides a staff/barber's working shift, breaks, or marks them as OFF on any specific date.

- **Endpoint:** `PUT /schedule/barber-schedule/` (or `PUT /schedule/barber/schedule/` or `PUT /schedule/shifts/override/`)
- **Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

#### Payload (Override Shift Hours on Specific Date):
```json
{
  "barber": 1,
  "date": "2026-09-07",
  "shift": {
    "start_time": "13:00:00",
    "end_time": "18:00:00",
    "is_off": false
  },
  "breaks": [
    {
      "start_time": "15:00:00",
      "end_time": "15:30:00",
      "title": "Afternoon Tea"
    }
  ]
}
```

#### Payload (Mark Barber as OFF on Specific Date):
```json
{
  "barber": 1,
  "date": "2026-09-07",
  "shift": {
    "is_off": true
  }
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "BARBER_SCHEDULE_UPDATED",
  "details": "Barber schedule and shift override updated.",
  "data": {
    "barber": 1,
    "barber_name": "Alex Hunter",
    "date": "2026-09-07",
    "shift_override": {
      "id": 1,
      "barber": 1,
      "barber_name": "Alex Hunter",
      "date": "2026-09-07",
      "start_time": "13:00:00",
      "end_time": "18:00:00",
      "is_off": false,
      "is_active": true,
      "reason": "",
      "created_at": "2026-08-29T12:40:00Z",
      "updated_at": "2026-08-29T12:40:00Z"
    }
  }
}
```

---

## 10. Contact & Customer List API

### 10.1 List All Contacts (Customers with `role="USER"`)
Admin endpoint to list all customer contacts registered across the platform.

- **Endpoint:** `GET /contact/list/` (or `GET /contact/`)
- **Headers:** `Authorization: Bearer <admin_token>`
- **Query Params:** `?search=<keyword>` (optional search by name, email, phone)

#### Response Example:
```json
{
  "status": true,
  "code": "CONTACTS_RETRIEVED",
  "details": "Contacts retrieved.",
  "data": [
    {
      "id": "c1f7a01d-5cf5-4cf5-b103-6f81dfce1101",
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "image": null,
      "address": "123 Main Street",
      "role": "USER",
      "status": 1,
      "last_active_at": "2026-08-29T10:00:00Z",
      "date_joined": "2026-08-29T09:30:00Z"
    }
  ]
}
```

### 10.2 Create Contact / Customer (or Submit Contact Form)
Creates a new customer User (with `role="USER"`), and optionally records a contact message for admin notification.

- **Endpoint:** `POST /contact/` (or `POST /contact/list/`)
- **Headers:** `Content-Type: application/json` (Public or Authenticated)

#### Payload:
```json
{
  "full_name": "Jane Smith",
  "email": "jane@example.com",
  "phone": "+1987654321",
  "message": "I would like to book a group appointment."
}
```

#### Response Example:
```json
{
  "status": true,
  "code": "CONTACT_CREATED",
  "details": "Contact created successfully.",
  "data": {
    "id": "a9b8c7d6-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
    "full_name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "+1987654321",
    "image": null,
    "address": "",
    "role": "USER",
    "status": 1,
    "last_active_at": "2026-08-29T11:40:00Z",
    "date_joined": "2026-08-29T11:40:00Z"
  }
}
```

---

## ⚡ Error Codes & Handling Guide

| Status Code | Error Code | Description |
|---|---|---|
| `400 Bad Request` | `MISSING_SHOP_ID` | `shop_id` query parameter is required. |
| `400 Bad Request` | `MISSING_PARAMS` | Required parameters for slot calculation are missing. |
| `400 Bad Request` | `INVALID_SERVICES` | The selected service IDs are invalid or inactive. |
| `400 Bad Request` | `EMAIL_REQUIRED` | Customer email is missing during new client registration. |
| `400 Bad Request` | `USER_EXISTS` | A user with this email address already exists. |
| `401 Unauthorized` | `UNAUTHORIZED` | Missing or expired JWT access token in `Authorization` header. |
| `404 Not Found` | `NOT_FOUND` | Booking, Barber, or Shop resource was not found. |

