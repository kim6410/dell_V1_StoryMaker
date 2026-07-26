import type { MobileOneShotJobData } from "../types";

const ACTIVE_JOB_KEY = "storymaker_mobile_active_job";
const PROCESSING_STALE_MS = 2 * 60 * 1000;
const COMPLETED_KEEP_MS = 12 * 60 * 60 * 1000;

export type ActiveMobileJobStatus = "processing" | "completed" | "failed";

export type ActiveMobileJob = {
  job_id: string;
  status: ActiveMobileJobStatus;
  created_at: string;
  updated_at: string;
};

function nowIso() {
  return new Date().toISOString();
}

function safeStorage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function isCompletedStatus(status?: string) {
  const value = String(status || "").toLowerCase();
  return (
    value.includes("complete") ||
    value.includes("completed") ||
    value.includes("done") ||
    value === "gemini_completed" ||
    value === "shortform_completed" ||
    value === "thumbnail_done"
  );
}

function isFailedStatus(status?: string) {
  const value = String(status || "").toLowerCase();
  return value.includes("fail") || value.includes("error");
}

export function toActiveMobileJobStatus(status?: string): ActiveMobileJobStatus {
  if (isFailedStatus(status)) return "failed";
  if (isCompletedStatus(status)) return "completed";
  return "processing";
}

export function readActiveMobileJob(): ActiveMobileJob | null {
  const storage = safeStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(ACTIVE_JOB_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ActiveMobileJob;
    if (!parsed?.job_id || !parsed.job_id.startsWith("mob-")) {
      storage.removeItem(ACTIVE_JOB_KEY);
      return null;
    }
    return parsed;
  } catch {
    storage.removeItem(ACTIVE_JOB_KEY);
    return null;
  }
}

export function writeActiveMobileJob(job: MobileOneShotJobData, forcedStatus?: ActiveMobileJobStatus) {
  const storage = safeStorage();
  if (!storage || !job?.job_id || !job.job_id.startsWith("mob-")) return;
  const previous = readActiveMobileJob();
  const now = nowIso();
  const activeJob: ActiveMobileJob = {
    job_id: job.job_id,
    status: forcedStatus || toActiveMobileJobStatus(job.status),
    created_at: previous?.job_id === job.job_id ? previous.created_at : now,
    updated_at: now,
  };
  storage.setItem(ACTIVE_JOB_KEY, JSON.stringify(activeJob));
}

export function updateActiveMobileJobStatus(job: MobileOneShotJobData) {
  writeActiveMobileJob(job);
}

export function clearActiveMobileJob() {
  const storage = safeStorage();
  if (!storage) return;
  storage.removeItem(ACTIVE_JOB_KEY);
}

export function isActiveMobileJobStale(activeJob: ActiveMobileJob | null) {
  if (!activeJob) return false;
  const updatedAt = Date.parse(activeJob.updated_at || activeJob.created_at || "");
  if (!Number.isFinite(updatedAt)) return true;
  const ageMs = Date.now() - updatedAt;
  if (activeJob.status === "processing") return ageMs > PROCESSING_STALE_MS;
  return ageMs > COMPLETED_KEEP_MS;
}

export function shouldBlockNewMobileJob(activeJob: ActiveMobileJob | null) {
  if (!activeJob) return false;
  if (activeJob.status !== "processing") return false;
  return !isActiveMobileJobStale(activeJob);
}
