# Frame — React frontend

A React + TypeScript + Vite client for the FastAPI Instagram backend.

## Requirements

- Node.js 20.19+ or 22.12+
- The backend running at `http://127.0.0.1:8000`

## Run locally

From this directory:

```bash
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend, avoiding the need for permissive CORS settings during local development.

## Implemented screens

- Register and login
- Authenticated home feed with cursor-based load more
- User profile and post list
- Follow / unfollow and relationship state
- Paginated follower and following lists
- Create posts with up to 10 direct-to-object-storage image uploads (JPEG, PNG, WebP; 10 MB each)
- Verify and process uploads through the media API before attaching media IDs to posts
- Retry transient completion failures without re-uploading an already transferred original
- Discard unattached uploads when removing them from the composer
- Edit profile bio and public/private account setting
- Delete your own posts
- Find a profile by exact username

## API contract

The client targets the existing `/api/v1` routes and Pydantic response shapes. Direct media upload uses the API to create an upload ticket, sends the file with a browser PUT to the presigned object-storage URL, then calls the completion endpoint. Posts are created only with media IDs whose processing status is `ready`. The backend still does not expose likes, comments, notifications, or block-management routes, so those interactions are intentionally not shown.

## Authentication security note

The current API returns the access token and opaque refresh token in JSON. This development client persists both in `localStorage` so local browser reloads work. This is **not a production browser security design**: JavaScript-accessible storage is exposed to successful XSS. Before production, move refresh-token transport to an HttpOnly, Secure, SameSite cookie with CSRF protection, and revisit access-token storage.

## Build

```bash
npm run typecheck
npm run build
```
