<script lang="ts">
  import type { CropRect } from "./image";

  interface Props {
    bitmap: ImageBitmap;
    onapply: (crop: CropRect) => void;
    oncancel: () => void;
  }
  const { bitmap, onapply, oncancel }: Props = $props();

  const VIEW = 280; // CSS pixels of the square crop viewport
  const MAX_ZOOM = 4;

  let canvasEl: HTMLCanvasElement;

  // Scale where the image exactly covers the viewport (short edge fits).
  const baseScale = $derived(VIEW / Math.min(bitmap.width, bitmap.height));
  let zoom = $state(1);
  const scale = $derived(baseScale * zoom);
  // Top-left of the drawn image, in viewport coordinates.
  let ox = $state(0);
  let oy = $state(0);

  function clamp(v: number, lo: number, hi: number): number {
    return Math.min(hi, Math.max(lo, v));
  }

  function clampOffsets() {
    ox = clamp(ox, VIEW - bitmap.width * scale, 0);
    oy = clamp(oy, VIEW - bitmap.height * scale, 0);
  }

  // Center (and reset zoom) whenever a new bitmap comes in
  $effect.pre(() => {
    zoom = 1;
    ox = (VIEW - bitmap.width * baseScale) / 2;
    oy = (VIEW - bitmap.height * baseScale) / 2;
  });

  function setZoom(next: number, cx = VIEW / 2, cy = VIEW / 2) {
    next = clamp(next, 1, MAX_ZOOM);
    const prevScale = scale;
    zoom = next;
    const newScale = baseScale * next;
    // Keep the point under (cx, cy) stationary while zooming
    ox = cx - ((cx - ox) / prevScale) * newScale;
    oy = cy - ((cy - oy) / prevScale) * newScale;
    clampOffsets();
  }

  let dragging = $state(false);
  let lastX = 0;
  let lastY = 0;

  function onPointerDown(e: PointerEvent) {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    canvasEl.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragging) return;
    ox += e.clientX - lastX;
    oy += e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    clampOffsets();
  }

  function onPointerUp() {
    dragging = false;
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    const rect = canvasEl.getBoundingClientRect();
    setZoom(
      zoom * (e.deltaY < 0 ? 1.08 : 1 / 1.08),
      e.clientX - rect.left,
      e.clientY - rect.top,
    );
  }

  $effect(() => {
    // Redraw whenever pan/zoom changes
    void ox, oy, scale;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = VIEW * dpr;
    canvasEl.height = VIEW * dpr;
    const ctx = canvasEl.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, VIEW, VIEW);
    ctx.drawImage(bitmap, ox, oy, bitmap.width * scale, bitmap.height * scale);
  });

  function apply() {
    onapply({
      x: -ox / scale,
      y: -oy / scale,
      size: VIEW / scale,
    });
  }
</script>

<div class="cropper">
  <div class="viewport" style="width: {VIEW}px; height: {VIEW}px;">
    <canvas
      bind:this={canvasEl}
      style="width: {VIEW}px; height: {VIEW}px;"
      class:dragging
      onpointerdown={onPointerDown}
      onpointermove={onPointerMove}
      onpointerup={onPointerUp}
      onpointercancel={onPointerUp}
      onwheel={onWheel}
    ></canvas>
    <div class="mask"></div>
  </div>

  <div class="controls">
    <input
      type="range"
      min="1"
      max={MAX_ZOOM}
      step="0.01"
      value={zoom}
      oninput={(e) => setZoom(parseFloat(e.currentTarget.value))}
      aria-label="Zoom"
    />
    <div class="buttons">
      <button type="button" class="cancel" onclick={oncancel}>Cancel</button>
      <button type="button" class="apply" onclick={apply}>Apply</button>
    </div>
  </div>
</div>

<style>
  .cropper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
  }
  .viewport {
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    background: #222;
  }
  canvas {
    display: block;
    cursor: grab;
    touch-action: none;
  }
  canvas.dragging {
    cursor: grabbing;
  }
  .mask {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    box-shadow: 0 0 0 999px rgba(0, 0, 0, 0.55);
    pointer-events: none;
  }
  .controls {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
  }
  input[type="range"] {
    width: 70%;
  }
  .buttons {
    display: flex;
    gap: 0.5rem;
  }
  .buttons button {
    padding: 0.3rem 0.9rem;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
    border: 1px solid #ccc;
    background: white;
  }
  .buttons button:hover {
    background: #eee;
  }
  .buttons .apply {
    background: #4a90d9;
    border-color: #4a90d9;
    color: white;
  }
  .buttons .apply:hover {
    background: #3a7fc4;
  }
</style>
