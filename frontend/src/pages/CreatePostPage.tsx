import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ImagePlus, LoaderCircle, X } from "lucide-react";
import { api } from "../lib/api";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

interface SelectedImage {
  id: string;
  file: File;
  previewUrl: string;
  mediaId?: string;
  uploadUrl?: string;
  uploaded: boolean;
  ready: boolean;
  status: string;
  error?: string;
}

function messageOf(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

export function CreatePostPage() {
  const navigate = useNavigate();
  const [caption, setCaption] = useState("");
  const [images, setImages] = useState<SelectedImage[]>([]);
  const imagesRef = useRef<SelectedImage[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  function replaceImages(update: (current: SelectedImage[]) => SelectedImage[]) {
    setImages((current) => {
      const next = update(current);
      imagesRef.current = next;
      return next;
    });
  }

  function updateImage(id: string, patch: Partial<SelectedImage>) {
    replaceImages((current) => current.map((image) =>
      image.id === id ? { ...image, ...patch } : image,
    ));
  }

  useEffect(() => () => {
    imagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl));
  }, []);

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = "";
    setError("");

    const remaining = 10 - images.length;
    if (remaining <= 0) {
      setError("A post can contain up to 10 images.");
      return;
    }

    const accepted: SelectedImage[] = [];
    for (const file of selected) {
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(`${file.name}: choose a JPEG, PNG, or WebP image.`);
        continue;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError(`${file.name}: images must be 10 MB or smaller.`);
        continue;
      }
      if (accepted.length >= remaining) {
        setError("A post can contain up to 10 images.");
        break;
      }
      accepted.push({
        id: crypto.randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
        uploaded: false,
        ready: false,
        status: "Ready to upload",
      });
    }
    if (accepted.length) replaceImages((current) => [...current, ...accepted]);
  }

  async function removeImage(image: SelectedImage) {
    if (submitting) return;
    setError("");
    if (image.mediaId) {
      try {
        await api.discardMedia(image.mediaId);
      } catch (cause) {
        setError(messageOf(cause, "Could not discard this upload."));
        return;
      }
    }
    URL.revokeObjectURL(image.previewUrl);
    replaceImages((current) => current.filter((item) => item.id !== image.id));
  }

  async function ensureMediaReady(image: SelectedImage): Promise<SelectedImage> {
    let current = image;

    if (!current.mediaId || !current.uploadUrl) {
      const ticket = await api.createMediaUpload(current.file.type, current.file.size);
      current = {
        ...current,
        mediaId: ticket.media_id,
        uploadUrl: ticket.upload_url,
        status: "Uploading original",
        error: undefined,
      };
      updateImage(current.id, current);
    }

    if (!current.mediaId || !current.uploadUrl) {
      throw new Error("Upload ticket is missing. Remove this image and select it again.");
    }

    if (!current.uploaded) {
      await api.uploadMediaObject(current.uploadUrl, current.file, current.file.type);
      current = { ...current, uploaded: true, status: "Verifying and processing" };
      updateImage(current.id, current);
    }

    if (!current.mediaId) {
      throw new Error("Media upload could not be initialized.");
    }
    const result = await api.completeMediaUpload(current.mediaId);
    if (result.status !== "ready") {
      throw new Error(result.failure_reason || `Image processing status: ${result.status}`);
    }

    current = { ...current, ready: true, status: "Processed and ready", error: undefined };
    updateImage(current.id, current);
    return current;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!images.length) {
      setError("Choose at least one image.");
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      const readyImages: SelectedImage[] = [];
      for (const image of images) {
        if (image.ready && image.mediaId) {
          readyImages.push(image);
          continue;
        }
        updateImage(image.id, { status: image.uploaded ? "Retrying processing" : "Preparing upload", error: undefined });
        try {
          readyImages.push(await ensureMediaReady(image));
        } catch (cause) {
          const message = messageOf(cause, "Could not upload this image.");
          updateImage(image.id, { status: "Needs attention", error: message });
          throw new Error(`${image.file.name}: ${message}`);
        }
      }

      await api.createPost(caption, readyImages.map((image) => image.mediaId!));
      navigate("/", { replace: true });
    } catch (cause) {
      setError(messageOf(cause, "Could not publish this post."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="content-page narrow-page">
      <span className="eyebrow">MAKE SOMETHING</span>
      <h1>Create a post</h1>
      <p className="muted">Choose up to 10 JPEG, PNG, or WebP images. We upload them directly to storage, validate and process them, then attach the ready media to your post.</p>

      <form className="form-stack create-form" onSubmit={(event) => void submit(event)}>
        <label>Caption
          <textarea value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={2200} rows={4} placeholder="Write a caption…" />
          <small>{caption.length}/2200</small>
        </label>

        <div className="upload-heading">
          <div><strong>Photos</strong> <span className="muted">· {images.length}/10</span></div>
          <button type="button" className="secondary-button" onClick={() => fileInput.current?.click()} disabled={submitting || images.length >= 10}>
            <ImagePlus size={16} /> Add photos
          </button>
          <input
            ref={fileInput}
            className="visually-hidden"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={selectFiles}
          />
        </div>

        {images.length > 0 ? (
          <div className="upload-grid">
            {images.map((image) => (
              <div className="upload-tile" key={image.id}>
                <img src={image.previewUrl} alt={image.file.name} />
                <button type="button" className="upload-remove" aria-label={`Remove ${image.file.name}`} onClick={() => void removeImage(image)} disabled={submitting}>
                  <X size={15} />
                </button>
                <div className="upload-tile-info">
                  <span>{image.file.name}</span>
                  <small className={image.error ? "upload-error" : "muted"}>
                    {image.error || image.status}
                  </small>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <button type="button" className="upload-dropzone" onClick={() => fileInput.current?.click()} disabled={submitting}>
            <ImagePlus size={28} />
            <strong>Choose photos</strong>
            <span>JPEG, PNG, WebP · up to 10 MB each</span>
          </button>
        )}

        {error && <div className="error-banner" role="alert">{error}</div>}
        <button className="primary-button" disabled={submitting || images.length === 0}>
          {submitting ? <><LoaderCircle size={15} className="spin" /> Uploading and publishing…</> : "Publish post"}
        </button>
      </form>
    </section>
  );
}
