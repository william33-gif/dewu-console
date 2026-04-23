import { API_BASE_URL } from "@/lib/api";

const MATERIAL_SEGMENT = "/storage/materials/";
const RESULT_SEGMENT = "/storage/results/";

export function getMaterialPreviewUrl(path?: string | null): string | null {
  if (!path) {
    return null;
  }

  const normalized = path.replace(/\\/g, "/");
  const markerIndex = normalized.lastIndexOf(MATERIAL_SEGMENT);
  if (markerIndex === -1) {
    return null;
  }

  const relativePath = normalized.slice(markerIndex + MATERIAL_SEGMENT.length);
  const encodedPath = relativePath
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  return encodedPath ? `${API_BASE_URL}/media/materials/${encodedPath}` : null;
}

export function getMaterialFileName(path?: string | null): string {
  if (!path) {
    return "-";
  }

  const normalized = path.replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).at(-1) ?? path;
}

export function getResultPreviewUrl(path?: string | null): string | null {
  if (!path) {
    return null;
  }

  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("/media/results/")) {
    return path.startsWith("/media/results/") ? `${API_BASE_URL}${path}` : path;
  }

  const normalized = path.replace(/\\/g, "/");
  const markerIndex = normalized.lastIndexOf(RESULT_SEGMENT);
  if (markerIndex === -1) {
    return null;
  }

  const relativePath = normalized.slice(markerIndex + RESULT_SEGMENT.length);
  const encodedPath = relativePath
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  return encodedPath ? `${API_BASE_URL}/media/results/${encodedPath}` : null;
}
