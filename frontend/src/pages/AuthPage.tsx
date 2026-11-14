import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await signIn(email, password);
      } else {
        await signUp({ username, email, password, is_private: isPrivate });
      }
      navigate("/", { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-art">
        <div className="auth-art-copy">
          <span className="eyebrow">YOUR WORLD, IN FRAMES</span>
          <h1>Small moments.<br /><em>Big stories.</em></h1>
          <p>A place to share the things worth remembering.</p>
        </div>
        <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
        <div className="art-photo art-photo-one" /><div className="art-photo art-photo-two" />
        <div className="art-photo art-photo-three" />
      </div>
      <section className="auth-panel">
        <Link to="/" className="brand">frame<span>.</span></Link>
        <div className="auth-form-wrap">
          <span className="eyebrow">{mode === "login" ? "WELCOME BACK" : "JOIN THE COMMUNITY"}</span>
          <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
          <p className="muted">{mode === "login" ? "Pick up where you left off." : "Start sharing your point of view."}</p>
          <form onSubmit={(event) => void handleSubmit(event)} className="form-stack">
            {mode === "register" && (
              <label>Username
                <input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={30} pattern="[a-zA-Z0-9_.]+" autoComplete="username" required />
              </label>
            )}
            <label>Email address
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
            </label>
            <label>Password
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={mode === "register" ? 12 : 1} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} required />
              {mode === "register" && <small>At least 12 characters.</small>}
            </label>
            {mode === "register" && (
              <label className="checkbox-label">
                <input type="checkbox" checked={isPrivate} onChange={(event) => setIsPrivate(event.target.checked)} />
                Make my account private
              </label>
            )}
            {error && <div className="error-banner" role="alert">{error}</div>}
            <button className="primary-button" disabled={submitting}>
              {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          <p className="auth-switch">
            {mode === "login" ? "New to Frame?" : "Already have an account?"}{" "}
            <Link to={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "Create an account" : "Sign in"}</Link>
          </p>
        </div>
        <span className="auth-legal">A learning project · FastAPI + React</span>
      </section>
    </main>
  );
}
