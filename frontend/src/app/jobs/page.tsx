"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  ArrowLeft,
  Briefcase,
  MapPin,
  Building2,
  Zap,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";
const POLL_INTERVAL_MS = 2000;
const REFILL_THRESHOLD = 5;

// Session storage keys — persist state across /jobs ↔ /jobs/[id] navigation
const SS_CARDS = "jobs_cards";
const SS_INDEX = "jobs_index";
const SS_SINCE = "jobs_since";
const SS_STATUS = "jobs_status";

type JobData = {
  title?: string;
  job_title?: string;
  company?: string;
  location?: string;
  industry?: string;
  employment_type?: string;
  job_type?: string;
  description?: string;
};
type VettedJob = {
  job_id: string;
  match_score: number;
  confidence: "high" | "medium" | "low";
  reasoning: string;
  matching_skills: string[];
  skill_gaps: string[];
  job_data: JobData;
};
type PollStatus = "processing" | "buffered" | "done" | "idle";

function getField(job: VettedJob, key: keyof JobData): string {
  const d = job.job_data;
  if (key === "title") return d?.title || d?.job_title || "";
  if (key === "employment_type") return d?.employment_type || d?.job_type || "";
  return (d?.[key] as string) || "";
}

/** Save current poll state to sessionStorage so navigating to /jobs/[id] and
 *  back doesn't restart everything from scratch. */
function saveSession(cards: VettedJob[], index: number, since: number, status: PollStatus) {
  try {
    sessionStorage.setItem(SS_CARDS, JSON.stringify(cards));
    sessionStorage.setItem(SS_INDEX, String(index));
    sessionStorage.setItem(SS_SINCE, String(since));
    sessionStorage.setItem(SS_STATUS, status);
  } catch { /* storage full / unavailable — ignore */ }
}

/** Returns restored session if one exists for the currently selected roles,
 *  otherwise null. */
function restoreSession(): { cards: VettedJob[]; index: number; since: number; status: PollStatus } | null {
  try {
    const raw = sessionStorage.getItem(SS_CARDS);
    if (!raw) return null;
    const cards: VettedJob[] = JSON.parse(raw);
    if (!cards.length) return null;
    return {
      cards,
      index: parseInt(sessionStorage.getItem(SS_INDEX) || "0", 10),
      since: parseInt(sessionStorage.getItem(SS_SINCE) || "0", 10),
      status: (sessionStorage.getItem(SS_STATUS) || "processing") as PollStatus,
    };
  } catch {
    return null;
  }
}

function clearSession() {
  [SS_CARDS, SS_INDEX, SS_SINCE, SS_STATUS].forEach(k => sessionStorage.removeItem(k));
}

// ── Job Card ───────────────────────────────────────────────────────────────────

interface JobCardProps {
  job: VettedJob;
  animating: "left" | "right" | null;
  onSkip: () => void;
  onApply: () => void;
}

function JobCard({ job, animating, onSkip, onApply }: JobCardProps) {
  const title = getField(job, "title");
  const company = getField(job, "company");
  const location = getField(job, "location");
  const industry = getField(job, "industry");
  const empType = getField(job, "employment_type");
  const pct = Math.round(job.match_score * 100);

  const scoreBg =
    pct >= 75
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
      : "bg-amber-500/20 text-amber-400 border-amber-500/40";

  const slideClass =
    animating === "left" ? "translate-x-[-110%] opacity-0"
      : animating === "right" ? "translate-x-[110%] opacity-0"
        : "translate-x-0 opacity-100";

  return (
    <div className={`w-full max-w-6xl bg-card border border-border rounded-2xl shadow-xl flex flex-col transition-all duration-300 ease-in-out ${slideClass}`}>
      {/* Header */}
      <div className="p-6 border-b border-border flex items-start justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <Briefcase className="w-6 h-6 text-primary" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xl font-bold leading-tight truncate">{title || "Untitled Role"}</h2>
            <div className="flex flex-wrap items-center gap-3 mt-1 text-sm text-muted-foreground">
              {company && <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" />{company}</span>}
              {location && <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{location}</span>}
              {(industry || empType) && <span>{industry}{industry && empType ? " · " : ""}{empType}</span>}
            </div>
          </div>
        </div>
        <div className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold border ${scoreBg}`}>
          <Zap className="w-3.5 h-3.5" />{pct}% match
        </div>
      </div>

      {/* Body */}
      <div className="p-6 flex flex-col gap-4 flex-grow">
        {job.matching_skills?.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Matching Skills</p>
            <div className="flex flex-wrap gap-2">
              {job.matching_skills.map(s => (
                <span key={s} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-sm border border-emerald-500/20">
                  <CheckCircle2 className="w-3.5 h-3.5" />{s}
                </span>
              ))}
            </div>
          </div>
        )}
        {job.skill_gaps?.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Skills to Develop</p>
            <div className="flex flex-wrap gap-2">
              {job.skill_gaps.map(s => (
                <span key={s} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-sm border border-amber-500/20">
                  <AlertCircle className="w-3.5 h-3.5" />{s}
                </span>
              ))}
            </div>
          </div>
        )}
        {job.reasoning && (
          <p className="text-sm text-muted-foreground italic border-l-2 border-primary/30 pl-3 mt-auto">{job.reasoning}</p>
        )}
      </div>

      {/* Actions */}
      <div className="p-6 border-t border-border flex items-center justify-between">
        <button id="skip-btn" onClick={onSkip} className="group flex flex-col items-center gap-1" aria-label="Skip">
          <div className="w-14 h-14 rounded-full border-2 border-border flex items-center justify-center group-hover:border-red-400 group-hover:bg-red-400/10 transition-all duration-200">
            <ChevronLeft className="w-6 h-6 text-muted-foreground group-hover:text-red-400 transition-colors" />
          </div>
          <span className="text-xs text-muted-foreground group-hover:text-red-400 transition-colors font-medium">Skip</span>
        </button>

        <span className="text-xs text-muted-foreground/40 select-none">
          <kbd className="px-1.5 py-0.5 rounded border border-border text-[10px]">←</kbd>
          {" "}skip · apply{" "}
          <kbd className="px-1.5 py-0.5 rounded border border-border text-[10px]">→</kbd>
        </span>

        <button id="apply-btn" onClick={onApply} className="group flex flex-col items-center gap-1" aria-label="Apply">
          <div className="w-14 h-14 rounded-full border-2 border-border flex items-center justify-center group-hover:border-emerald-400 group-hover:bg-emerald-400/10 transition-all duration-200">
            <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:text-emerald-400 transition-colors" />
          </div>
          <span className="text-xs text-muted-foreground group-hover:text-emerald-400 transition-colors font-medium">Apply</span>
        </button>
      </div>
    </div>
  );
}

function LoadingCard() {
  return (
    <div className="w-full max-w-6xl bg-card border border-border rounded-2xl shadow-xl p-12 flex flex-col items-center justify-center gap-4 min-h-[340px]">
      <Loader2 className="w-10 h-10 text-primary animate-spin" />
      <p className="text-muted-foreground font-medium">Finding matching jobs…</p>
    </div>
  );
}

function EmptyCard() {
  return (
    <div className="w-full max-w-6xl bg-card border border-border rounded-2xl shadow-xl p-12 flex flex-col items-center justify-center gap-4 min-h-[340px]">
      <Briefcase className="w-10 h-10 text-muted-foreground" />
      <h2 className="text-lg font-semibold">No more matching jobs</h2>
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        You&apos;ve seen all available matches. Go back and try different roles.
      </p>
      <Link href="/select-jobs" className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const router = useRouter();

  const [userId, setUserId] = useState<string | null>(null);
  const [cards, setCards] = useState<VettedJob[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [status, setStatus] = useState<PollStatus>("processing");
  const [animating, setAnimating] = useState<"left" | "right" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs — live values accessible inside interval/timeout without re-creating them
  const sinceRef = useRef(0);
  const indexRef = useRef(0);
  const statusRef = useRef<PollStatus>("processing");
  const cardsRef = useRef<VettedJob[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animRef = useRef(false);

  // Keep refs in sync with state
  useEffect(() => { indexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { statusRef.current = status; }, [status]);
  useEffect(() => { cardsRef.current = cards; }, [cards]);

  // ── Auth ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    async function loadUser() {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (user?.id) setUserId(user.id);
      else setError("Please log in first.");
    }
    loadUser();
  }, []);

  // ── Save session whenever cards/index/since/status changes ─────────────────
  useEffect(() => {
    if (cards.length > 0) {
      saveSession(cards, currentIndex, sinceRef.current, status);
    }
  }, [cards, currentIndex, status]);

  // ── Single poll ────────────────────────────────────────────────────────────
  const poll = useCallback(async (uid: string) => {
    try {
      const since = sinceRef.current;
      const consumed = indexRef.current;
      const res = await fetch(
        `${BACKEND_BASE}/api/jobs/results?user_id=${uid}&since=${since}&consumed=${consumed}`
      );
      if (!res.ok) return;

      const data: { jobs: VettedJob[]; total: number; status: string } = await res.json();

      if (data.jobs?.length) {
        sinceRef.current = data.total;
        setCards(prev => {
          const updated = [...prev, ...data.jobs];
          return updated;
        });
      }

      const newStatus = data.status as PollStatus;

      if (newStatus === "done") {
        setStatus("done");
        statusRef.current = "done";
        stopPolling();
      } else if (newStatus === "buffered") {
        // Thread paused — buffer is full. Stop regular polling.
        // We'll restart it only when the refill threshold is hit.
        setStatus("buffered");
        statusRef.current = "buffered";
        stopPolling();
      }
    } catch { /* transient — keep going */ }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(uid: string) {
    stopPolling(); // always clear first
    pollRef.current = setInterval(() => poll(uid), POLL_INTERVAL_MS);
  }

  // ── Init: restore from session or start fresh ──────────────────────────────
  useEffect(() => {
    if (!userId) return;

    const restored = restoreSession();

    if (restored) {
      // Came back from /jobs/[id] — restore exactly where we were
      setCards(restored.cards);
      setCurrentIndex(restored.index);
      sinceRef.current = restored.since;
      indexRef.current = restored.index;
      cardsRef.current = restored.cards;
      const st = restored.status;
      setStatus(st);
      statusRef.current = st;

      // If was still fetching, resume polling
      if (st === "processing") {
        startPolling(userId);
      }
      // If buffered/done, polling stays off until refill trigger fires
    } else {
      // Fresh start
      const raw = sessionStorage.getItem("selectedRoles");
      let roles: string[] = [];
      try { if (raw) roles = JSON.parse(raw); } catch { /* ignore */ }

      if (!roles.length) {
        setError("No roles selected. Go back and pick at least one role.");
        setStatus("idle");
        return;
      }

      async function begin() {
        const res = await fetch(`${BACKEND_BASE}/api/jobs/start-vetting`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId, roles }),
        });
        if (!res.ok) { setError("Failed to start job search."); setStatus("idle"); return; }

        sinceRef.current = 0;
        setStatus("processing");
        statusRef.current = "processing";
        startPolling(userId!);
      }
      begin();
    }

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // ── Refill trigger ─────────────────────────────────────────────────────────
  // Fires when remaining cards drop below threshold.
  // Restarts polling (which sends updated consumed → backend wakes thread).
  useEffect(() => {
    if (!userId) return;
    const remaining = cardsRef.current.length - currentIndex;
    const canRefill = statusRef.current !== "done" && statusRef.current !== "idle";

    if (remaining >= 0 && remaining < REFILL_THRESHOLD && canRefill && cardsRef.current.length > 0) {
      // Resume polling — backend will see consumed and resume vetting
      setStatus("processing");
      statusRef.current = "processing";
      startPolling(userId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex]);

  // ── Skip ──────────────────────────────────────────────────────────────────
  const handleSkip = useCallback(() => {
    if (indexRef.current >= cardsRef.current.length || animRef.current) return;
    animRef.current = true;
    setAnimating("left");
    setTimeout(() => {
      setCurrentIndex(i => i + 1);
      setAnimating(null);
      animRef.current = false;
    }, 300);
  }, []);

  // ── Apply ─────────────────────────────────────────────────────────────────
  const handleApply = useCallback(() => {
    const idx = indexRef.current;
    const job = cardsRef.current[idx];
    if (!job || animRef.current) return;
    animRef.current = true;
    setAnimating("right");
    // Save position before navigating away
    saveSession(cardsRef.current, idx + 1, sinceRef.current, statusRef.current);
    setTimeout(() => {
      router.push(`/jobs/${encodeURIComponent(job.job_id)}`);
    }, 200);
  }, [router]);

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") handleSkip();
      if (e.key === "ArrowRight") handleApply();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleSkip, handleApply]);

  // ── Render ────────────────────────────────────────────────────────────────
  const currentJob = cards[currentIndex] ?? null;
  const isWaiting = !currentJob && (status === "processing" || (status === "buffered" && cards.length === 0));
  const isEmpty = !currentJob && cards.length > 0 && (status === "done" || status === "idle")
    || !currentJob && cards.length === 0 && status === "idle";

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/select-jobs"
          onClick={clearSession}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      {error && (
        <div className="mt-16 mx-auto w-full max-w-6xl text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="flex-1 w-full flex items-center justify-center px-4 py-4 overflow-hidden mx-auto">
        <div className="w-full max-w-6xl flex justify-center h-full items-center">
          {currentJob ? <JobCard job={currentJob} animating={animating} onSkip={handleSkip} onApply={handleApply} />
            : isWaiting ? <LoadingCard />
              : isEmpty ? <EmptyCard />
                : null}
        </div>
      </div>
    </div>
  );
}
