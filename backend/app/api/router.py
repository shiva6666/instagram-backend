from fastapi import APIRouter

from app.api.routes import health
from app.modules.auth.router import router as auth_router
from app.modules.feed.router import router as feed_router
from app.modules.follows.router import router as follows_router
from app.modules.posts.router import router as posts_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(posts_router)
api_router.include_router(follows_router)
api_router.include_router(feed_router)
