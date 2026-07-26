import { fetchPersonas } from "../../services/personaApi";
import type { MobileJobListItem, MobileLibraryApiResponse, MobileOneShotJobData, MobilePersona } from "../types";

function readMobileLibraryCache(): MobileJobListItem[] | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const saved = JSON.parse(localStorage.getItem("storymaker_mobile_content_board_cache_v1") || "[]") as MobileJobListItem[];
    return Array.isArray(saved) && saved.length ? saved : null;
  } catch {
    return null;
  }
}

function persistMobileLibraryCache(items: MobileJobListItem[]) {
  if (typeof localStorage === "undefined" || !items.length) return;
  try {
    const compactItems = items.slice(0, 200).map((item) => ({
      ...item,
      raw_result: undefined,
      outputs: undefined,
    }));
    localStorage.setItem("storymaker_mobile_content_board_cache_v1", JSON.stringify(compactItems));
  } catch {
    // 브라우저 저장 공간이 부족해도 메모리 캐시는 유지합니다.
  }
}

let mobileLibraryCache: MobileJobListItem[] | null = readMobileLibraryCache();
let mobileLibraryLoadPromise: Promise<MobileJobListItem[]> | null = null;

export async function fetchMobilePersonas(): Promise<MobilePersona[]> {
  return fetchPersonas() as Promise<MobilePersona[]>;
}

export async function fetchMobileLibraryJobs(page = 0, limit = 10): Promise<MobileJobListItem[]> {
  const safePage = Math.max(0, page);
  const safeLimit = Math.max(1, Math.min(limit, 10));
  const offset = safePage * safeLimit;

  const cachedFirstPage = safePage === 0 && mobileLibraryCache?.length
    ? mobileLibraryCache.slice(0, safeLimit)
    : null;

  if (!mobileLibraryLoadPromise) {
    mobileLibraryLoadPromise = (async () => {
      const token = typeof localStorage !== "undefined" ? String(localStorage.getItem("storymaker_token") || "").trim() : "";
      const response = await fetch(`/api/v2/content-board?limit=${safeLimit}&offset=${offset}`, {
        credentials: "include",
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const payload = (await response.json().catch(() => ({}))) as MobileLibraryApiResponse;
      if (!response.ok || !payload.ok) {
        throw new Error(payload?.detail || payload?.message || "서버 보관함을 불러오지 못했습니다.");
      }
      const serverItems = payload.items || [];
      if (safePage === 0) {
        mobileLibraryCache = serverItems;
        persistMobileLibraryCache(serverItems);
      }
      return serverItems;
    })().finally(() => {
      mobileLibraryLoadPromise = null;
    });
  }

  try {
    return await mobileLibraryLoadPromise;
  } catch (error) {
    if (cachedFirstPage) return cachedFirstPage;
    throw error;
  }
}

export function getMobileOneShotDownloadUrl(jobId: string): string {
  return `/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/download`;
}

export async function fetchMobileOneShotJob(jobId: string): Promise<MobileOneShotJobData> {
  const token = typeof localStorage !== "undefined" ? String(localStorage.getItem("storymaker_token") || "").trim() : "";
  const response = await fetch(`/api/v2/content-board/${encodeURIComponent(jobId)}`, {
    credentials: "include",
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; data?: MobileOneShotJobData; message?: string; detail?: string };
  if (!response.ok || payload.ok === false) {
    const error = new Error(payload?.detail || payload?.message || "작업 결과를 불러오지 못했습니다.") as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return payload.data || ({ job_id: jobId, status: "알 수 없음" } as MobileOneShotJobData);
}

export async function fetchMobileOneShotTextFallback(jobId: string): Promise<string> {
  const response = await fetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/text`, { credentials: "include" });
  const text = await response.text().catch(() => "");
  if (!response.ok || !text.trim()) {
    throw new Error("저장된 글 파일을 찾지 못했습니다.");
  }
  return text.trim();
}

export async function startMobileOneShotPodcast(jobId: string): Promise<MobileOneShotJobData> {
  const response = await fetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/podcast`, {
    method: "POST",
    credentials: "include",
  });
  const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; data?: MobileOneShotJobData; message?: string; detail?: string };
  if (!response.ok || payload.ok === false) {
    throw new Error(payload?.detail || payload?.message || "팟캐스트 만들기를 시작하지 못했습니다.");
  }
  return payload.data || ({ job_id: jobId, status: "podcast_requested" } as MobileOneShotJobData);
}

export async function uploadMobileBrowserPodcast(
  jobId: string,
  mp3Blob: Blob,
  srtBlob: Blob,
  provider: "webgpu" | "wasm",
  durationSeconds: number,
): Promise<MobileOneShotJobData> {
  const form = new FormData();
  form.append("mp3", mp3Blob, "browser_podcast.mp3");
  form.append("srt", srtBlob, "browser_podcast.srt");
  form.append("provider", provider);
  form.append("duration_seconds", String(Math.max(0, durationSeconds || 0)));

  const response = await fetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/browser-podcast`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const payload = (await response.json().catch(() => ({}))) as {
    ok?: boolean;
    data?: MobileOneShotJobData;
    message?: string;
    detail?: string;
  };
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.detail || payload.message || "모바일 브라우저 MP3 결과를 저장하지 못했습니다.");
  }
  return payload.data || ({ job_id: jobId, status: "podcast_completed" } as MobileOneShotJobData);
}

export async function startMobileOneShotShortform(jobId: string): Promise<MobileOneShotJobData> {
  const response = await fetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/shortform`, {
    method: "POST",
    credentials: "include",
  });
  const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; data?: MobileOneShotJobData; message?: string; detail?: string };
  if (!response.ok || payload.ok === false) {
    throw new Error(payload?.detail || payload?.message || "숏폼 제작을 시작하지 못했습니다.");
  }
  return payload.data || ({ job_id: jobId, status: "shortform_requested" } as MobileOneShotJobData);
}

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = 180_000): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("AI 응답이 3분 이상 없어 작업을 초기화했습니다. 다시 시도해주세요.");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function createMobileOneShotJob(memo: string, images: File[], persona: MobilePersona | null): Promise<MobileOneShotJobData> {
  const form = new FormData();
  form.append("memo", memo);
  form.append("browser_podcast", "false");
  if (persona?.id) form.append("persona_id", String(persona.id));

  const response = await fetchWithTimeout("/api/mobile/one-shot/jobs", {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; data?: MobileOneShotJobData; message?: string; detail?: string };
  if (!response.ok || payload.ok === false) {
    throw new Error(payload?.detail || payload?.message || "모바일 보관함 저장 작업을 만들지 못했습니다.");
  }
  const job = payload.data || ({ job_id: "unknown", status: "created" } as MobileOneShotJobData);
  if (job.job_id && job.job_id !== "unknown" && images.length > 0) {
    await uploadMobileOneShotImages(job.job_id, images);
  }
  return job;
}

export async function uploadMobileOneShotImages(jobId: string, images: File[]): Promise<MobileOneShotJobData> {
  const form = new FormData();
  images.forEach((file) => form.append("images", file));
  const response = await fetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/images`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; data?: MobileOneShotJobData; message?: string; detail?: string };
  if (!response.ok || payload.ok === false) {
    throw new Error(payload?.detail || payload?.message || "사진 업로드를 완료하지 못했습니다.");
  }
  return payload.data || ({ job_id: jobId, status: "images_uploaded" } as MobileOneShotJobData);
}
