<script lang="ts">
  import { loadPageData } from "../../page_data/load";
  import type { ProfilesPageData } from "../../page_data/ProfilesPageData.types";

  const pageData = loadPageData<ProfilesPageData>();
  const profiles = pageData.profiles ?? [];
</script>

<main>
  <h1>Profiles</h1>

  {#if profiles.length === 0}
    <p class="empty">No profiles yet.</p>
  {:else}
    <ul class="profile-list">
      {#each profiles as profile}
        <li class="profile-card">
          <a href="/-/profile/{encodeURIComponent(profile.actor_id)}" class="profile-link">
            <div class="avatar">
              {#if profile.has_photo || (profile.avatar_icon && profile.avatar_color)}
                <img
                  src="/-/profile/pic/{encodeURIComponent(profile.actor_id)}"
                  alt={profile.display_name || profile.actor_id}
                  class="avatar-img"
                />
              {:else}
                <div class="avatar-placeholder">
                  {(profile.display_name || profile.actor_id).charAt(0).toUpperCase()}
                </div>
              {/if}
            </div>
            <div class="info">
              <span class="name">{profile.display_name || profile.actor_id}</span>
              {#if profile.display_name}
                <span class="actor-id">@{profile.actor_id}</span>
              {/if}
              {#if profile.bio}
                <span class="bio">{profile.bio}</span>
              {/if}
            </div>
          </a>
          {#if profile.actor_id === pageData.current_actor_id}
            <a href="/-/user-profile/edit" class="edit-link">edit</a>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if !pageData.has_own_profile}
    <p class="create-prompt"><a href="/-/user-profile/edit">Create your profile</a></p>
  {/if}
</main>

<style>
  main {
    max-width: 600px;
    margin: 2rem auto;
  }
  .create-prompt {
    margin-top: 1rem;
  }
  .empty {
    color: #888;
  }
  .profile-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .profile-card {
    display: flex;
    align-items: center;
    padding: 0.75rem;
    border: 1px solid #eee;
    border-radius: 6px;
    transition: background 0.1s;
  }
  .profile-link {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex: 1;
    min-width: 0;
    text-decoration: none;
    color: inherit;
  }
  .edit-link {
    margin-left: auto;
    font-size: 0.8rem;
    color: #4a90d9;
    text-decoration: none;
  }
  .edit-link:hover {
    text-decoration: underline;
  }
  .profile-card:hover {
    background: #f9f9f9;
  }
  .avatar-img {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
  }
  .avatar-placeholder {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    font-weight: 600;
    color: #666;
  }
  .info {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .name {
    font-weight: 600;
    font-size: 0.95rem;
  }
  .actor-id {
    color: #888;
    font-size: 0.8rem;
  }
  .bio {
    color: #666;
    font-size: 0.85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 400px;
  }
</style>
