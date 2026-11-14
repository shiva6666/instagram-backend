import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { PostCard } from "../components/PostCard";
import type { Post } from "../types";

export function FeedPage() {
  const { user } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api.feed();
      setPosts(page.posts);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load your feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadFirstPage(); }, [loadFirstPage]);

  async function loadMore() {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await api.feed(20, cursor);
      setPosts((current) => [...current, ...page.posts]);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load more posts");
    } finally {
      setLoadingMore(false);
    }
  }

  async function deletePost(postId: string) {
    if (!window.confirm("Delete this post?")) return;
    await api.deletePost(postId);
    setPosts((current) => current.filter((post) => post.id !== postId));
  }

  return (
    <div className="feed-page">
      <div className="page-heading">
        <div><span className="eyebrow">YOUR DAILY WINDOW</span><h1>Home</h1></div>
        <Link to="/create" className="text-link">Share a moment ↗</Link>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {loading ? <div className="loading-state">Gathering your feed…</div> :
        posts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">✳</div>
            <h2>Your feed starts here.</h2>
            <p>Follow people to see their posts, or share your first moment.</p>
            <Link to="/explore" className="primary-button inline-button">Find people</Link>
          </div>
        ) : (
          <div className="feed-list">
            {posts.map((post) => (
              <PostCard key={post.id} post={post} currentUserId={user?.id} onDelete={deletePost} />
            ))}
            {cursor && <button className="secondary-button load-more" onClick={() => void loadMore()} disabled={loadingMore}>{loadingMore ? "Loading…" : "Load more"}</button>}
          </div>
        )}
    </div>
  );
}
