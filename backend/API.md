# REST API

Base URL: `/api/v1/`. JSON responses use `{ "data": ... }` for successful requests and `{ "code", "message", "details" }` for errors. Protected endpoints require a Django REST Framework JWT access token in `Authorization: Bearer <token>`.

## Authentication

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register/` | Local development only | Register an Admin/Lead when `ALLOW_PUBLIC_ADMIN_REGISTRATION=True`; disabled in production. |
| POST | `/auth/login/` | Public | Return access token, refresh token, and current user. |
| POST | `/auth/refresh/` | Public | Exchange a valid refresh token for an access token. |
| POST | `/auth/logout/` | Authenticated | Blacklist the supplied refresh token. The request body is `{ "refresh": "..." }`. |
| GET | `/auth/me/` | Authenticated | Return current-user profile. |
| POST | `/auth/team-members/` | Admin | Create a Team Member account. |

## Events and assignments

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/events/` | Authenticated | Admin-owned events for Admins; assigned events for Team Members. |
| POST | `/events/` | Admin | Create an event. |
| GET | `/events/{event_id}/` | Event member/owner | Retrieve an accessible event. |
| PATCH | `/events/{event_id}/` | Event owner Admin | Update event name. |
| GET | `/events/{event_id}/members/` | Event member/owner | View assignments. |
| POST | `/events/{event_id}/members/` | Event owner Admin | Assign an active Team Member. Duplicate assignment returns `409`. |

## Photos

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/photos/events/{event_id}/` | Event owner Admin or assigned Team Member | Paginated metadata. Admins see all event photos; Team Members see their own uploads only. |
| POST | `/photos/events/{event_id}/` | Event owner Admin or assigned Team Member | Create metadata and receive a 10-minute presigned S3 upload URL. Binary content never enters PostgreSQL. |
| POST | `/photos/{photo_id}/upload-complete/` | Uploader/Admin | Verify the private S3 object exists with the declared size. |
| GET | `/photos/{photo_id}/` | Event member/owner | Retrieve photo metadata. |
| GET | `/photos/{photo_id}/download-url/` | Event member/owner | Receive a 5-minute presigned S3 download URL. |

## Galleries

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/galleries/events/{event_id}/` | Event owner Admin | List galleries for an owned event. |
| POST | `/galleries/events/{event_id}/` | Event owner Admin | Create a draft gallery with a hashed PIN. |
| GET | `/galleries/{gallery_id}/` | Event owner Admin | Retrieve gallery and selected photos. |
| POST | `/galleries/{gallery_id}/photos/` | Event owner Admin | Select a photo from the same event. Duplicate returns `409`. |
| POST | `/galleries/{gallery_id}/publish/` | Event owner Admin | Publish a gallery containing at least one selected photo. |

## Customer access

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/public/galleries/{public_identifier}/verify-pin/` | Public with PIN | Return a short-lived gallery-scoped access token. |
| GET | `/public/galleries/{public_identifier}/` | Gallery token | Return only selected photos from a published gallery. |
| GET | `/public/galleries/{public_identifier}/photos/{photo_id}/url/` | Gallery token | Return a temporary URL for a selected published photo. |

Customer requests send the token in `X-Gallery-Token`. Draft or revoked/unpublished galleries return `404`, and tokens are scoped to one gallery identifier.