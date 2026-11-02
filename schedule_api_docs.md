# BarberBay Schedule API Documentation

Frontend integration guide for shop business hours, barber shifts, barber breaks, and barber time off.

## General Configuration

- **Base URL:** `http://<your-domain>/api/v1/schedule/`
- **Content-Type:** `application/json`
- **Authentication:** All schedule endpoints require a JWT access token.

```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### Standard Response

```json
{
  "status": true,
  "code": "RESPONSE_CODE",
  "details": "Human readable message",
  "data": {}
}
```

> IDs are numeric. Times use `HH:MM[:ss]` format, for example `09:00:00`. Dates use `YYYY-MM-DD` format.

## Table of Contents

1. [Business Hours](#1-business-hours)
2. [Barber Shifts](#2-barber-shifts)
3. [Barber Breaks](#3-barber-breaks)
4. [Barber Time Off](#4-barber-time-off)
5. [Frontend Integration Flow](#5-frontend-integration-flow)

---

## 1. Business Hours

Business hours belong to a shop. The shop endpoint returns all saved weekly hours. The update endpoint accepts a list of day objects and updates or creates each supplied day.

### 1.1 Get Shop Business Hours

```http
GET /api/v1/schedule/business-hours/{shop_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Example:

```http
GET /api/v1/schedule/business-hours/7/
```

### Response

```json
{
  "status": true,
  "code": "BUSINESS_HOURS_RETRIEVED",
  "details": "Business hours retrieved.",
  "data": [
    {
      "id": 1,
      "shop": 7,
      "day_of_week": "monday",
      "open_time": "09:00:00",
      "close_time": "21:00:00",
      "is_closed": false
    },
    {
      "id": 2,
      "shop": 7,
      "day_of_week": "tuesday",
      "open_time": "09:00:00",
      "close_time": "21:00:00",
      "is_closed": false
    }
  ]
}
```

### 1.2 Update Shop Business Hours

Updates multiple days in one request. Send an array. The frontend can send all 7 days or only the days being changed.

```http
PUT /api/v1/schedule/business-hours/{shop_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

### Request Payload

```json
[
  {
    "day_of_week": "sunday",
    "open_time": null,
    "close_time": null,
    "is_closed": true
  },
  {
    "day_of_week": "monday",
    "open_time": "09:00:00",
    "close_time": "21:00:00",
    "is_closed": false
  },
  {
    "day_of_week": "tuesday",
    "open_time": "09:00:00",
    "close_time": "21:00:00",
    "is_closed": false
  },
  {
    "day_of_week": "wednesday",
    "open_time": "09:00:00",
    "close_time": "21:00:00",
    "is_closed": false
  },
  {
    "day_of_week": "thursday",
    "open_time": "09:00:00",
    "close_time": "21:00:00",
    "is_closed": false
  },
  {
    "day_of_week": "friday",
    "open_time": "09:00:00",
    "close_time": "21:00:00",
    "is_closed": false
  },
  {
    "day_of_week": "saturday",
    "open_time": "10:00:00",
    "close_time": "18:00:00",
    "is_closed": false
  }
]
```

The same `PUT /api/v1/schedule/business-hours/{shop_id}/` endpoint also accepts a single-day object with a `date` field. In that case it creates or updates only that date's custom schedule; the recurring 7-day schedule is unchanged.

```json
{
  "date": "2026-08-27",
  "open_time": "08:00:00",
  "close_time": "18:00:00",
  "is_closed": false,
  "breaks": [
    {"start_time": "11:00:00", "end_time": "11:30:00"}
  ]
}
```

### Response

```json
{
  "status": true,
  "code": "BUSINESS_HOURS_UPDATED",
  "details": "Business hours updated.",
  "data": [
    {
      "id": 1,
      "shop": 7,
      "day_of_week": "sunday",
      "open_time": null,
      "close_time": null,
      "is_closed": true
    },
    {
      "id": 2,
      "shop": 7,
      "day_of_week": "monday",
      "open_time": "09:00:00",
      "close_time": "21:00:00",
      "is_closed": false
    }
  ]
}
```

### 1.1.1 Date-wise Calendar View

Use `calendar_view=true` when opening the business-hours editor for one date. The API first checks for a date-specific custom schedule. If none exists, it returns that date's recurring weekday schedule. The response includes the effective opening time, closing time, multiple breaks, and the day's shop time-off/closed state.

```http
GET /api/v1/schedule/business-hours/7/?calendar_view=true&date=2026-08-30
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Response when a custom schedule exists:

```json
{
  "status": true,
  "code": "BUSINESS_HOURS_CALENDAR_RETRIEVED",
  "details": "Business hours calendar retrieved.",
  "data": {
    "date": "2026-08-30",
    "shop": {
      "id": 7,
      "name": "BarberBay Studio"
    },
    "source": "custom",
    "business_hours": {
      "open_time": "10:00:00",
      "close_time": "18:00:00",
      "is_closed": false,
      "time_off": {
        "is_off": false,
        "start_time": "10:00:00",
        "end_time": "18:00:00"
      },
      "breaks": [
        {
          "id": 1,
          "start_time": "13:00:00",
          "end_time": "13:30:00"
        },
        {
          "id": 2,
          "start_time": "15:30:00",
          "end_time": "15:45:00"
        }
      ]
    }
  }
}
```

If the shop is closed for that date, `is_closed` and `time_off.is_off` are `true`, and opening/closing times are `null`. If no custom date exists, `source` is `recurring`.

### Business Hour Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `day_of_week` | string | Yes | `sunday`, `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, or `saturday` |
| `open_time` | time/null | No | Opening time. Use `null` for a closed day. |
| `close_time` | time/null | No | Closing time. Use `null` for a closed day. |
| `is_closed` | boolean | No | Whether the shop is closed that day. |

### Single-Day Edit with Multiple Breaks

The same PUT endpoint supports editing one day and saving multiple shop breaks at once. The `breaks` array replaces the existing breaks for that day.

```http
PUT /api/v1/schedule/business-hours/7/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
[
  {
    "day_of_week": "saturday",
    "open_time": "10:00:00",
    "close_time": "17:00:00",
    "is_closed": false,
    "breaks": [
      {
        "start_time": "12:00:00",
        "end_time": "12:30:00"
      },
      {
        "start_time": "15:00:00",
        "end_time": "15:15:00"
      }
    ]
  }
]
```

To remove all breaks for a day, send `"breaks": []`.

The updated day is returned with its breaks:

```json
{
  "id": 7,
  "shop": 7,
  "day_of_week": "saturday",
  "open_time": "10:00:00",
  "close_time": "17:00:00",
  "is_closed": false,
  "breaks": [
    {
      "id": 1,
      "start_time": "12:00:00",
      "end_time": "12:30:00"
    },
    {
      "id": 2,
      "start_time": "15:00:00",
      "end_time": "15:15:00"
    }
  ]
}
```

---

## 2. Barber Shifts

A shift represents a barber's working hours. It can be recurring by weekday or a date-specific override.

### 2.1 List All Shifts

```http
GET /api/v1/schedule/shifts/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### 2.2 List Shifts for One Barber

```http
GET /api/v1/schedule/shifts/?barber={barber_id}
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Example:

```http
GET /api/v1/schedule/shifts/?barber=8
```

### 2.3 Create a Recurring Weekly Shift

```http
POST /api/v1/schedule/shifts/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "barber": 8,
  "day_of_week": "monday",
  "shift_date": null,
  "start_time": "09:00:00",
  "end_time": "18:00:00",
  "is_active": true
}
```

### 2.4 Create a Date-Specific Shift

```json
{
  "barber": 8,
  "day_of_week": null,
  "shift_date": "2026-08-31",
  "start_time": "12:00:00",
  "end_time": "20:00:00",
  "is_active": true
}
```

Use either `day_of_week` for a recurring shift or `shift_date` for a specific date override.

### Shift Response

```json
{
  "status": true,
  "code": "SHIFT_ADDED",
  "details": "Shift added.",
  "data": {
    "id": 21,
    "barber": 8,
    "day_of_week": "monday",
    "shift_date": null,
    "start_time": "09:00:00",
    "end_time": "18:00:00",
    "is_active": true
  }
}
```

### 2.5 Update a Shift

```http
PATCH /api/v1/schedule/shifts/{shift_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "start_time": "10:00:00",
  "end_time": "19:00:00",
  "is_active": true
}
```

Response code: `SHIFT_UPDATED`

### 2.6 Delete a Shift

```http
DELETE /api/v1/schedule/shifts/{shift_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Response:

```json
{
  "status": true,
  "code": "SHIFT_DELETED",
  "details": "Shift deleted.",
  "data": {}
}
```

### Shift Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `barber` | integer | Yes | Barber profile ID. |
| `day_of_week` | string/null | No | Recurring weekday. |
| `shift_date` | date/null | No | Specific date override. |
| `start_time` | time | Yes | Shift start. |
| `end_time` | time | Yes | Shift end. |
| `is_active` | boolean | No | Enables or disables the shift. |

---

## 3. Barber Breaks

Breaks represent unavailable time during a barber's shift. They can be recurring or date-specific.

### 3.1 List All Breaks

```http
GET /api/v1/schedule/breaks/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### 3.2 List Breaks for One Barber

```http
GET /api/v1/schedule/breaks/?barber={barber_id}
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### 3.3 List Shop and Barber Breaks by Date

```http
GET /api/v1/schedule/breaks/?shop={shop_id}&date=2026-08-27
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

This response contains both shop-level breaks and grouped barber breaks. If `barber` is omitted, all barbers in the selected shop are returned. Filter one barber as well:

```http
GET /api/v1/schedule/breaks/?shop={shop_id}&barber={barber_id}&date=2026-08-27
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

When `shop` is omitted, the authenticated user's saved `active_shop` is used. When `date` is provided, the response includes the shop break for that weekday, barber breaks for that weekday/date, and `today_off` for each barber. `today_off` is `true` when the barber has an approved time-off record covering the requested date.

Example response:

```json
{
  "status": true,
  "code": "BREAKS_RETRIEVED",
  "details": "Breaks retrieved.",
  "data": {
    "shop_breaks": [
      {
        "id": 1,
        "day_of_week": "thursday",
        "start_time": "13:00:00",
        "end_time": "14:00:00"
      }
    ],
    "barber_breaks": [
      {
        "barber": {
          "id": 8,
          "name": "Arif Hossain"
        },
        "breaks": [
          {
            "id": 31,
            "barber": 8,
            "day_of_week": "thursday",
            "break_date": null,
            "start_time": "13:00:00",
            "end_time": "14:00:00",
            "title": "Lunch Break",
            "is_active": true
          }
        ],
        "today_off": false
      }
    ]
  }
}
```

`date` must use `YYYY-MM-DD`; invalid dates return `400` with code `INVALID_DATE`.

### 3.4 Create a Recurring Break

```http
POST /api/v1/schedule/breaks/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "barber": 8,
  "day_of_week": "monday",
  "break_date": null,
  "start_time": "13:00:00",
  "end_time": "14:00:00",
  "title": "Lunch Break",
  "is_active": true
}
```

### 3.5 Create a Date-Specific Break

```json
{
  "barber": 8,
  "day_of_week": null,
  "break_date": "2026-08-31",
  "start_time": "15:00:00",
  "end_time": "15:30:00",
  "title": "Personal Break",
  "is_active": true
}
```

### Break Response

```json
{
  "status": true,
  "code": "BREAK_ADDED",
  "details": "Break added.",
  "data": {
    "id": 31,
    "barber": 8,
    "day_of_week": "monday",
    "break_date": null,
    "start_time": "13:00:00",
    "end_time": "14:00:00",
    "title": "Lunch Break",
    "is_active": true
  }
}
```

### 3.6 Update a Break

```http
PATCH /api/v1/schedule/breaks/{break_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "start_time": "13:30:00",
  "end_time": "14:30:00",
  "title": "Lunch Break",
  "is_active": true
}
```

Response code: `BREAK_UPDATED`

### 3.7 Delete a Break

```http
DELETE /api/v1/schedule/breaks/{break_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Response:

```json
{
  "status": true,
  "code": "BREAK_DELETED",
  "details": "Break deleted.",
  "data": {}
}
```

### Break Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `barber` | integer | Yes | Barber profile ID. |
| `day_of_week` | string/null | No | Recurring weekday. |
| `break_date` | date/null | No | Specific date override. |
| `start_time` | time | Yes | Break start. |
| `end_time` | time | Yes | Break end. |
| `title` | string | No | Break label. Defaults to `lunch`. |
| `is_active` | boolean | No | Enables or disables the break. |

---

## 4. Barber Time Off

Time off is used for leave or unavailable dates. `status` is controlled by the backend and cannot be set through create/update payloads.

### 4.1 List All Time Off

```http
GET /api/v1/schedule/time-off/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### 4.2 List Time Off for One Barber

```http
GET /api/v1/schedule/time-off/?barber={barber_id}
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### 4.2.1 List Breaks and Time Off Together

Use `schedule=true` to return both break and time-off data grouped by barber. Omit `barber` to return every barber in the selected shop. If `shop` is omitted, the authenticated user's `active_shop` is used.

```http
GET /api/v1/schedule/time-off/?shop=7&date=2026-08-30&schedule=true
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Response:

```json
{
  "status": true,
  "code": "BARBER_BREAKS_TIME_OFF_RETRIEVED",
  "details": "Barber breaks and time off retrieved.",
  "data": [
    {
      "barber": {
        "id": 8,
        "name": "Arif Hossain",
        "image": null
      },
      "breaks": [
        {
          "id": 31,
          "barber": 8,
          "day_of_week": "saturday",
          "break_date": null,
          "start_time": "13:00:00",
          "end_time": "14:00:00",
          "title": "Lunch Break",
          "is_active": true
        }
      ],
      "time_off": [
        {
          "id": 41,
          "barber": 8,
          "start_date": "2026-08-30",
          "end_date": "2026-08-30",
          "is_full_day": true,
          "start_time": null,
          "end_time": null,
          "reason": "Personal leave",
          "status": "approved",
          "reviewed_by": 1
        }
      ]
    }
  ]
}
```

### 4.3 Create Full-Day Time Off

```http
POST /api/v1/schedule/time-off/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "barber": 8,
  "start_date": "2026-09-05",
  "end_date": "2026-09-06",
  "is_full_day": true,
  "reason": "Personal leave"
}
```

### 4.4 Create Partial-Day Time Off

```json
{
  "barber": 8,
  "start_date": "2026-09-10",
  "end_date": "2026-09-10",
  "is_full_day": false,
  "start_time": "15:00:00",
  "end_time": "18:00:00",
  "reason": "Appointment"
}
```

### Time Off Response

```json
{
  "status": true,
  "code": "TIMEOFF_ADDED",
  "details": "Time off added.",
  "data": {
    "id": 41,
    "barber": 8,
    "start_date": "2026-09-05",
    "end_date": "2026-09-06",
    "is_full_day": true,
    "start_time": null,
    "end_time": null,
    "reason": "Personal leave",
    "status": "pending",
    "reviewed_by": null
  }
}
```

### 4.5 Update Time Off

```http
PATCH /api/v1/schedule/time-off/{timeoff_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "start_date": "2026-09-06",
  "end_date": "2026-09-07",
  "reason": "Updated personal leave"
}
```

`status` and `reviewed_by` are read-only in this API.

Response code: `TIMEOFF_UPDATED`

### 4.6 Delete Time Off

```http
DELETE /api/v1/schedule/time-off/{timeoff_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

Response:

```json
{
  "status": true,
  "code": "TIMEOFF_DELETED",
  "details": "Time off deleted.",
  "data": {}
}
```

### Time Off Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `barber` | integer | Yes | Barber profile ID. |
| `start_date` | date | Yes | First unavailable date. |
| `end_date` | date | Yes | Last unavailable date. |
| `is_full_day` | boolean | No | Use `false` for partial-day leave. |
| `start_time` | time/null | No | Required for partial-day leave. |
| `end_time` | time/null | No | Required for partial-day leave. |
| `reason` | string | Yes | Reason for leave. |
| `status` | string | Read-only | Backend-managed status. |
| `reviewed_by` | integer/null | Read-only | Reviewing user ID. |

---

## 5. Frontend Integration Flow

### Shop Schedule Screen

1. Load the selected shop's business hours:
   `GET /api/v1/schedule/business-hours/{shop_id}/`
2. Render the returned `data` array by `day_of_week`.
3. Save all weekly changes with:
   `PUT /api/v1/schedule/business-hours/{shop_id}/`

### Barber Schedule Screen

1. Load barber options from the barber API.
2. Load that barber's recurring/date-specific shifts:
   `GET /api/v1/schedule/shifts/?barber={barber_id}`
3. Load breaks:
   `GET /api/v1/schedule/breaks/?barber={barber_id}`
4. Load leave records:
   `GET /api/v1/schedule/time-off/?barber={barber_id}`
5. Use the returned `id` for PATCH and DELETE operations.

### Important UI Rules

- A recurring item uses `day_of_week` and should have `shift_date` or `break_date` as `null`.
- A date-specific item uses `shift_date` or `break_date` and can have `day_of_week` as `null`.
- Do not display `status` or `reviewed_by` as editable fields for time off.
- After every create, update, or delete request, refresh the relevant list using GET.
- Show the API `details` message for validation errors and use the API `code` for frontend branching.

---

## 6. Opening Calendar: Date-wise Shop and Staff Schedule

Use this endpoint for the opening calendar screen. It returns the selected shop's effective hours, shop breaks, every staff member's shift and duration, and staff members who have approved time off on that date.

```http
GET /api/v1/schedule/opening-calendar/?shop=7&date=2026-08-30
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

If `shop` is omitted, the authenticated user's saved `active_shop` is used.

### Response

```json
{
  "status": true,
  "code": "OPENING_CALENDAR_RETRIEVED",
  "details": "Opening calendar retrieved.",
  "data": {
    "date": "2026-08-30",
    "shop": {
      "id": 7,
      "name": "BarberBay Studio"
    },
    "shop_hours": {
      "open_time": "10:00:00",
      "close_time": "18:00:00",
      "is_closed": false,
      "breaks": [
        {
          "start_time": "13:00:00",
          "end_time": "14:00:00"
        }
      ]
    },
    "staff_shifts": [
      {
        "staff": {
          "id": 8,
          "name": "Arif Hossain",
          "image": "http://api.example.com/media/profile/arif.jpg"
        },
        "shift_time": [
          {
            "start_time": "09:00:00",
            "end_time": "18:00:00"
          }
        ],
        "duration_minutes": 540
      }
    ],
    "staff_time_off": [
      {
        "staff": {
          "id": 9,
          "name": "Nabil Hasan",
          "image": null
        },
        "start_date": "2026-08-30",
        "end_date": "2026-08-30",
        "reason": "Personal leave"
      }
    ]
  }
}
```

Date-specific shifts override recurring weekday shifts for that staff member. Date-specific shop hours override the recurring shop hours for that date.

## 7. Single-day Shop Hours and Breaks

Create or update a specific shop date. The `breaks` array supports multiple breaks. Sending `breaks: []` removes all breaks for that date.

### Create

```http
POST /api/v1/schedule/business-hours/7/date/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "date": "2026-08-30",
  "open_time": "10:00:00",
  "close_time": "18:00:00",
  "is_closed": false,
  "breaks": [
    {"start_time": "13:00:00", "end_time": "13:30:00"},
    {"start_time": "15:30:00", "end_time": "15:45:00"}
  ]
}
```

Response code: `SHOP_DATE_HOURS_CREATED`

### Update

```http
PUT /api/v1/schedule/business-hours/7/date/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "date": "2026-08-30",
  "open_time": "11:00:00",
  "close_time": "19:00:00",
  "is_closed": false,
  "breaks": [
    {"start_time": "14:00:00", "end_time": "14:30:00"},
    {"start_time": "17:00:00", "end_time": "17:15:00"}
  ]
}
```

Response code: `SHOP_DATE_HOURS_UPDATED`

## 8. Staff Time Off: Date Range, Full or Partial Day

### Create

```http
POST /api/v1/schedule/time-off/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Full-day leave for a date range:

```json
{
  "barber": 8,
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "is_full_day": true,
  "reason": "Annual leave"
}
```

Partial-day leave:

```json
{
  "barber": 8,
  "start_date": "2026-09-05",
  "end_date": "2026-09-05",
  "is_full_day": false,
  "start_time": "14:00:00",
  "end_time": "17:00:00",
  "reason": "Personal appointment"
}
```

### Update / Approve

```http
PUT /api/v1/schedule/time-off/{timeoff_id}/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "start_date": "2026-09-01",
  "end_date": "2026-09-04",
  "reason": "Updated annual leave"
}
```

The API returns `status: "pending"` initially. `status: "approved"` is the approved state used by the opening calendar's `staff_time_off` list and `today_off` calculation. `reviewed_by` is managed by the backend.

### Approve or Reject (Admin)

```http
PATCH /api/v1/schedule/time-off/{timeoff_id}/approval/
Authorization: Bearer <ADMIN_ACCESS_TOKEN>
Content-Type: application/json
```

Approve:

```json
{"status": "approved"}
```

Reject:

```json
{"status": "rejected"}
```

Response code: `TIMEOFF_STATUS_UPDATED`

### Update Breaks and Time Off Together

Use this endpoint from the barber schedule editor to save multiple breaks and time off for one barber/date in one request.

```http
PUT /api/v1/schedule/barber-schedule/
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "barber": 8,
  "date": "2026-08-30",
  "breaks": [
    {"start_time": "13:00:00", "end_time": "13:30:00", "title": "Lunch Break"},
    {"start_time": "16:00:00", "end_time": "16:15:00", "title": "Short Break"}
  ],
  "time_off": [
    {
      "start_date": "2026-08-30",
      "end_date": "2026-08-30",
      "is_full_day": false,
      "start_time": "17:00:00",
      "end_time": "18:00:00",
      "reason": "Personal appointment"
    }
  ]
}
```

`breaks: []` removes date-specific breaks. `time_off: []` removes same-day time-off records. Response code: `BARBER_BREAKS_TIME_OFF_UPDATED`.
