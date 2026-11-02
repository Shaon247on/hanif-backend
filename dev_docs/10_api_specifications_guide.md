# BarberBay API Specification Guide

This guide details the RESTful API endpoints derived directly from the **BarberBay Figma Design** and our **DBML Database Schema**. Each section covers the required endpoints across the three core interfaces (**Customer App**, **Staff/Barber Partner Portal**, and **Shop Admin Dashboard**), detailing the exact **HTTP Method**, **Payload (Request JSON)**, and **Response JSON**.

---

## 📱 1. Authentication, Profile & Settings (All Users)

### 1.1 Request OTP / Login
- **Endpoint:** `/api/v1/auth/login/`
- **Method:** `POST`
- **Description:** Initiates user login via Phone Number (or Email) with OTP for Customers, Barbers, and Admins.
- **Payload:**
  ```json
  { "phone": "+8801700000000" }
  ```
- **Response:** `200 OK`
  ```json
  { "message": "OTP sent successfully", "expires_in_seconds": 300 }
  ```

### 1.2 Verify OTP & Generate Token
- **Endpoint:** `/api/v1/auth/verify-otp/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "phone": "+8801700000000", "otp": "4589" }
  ```
- **Response:** `200 OK`
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "user": { 
      "id": 12, 
      "username": "siam", 
      "role": "customer", 
      "phone": "+8801700000000" 
    }
  }
  ```

### 1.3 Update User Preference Settings (Notifications / Dark Mode)
- **Endpoint:** `/api/v1/users/settings/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "push_notifications_enabled": true, "dark_mode_enabled": true }
  ```
- **Response:** `200 OK`
  ```json
  { "status": "success", "updated_at": "2026-07-28T11:50:00Z" }
  ```

---

## 🏪 2. Shop Discovery, Services & Team (Customer App)

### 2.1 Search Nearby Shops
- **Endpoint:** `/api/v1/shops/?city=Dhaka&latitude=23.777&longitude=90.399&search=Gentlemen`
- **Method:** `GET`
- **Payload:** *None (Query Params)*
- **Response:** `200 OK`
  ```json
  {
    "count": 5,
    "results": [
      {
        "id": 1,
        "name": "BarberBay Executive Salon",
        "slug": "barberbay-executive-salon",
        "logo_url": "https://cdn.barberbay.com/logos/salon_1.png",
        "address": "Gulshan-2, Dhaka",
        "distance_km": 1.4,
        "average_rating": 4.8,
        "is_open_now": true
      }
    ]
  }
  ```

### 2.2 Get Shop Full Details (About, Business Hours, Gallery & Social Links)
- **Endpoint:** `/api/v1/shops/{slug}/`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "id": 1,
    "name": "BarberBay Executive Salon",
    "details": {
      "about_us": "Premium grooming services for gentlemen.",
      "address": "Gulshan-2, Dhaka",
      "cancellation_policy": "Cancel up to 2 hours before appointment."
    },
    "business_hours": [
      { "day_of_week": 1, "open_time": "10:00:00", "close_time": "22:00:00", "is_closed": false }
    ],
    "gallery": [ {"image_url": "{base_url}/img/lounge.jpg", "caption": "VIP Lounge" } ],
    "social_media": [ { "platform": "instagram", "url": "https://{base_url}/img/barberbay.jpg" } ]
  }
  ```

### 2.3 Get Shop Services & Categories
- **Endpoint:** `/api/v1/shops/{slug}/services/`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "categories": [
      {
        "id": 1,
        "name": "Haircuts & Styling",
        "services": [
          { "id": 101, "name": "Classic Fade & Trim", "price": "1200.00", "duration_minutes": 45 }
        ]
      }
    ]
  }
  ```

### 2.4 Get Available Barbers / Staff List
- **Endpoint:** `/api/v1/shops/{slug}/barbers/`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "barbers": [
      { 
        "id": 5, 
        "name": "Rahim Khan", 
        "specialty": "Senior Stylist", 
        "experience_years": 8, 
        "avatar_url": "https://cdn.barberbay.com/barbers/rahim.jpg" 
      }
    ]
  }
  ```

---

## 📅 3. Customer Booking & Appointment Checkout

### 3.1 Get Available Time Slots (Calculated from Shifts, Breaks & Time-Offs)
- **Endpoint:** `/api/v1/shops/{slug}/slots/?date=2026-08-01&service_id=101&barber_id=5`
- **Method:** `GET`
- **Description:** Evaluates the barber's scheduled shift (`barber_shifts`), excludes daily recurring & custom single-day breaks (`barber_breaks`) and approved leaves (`barber_time_offs`), and returns free time slots for the Figma time picker.
- **Payload:** *None (Query Params)*
- **Response:** `200 OK`
  ```json
  {
    "date": "2026-08-01",
    "barber_id": 5,
    "available_slots": ["10:00", "11:00", "14:30", "16:00", "18:00"]
  }
  ```

### 3.2 Create Booking & Appointments (Checkout Order)
- **Endpoint:** `/api/v1/bookings/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "shop_id": 1,
    "payment_method": "online",
    "appointments": [
      { 
        "service_id": 101, 
        "barber_id": 5, 
        "appointment_date": "2026-08-01", 
        "start_time": "14:30" 
      }
    ]
  }
  ```
- **Response:** `201 Created`
  ```json
  {
    "booking_code": "BB-2026-X99",
    "total_amount": "1200.00",
    "payment_status": "pending",
    "payment_gateway_url": "https://sandbox.sslcommerz.com/gw/pay/..." 
  }
  ```

### 3.3 Request Cancellation & Refund
- **Endpoint:** `/api/v1/bookings/{booking_code}/refund/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "reason": "Emergency travel plan change." }
  ```
- **Response:** `200 OK`
  ```json
  { 
    "booking_code": "BB-2026-X99", 
    "refund_status": "requested", 
    "message": "Refund request submitted successfully." 
  }
  ```

### 3.4 Submit Verified Review (Post-Service)
- **Endpoint:** `/api/v1/shops/{slug}/reviews/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "booking_code": "BB-2026-X99", "barber_id": 5, "rating": 5, "comment": "Excellent skin fade!" }
  ```
- **Response:** `201 Created`
  ```json
  { "status": "success", "message": "Review published." }
  ```

---

## ✂️ 4. Barber Staff Partner Portal (Staff UI)

### 4.1 Get My Assigned Appointments (Daily Schedule)
- **Endpoint:** `/api/v1/staff/appointments/?date=2026-08-01`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "total_today": 6,
    "appointments": [
      {
        "id": 501,
        "time_slot": "14:30 - 15:15",
        "customer_name": "Siam Ahmed",
        "service": "Classic Fade & Trim",
        "status": "scheduled"
      }
    ]
  }
  ```

### 4.2 Update Appointment Service Status (In Chair / Done)
- **Endpoint:** `/api/v1/staff/appointments/{id}/status/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "status": "in_progress" }  // Options: "in_progress" | "completed" | "no_show"
  ```
- **Response:** `200 OK`
  ```json
  { "id": 501, "status": "in_progress", "updated_at": "2026-08-01T14:32:00Z" }
  ```

### 4.3 Manage Breaks (Daily Recurring & Custom Single-Day Breaks)
- **Endpoint:** `/api/v1/staff/breaks/`
- **Method:** `POST`
- **Description:** Allows staff to schedule regular everyday breaks OR single-day custom absences.
- **Payload (Daily Recurring Lunch):**
  ```json
  { "day_of_week": 1, "start_time": "13:00", "end_time": "14:00", "title": "lunch" }
  ```
- **Payload (Single-Day Custom Errand):**
  ```json
  { "break_date": "2026-08-05", "start_time": "16:00", "end_time": "17:00", "title": "custom_errand" }
  ```
- **Response:** `201 Created`
  ```json
  { "id": 12, "message": "Break schedule successfully blocked out from booking slots." }
  ```

### 4.4 Request Time Off (Full Day vs. Partial Hours Leave)
- **Endpoint:** `/api/v1/staff/time-off/`
- **Method:** `POST`
- **Description:** Allows staff to apply for a full day off or a partial hours leave.
- **Payload (Full Day Leave):**
  ```json
  { "start_date": "2026-08-10", "end_date": "2026-08-12", "is_full_day": true, "reason": "Family vacation" }
  ```
- **Payload (Partial Hours Leave):**
  ```json
  { "start_date": "2026-08-15", "end_date": "2026-08-15", "is_full_day": false, "start_time": "15:00", "end_time": "20:00", "reason": "Doctor visit" }
  ```
- **Response:** `201 Created`
  ```json
  { "id": 88, "status": "pending", "message": "Leave request submitted to Admin for approval." }
  ```

---

## 👑 5. Shop Owner / Admin Management Dashboard (Admin UI)

### 5.1 Get Shop Analytics & Revenue Summary
- **Endpoint:** `/api/v1/admin/dashboard-stats/`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "total_revenue": "145000.00",
    "today_bookings": 24,
    "active_staff_count": 8,
    "pending_leave_requests": 2
  }
  ```

### 5.2 Approve/Reject Staff Time Off Requests
- **Endpoint:** `/api/v1/admin/time-off/{id}/review/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "status": "approved" }  // Options: "approved" | "rejected"
  ```
- **Response:** `200 OK`
  ```json
  { "id": 88, "status": "approved", "reviewed_by": "Shop Admin", "message": "Barber's slots are now blocked off." }
  ```

### 5.3 Toggle Shop Settings (Payment Gateway ON/OFF & Auto-Confirm)
- **Endpoint:** `/api/v1/admin/shop-settings/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "payment_gateway_enabled": false, "auto_confirm_bookings": true }
  ```
- **Response:** `200 OK`
  ```json
  {
    "status": "updated",
    "note": "Online payment disabled. Customers will only see Cash payment at checkout."
  }
  ```

### 5.4 Approve/Reject Customer Refund Request
- **Endpoint:** `/api/v1/admin/refunds/{id}/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "status": "approved", "refund_amount": "1200.00" }
  ```
- **Response:** `200 OK`
  ```json
  { "booking_code": "BB-2026-X99", "status": "approved", "processed_at": "2026-07-28T11:55:00Z" }
  ```

---

## 🔔 6. Notifications & Legal Support (All Users)

### 6.1 Get Notifications
- **Endpoint:** `/api/v1/notifications/`
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  {
    "unread_count": 2,
    "notifications": [
      { "id": 1, "title": "Booking Confirmed!", "message": "Your appointment BB-2026-X99 is confirmed.", "is_read": false }
    ]
  }
  ```

### 6.2 Submit Contact Us / Support Inquiry
- **Endpoint:** `/api/v1/contact/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "name": "Siam", "email": "siam@example.com", "subject": "App Booking Issue", "message": "Need help with..." }
  ```
- **Response:** `201 Created`
  ```json
  { "status": "success", "ticket_id": "#SUPPORT-1022" }
  ```

### 6.3 Get Terms and Privacy Policy
- **Endpoint:** `/api/v1/legal/{type}/` *(Where `{type}` is `terms` or `privacy`)*
- **Method:** `GET`
- **Payload:** *None*
- **Response:** `200 OK`
  ```json
  { 
    "version": "v1.0", 
    "title": "Privacy Policy", 
    "content": "We respect your data privacy...", 
    "effective_date": "2026-01-01" 
  }
  ```
