# BarberBay Dashboard API Documentation

This document outlines all the APIs available for the Admin Dashboard.
Base URL: `/api/v1/dashboard`
Headers Required: `Authorization: Bearer <your_jwt_token>`

---

## 1. Dashboard Overview Stats
**Endpoint:** `GET /`  
**Query Parameters:** 
- `shop` (integer, optional) - Filter by specific shop ID

**Response:**
```json
{
  "success": true,
  "details": "Dashboard data retrieved",
  "code": "DASHBOARD_DATA",
  "data": {
    "metrics": {
      "todays_bookings": 10,
      "completed": 5,
      "in_service": 2,
      "revenue_today": 450.50
    },
    "upcoming_bookings": [
      {
        "id": 1,
        "customer_name": "John Doe",
        "services": "Haircut, Beard Trim",
        "price": "35.00",
        "duration_minutes": 45,
        "start_time": "14:30"
      }
    ]
  }
}
```

---

## 2. Staff / Barbers Management

### 2.1 Get Staff List
**Endpoint:** `GET /shops/<shop_id>/staff/`

**Response:**
```json
{
  "success": true,
  "details": "Staff retrieved",
  "code": "STAFF_RETRIEVED",
  "data": [
    {
      "id": 1,
      "user_id": "uuid-here",
      "name": "Mike Johnson",
      "email": "mike@example.com",
      "phone": "+1234567890",
      "role": "barber",
      "position": "Senior Barber",
      "avatar": "https://example.com/media/profile/mike.jpg"
    }
  ]
}
```

### 2.2 Create New Staff
**Endpoint:** `POST /shops/<shop_id>/staff/`  
**Content-Type:** `multipart/form-data` or `application/json`

**Payload:**
- `email` (string, required)
- `name` (string, required)
- `phone` (string, optional)
- `position` (string, optional) e.g., "Senior Barber"
- `role` (string, optional) e.g., "barber" or "manager"
- `services` (list/array of service IDs, optional)
- `avatar` (file, optional, only via multipart/form-data)

**Response:**
```json
{
  "success": true,
  "details": "Staff member created and credentials emailed successfully",
  "code": "STAFF_CREATED",
  "data": {
    "id": 2,
    "user_id": "uuid-here",
    "username": "mikejohnson123",
    "email": "mike@example.com",
    "password": "generated_password_here",
    "role": "barber",
    "position": "Senior Barber"
  }
}
```

### 2.3 Update Staff
**Endpoint:** `PATCH /shops/<shop_id>/staff/<pk>/`  
*(pk is the Barber ID)*  
**Content-Type:** `multipart/form-data` or `application/json`

**Payload (All Optional):**
- `name` (string)
- `phone` (string)
- `position` (string)
- `services` (array of IDs)
- `avatar` (file)

**Response:**
```json
{
  "success": true,
  "details": "Staff member updated",
  "code": "STAFF_UPDATED",
  "data": {}
}
```

### 2.4 Delete/Remove Staff
**Endpoint:** `DELETE /shops/<shop_id>/staff/<pk>/`  
*(pk is the Barber ID)*  

**Response:**
```json
{
  "success": true,
  "details": "Staff member removed",
  "code": "STAFF_DELETED",
  "data": {}
}
```

---

## 3. Reviews Management

### 3.1 Get Reviews List
**Endpoint:** `GET /shops/<shop_id>/reviews/`  
**Query Parameters:** 
- `barber_id` (integer, optional) - Filter reviews for a specific staff

**Response:**
```json
{
  "success": true,
  "details": "Reviews retrieved",
  "code": "REVIEWS_RETRIEVED",
  "data": {
    "summary": {
      "average_rating": 4.5,
      "total_reviews": 12,
      "distribution": {
        "1": 0, "2": 0, "3": 1, "4": 4, "5": 7
      }
    },
    "reviews": [
      {
        "id": 1,
        "rating": 5,
        "comment": "Great service!",
        "customer_name": "Jane Doe",
        "customer_avatar": "https://example.com/media/avatar.jpg",
        "date": "22 Aug 2026"
      }
    ]
  }
}
```

---

## 4. Client Management

### 4.1 Get Client List
**Endpoint:** `GET /shops/<shop_id>/clients/`

**Response:**
```json
{
  "success": true,
  "details": "Clients retrieved",
  "code": "CLIENTS_RETRIEVED",
  "data": [
    {
      "id": "uuid-here",
      "email": "client@example.com",
      "full_name": "John Doe",
      "phone": "+123456789",
      "avatar": null
    }
  ]
}
```

### 4.2 Create Single Client
**Endpoint:** `POST /shops/<shop_id>/clients/`  
**Content-Type:** `application/json`

**Payload:**
```json
{
  "email": "client@example.com",
  "name": "John Doe",
  "phone": "+1234567890"
}
```

**Response:**
```json
{
  "success": true,
  "details": "Client created successfully",
  "code": "CLIENT_CREATED",
  "data": {
     "id": "uuid-here",
     "email": "client@example.com",
     ...
  }
}
```

### 4.3 Get Client Details & Metrics
**Endpoint:** `GET /shops/<shop_id>/clients/<client_uuid>/`

**Response:**
```json
{
  "success": true,
  "details": "Client details retrieved",
  "code": "CLIENT_DETAILS",
  "data": {
    "client": { /* User Profile Object */ },
    "metrics": {
      "total_appointments": 5,
      "cancellations": 0,
      "last_visit": "2026-08-15",
      "total_revenue": 150.00
    },
    "upcoming_bookings": [ /* List of Bookings */ ],
    "past_bookings": [ /* List of Bookings */ ]
  }
}
```

### 4.4 Get Client Groups
**Endpoint:** `GET /shops/<shop_id>/client-groups/`

**Response:**
```json
{
  "success": true,
  "details": "Groups retrieved",
  "code": "GROUPS_RETRIEVED",
  "data": [
    {
      "id": 1,
      "name": "VIP Customers",
      "clients": ["uuid-1", "uuid-2"],
      "created_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```

### 4.5 Create/Update Client Group
**Endpoint:** `POST /shops/<shop_id>/client-groups/`  
**Content-Type:** `application/json`

**Payload:**
```json
{
  "name": "VIP Customers",
  "clients": ["uuid-1", "uuid-2"]
}
```

**Response:**
```json
{
  "success": true,
  "details": "Group created/updated",
  "code": "GROUP_SAVED",
  "data": {
     "id": 1,
     "name": "VIP Customers",
     "clients": ["uuid-1", "uuid-2"]
  }
}
```

### 4.6 Import Clients via CSV
**Endpoint:** `POST /shops/<shop_id>/clients/import/`  
**Content-Type:** `multipart/form-data`

**Payload:**
- `file` (File, .csv format)
*(Columns required in CSV: name, email, phone)*

**Response:**
```json
{
  "success": true,
  "details": "Imported 10 clients.",
  "code": "IMPORT_SUCCESS",
  "data": {
     "created_count": 10,
     "errors": []
  }
}
```

### 4.7 Send Messages (Email/SMS) to Clients
**Endpoint:** `POST /shops/<shop_id>/send-messages/`  
**Content-Type:** `application/json`

**Payload:**
```json
{
  "group_id": 1, 
  "client_ids": ["uuid-1", "uuid-2"], 
  "email_title": "Special Discount!",
  "email_content": "Get 20% off on your next haircut.",
  "sms_content": "Get 20% off! Visit our shop today."
}
```
*(Note: Send either `group_id` or `client_ids`. You can send email, SMS, or both.)*

**Response:**
```json
{
  "success": true,
  "details": "Messages dispatched.",
  "code": "MESSAGES_SENT",
  "data": {
    "emails_sent": 2,
    "sms_sent": 2
  }
}
```
