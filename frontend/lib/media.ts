import { API_BASE_URL } from "@/lib/api";

const MATERIAL_SEGMENT = "/storage/materials/";
const RESULT_SEGMENT = "/storage/results/";

function encodeRelativePath(relativePath: string): string {
  return relativePath
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function getRelativePath(path: string | null | undefined, marker: string): string | null {
  if (!path) {
    return null;
  }

  const normalized = path.replace(/\\/g, "/");
  const markerIndex = normalized.lastIndexOf(marker);
  if (markerIndex === -1) {
    return null;
  }

  return normalized.slice(markerIndex + marker.length);
}

export function getMaterialOriginalUrl(path?: string | null): string | null {
  const relativePath = getRelativePath(path, MATERIAL_SEGMENT);
  const encodedPath = relativePath ? encodeRelativePath(relativePath) : "";
  return encodedPath ? `${API_BASE_URL}/media/materials/${encodedPath}` : null;
}

export function getMaterialPreviewUrl(path?: string | null): string | null {
  const relativePath = getRelativePath(path, MATERIAL_SEGMENT);
  const encodedPath = relativePath ? encodeRelativePath(relativePath) : "";
  return encodedPath ? `${API_BASE_URL}/media/material-thumbs/${encodedPath}` : null;
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
  const encodedPath = encodeRelativePath(relativePath);

  return encodedPath ? `${API_BASE_URL}/media/results/${encodedPath}` : null;
}

export function getResultThumbnailUrl(path?: string | null): string | null {
  if (!path || path.startsWith("http://") || path.startsWith("https://")) {
    return null;
  }

  if (path.startsWith("/media/results/")) {
    const encodedPath = encodeRelativePath(path.slice("/media/results/".length));
    return encodedPath ? `${API_BASE_URL}/media/result-thumbs/${encodedPath}` : null;
  }

  const relativePath = getRelativePath(path, RESULT_SEGMENT);
  const encodedPath = relativePath ? encodeRelativePath(relativePath) : "";
  return encodedPath ? `${API_BASE_URL}/media/result-thumbs/${encodedPath}` : null;
}
