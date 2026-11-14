from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user, get_db_session
from app.modules.feed.repository import SqlAlchemyFeedRepository
from app.modules.feed.schemas import FeedResponse
from app.modules.feed.service import FeedService, InvalidFeedCursorError
from app.modules.posts.schemas import PostImageResponse, PostResponse
from app.modules.users.models import User

router = APIRouter(prefix="/feed", tags=["feed"])


def get_feed_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeedService:
    return FeedService(SqlAlchemyFeedRepository(session))


@router.get(
    "",
    response_model=FeedResponse,
    summary="Get the authenticated user's home feed",
)
async def get_home_feed(
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FeedService, Depends(get_feed_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> FeedResponse:
    try:
        page = await service.get_feed(
            viewer_id=viewer.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidFeedCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    posts = [
        PostResponse(
            id=item.post.id,
            user_id=item.post.user_id,
            username=item.author.username,
            user_avatar=item.author.avatar_key,
            caption=item.post.caption,
            post_img_url=[
                PostImageResponse(position=image.position, url=image.url)
                for image in item.post.images
            ],
            created_at=item.post.created_at,
            is_private=item.post.is_private,
            is_deleted=item.post.is_deleted,
        )
        for item in page.items
    ]
    return FeedResponse(posts=posts, limit=limit, next_cursor=page.next_cursor)
