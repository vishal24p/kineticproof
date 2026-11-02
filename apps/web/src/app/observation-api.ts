export type TrackResult = {
  status: "succeeded" | "partial" | "failed";
  provider_name: string;
  model_name: string;
  model_version: string;
  frames: {
    frame_index: number;
    timestamp_seconds: number;
    center_x_px: number | null;
    center_y_px: number | null;
    quality_flags: string[];
  }[];
  failures: {
    frame_index: number;
    reason: string;
    recovery_suggestion: string;
  }[];
  provenance: { source_video_sha256: string; [key: string]: unknown };
};

export async function checkedResponse(response: Response) {
  if (response.ok) return response;
  const body = await response.json().catch(() => null);
  const detail =
    typeof body?.detail === "string"
      ? body.detail
      : body?.detail
        ? JSON.stringify(body.detail)
        : response.statusText;
  const recovery =
    response.status === 401
      ? " Local session expired; refresh the page and re-upload your video. An API restart clears local observations."
      : response.status === 404
        ? " Local observation unavailable; upload again after an API restart."
        : "";
  throw new Error(
    `API ${response.status}: ${detail || "Request failed"}.${recovery}`,
  );
}
