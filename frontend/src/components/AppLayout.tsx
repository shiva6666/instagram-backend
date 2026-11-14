import { useState } from "react";
import { Compass, House, LogOut, PlusSquare, Search, UserRound } from "lucide-react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AppLayout() {
  const { user, signOut } = useAuth();
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">frame<span>.</span></Link>
        <nav className="main-nav">
          <NavLink to="/" end><House /> <span>Home</span></NavLink>
          <NavLink to="/explore"><Compass /> <span>Explore</span></NavLink>
          <NavLink to="/create"><PlusSquare /> <span>Create</span></NavLink>
          {user && <NavLink to={`/profile/${user.username}`}><UserRound /> <span>Profile</span></NavLink>}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-link logout-link" onClick={() => void handleSignOut()}>
            <LogOut /> <span>Log out</span>
          </button>
          <div className="sidebar-user">
            <div className="avatar avatar-sm">{user?.username.slice(0, 1).toUpperCase()}</div>
            <div><strong>{user?.username}</strong><span className="muted">Your account</span></div>
          </div>
        </div>
      </aside>

      <header className="mobile-header">
        <Link to="/" className="brand">frame<span>.</span></Link>
        <button className="icon-button" onClick={() => navigate("/explore")} aria-label="Explore">
          <Search />
        </button>
      </header>

      <main className="main-content"><Outlet /></main>

      <aside className="right-rail">
        <form
          className="search-box"
          onSubmit={(event) => {
            event.preventDefault();
            if (search.trim()) navigate(`/profile/${encodeURIComponent(search.trim().replace(/^@/, ""))}`);
          }}
        >
          <Search size={17} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a username" />
        </form>
        <div className="rail-note">
          <span className="eyebrow">BUILT IN PUBLIC</span>
          <h3>A social app, one system at a time.</h3>
          <p>This frontend is a client for your FastAPI modules. Likes, comments and media uploads will arrive when their backend APIs do.</p>
        </div>
        <p className="footer-note">About · Help · Privacy · Terms<br />© 2026 Frame</p>
      </aside>
    </div>
  );
}
