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
- Create a post from one or more image URLs
- Delete your own posts
- Find a profile by exact username

## API contract

The client targets the existing `/api/v1` routes and Pydantic response shapes. Likes, comments, direct media uploads, notifications, and profile editing are intentionally not implemented because those backend endpoints are not currently available.

## Authentication security note

The current API returns the access token and opaque refresh token in JSON. This development client persists both in `localStorage` so local browser reloads work. This is **not a production browser security design**: JavaScript-accessible storage is exposed to successful XSS. Before production, move refresh-token transport to an HttpOnly, Secure, SameSite cookie with CSRF protection, and revisit access-token storage.

## Build

```bash
npm run typecheck
npm run build
```
