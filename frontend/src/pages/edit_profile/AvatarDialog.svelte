<script module lang="ts">
  // Avatar state being edited in the dialog. Nothing hits the server until
  // "Save", which hands the draft to `onsave`.
  export interface AvatarDraft {
    // What to show as the photo: the server URL, a blob: URL for a newly
    // cropped image, or null for no photo (icon or letter fallback).
    photoUrl: string | null;
    // Newly selected image to upload on save
    file: File | null;
    // Uncropped source of `file`, kept so the crop can be adjusted later
    originalFile: File | null;
    sizeNote: string | null;
    sourceWarning: string | null;
    icon: string;
    color: string;
  }
</script>

<script lang="ts">
  import { onMount, untrack } from "svelte";
  import AvatarCropper from "./AvatarCropper.svelte";
  import AvatarPreview from "./AvatarPreview.svelte";
  import {
    decodeImage,
    exportAvatar,
    formatBytes,
    ImageDecodeError,
    MIN_SOURCE_SIZE,
    type CropRect,
  } from "./image";

  interface Props {
    initial: AvatarDraft;
    iconChoices: string[];
    colorChoices: Record<string, string>;
    iconSvgs: Record<string, string>;
    letter: string;
    // Persist the draft; resolves to an error message, or null on success
    onsave: (draft: AvatarDraft) => Promise<string | null>;
    onclose: () => void;
  }
  const { initial, iconChoices, colorChoices, iconSvgs, letter, onsave, onclose }: Props =
    $props();

  // The dialog is mounted fresh each time it opens, so reading props once is
  // intentional.
  const colorEntries = untrack(() => Object.entries(colorChoices));

  let draft: AvatarDraft = $state(untrack(() => ({ ...initial })));
  let tab: "photo" | "icon" = $state(
    untrack(() => (!initial.photoUrl && initial.icon && iconChoices.length ? "icon" : "photo")),
  );
  let error: string | null = $state(null);
  let cropBitmap: ImageBitmap | null = $state(null);
  let pendingOriginal: File | null = null;
  let dragging = $state(false);
  let dialogEl: HTMLDialogElement;

  // blob: URLs created while the dialog is open, revoked when it closes
  const createdUrls: string[] = [];

  onMount(() => {
    dialogEl.showModal();
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  });

  let closed = false;

  let saving = $state(false);

  const changed = $derived(
    draft.file !== null ||
      draft.photoUrl !== initial.photoUrl ||
      draft.icon !== initial.icon ||
      draft.color !== initial.color,
  );

  function close() {
    if (closed) return;
    closed = true;
    for (const url of createdUrls) URL.revokeObjectURL(url);
    onclose();
  }

  async function save() {
    saving = true;
    error = null;
    try {
      error = await onsave($state.snapshot(draft) as AvatarDraft);
    } catch (e: any) {
      error = e.message ?? "Save failed";
    } finally {
      saving = false;
    }
    if (!error) close();
  }

  async function handleImageFile(file: File) {
    tab = "photo";
    error = null;
    if (!file.type.startsWith("image/") && !/\.hei[cf]$/i.test(file.name)) {
      error = "Please select an image file";
      return;
    }
    if (file.size > 20 * 1048576) {
      error = `Image must be under 20MB (yours is ${formatBytes(file.size)})`;
      return;
    }
    // Small GIFs pass through untouched so animation survives; cropping or
    // re-encoding through a canvas would freeze the first frame.
    if (file.type === "image/gif" && file.size <= 1048576) {
      setPhoto(file, null, null, null);
      return;
    }
    try {
      const bitmap = await decodeImage(file);
      draft.sourceWarning =
        Math.min(bitmap.width, bitmap.height) < MIN_SOURCE_SIZE
          ? `This image is only ${bitmap.width}×${bitmap.height} — it may look blurry`
          : null;
      pendingOriginal = file;
      cropBitmap = bitmap;
    } catch (e: any) {
      error = e instanceof ImageDecodeError ? e.message : "Couldn't read that image";
    }
  }

  function setPhoto(
    file: File,
    originalFile: File | null,
    sizeNote: string | null,
    sourceWarning: string | null,
  ) {
    const url = URL.createObjectURL(file);
    createdUrls.push(url);
    draft.file = file;
    draft.originalFile = originalFile;
    draft.photoUrl = url;
    draft.sizeNote = sizeNote;
    draft.sourceWarning = sourceWarning;
  }

  async function applyCrop(crop: CropRect) {
    if (!cropBitmap || !pendingOriginal) return;
    const original = pendingOriginal;
    try {
      const blob = await exportAvatar(cropBitmap, crop);
      const ext = blob.type === "image/webp" ? "webp" : "jpg";
      setPhoto(
        new File([blob], `avatar.${ext}`, { type: blob.type }),
        original,
        blob.size < original.size
          ? `${formatBytes(original.size)} → ${formatBytes(blob.size)}`
          : formatBytes(blob.size),
        draft.sourceWarning,
      );
    } catch (e: any) {
      error = e.message;
    }
    cropBitmap = null;
    pendingOriginal = null;
  }

  function cancelCrop() {
    cropBitmap = null;
    pendingOriginal = null;
  }

  async function adjustCrop() {
    if (!draft.originalFile) return;
    try {
      pendingOriginal = draft.originalFile;
      cropBitmap = await decodeImage(draft.originalFile);
    } catch {
      error = "Couldn't re-open that image";
    }
  }

  function removePicture() {
    error = null;
    if (draft.photoUrl) {
      draft.photoUrl = null;
      draft.file = null;
      draft.originalFile = null;
      draft.sizeNote = null;
      draft.sourceWarning = null;
    } else {
      draft.icon = "";
      draft.color = "";
    }
  }

  // Picking an icon means "use this instead of a photo"
  function pickIcon(icon: string, color: string) {
    draft.icon = icon;
    draft.color = color;
    draft.photoUrl = null;
    draft.file = null;
    draft.originalFile = null;
    draft.sizeNote = null;
    draft.sourceWarning = null;
  }

  // Random pick among the first few colors, highlighted in the swatches but
  // not applied until an icon is chosen
  let suggestedColor = $state("");

  function showIconTab() {
    tab = "icon";
    if (!draft.color && !suggestedColor && colorEntries.length) {
      const idx = Math.floor(Math.random() * Math.min(4, colorEntries.length));
      suggestedColor = colorEntries[idx]![1];
    }
  }

  function onFileInput(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    // Reset so picking the same file again (e.g. after canceling the crop)
    // still fires change
    input.value = "";
    if (file) handleImageFile(file);
  }

  function onPaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) handleImageFile(file);
        return;
      }
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    const file = e.dataTransfer?.files[0];
    if (file) handleImageFile(file);
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    dragging = true;
  }

  function onDragLeave(e: DragEvent) {
    // Ignore leave events fired when moving between child elements
    if (!(e.currentTarget as Node).contains(e.relatedTarget as Node | null)) {
      dragging = false;
    }
  }

  function onDialogCancel(e: Event) {
    // Dismissing the file picker fires a bubbling "cancel" on the <input>;
    // only react to the dialog's own cancel (Escape).
    if (e.target !== dialogEl) return;
    // Escape backs out of the crop step first. Browsers don't always let
    // this be prevented, so onclose below catches any native close.
    if (cropBitmap) {
      e.preventDefault();
      cancelCrop();
    }
  }

  const activeColor = $derived(draft.color || suggestedColor || colorEntries[0]?.[1] || "");
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog
  bind:this={dialogEl}
  aria-label="Profile picture"
  oncancel={onDialogCancel}
  onclose={() => close()}
  onclick={(e) => {
    if (e.target === dialogEl && !cropBitmap) close();
  }}
  ondrop={onDrop}
  ondragover={onDragOver}
  ondragleave={onDragLeave}
>
  <div class="body" class:dragging>
    {#if cropBitmap}
      <h2>Crop your photo</h2>
      <p class="hint">Drag to reposition, scroll or slide to zoom.</p>
      <AvatarCropper bitmap={cropBitmap} onapply={applyCrop} oncancel={cancelCrop} />
    {:else}
      <h2>Profile picture</h2>

      <div class="current">
        <AvatarPreview
          photoUrl={draft.photoUrl}
          icon={draft.icon}
          color={draft.color}
          {iconSvgs}
          {letter}
          size={112}
        />
        {#if draft.file && draft.photoUrl}
          <div class="size-previews" title="How your photo looks at smaller sizes">
            <img src={draft.photoUrl} alt="" style="width: 40px; height: 40px;" />
            <img src={draft.photoUrl} alt="" style="width: 24px; height: 24px;" />
          </div>
        {/if}
      </div>

      {#if iconChoices.length}
        <div class="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "photo"}
            class:active={tab === "photo"}
            onclick={() => (tab = "photo")}>Photo</button
          >
          <button
            type="button"
            role="tab"
            aria-selected={tab === "icon"}
            class:active={tab === "icon"}
            onclick={showIconTab}>Icon</button
          >
        </div>
      {/if}

      {#if tab === "photo"}
        <label class="dropzone">
          <input type="file" accept="image/*" onchange={onFileInput} hidden />
          <span class="dropzone-title">
            {draft.photoUrl ? "Choose a different photo" : "Upload a photo"}
          </span>
          <span class="hint">Click to browse, drag an image here, or paste.</span>
        </label>
        {#if draft.file && draft.originalFile}
          <button type="button" class="link-btn" onclick={adjustCrop}>Adjust crop</button>
        {/if}
        {#if draft.sizeNote}
          <p class="size-note">{draft.sizeNote}</p>
        {/if}
        {#if draft.sourceWarning}
          <p class="warning">{draft.sourceWarning}</p>
        {/if}
      {:else}
        {#if draft.photoUrl}
          <p class="hint">Picking an icon will replace your photo.</p>
        {/if}
        <div class="icon-grid">
          {#each iconChoices as name}
            <button
              type="button"
              class="icon-btn"
              class:selected={!draft.photoUrl && draft.icon === name}
              onclick={() => pickIcon(name, activeColor)}
              title={name}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 16 16"
                fill="currentColor"
              >
                {@html iconSvgs[name]}
              </svg>
            </button>
          {/each}
        </div>
        <div class="color-row">
          {#each colorEntries as [name, hex]}
            <button
              type="button"
              class="color-btn"
              class:selected={activeColor === hex}
              style="background: {hex};"
              onclick={() => pickIcon(draft.icon || iconChoices[0]!, hex)}
              title={name}
            ></button>
          {/each}
        </div>
      {/if}

      {#if error}
        <p class="error">{error}</p>
      {/if}

      <div class="footer">
        {#if draft.photoUrl || (draft.icon && draft.color)}
          <button type="button" class="remove-btn" onclick={removePicture}>
            {draft.photoUrl ? "Remove photo" : "Remove icon"}
          </button>
        {/if}
        <span class="spacer"></span>
        <button type="button" class="btn" onclick={() => close()} disabled={saving}>
          Cancel
        </button>
        <button type="button" class="btn primary" onclick={save} disabled={!changed || saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    {/if}
  </div>
</dialog>

<style>
  dialog {
    border: none;
    border-radius: 8px;
    padding: 0;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
    width: min(360px, calc(100vw - 32px));
    box-sizing: border-box;
  }
  dialog::backdrop {
    background: rgba(0, 0, 0, 0.4);
  }
  .body {
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    border: 2px solid transparent;
    border-radius: 8px;
  }
  .body.dragging {
    border-color: #4a90d9;
    background: #f0f7ff;
  }
  h2 {
    font-size: 1.1rem;
    margin: 0;
  }
  .hint {
    font-size: 0.8rem;
    color: #888;
    margin: 0;
    line-height: 1.4;
  }
  .current {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 0.5rem;
    margin: 0.5rem 0;
  }
  .size-previews {
    display: flex;
    align-items: flex-end;
    gap: 0.4rem;
  }
  .size-previews img {
    border-radius: 50%;
    object-fit: cover;
  }
  .tabs {
    display: flex;
    border-bottom: 1px solid #ddd;
  }
  .tabs button {
    flex: 1;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    padding: 0.45rem;
    font-size: 0.9rem;
    cursor: pointer;
    color: #666;
  }
  .tabs button.active {
    border-bottom-color: #333;
    color: #111;
    font-weight: 600;
  }
  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 1.25rem 1rem;
    border: 2px dashed #ccc;
    border-radius: 8px;
    cursor: pointer;
    text-align: center;
  }
  .dropzone:hover {
    border-color: #4a90d9;
    background: #f7fbff;
  }
  .dropzone-title {
    font-weight: 600;
    font-size: 0.9rem;
  }
  .link-btn {
    align-self: center;
    font-size: 0.8rem;
    color: #4a90d9;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .link-btn:hover {
    text-decoration: underline;
  }
  .size-note {
    font-size: 0.75rem;
    color: #060;
    margin: 0;
    text-align: center;
  }
  .warning {
    font-size: 0.75rem;
    color: #a60;
    margin: 0;
    text-align: center;
  }
  .icon-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, 36px);
    gap: 4px;
    justify-content: center;
  }
  .icon-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid transparent;
    border-radius: 6px;
    background: white;
    cursor: pointer;
    color: #555;
    padding: 0;
  }
  .icon-btn:hover {
    background: #eee;
  }
  .icon-btn.selected {
    border-color: #333;
    background: #e8e8e8;
  }
  .color-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    margin-top: 0.25rem;
  }
  .color-btn {
    width: 28px;
    height: 28px;
    border: 2px solid transparent;
    border-radius: 50%;
    cursor: pointer;
    padding: 0;
  }
  .color-btn:hover {
    opacity: 0.8;
  }
  .color-btn.selected {
    border-color: #333;
    box-shadow:
      0 0 0 2px white,
      0 0 0 4px #333;
  }
  .error {
    color: #c00;
    font-size: 0.85rem;
    margin: 0;
  }
  .footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .spacer {
    flex: 1;
  }
  .remove-btn {
    font-size: 0.8rem;
    color: #c00;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .remove-btn:hover {
    text-decoration: underline;
  }
  .btn {
    padding: 0.3rem 0.9rem;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
    border: 1px solid #ccc;
    background: white;
  }
  .btn:hover {
    background: #eee;
  }
  .btn.primary {
    background: #4a90d9;
    border-color: #4a90d9;
    color: white;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .btn.primary:hover:not(:disabled) {
    background: #3a7fc4;
  }
</style>
