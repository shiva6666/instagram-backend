import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";

export function EditProfilePage() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();
  const [bio, setBio] = useState(user?.bio ?? "");
  const [isPrivate, setIsPrivate] = useState(user?.is_private ?? false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const updated = await api.updateMyProfile({ bio: bio.trim() || null, is_private: isPrivate });
      updateUser({ ...user!, ...updated });
      navigate(`/profile/${encodeURIComponent(updated.username)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="content-page narrow-page">
      <span className="eyebrow">YOUR ACCOUNT</span>
      <h1>Edit profile</h1>
      <p className="muted">Update the details that are visible on your profile. Your email and username are not editable here.</p>
      <form className="form-stack" onSubmit={(event) => void submit(event)}>
        <label>Username
          <input value={user?.username ?? ""} disabled />
        </label>
        <label>Bio
          <textarea value={bio} onChange={(event) => setBio(event.target.value)} maxLength={500} rows={5} placeholder="A little about you…" />
          <small>{bio.length}/500</small>
        </label>
        <label className="checkbox-label">
          <input type="checkbox" checked={isPrivate} onChange={(event) => setIsPrivate(event.target.checked)} />
          Make my account private
        </label>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="form-actions">
          <Link to={`/profile/${user?.username ?? ""}`} className="secondary-button">Cancel</Link>
          <button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </section>
  );
}
