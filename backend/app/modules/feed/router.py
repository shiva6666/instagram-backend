from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.dependencies import DatabaseSession, get_current_user
from app.modules.feed.repository import SqlAlchemyFeedRepository
from app.modules.feed.schemas import FeedResponse
from app.modules.feed.service import FeedService, InvalidFeedCursorError
from app.modules.media.dependencies import get_media_url_resolver
from app.modules.media.service import MediaUrlResolver
from app.modules.posts.schemas import PostImageResponse, PostResponse
from app.modules.users.models import User

router = APIRouter(prefix="/feed", tags=["feed"])


def get_feed_service(session: DatabaseSession) -> FeedService:
    return FeedService(SqlAlchemyFeedRepository(session))


@router.get(
    "",
    response_model=FeedResponse,
    summary="Get the authenticated user's home feed",
)
async def get_home_feed(
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FeedService, Depends(get_feed_service)],
    media_urls: Annotated[MediaUrlResolver, Depends(get_media_url_resolver)],
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

    all_images = tuple(
        image for item in page.items for image in item.post.images
    )
    resolved_images = await media_urls.resolve(all_images)
    posts: list[PostResponse] = []
    image_offset = 0
    for item in page.items:
        image_count = len(item.post.images)
        images = resolved_images[image_offset : image_offset + image_count]
        image_offset += image_count
        posts.append(
            PostResponse(
                id=item.post.id,
                user_id=item.post.user_id,
                username=item.author.username,
                user_avatar=item.author.avatar_key,
                caption=item.post.caption,
                post_img_url=[
                    PostImageResponse(position=image.position, url=image.url)
                    for image in images
                ],
                created_at=item.post.created_at,
                is_private=item.post.is_private,
                is_deleted=item.post.is_deleted,
            )
        )
    return FeedResponse(posts=posts, limit=limit, next_cursor=page.next_cursor)
