import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

export function ExplorePage() {
  const [username, setUsername] = useState("");
  const navigate = useNavigate();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = username.trim().replace(/^@/, "");
    if (value) navigate(`/profile/${encodeURIComponent(value)}`);
  }
  return (
    <section className="content-page narrow-page">
      <span className="eyebrow">DISCOVER</span>
      <h1>Find your people.</h1>
      <p className="muted">Search by an exact username to visit a profile.</p>
      <form className="explore-search" onSubmit={submit}>
        <span>@</span>
        <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="username" autoFocus />
        <button className="primary-button">View profile</button>
      </form>
    </section>
  );
}
