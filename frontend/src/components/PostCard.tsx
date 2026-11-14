import { useState } from "react";
import { Heart, MessageCircle, MoreHorizontal, Send } from "lucide-react";
import type { Post } from "../types";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function PostCard({
  post,
  currentUserId,
  onDelete,
}: {
  post: Post;
  currentUserId?: string;
  onDelete?: (postId: string) => Promise<void>;
}) {
  const [imageIndex, setImageIndex] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const image = post.post_img_url[imageIndex];

  return (
    <article className="post-card">
      <header className="post-header">
        <a className="avatar avatar-sm" href={`/profile/${post.username}`}>
          {post.user_avatar ? (
            <img src={post.user_avatar} alt="" />
          ) : (
            post.username.slice(0, 1).toUpperCase()
          )}
        </a>
        <div className="post-author">
          <a href={`/profile/${post.username}`} className="username">
            {post.username}
          </a>
          <span className="muted">{formatDate(post.created_at)}</span>
        </div>
        {currentUserId === post.user_id && onDelete && (
          <div className="post-menu-wrap">
            <button
              className="icon-button"
              aria-label="Post options"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <MoreHorizontal size={20} />
            </button>
            {menuOpen && (
              <button
                className="menu-item"
                onClick={async () => {
                  setMenuOpen(false);
                  await onDelete(post.id);
                }}
              >
                Delete post
              </button>
            )}
          </div>
        )}
      </header>

      <div className="post-image-wrap">
        {image && !imageFailed ? (
          <img
            className="post-image"
            src={image.url}
            alt={post.caption ?? `Post by ${post.username}`}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="image-placeholder">Image unavailable</div>
        )}
        {post.post_img_url.length > 1 && (
          <div className="image-pagination">
            {post.post_img_url.map((item, index) => (
              <button
                key={item.position}
                aria-label={`Show image ${index + 1}`}
                className={index === imageIndex ? "active" : ""}
                onClick={() => {
                  setImageIndex(index);
                  setImageFailed(false);
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="post-actions">
        <div className="post-action-icons">
          <button className="icon-button" aria-label="Like (coming soon)" disabled>
            <Heart size={23} />
          </button>
          <button className="icon-button" aria-label="Comments (coming soon)" disabled>
            <MessageCircle size={23} />
          </button>
          <button className="icon-button" aria-label="Share (coming soon)" disabled>
            <Send size={22} />
          </button>
        </div>
      </div>
      {post.caption && (
        <p className="post-caption">
          <a href={`/profile/${post.username}`} className="username">
            {post.username}
          </a>{" "}
          {post.caption}
        </p>
      )}
    </article>
  );
}
