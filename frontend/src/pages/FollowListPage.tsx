import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { FollowUser } from "../types";

export function FollowListPage() {
  const { username = "", connection = "followers" } = useParams();
  const kind = connection === "following" ? "following" : "followers";
  const [users, setUsers] = useState<FollowUser[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api.followList(username, kind);
      setUsers(page.users);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load this list.");
    } finally {
      setLoading(false);
    }
  }, [username, kind]);

  useEffect(() => { void load(); }, [load]);

  async function loadMore() {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await api.followList(username, kind, 20, cursor);
      setUsers((current) => [...current, ...page.users]);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load more accounts.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <section className="content-page narrow-page">
      <Link to={`/profile/${encodeURIComponent(username)}`} className="text-link">← Back to profile</Link>
      <span className="eyebrow connection-eyebrow">COMMUNITY</span>
      <h1>{kind === "followers" ? "Followers" : "Following"}</h1>
      <p className="muted">@{username}</p>

      {error && <div className="error-banner">{error}</div>}
      {loading ? <div className="loading-state">Loading accounts…</div> :
        users.length ? (
          <div className="connection-list">
            {users.map((person) => (
              <Link to={`/profile/${encodeURIComponent(person.username)}`} className="connection-row" key={person.id}>
                <div className="avatar avatar-sm">{person.username.slice(0, 1).toUpperCase()}</div>
                <div><strong>{person.username}</strong><span>{person.bio || (person.is_private ? "Private account" : "On Frame")}</span></div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-state compact"><h2>No accounts here yet</h2><p>This list is currently empty.</p></div>
        )}
      {cursor && <button className="secondary-button load-more" onClick={() => void loadMore()} disabled={loadingMore}>{loadingMore ? "Loading…" : "Load more"}</button>}
    </section>
  );
}
