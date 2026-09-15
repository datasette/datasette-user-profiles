<script lang="ts">
  interface Props {
    photoUrl: string | null;
    icon: string;
    color: string;
    iconSvgs: Record<string, string>;
    letter: string;
    size?: number;
  }
  const { photoUrl, icon, color, iconSvgs, letter, size = 80 }: Props = $props();

  function makeIconSvg(name: string, color: string, size: number): string {
    const inner = iconSvgs[name];
    if (!inner || !color) return "";
    const iconSize = size * 0.5625;
    const offset = (size - iconSize) / 2;
    const scale = iconSize / 16;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="${color}"/><g transform="translate(${offset.toFixed(1)},${offset.toFixed(1)}) scale(${scale.toFixed(4)})" fill="white">${inner}</g></svg>`;
  }
</script>

{#if photoUrl}
  <img src={photoUrl} alt="" class="avatar" style="width: {size}px; height: {size}px;" />
{:else if icon && color && iconSvgs[icon]}
  <div class="avatar icon" style="width: {size}px; height: {size}px;">
    {@html makeIconSvg(icon, color, size)}
  </div>
{:else}
  <div
    class="avatar placeholder"
    style="width: {size}px; height: {size}px; font-size: {size * 0.4}px;"
  >
    {letter}
  </div>
{/if}

<style>
  .avatar {
    border-radius: 50%;
    object-fit: cover;
    display: block;
    flex-shrink: 0;
  }
  .icon :global(svg) {
    display: block;
  }
  .placeholder {
    background: #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    color: #666;
  }
</style>
