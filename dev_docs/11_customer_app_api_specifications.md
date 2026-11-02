# BarberBay: Customer App Page-by-Page API Specification

This specification maps every single screen in the **Customer (User) Application Figma Design** to its exact backend REST API endpoint, HTTP Method, Request JSON payload, and Response JSON structure.

---

# 🔐 Phase 1: Authentication & Onboarding (Top Row Screens)

### 1. Page 1.1: Customer Login Screen
- **Screen description:** Phone number input, "Sign In" button, Social login (Google / Apple), and navigation links to Sign Up or Forgot Password.
- **Endpoint:** `/api/v1/auth/login/`
- **Method:** `POST`
- **Payload:**
  ```json
  { 
    "phone": "+8801700000000",
    "password": "Password123"  
  }
  ```
- **Response:** `200 OK`
  ```json
  { "message": "OTP sent via SMS", "otp_expires_in_seconds": 300 }
  ```
- **Social Login Endpoint:** `/api/v1/auth/social-login/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "provider": "google", "id_token": "eyJhbGciOi..." }
  ```
- **Response:** `200 OK` (Returns access & refresh tokens)

---

### 2. Page 1.2: Sign Up / New Account Registration Screen
- **Screen description:** Input fields for Full Name, Phone Number, Email, Password, Terms & Conditions checkbox, and "Create Account" button.
- **Endpoint:** `/api/v1/auth/register/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "full_name": "Siam Ahmed",
    "phone": "+8801700000000",
    "email": "siam@example.com",
    "password": "StrongPassword123!",
    "agreed_to_terms": true
  }
  ```
- **Response:** `201 Created`
  ```json
  { "message": "Account created. Verification OTP sent to phone.", "user_id": 105 }
  ```

---

### 3. Page 1.3: OTP Verification Screen (4-Digit / 6-Digit PIN)
- **Screen description:** Code input boxes for OTP received via SMS/Email, timer countdown, and "Resend OTP" clickable text.
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
      "id": 105,
      "full_name": "Siam Ahmed",
      "phone": "+8801700000000",
      "role": "customer",
      "is_active": true
    }
  }
  ```
- **Resend OTP Endpoint:** `POST /api/v1/auth/resend-otp/`
- **Payload:** `{ "phone": "+8801700000000" }`
- **Response:** `200 OK` (`{ "message": "New OTP sent." }`)

---

### 4. Page 1.4: Forgot Password & Reset Password Screens
- **Screen description:** Request OTP for forgotten password, enter new password & confirm password.
- **Request OTP Endpoint:** `/api/v1/auth/forgot-password/`
- **Method:** `POST`
- **Payload:** `{ "phone": "+8801700000000" }`
- **Response:** `200 OK` (`{ "message": "Reset OTP sent." }`)
- **Set New Password Endpoint:** `/api/v1/auth/reset-password/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "phone": "+8801700000000",
    "otp": "4589",
    "password": "NewSecretPassword99!",
    "confirm_password": "NewSecretPassword99!"
  }
  ```
- **Response:** `200 OK` (`{ "status": "success", "message": "Password updated successfully." }`)

---

# 🏪 Phase 2: Explore, Shop Profile & Smart Booking Flow

### 5. Page 2.1: Welcome Splash & Home Explore Screen
- **Screen description:** Location city selector, search bar ("Search haircut, beard, spa..."), horizontal service category icons, "Featured Salons" cards, and "Top Barbers Near You" grid.
- **Endpoint (App Config & Categories):** `/api/v1/explore/categories/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "categories": [
      { "id": 1, "name": "Haircut", "icon_url": "https://.../haircut.png" },
      { "id": 2, "name": "Beard Trim", "icon_url": "https://.../beard.png" },
      { "id": 3, "name": "Facial & Spa", "icon_url": "https://.../spa.png" }
    ]
  }
  ```
- **Endpoint (Nearby & Featured Shops):** `/api/v1/shops/?city=Dhaka&latitude=23.777&longitude=90.399&search=&category_id=`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "total": 12,
    "results": [
      {
        "id": 1,
        "name": "BarberBay Executive Salon",
        "slug": "barberbay-executive-salon",
        "logo_url": "https://cdn.barberbay.com/salon_1.png",
        "cover_url": "https://cdn.barberbay.com/cover_1.jpg",
        "address": "Gulshan-2, Dhaka",
        "distance_km": 1.2,
        "average_rating": 4.9,
        "total_reviews": 128,
        "is_open_now": true
      }
    ]
  }
  ```

---

### 6. Page 2.2: Shop Detail Screen (Tabs: Services, Gallery, About & Policies, Reviews)
- **Screen description:** Full salon cover header, rating badge, address. Navigation tabs to view available haircut items with prices, interior photo galleries, map pin coordinates, cancellation terms, and verified customer testimonials.
- **Endpoint (Full Shop Profile, Hours & About):** `/api/v1/shops/{slug}/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "id": 1,
    "name": "BarberBay Executive Salon",
    "slug": "barberbay-executive-salon",
    "contact": { "phone": "+8801811111111", "email": "salon@barberbay.com" },
    "location": {
      "address": "Road 11, Block G, Banani, Dhaka",
      "latitude": 23.791,
      "longitude": 90.404,
      "directions_hint": "Opposite to Super Saver market"
    },
    "details": {
      "about_us": "Dhaka's leading luxury gentlemens grooming salon.",
      "cancellation_policy": "Free cancellation up to 3 hours prior to scheduled time."
    },
    "business_hours": [
      { "day_of_week": 1, "day_name": "Monday", "open_time": "10:00:00", "close_time": "22:00:00", "is_closed": false },
      { "day_of_week": 5, "day_name": "Friday", "open_time": "14:00:00", "close_time": "22:00:00", "is_closed": false }
    ],
    "social_media_links": [
      { "platform": "facebook", "url": "https://fb.com/barberbay" },
      { "platform": "whatsapp", "url": "https://wa.me/8801811111111" }
    ]
  }
  ```
- **Endpoint (Tab 1: Shop Services & Categories):** `/api/v1/shops/{slug}/services/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "categories": [
      {
        "id": 10,
        "name": "Haircuts & Styling",
        "services": [
          {
            "id": 101,
            "name": "Classic Fade & Scissor Trim",
            "description": "Includes wash, skin fade, and styling.",
            "price": "1000.00",
            "duration_minutes": 40,
            "is_active": true
          },
          {
            "id": 102,
            "name": "Beard Sculpting & Hot Towel",
            "description": "Trim and hot steam towel treat.",
            "price": "500.00",
            "duration_minutes": 25,
            "is_active": true
          }
        ]
      }
    ]
  }
  ```
- **Endpoint (Tab 2: Photo Gallery):** `/api/v1/shops/{slug}/gallery/`
- **Method:** `GET`
- **Response:** `200 OK` (`{ "gallery": [ { "id": 1, "image_url": "...", "caption": "Haircut styling", "order": 0 } ] }`)
- **Endpoint (Tab 4: Shop Reviews List):** `/api/v1/shops/{slug}/reviews/?page=1`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "average_rating": 4.9,
    "total_reviews": 128,
    "rating_distribution": { "5_stars": 115, "4_stars": 10, "3_stars": 2, "2_stars": 1, "1_star": 0 },
    "results": [
      {
        "id": 51,
        "customer_name": "Tanvir H.",
        "barber_name": "Rahim Stylist",
        "rating": 5,
        "comment": "Perfect fade and very hygienic chair!",
        "created_at": "2026-07-25T14:20:00Z"
      }
    ]
  }
  ```

---

### 7. Page 2.3: Barber (Stylist) Selection Screen
- **Screen description:** When user taps "Continue with Services", show eligible barbers who specialize in those services. Includes "Any Available Stylist" card and specific barber profiles with rating tags.
- **Endpoint:** `/api/v1/shops/{slug}/barbers/?service_ids=101,102`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "barbers": [
      {
        "id": 5,
        "full_name": "Rahim Khan",
        "specialty": "Senior Fade & Beard Master",
        "experience_years": 7,
        "avatar_url": "https://cdn.barberbay.com/barbers/rahim.jpg",
        "rating": 4.95,
        "is_available_today": true
      }
    ]
  }
  ```

---

### 8. Page 2.4: Date & Time Slot Selection Screen
- **Screen description:** Calendar month viewer to select a desired day. Below it displays available time badges grouped by Morning, Afternoon, and Evening.
- **Backend Logic Note:** This API is vital—it examines the selected barber's `barber_shifts`, removes their regular or date-custom `barber_breaks`, removes approved `barber_time_offs`, and excludes existing scheduled `appointments`!
- **Endpoint:** `/api/v1/shops/{slug}/barbers/{barber_id}/available-slots/`
- **Method:** `GET`
- **Query Parameters:** `?date=2026-08-01&service_ids=101,102`
- **Response:** `200 OK`
  ```json
  {
    "date": "2026-08-01",
    "barber_id": 5,
    "total_duration_minutes": 65,
    "slots": {
      "morning": ["10:00", "11:00"],
      "afternoon": ["14:30", "15:45"],
      "evening": ["18:00", "19:15", "20:30"]
    }
  }
  ```

---

### 9. Page 2.5: Order Summary, Promo & Payment Method Selection Screen
- **Screen description:** Cart review showing Shop Name, Stylist Name, Date/Time, list of selected treatments, price subtotal, Promo/Coupon code input box, and payment selection (Online Gateway Cards/bKash vs Cash at Salon).
- **Apply Promo Code Endpoint:** `/api/v1/bookings/apply-promo/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "shop_id": 1, "promo_code": "EID2026", "subtotal": "1500.00" }
  ```
- **Response:** `200 OK`
  ```json
  { "is_valid": true, "discount_amount": "150.00", "new_total": "1350.00", "message": "10% discount applied!" }
  ```
- **Get Allowed Payment Methods Endpoint:** `/api/v1/shops/{slug}/payment-methods/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  { "payment_gateway_enabled": true, "cash_on_arrival_enabled": true, "supported_gateways": ["bkash", "nagad", "card"] }
  ```

---

### 10. Page 2.6: Booking Creation & Checkout Confirmation
- **Screen description:** Tapping "Confirm & Pay" submits the complete reservation. Leads to the Green Checkmark Success Confirmation Screen with QR code and Booking ID (`BB-2026-X99`).
- **Endpoint:** `/api/v1/bookings/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "shop_id": 1,
    "payment_method": "online", 
    "promo_code": "EID2026",
    "appointments": [
      { "service_id": 101, "barber_id": 5, "appointment_date": "2026-08-01", "start_time": "14:30" },
      { "service_id": 102, "barber_id": 5, "appointment_date": "2026-08-01", "start_time": "15:10" }
    ]
  }
  ```
- **Response (If Online Payment selected):** `201 Created`
  ```json
  {
    "booking_code": "BB-2026-X99",
    "status": "pending",
    "payment_status": "pending",
    "total_amount": "1350.00",
    "payment_gateway_redirect_url": "https://sandbox.sslcommerz.com/gw/pay/BB-2026-X99"
  }
  ```
- **Response (If Cash on Arrival selected):** `201 Created`
  ```json
  {
    "booking_code": "BB-2026-X99",
    "status": "confirmed",
    "payment_status": "pending",
    "total_amount": "1350.00",
    "qr_code_string": "BARBY:BB-2026-X99:CUSTOMER-105:CONFIRMED",
    "message": "Appointment booked successfully! Pay cash when you arrive at salon."
  }
  ```

---

# 📅 Phase 3: My Bookings, History & Reviews (Bottom Row Screens)

### 11. Page 3.1: My Bookings List (Tabs: Upcoming vs. Past History)
- **Screen description:** View current active appointments vs past visits. Displays booking status badge (`Confirmed`, `In Progress`, `Completed`, `Cancelled`).
- **Endpoint:** `/api/v1/customer/bookings/`
- **Method:** `GET`
- **Query Parameters:** `?status=upcoming` *(or `?status=past` for completed/cancelled history)*
- **Response:** `200 OK`
  ```json
  {
    "count": 2,
    "results": [
      {
        "booking_code": "BB-2026-X99",
        "shop_name": "BarberBay Executive Salon",
        "barber_name": "Rahim Khan",
        "date_string": "Saturday, 01 Aug 2026",
        "time_string": "2:30 PM",
        "total_amount": "1350.00",
        "status": "confirmed",
        "can_cancel": true
      }
    ]
  }
  ```

---

### 12. Page 3.2: Booking Detail & Digital Ticket (QR Code Screen)
- **Screen description:** Single booking overview with digital check-in QR Code for salon desk reception, list of booked services, store address with map launch button, and options to Cancel or Reschedule.
- **Endpoint:** `/api/v1/customer/bookings/{booking_code}/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "booking_code": "BB-2026-X99",
    "status": "confirmed",
    "qr_data": "BARBY:BB-2026-X99:CUST-105",
    "shop": { "id": 1, "name": "BarberBay Executive Salon", "phone": "+8801811111111", "address": "Banani, Dhaka" },
    "barber": { "id": 5, "name": "Rahim Khan", "avatar_url": "..." },
    "appointment_date": "2026-08-01",
    "start_time": "14:30:00",
    "services": [
      { "name": "Classic Fade & Scissor Trim", "price": "1000.00" },
      { "name": "Beard Sculpting", "price": "500.00" }
    ],
    "discount": "150.00",
    "total_amount": "1350.00",
    "payment_method": "cash",
    "cancellation_deadline": "2026-08-01T11:30:00Z"
  }
  ```

---

### 13. Page 3.3: Cancellation & Refund Request Modal
- **Screen description:** Customer taps "Cancel Appointment", enters reason from dropdown or text box, and requests online refund if paid via Gateway.
- **Endpoint:** `/api/v1/customer/bookings/{booking_code}/cancel/`
- **Method:** `POST`
- **Payload:**
  ```json
  { "reason": "Schedule clash with work meeting." }
  ```
- **Response:** `200 OK`
  ```json
  {
    "booking_code": "BB-2026-X99",
    "status": "cancelled",
    "refund_status": "requested",
    "refund_amount": "1350.00",
    "message": "Appointment cancelled. Refund has been queued for admin approval."
  }
  ```

---

### 14. Page 3.4: Post-Service Rating & Review Submission Screen
- **Screen description:** After appointment status becomes `Completed`, prompt user to submit a 1 to 5 star rating for the Salon and their specific Stylist, with optional photo upload.
- **Endpoint:** `/api/v1/customer/bookings/{booking_code}/review/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "shop_rating": 5,
    "barber_rating": 5,
    "comment": "Rahim bhai gave me the best fade in Dhaka! Will revisit definitely.",
    "photo_url": "https://cdn.barberbay.com/reviews/user_photo_99.jpg"
  }
  ```
- **Response:** `201 Created` (`{ "status": "success", "message": "Thank you for your valuable feedback!" }`)

---

# ⚙️ Phase 4: Customer Profile, Notifications & Legal Support (Right Side Screens)

### 15. Page 4.1: User Profile & Preferences Dashboard
- **Screen description:** View personal profile details, toggle push/email notification reminders, and switch between Light / Dark themes.
- **Get Profile Endpoint:** `/api/v1/user/profile/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "id": 105,
    "full_name": "Siam Ahmed",
    "email": "siam@example.com",
    "phone": "+8801700000000",
    "avatar_url": "https://cdn.barberbay.com/avatars/siam.png",
    "preferences": {
      "push_notifications_enabled": true,
      "email_notifications_enabled": false,
      "dark_mode_enabled": true
    }
  }
  ```
- **Update Profile & Preferences Endpoint:** `/api/v1/user/profile/`
- **Method:** `PATCH`
- **Payload:**
  ```json
  { "full_name": "Siam Ahmed", "dark_mode_enabled": true, "push_notifications_enabled": false }
  ```
- **Response:** `200 OK` (`{ "message": "Profile updated successfully." }`)

---

### 16. Page 4.2: Notifications Center
- **Screen description:** List of recent alerts (Booking confirmations, Appointment reminders 2 hours prior, promotional coupon announcements).
- **Get Notifications Endpoint:** `/api/v1/user/notifications/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  {
    "unread_count": 1,
    "notifications": [
      {
        "id": 801,
        "title": "Appointment Tomorrow!",
        "message": "Reminder: You have a haircut appointment tomorrow at 2:30 PM with Rahim Khan at BarberBay Executive Salon.",
        "type": "reminder",
        "is_read": false,
        "created_at": "2026-07-31T12:00:00Z"
      }
    ]
  }
  ```
- **Mark as Read Endpoint:** `/api/v1/user/notifications/{id}/read/`
- **Method:** `PATCH`
- **Response:** `200 OK` (`{ "id": 801, "is_read": true }`)

---

### 17. Page 4.3: Contact Us / Support Help Center
- **Screen description:** Customer issue form to reach platform support regarding failed payment, disputed service, or technical bugs.
- **Endpoint:** `/api/v1/contact/submit/`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "name": "Siam Ahmed",
    "email": "siam@example.com",
    "phone": "+8801700000000",
    "subject": "Payment deducted but booking shows pending",
    "message": "I paid via bKash for booking BB-2026-X99. Transaction ID is 8HXX7659. Please confirm my appointment."
  }
  ```
- **Response:** `201 Created`
  ```json
  { "status": "success", "ticket_id": "TICKET-2026072801", "message": "Support team has received your inquiry and will respond within 4 hours." }
  ```

---

### 18. Page 4.4: Legal Screens (Terms & Conditions, Privacy Policy)
- **Screen description:** Static text views in Figma displaying company compliance terms, refund rules, and user data privacy policies.
- **Get Terms Endpoint:** `/api/v1/legal/terms-and-conditions/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  { "version": "v1.0", "title": "Terms of Service & Cancellation Policy", "content": "1. Booking Terms...", "effective_date": "2026-01-01" }
  ```
- **Get Privacy Policy Endpoint:** `/api/v1/legal/privacy-policy/`
- **Method:** `GET`
- **Response:** `200 OK`
  ```json
  { "version": "v1.0", "title": "User Privacy Policy", "content": "Your phone and location data are strictly safeguarded...", "effective_date": "2026-01-01" }
  ```
