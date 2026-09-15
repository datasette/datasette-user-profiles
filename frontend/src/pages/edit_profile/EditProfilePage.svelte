<script lang="ts">
  import createClient from "openapi-fetch";
  import type { paths } from "../../../api.d.ts";
  import { loadPageData } from "../../page_data/load";
  import type { EditProfilePageData } from "../../page_data/EditProfilePageData.types";
  import AvatarDialog, { type AvatarDraft } from "./AvatarDialog.svelte";
  import AvatarPreview from "./AvatarPreview.svelte";

  const client = createClient<paths>({ baseUrl: "/" });
  const pageData = loadPageData<EditProfilePageData>();
  const profile = pageData.profile;

  // Which fields this deployment allows users to edit. A field is editable
  // unless explicitly turned off via plugin config; missing map => all on.
  const editable = pageData.editable ?? {};
  const canEdit = (field: string) => editable[field] !== false;
  const canEditAvatar = canEdit("avatar");

  let displayName = $state(profile.display_name ?? "");
  let bio = $state(profile.bio ?? "");
  let email = $state(profile.email ?? "");
  let saving = $state(false);
  let error: string | null = $state(null);
  let success: string | null = $state(null);

  const iconChoices = pageData.avatar_icon_choices ?? [];
  const colorChoices = pageData.avatar_color_choices ?? {};
  const iconSvgs = pageData.avatar_icon_svgs ?? {};
  const letter = (profile.display_name || profile.actor_id).charAt(0).toUpperCase();

  const photoUrl = (bust = false) =>
    `/-/api/user-profile/photo/${encodeURIComponent(profile.actor_id)}` +
    (bust ? `?t=${Date.now()}` : "");

  // Whether the server currently has a photo stored for this user
  let hasPhoto = $state(profile.has_photo);
  // The saved avatar, as shown on the page
  let avatar = $state({
    photoUrl: profile.has_photo ? photoUrl() : null,
    icon: profile.avatar_icon ?? "",
    color: profile.avatar_color ?? "",
  });
  let dialogOpen = $state(false);

  // Text fields as last saved, for the leave-page warning
  let saved = $state({
    displayName: profile.display_name ?? "",
    bio: profile.bio ?? "",
    email: profile.email ?? "",
  });
  const hasUnsavedChanges = $derived(
    displayName !== saved.displayName || bio !== saved.bio || email !== saved.email,
  );

  $effect(() => {
    if (!hasUnsavedChanges) return;
    success = null;
    // Browsers show their own generic "leave site?" prompt; custom text is ignored
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  });

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

  function apiError(data: any, err: any, fallback: string): string | null {
    if (err) return err.error ?? fallback;
    if (data && !data.ok) return data.error ?? fallback;
    return null;
  }

  // Called by the picture dialog's Save; returns an error message or null
  async function saveAvatar(draft: AvatarDraft): Promise<string | null> {
    if (draft.file) {
      const base64 = await readFileAsBase64(draft.file);
      const { data, error: err } = await client.POST("/-/api/user-profile/photo", {
        body: {
          photo_data: base64,
          content_type: draft.file.type || "image/jpeg",
        } as any,
      });
      const msg = apiError(data, err, "Photo upload failed");
      if (msg) return msg;
      hasPhoto = true;
    } else if (hasPhoto && !draft.photoUrl) {
      const { data, error: err } = await client.POST(
        "/-/api/user-profile/photo/delete" as any,
        { body: {} },
      );
      const msg = apiError(data, err, "Couldn't remove photo");
      if (msg) return msg;
      hasPhoto = false;
    }

    if (draft.icon !== avatar.icon || draft.color !== avatar.color) {
      const { data, error: err } = await client.POST("/-/api/user-profile/update", {
        body: { avatar_icon: draft.icon || null, avatar_color: draft.color || null } as any,
      });
      const msg = apiError(data, err, "Save failed");
      if (msg) {
        // A new photo may already be stored; reflect that even though the
        // icon change failed
        avatar.photoUrl = hasPhoto ? photoUrl(true) : null;
        return msg;
      }
    }

    avatar = {
      photoUrl: hasPhoto ? photoUrl(true) : null,
      icon: draft.icon,
      color: draft.color,
    };
    return null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    saving = true;
    error = null;
    success = null;
    try {
      const { data, error: err } = await client.POST("/-/api/user-profile/update", {
        body: {
          display_name: displayName || null,
          bio: bio || null,
          email: email || null,
        } as any,
      });
      error = apiError(data, err, "Save failed");
      if (error) return;
      saved = { displayName, bio, email };
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

  <section class="photo-section">
    {#if canEditAvatar}
      <button
        type="button"
        class="avatar-btn"
        onclick={() => (dialogOpen = true)}
        aria-label="Change profile picture"
      >
        <AvatarPreview
          photoUrl={avatar.photoUrl}
          icon={avatar.icon}
          color={avatar.color}
          {iconSvgs}
          {letter}
        />
        <span class="edit-badge" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
            <path
              d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325"
            />
          </svg>
        </span>
      </button>
    {:else}
      <AvatarPreview
        photoUrl={avatar.photoUrl}
        icon={avatar.icon}
        color={avatar.color}
        {iconSvgs}
        {letter}
      />
    {/if}
    <div class="identity">
      <div class="name">{saved.displayName || profile.actor_id}</div>
      {#if canEditAvatar}
        <button type="button" class="link-btn" onclick={() => (dialogOpen = true)}>
          Change picture
        </button>
      {:else}
        <p class="hint">Picture is managed elsewhere</p>
      {/if}
    </div>
  </section>

  {#if dialogOpen}
    <AvatarDialog
      initial={{
        ...$state.snapshot(avatar),
        file: null,
        originalFile: null,
        sizeNote: null,
        sourceWarning: null,
      }}
      {iconChoices}
      {colorChoices}
      {iconSvgs}
      {letter}
      onsave={saveAvatar}
      onclose={() => (dialogOpen = false)}
    />
  {/if}

  <form onsubmit={handleSubmit}>
    <label for="display-name">
      Display Name
      {#if !canEdit("display_name")}<span class="locked">locked</span>{/if}
    </label>
    <input
      id="display-name"
      type="text"
      bind:value={displayName}
      placeholder={profile.actor_id}
      disabled={!canEdit("display_name")}
    />

    <label for="bio">
      Bio
      {#if !canEdit("bio")}<span class="locked">locked</span>{/if}
    </label>
    <textarea
      id="bio"
      bind:value={bio}
      rows="4"
      placeholder="Tell us about yourself"
      disabled={!canEdit("bio")}
    ></textarea>

    <label for="email">
      Email
      {#if !canEdit("email")}<span class="locked">locked</span>{/if}
    </label>
    <input
      id="email"
      type="email"
      bind:value={email}
      placeholder="you@example.com"
      disabled={!canEdit("email")}
    />

    <button type="submit" disabled={saving || !hasUnsavedChanges}>
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
  .photo-section {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .avatar-btn {
    position: relative;
    padding: 0;
    border: none;
    background: none;
    border-radius: 50%;
    cursor: pointer;
    flex-shrink: 0;
  }
  .avatar-btn:hover :global(.avatar) {
    filter: brightness(0.9);
  }
  .avatar-btn:focus-visible {
    outline: 2px solid #4a90d9;
    outline-offset: 3px;
  }
  .edit-badge {
    position: absolute;
    right: -2px;
    bottom: -2px;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: white;
    border: 1px solid #ddd;
    color: #444;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  }
  .avatar-btn:hover .edit-badge {
    color: #111;
    border-color: #bbb;
  }
  .identity {
    min-width: 0;
  }
  .name {
    font-size: 1.15rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .link-btn {
    margin-top: 0.15rem;
    padding: 0;
    border: none;
    background: none;
    color: #4a90d9;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .link-btn:hover {
    text-decoration: underline;
  }
  .hint {
    font-size: 0.8rem;
    color: #888;
    margin: 0.15rem 0 0;
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
  .locked {
    margin-left: 0.4rem;
    font-weight: 400;
    font-size: 0.7rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  input:disabled,
  textarea:disabled {
    background: #f3f3f3;
    color: #888;
    cursor: not-allowed;
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
