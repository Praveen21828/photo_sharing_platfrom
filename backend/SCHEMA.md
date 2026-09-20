# Database Schema

The PostgreSQL schema is represented by Django ORM models in the domain apps. Photo binary content is not stored in PostgreSQL; `Photo.storage_key` points to a private S3 object.

## Tables

- `accounts_user`: UUID identity, email authentication, role, password hash, and account timestamps.
- `events_event`: event name, Admin/Lead creator, and timestamps.
- `events_eventmember`: event/team-member assignment with a unique `(event, user)` constraint.
- `photos_photo`: event photo metadata and unique S3 storage key. Event deletion cascades to photos; uploader deletion is protected.
- `galleries_gallery`: event gallery, opaque public identifier, hashed PIN, publication state, and publication timestamp.
- `galleries_galleryphoto`: selected-photo join table with a unique `(gallery, photo)` constraint.

All primary keys are UUIDs. Foreign keys isolate ownership and preserve audit history using `PROTECT` for users who created events or uploaded photos. Event-owned records cascade when an event is deleted. Public gallery access is represented by `public_identifier`; the PIN is stored only as a hash.

The model tests cover relationship traversal, uniqueness constraints, invalid file metadata, protected event ownership, role/reference validation, and cross-event gallery selections.

The custom user model is configured through `AUTH_USER_MODEL=accounts.User`. Because the initial scaffold may have been migrated with Django's default user, an existing local database must be recreated before applying these initial migrations.