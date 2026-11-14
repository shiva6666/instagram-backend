import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { PostCard } from "../components/PostCard";
import type { FollowCounts, FollowStatus, Post, PublicProfile } from "../types";

export function ProfilePage() {
  const { username = "" } = useParams();
  const { user } = useAuth();
  const isOwnProfile = user?.username.toLowerCase() === username.toLowerCase();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [counts, setCounts] = useState<FollowCounts | null>(null);
  const [relationship, setRelationship] = useState<FollowStatus | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [profileResult, countsResult, postsResult, relationshipResult] = await Promise.all([
        api.profile(username),
        api.counts(username),
        api.profilePosts(username),
        isOwnProfile ? Promise.resolve(null) : api.relationship(username),
      ]);
      setProfile(profileResult);
      setCounts(countsResult);
      setPosts(postsResult.posts);
      setCursor(postsResult.next_cursor);
      setRelationship(relationshipResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load profile");
    } finally {
      setLoading(false);
    }
  }, [username, isOwnProfile]);

  useEffect(() => { void load(); }, [load]);

  async function toggleFollow() {
    if (!relationship || busy) return;
    setBusy(true);
    try {
      if (relationship.status) {
        await api.unfollow(username);
      } else {
        await api.follow(username);
      }
      const [nextRelationship, nextCounts] = await Promise.all([api.relationship(username), api.counts(username)]);
      setRelationship(nextRelationship);
      setCounts(nextCounts);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update follow");
    } finally {
      setBusy(false);
    }
  }

  async function loadMore() {
    if (!cursor) return;
    try {
      const page = await api.profilePosts(username, 20, cursor);
      setPosts((current) => [...current, ...page.posts]);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load posts");
    }
  }

  if (loading) return <div className="loading-state">Loading profile…</div>;
  if (error && !profile) return <div className="content-page"><div className="error-banner">{error}</div></div>;
  if (!profile) return null;

  const followLabel = relationship?.is_following ? "Following" : relationship?.request_pending ? "Requested" : "Follow";

  return (
    <section className="content-page profile-page">
      <header className="profile-header">
        <div className="profile-avatar avatar">{profile.username.slice(0, 1).toUpperCase()}</div>
        <div className="profile-info">
          <div className="profile-title-row"><h1>{profile.username}</h1>
            {!isOwnProfile && <button className={relationship?.status ? "secondary-button" : "primary-button"} onClick={() => void toggleFollow()} disabled={busy}>{busy ? "…" : followLabel}</button>}
            {isOwnProfile && <span className="profile-you">You</span>}
          </div>
          <div className="profile-stats">
            <span><strong>{posts.length}</strong> posts</span>
            <span><strong>{counts?.followers ?? "—"}</strong> followers</span>
            <span><strong>{counts?.following ?? "—"}</strong> following</span>
          </div>
          {profile.bio && <p className="profile-bio">{profile.bio}</p>}
          {profile.is_private && <span className="private-label">Private account</span>}
        </div>
      </header>
      <div className="section-rule"><span>POSTS</span></div>
      {error && <div className="error-banner">{error}</div>}
      {posts.length ? <div className="profile-posts">{posts.map((post) => <PostCard key={post.id} post={post} currentUserId={user?.id} />)}</div> :
        <div className="empty-state compact"><h2>No posts yet</h2><p>When this account shares something, it will appear here.</p></div>}
      {cursor && <button className="secondary-button load-more" onClick={() => void loadMore()}>Load more</button>}
    </section>
  );
}
