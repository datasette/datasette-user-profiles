// Client-side avatar image processing: decode, crop, downscale, re-encode.
// Re-encoding through a canvas also strips EXIF metadata (including GPS)
// and bakes in EXIF orientation, so stored photos are clean and small.

/** Longest edge of the stored avatar. Avatars render at 80px max. */
export const AVATAR_EXPORT_SIZE = 512;

/** Warn below this source dimension — the avatar will look blurry. */
export const MIN_SOURCE_SIZE = 128;

export interface CropRect {
  /** Source-image coordinates of the square crop region. */
  x: number;
  y: number;
  size: number;
}

export class ImageDecodeError extends Error {}

function looksLikeHeic(file: File): boolean {
  return /image\/hei[cf]/.test(file.type) || /\.hei[cf]$/i.test(file.name);
}

/** Decode a file to an ImageBitmap with EXIF orientation applied. */
export async function decodeImage(file: File): Promise<ImageBitmap> {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    if (looksLikeHeic(file)) {
      throw new ImageDecodeError(
        "HEIC images aren't supported by your browser — export as JPEG or PNG first",
      );
    }
    throw new ImageDecodeError("Couldn't read that image file");
  }
}

/**
 * Crop a square region out of the bitmap, downscale it to at most
 * AVATAR_EXPORT_SIZE, and encode it. Prefers WebP; falls back to JPEG
 * (composited on white, since JPEG has no alpha) on browsers that
 * can't encode WebP.
 */
export async function exportAvatar(
  bitmap: ImageBitmap,
  crop: CropRect,
): Promise<Blob> {
  const out = Math.min(AVATAR_EXPORT_SIZE, Math.round(crop.size));
  const canvas = document.createElement("canvas");
  canvas.width = out;
  canvas.height = out;
  const ctx = canvas.getContext("2d")!;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, crop.x, crop.y, crop.size, crop.size, 0, 0, out, out);

  let blob = await encode(canvas, "image/webp");
  if (!blob || blob.type !== "image/webp") {
    // Safari: toBlob ignores unsupported types. Re-draw on white for JPEG.
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, out, out);
    ctx.drawImage(bitmap, crop.x, crop.y, crop.size, crop.size, 0, 0, out, out);
    blob = await encode(canvas, "image/jpeg");
  }
  if (!blob) {
    throw new ImageDecodeError("Couldn't encode the image");
  }
  return blob;
}

function encode(canvas: HTMLCanvasElement, type: string): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, 0.85));
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}
