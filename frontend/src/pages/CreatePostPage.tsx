import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export function CreatePostPage() {
  const navigate = useNavigate();
  const [caption, setCaption] = useState("");
  const [urls, setUrls] = useState([""]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateUrl(index: number, value: string) {
    setUrls((current) => current.map((url, i) => i === index ? value : url));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const imageUrls = urls.map((url) => url.trim()).filter(Boolean);
    if (!imageUrls.length) {
      setError("Add at least one image URL.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await api.createPost(caption.trim(), imageUrls);
      navigate("/", { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create post");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="content-page narrow-page">
      <span className="eyebrow">MAKE SOMETHING</span>
      <h1>Create a post</h1>
      <p className="muted">The current backend accepts image URLs. Direct file upload will be added with the media module.</p>
      <form className="form-stack create-form" onSubmit={(event) => void submit(event)}>
        <label>Caption
          <textarea value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={2200} rows={4} placeholder="Write a caption…" />
          <small>{caption.length}/2200</small>
        </label>
        <div className="form-label">Image URLs <span className="muted">· up to 10</span></div>
        {urls.map((url, index) => (
          <label key={index}>Image {index + 1}
            <input type="url" value={url} onChange={(event) => updateUrl(index, event.target.value)} placeholder="https://images.example.com/photo.jpg" required={index === 0} />
          </label>
        ))}
        {urls.length < 10 && <button type="button" className="add-image-button" onClick={() => setUrls((current) => [...current, ""])}>+ Add another image URL</button>}
        {error && <div className="error-banner">{error}</div>}
        <button className="primary-button" disabled={submitting}>{submitting ? "Publishing…" : "Publish post"}</button>
      </form>
    </section>
  );
}
