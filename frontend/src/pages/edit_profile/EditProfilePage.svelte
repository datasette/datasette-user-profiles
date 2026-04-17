<script lang="ts">
  import createClient from "openapi-fetch";
  import type { paths } from "../../../api.d.ts";
  import { loadPageData } from "../../page_data/load";
  import type { EditProfilePageData } from "../../page_data/EditProfilePageData.types";

  const client = createClient<paths>({ baseUrl: "/" });
  const pageData = loadPageData<EditProfilePageData>();
  const profile = pageData.profile;

  let displayName = $state(profile.display_name ?? "");
  let bio = $state(profile.bio ?? "");
  let email = $state(profile.email ?? "");
  let saving = $state(false);
  let error: string | null = $state(null);
  let success: string | null = $state(null);

  const iconChoices = pageData.avatar_icon_choices ?? [];
  const colorChoices = pageData.avatar_color_choices ?? {};
  const colorEntries = Object.entries(colorChoices);
  const iconSvgs = pageData.avatar_icon_svgs ?? {};
  let avatarIcon = $state(profile.avatar_icon ?? "");
  let avatarColor = $state(profile.avatar_color ?? "");
  let pickerOpen = $state(false);
  let anchorEl: HTMLDivElement;

  function openPicker() {
    if (pickerOpen) { pickerOpen = false; return; }
    if (!avatarIcon && iconChoices.length) {
      avatarIcon = iconChoices[0]!;
    }
    if (!avatarColor && colorEntries.length) {
      const idx = Math.floor(Math.random() * Math.min(4, colorEntries.length));
      avatarColor = colorEntries[idx]![1];
    }
    pickerOpen = true;
  }

  function onClickOutside(e: MouseEvent) {
    if (pickerOpen && anchorEl && !anchorEl.contains(e.target as Node)) {
      pickerOpen = false;
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && pickerOpen) {
      pickerOpen = false;
    }
  }

  $effect(() => {
    if (pickerOpen) {
      document.addEventListener("click", onClickOutside, true);
      document.addEventListener("keydown", onKeydown);
      return () => {
        document.removeEventListener("click", onClickOutside, true);
        document.removeEventListener("keydown", onKeydown);
      };
    }
  });

  function makeIconSvg(name: string, color: string, size: number = 40): string {
    const inner = iconSvgs[name];
    if (!inner || !color) return "";
    const iconSize = size * 0.5625;
    const offset = (size - iconSize) / 2;
    const scale = iconSize / 16;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="${color}"/><g transform="translate(${offset.toFixed(1)},${offset.toFixed(1)}) scale(${scale.toFixed(4)})" fill="white">${inner}</g></svg>`;
  }

  let hasPhoto = $state(profile.has_photo);
  let selectedFile: File | null = $state(null);
  let photoPreview: string | null = $state(
    profile.has_photo
      ? `/-/api/user-profile/photo/${encodeURIComponent(profile.actor_id)}`
      : null,
  );
  let photoError: string | null = $state(null);

  function readFileAsBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        resolve(dataUrl.split(",")[1]!);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function handleImageFile(file: File) {
    if (!file.type.startsWith("image/")) {
      photoError = "Please select an image file";
      return;
    }
    if (file.size > 1048576) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      photoError = `Image must be under 1MB (yours is ${sizeMB}MB)`;
      return;
    }
    selectedFile = file;
    photoError = null;
    const reader = new FileReader();
    reader.onload = () => {
      photoPreview = reader.result as string;
    };
    reader.readAsDataURL(file);
  }

  function onFileInput(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
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

  let dragging = $state(false);

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
    e.preventDefault();
    dragging = false;
  }

  async function deletePhoto() {
    saving = true;
    photoError = null;
    try {
      await client.POST("/-/api/user-profile/photo/delete" as any, { body: {} });
      hasPhoto = false;
      photoPreview = null;
      selectedFile = null;
    } catch (e: any) {
      photoError = e.message;
    } finally {
      saving = false;
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    saving = true;
    error = null;
    success = null;
    photoError = null;
    try {
      // Upload photo if a new one was selected
      if (selectedFile) {
        const base64 = await readFileAsBase64(selectedFile);
        const { data: photoData, error: photoApiError } = await client.POST(
          "/-/api/user-profile/photo",
          {
            body: {
              photo_data: base64,
              content_type: selectedFile.type || "image/jpeg",
            } as any,
          },
        );
        if (photoApiError) {
          error = (photoApiError as any).error ?? "Photo upload failed";
          return;
        }
        if (photoData && !(photoData as any).ok) {
          error = (photoData as any).error ?? "Photo upload failed";
          return;
        }
        hasPhoto = true;
        selectedFile = null;
        photoPreview = `/-/api/user-profile/photo/${encodeURIComponent(profile.actor_id)}?t=${Date.now()}`;
      }

      // Save profile fields
      const { data, error: apiError } = await client.POST(
        "/-/api/user-profile/update",
        {
          body: {
            display_name: displayName || null,
            bio: bio || null,
            email: email || null,
            avatar_icon: avatarIcon || null,
            avatar_color: avatarColor || null,
          } as any,
        },
      );
      if (apiError) {
        error = (apiError as any).error ?? "Save failed";
        return;
      }
      if (data && !(data as any).ok) {
        error = (data as any).error ?? "Save failed";
        return;
      }
      success = "Profile saved";
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }
</script>

<main>
  <h1>Edit Profile</h1>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <section
    class="photo-section"
    class:dragging
    onpaste={onPaste}
    ondrop={onDrop}
    ondragover={onDragOver}
    ondragleave={onDragLeave}
  >
    <div class="photo-section-inner">
      <div class="photo-info">
        <h2>Profile Photo</h2>
        <p class="hint">Drag/drop, or paste an image.<br/>1MB max, JPG, PNG, or GIF</p>
        <div class="photo-actions">
          <label class="file-btn">
            {hasPhoto || selectedFile ? "Change photo" : "Upload photo"}
            <input type="file" accept="image/*" onchange={onFileInput} hidden />
          </label>
          {#if selectedFile}
            <button
              type="button"
              onclick={() => { selectedFile = null; photoPreview = hasPhoto ? `/-/api/user-profile/photo/${encodeURIComponent(profile.actor_id)}` : null; }}
              class="clear-btn"
            >
              Undo
            </button>
          {/if}
        </div>
      </div>
      <div class="photo-preview-area">
        <div class="avatar-anchor" bind:this={anchorEl}>
          {#if photoPreview}
            <img src={photoPreview} alt="{profile.display_name || profile.actor_id}" class="photo-preview" />
          {:else if avatarIcon && avatarColor}
            <div class="avatar-icon-preview">
              {@html makeIconSvg(avatarIcon, avatarColor, 80)}
            </div>
          {:else}
            <div class="photo-placeholder">
              {(profile.display_name || profile.actor_id).charAt(0).toUpperCase()}
            </div>
          {/if}

          {#if pickerOpen}
            <div class="icon-picker-popover">
              <div class="icon-grid">
                {#each iconChoices as name}
                  <button
                    type="button"
                    class="icon-btn"
                    class:selected={avatarIcon === name}
                    onclick={() => { avatarIcon = name; if (!avatarColor) avatarColor = colorEntries[0]?.[1] ?? ""; }}
                    title={name}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
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
                    class:selected={avatarColor === hex}
                    style="background: {hex};"
                    onclick={() => { avatarColor = hex; if (!avatarIcon) avatarIcon = iconChoices[0] ?? ""; }}
                    title={name}
                  ></button>
                {/each}
              </div>

              {#if avatarIcon || avatarColor}
                <div class="picker-footer">
                  <button type="button" class="clear-icon-btn" onclick={() => { avatarIcon = ""; avatarColor = ""; pickerOpen = false; }}>
                    Clear
                  </button>
                </div>
              {/if}
            </div>
          {/if}
        </div>
        <div class="below-avatar">
          {#if hasPhoto && !selectedFile}
            <button type="button" onclick={deletePhoto} disabled={saving} class="remove-btn">Remove</button>
          {/if}
          <button type="button" class="icon-picker-toggle" onclick={openPicker}>
            {avatarIcon ? "Change icon" : "Choose icon"}
          </button>
        </div>
      </div>
    </div>

    {#if photoError}
      <p class="error">{photoError}</p>
    {/if}
  </section>

  <form onsubmit={handleSubmit}>
    <label for="display-name">Display Name</label>
    <input
      id="display-name"
      type="text"
      bind:value={displayName}
      placeholder={profile.actor_id}
    />

    <label for="bio">Bio</label>
    <textarea id="bio" bind:value={bio} rows="4" placeholder="Tell us about yourself"></textarea>

    <label for="email">Email</label>
    <input id="email" type="email" bind:value={email} placeholder="you@example.com" />

    <button type="submit" disabled={saving}>
      {saving ? "Saving..." : "Save Profile"}
    </button>
  </form>

  {#if error}
    <p class="error">{error}</p>
  {/if}
  {#if success}
    <p class="success">{success}</p>
  {/if}

  <div class="view-link">
    <a href="/-/profile/{encodeURIComponent(profile.actor_id)}">View your profile</a>
    &middot;
    <a href="/-/profiles/">All profiles</a>
  </div>
</main>

<style>
  main {
    max-width: 500px;
    margin: 2rem auto;
  }
  h2 {
    font-size: 1.1rem;
    margin: 0 0 0.5rem;
  }
  .photo-section {
    margin-bottom: 2rem;
    padding: 1.25rem;
    background: #f9f9f9;
    border-radius: 8px;
    border: 2px solid transparent;
    transition: border-color 0.15s, background 0.15s;
  }
  .photo-section.dragging {
    border-color: #4a90d9;
    background: #f0f7ff;
  }
  .photo-section-inner {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
  }
  .photo-info {
    flex: 1;
  }
  .photo-preview-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
  }
  .photo-preview {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
  }
  .avatar-icon-preview :global(svg) {
    border-radius: 50%;
    display: block;
  }
  .photo-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    font-weight: 600;
    color: #666;
  }
  .below-avatar {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
  }
  .photo-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  .file-btn {
    padding: 0.3rem 0.8rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .file-btn:hover {
    background: #eee;
  }
  .clear-btn {
    padding: 0.3rem 0.8rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 0.85rem;
    color: #666;
  }
  .clear-btn:hover {
    background: #eee;
  }
  .remove-btn {
    font-size: 0.75rem;
    color: #c00;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .remove-btn:hover {
    text-decoration: underline;
  }
  .icon-picker-toggle {
    font-size: 0.75rem;
    color: #4a90d9;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .icon-picker-toggle:hover {
    text-decoration: underline;
  }
  .hint {
    font-size: 0.8rem;
    color: #888;
    margin: 0.25rem 0 0;
    line-height: 1.4;
  }

  .avatar-anchor {
    position: relative;
  }
  .icon-picker-popover {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: 50%;
    transform: translateX(50%);
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 0.75rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    z-index: 10;
    width: max-content;
  }
  .icon-grid {
    display: grid;
    grid-template-columns: repeat(4, 36px);
    gap: 4px;
    margin-bottom: 0.75rem;
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
    display: grid;
    grid-template-columns: repeat(4, 28px);
    gap: 4px;
    justify-content: center;
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
    box-shadow: 0 0 0 2px white, 0 0 0 4px #333;
  }
  .picker-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 0.4rem;
  }
  .clear-icon-btn {
    font-size: 0.75rem;
    color: #c00;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .clear-icon-btn:hover {
    text-decoration: underline;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-weight: 600;
    margin-top: 0.5rem;
  }
  input[type="text"],
  input[type="email"],
  textarea {
    padding: 0.4rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.9rem;
    font-family: inherit;
  }
  textarea {
    resize: vertical;
  }
  button[type="submit"] {
    align-self: flex-start;
    margin-top: 0.5rem;
    padding: 0.4rem 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    cursor: pointer;
  }
  button[type="submit"]:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .error {
    color: #c00;
  }
  .success {
    color: #060;
  }
  .view-link {
    margin-top: 1.5rem;
  }
  .view-link a {
    font-size: 0.9rem;
  }
</style>
