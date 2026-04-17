<script lang="ts">
  import { loadPageData } from "../../page_data/load";
  import type { ProfilePageData } from "../../page_data/ProfilePageData.types";

  const pageData = loadPageData<ProfilePageData>();
  const profile = pageData.profile;
  const isOwn = pageData.is_own_profile;
  const sections = pageData.sections || [];

  const hasAvatar = profile.has_photo || (profile.avatar_icon && profile.avatar_color);
  const avatarUrl = hasAvatar
    ? `/-/profile/pic/${encodeURIComponent(profile.actor_id)}`
    : null;

  // Dynamically load JS/CSS for each plugin section
  sections.forEach((section) => {
    for (const cssUrl of section.css_urls || []) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = cssUrl;
      document.head.appendChild(link);
    }
    for (const jsUrl of section.js_urls || []) {
      const script = document.createElement("script");
      script.src = jsUrl;
      script.type = "module";
      document.head.appendChild(script);
    }
  });
</script>

<main>
  <div class="profile-header">
    <div class="header-left">
      <div class="avatar">
        {#if avatarUrl}
          <img src={avatarUrl} alt="{profile.display_name || profile.actor_id}" class="avatar-img" />
        {:else}
          <div class="avatar-placeholder">
            {(profile.display_name || profile.actor_id).charAt(0).toUpperCase()}
          </div>
        {/if}
      </div>
      <div class="profile-info">
        <h1>{profile.display_name || profile.actor_id}</h1>
        {#if profile.display_name}
          <p class="actor-id">@{profile.actor_id}</p>
        {/if}
      </div>
    </div>
    {#if isOwn}
      <a href="/-/user-profile/edit" class="edit-btn">Edit profile</a>
    {/if}
  </div>

  {#if profile.bio}
    <div class="bio">
      <p>{profile.bio}</p>
    </div>
  {/if}

  {#if profile.email}
    <div class="email">
      <a href="mailto:{profile.email}">{profile.email}</a>
    </div>
  {/if}

  {#if sections.length > 0}
    <div class="profile-sections">
      {#each sections as section (section.id)}
        <div class="profile-section">
          <h2>
            {section.label}
          </h2>
          <div class="section-content">
            <!-- Web component rendered dynamically -->
            {@html `<${section.tag_name} actor-id="${profile.actor_id}" is-own-profile="${isOwn}"></${section.tag_name}>`}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <div class="actions">
    <a href="/-/profiles/" class="link">All profiles</a>
  </div>
</main>

<style>
  main {
    max-width: 600px;
    margin: 2rem auto;
  }
  .profile-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 1.5rem;
  }
  .edit-btn {
    padding: 0.4rem 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    text-decoration: none;
    color: #333;
    font-size: 0.85rem;
    white-space: nowrap;
  }
  .edit-btn:hover {
    background: #f5f5f5;
  }
  .avatar-img {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    object-fit: cover;
  }
  .avatar-placeholder {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    background: #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    font-weight: 600;
    color: #666;
  }
  h1 {
    margin: 0;
    font-size: 1.5rem;
  }
  .actor-id {
    margin: 0.25rem 0 0;
    color: #666;
    font-size: 0.9rem;
  }
  .bio {
    margin-bottom: 1rem;
  }
  .bio p {
    white-space: pre-wrap;
    margin: 0;
  }
  .email {
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  .profile-sections {
    margin-top: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .profile-section h2 {
    font-size: 1.1rem;
    margin: 0 0 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .section-icon {
    display: inline-flex;
    width: 18px;
    height: 18px;
  }
  :global(.section-icon svg) {
    width: 18px;
    height: 18px;
  }
  .actions {
    margin-top: 1.5rem;
  }
  .link {
    font-size: 0.9rem;
  }
</style>
