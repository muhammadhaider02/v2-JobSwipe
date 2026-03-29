"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  MapPin,
  Building2,
  User,
  CheckCircle2,
  Loader2,
} from "lucide-react";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";
const POLL_INTERVAL_MS = 2000;
const REFILL_THRESHOLD = 10;

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
  job_description?: string;
  experience_required?: number | string;
  skills_required?: string[];
};
type VettedJob = {
  job_id: string;
  match_score: number;
  confidence: "high" | "medium" | "low";
  matching_skills: string[];
  skill_gaps: string[];
  job_data: JobData;
};
type PollStatus = "processing" | "buffered" | "done" | "idle";

function getField(job: VettedJob, key: keyof JobData): string {
  const d = job.job_data;
  if (key === "title") return d?.title || d?.job_title || "";
  if (key === "employment_type") return d?.employment_type || d?.job_type || "";
  if (key === "description") return d?.description || d?.job_description || "";
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
}

// ── Description renderer ──────────────────────────────────────────────────────
// • Strips separator-only lines ("----", "______", etc.) but keeps "-" in text
// • Renders **bold** markdown as <strong>
function renderDescription(text: string): React.ReactNode {
  // Strip any "show more" artifacts (case-insensitive)
  const cleaned0 = text.replace(/show more/gi, "");
  // Remove lines that are only dashes/underscores/spaces (3+ chars)
  const lines = cleaned0
    .split("\n")
    .filter(line => !/^[-–—_\s]{3,}$/.test(line.trim()));

  // Re-join and split into paragraphs
  const paragraphs = lines
    .join("\n")
    .split(/\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean);

  return (
    <>
      {paragraphs.map((para, i) => {
        // Parse **bold** tokens
        const parts = para.split(/(\*\*[^*]+\*\*)/g);
        return (
          <p key={i} className={i > 0 ? "mt-2" : ""}>
            {parts.map((part, j) =>
              part.startsWith("**") && part.endsWith("**")
                ? <strong key={j} className="text-white/80 font-semibold">{part.slice(2, -2)}</strong>
                : <span key={j}>{part}</span>
            )}
          </p>
        );
      })}
    </>
  );
}

function JobCard({ job, animating }: JobCardProps) {
  const [descExpanded, setDescExpanded] = useState(false);

  const title = getField(job, "title");
  const company = getField(job, "company");
  const location = getField(job, "location");
  const empType = getField(job, "employment_type");
  const description = getField(job, "description");
  const expRaw = job.job_data?.experience_required;
  const experience = expRaw != null ? `${expRaw} yrs exp` : null;
  const pct = Math.round(job.match_score * 100);

  // Build a unified ordered skills list: matching first, then gaps
  const matchingSet = new Set((job.matching_skills || []).map(s => s.toLowerCase()));
  // Authoritative list from job data (if available), otherwise fall back to union
  const rawSkills = job.job_data?.skills_required ?? [
    ...(job.matching_skills || []),
    ...(job.skill_gaps || []),
  ];

  // Match% colour logic
  const isHighMatch = pct >= 80;
  // High match → bright green; lower → dimmer green
  const matchBadgeCls = isHighMatch
    ? "bg-green-500/20 text-green-400 border-green-500/30"
    : "bg-green-900/40 text-green-600 border-green-800/60";
  // Left border brightness: bright green for high match, dimmer for lower
  const leftBorderColor = isHighMatch ? "rgba(34,197,94,0.85)" : "rgba(34,197,94,0.3)";

  const slideClass =
    animating === "left" ? "translate-x-[-110%] opacity-0"
      : animating === "right" ? "translate-x-[110%] opacity-0"
        : "translate-x-0 opacity-100";

  return (
    <div
      className={`
        relative w-full h-[70vh] bg-[#111613] border border-white/[0.07]
        rounded-2xl shadow-2xl flex flex-col overflow-hidden
        transition-all duration-300 ease-in-out ${slideClass}
      `}
      style={{
        borderLeft: `4px solid ${leftBorderColor}`,
      }}
    >

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="relative p-5 flex items-start justify-between gap-4">
        {/* Icon */}
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
            <Briefcase className="w-5 h-5 text-green-400/80" />
          </div>
          <div className="min-w-0">
            <h2 className="text-[17px] font-bold leading-snug text-white">{title || "Untitled Role"}</h2>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-[13px] text-white/50">
              {company && (
                <span className="flex items-center gap-1">
                  <Building2 className="w-3.5 h-3.5" />{company}
                </span>
              )}
              {company && (location || empType || experience) && <span className="opacity-40">·</span>}
              {location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />{location}
                </span>
              )}
              {location && (empType || experience) && <span className="opacity-40">·</span>}
              {empType && (
                <span className="text-green-400/70 font-medium">{empType}</span>
              )}
              {empType && experience && <span className="opacity-40">·</span>}
              {experience && (
                <span className="flex items-center gap-1">
                  <User className="w-3.5 h-3.5" />{experience}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Match badge */}
        <div className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-bold border ${matchBadgeCls}`}>
          <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
          {pct}% match
        </div>
      </div>

      {/* ── Scrollable body ────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">

        {/* Description */}
        {description && (
          <div className="px-5 pb-4">
            <div className="relative">
              <div
                className="text-[13.5px] text-white/50 leading-relaxed overflow-hidden transition-all duration-300"
                style={{ maxHeight: descExpanded ? "none" : "18em" }}
              >
                {renderDescription(description)}
              </div>
              {!descExpanded && (
                <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-[#111613] to-transparent pointer-events-none" />
              )}
            </div>
            <button
              onClick={() => setDescExpanded(v => !v)}
              className="mt-1.5 text-green-400/70 text-[12px] font-medium hover:text-green-400 transition-colors"
            >
              {descExpanded ? "View less..." : "View more..."}
            </button>
          </div>
        )}

        {/* Required Skills */}
        {rawSkills.length > 0 && (
          <div className="px-5 pb-5">
            <p className="text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5">
              Required Skills
            </p>
            <div className="flex flex-wrap gap-2">
              {rawSkills.map(s => {
                const has = matchingSet.has(s.toLowerCase());
                return has ? (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[12.5px] font-medium
                               bg-green-500/20 text-green-400 border border-green-500/30"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                    {s}
                  </span>
                ) : (
                  <span
                    key={s}
                    className="inline-flex items-center px-3 py-1 rounded-full text-[12.5px] font-medium
                               bg-white/[0.04] text-white/35 border border-white/[0.08]"
                  >
                    {s}
                  </span>
                );
              })}
            </div>
          </div>
        )}

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

function EmptyCard({ onBack }: { onBack: () => void }) {
  return (
    <div className="w-full max-w-6xl bg-card border border-border rounded-2xl shadow-xl p-12 flex flex-col items-center justify-center gap-4 min-h-[340px]">
      <Briefcase className="w-10 h-10 text-muted-foreground" />
      <h2 className="text-lg font-semibold">No more matching jobs</h2>
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        You&apos;ve seen all available matches. Go back and try different roles.
      </p>
      <Link
        href="/select-jobs"
        onClick={onBack}
        className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
      >
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
  // isEmpty = no card to show AND we're not still loading
  // Covers: (a) swiped through all cards, (b) backend finished with 0 results, (c) idle/error
  const isEmpty = !currentJob && !isWaiting;

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

      <div className="flex-1 w-full flex items-center justify-center px-4 py-1 overflow-hidden">
        {/* Outer row: [Skip] [Card] [Apply] */}
        <div className="w-[90%] flex items-center justify-center gap-6">

          {/* ── Skip button ─────────────────────────────────────── */}
          <div className="flex-shrink-0 flex flex-col items-center justify-center">
            <button
              id="skip-btn"
              onClick={handleSkip}
              aria-label="Skip"
              disabled={!currentJob}
              className="
                flex flex-col items-center gap-2
                group disabled:opacity-30 disabled:cursor-not-allowed
              "
            >
              <div className="
                w-14 h-14 rounded-full border-2 border-white/15 bg-white/5
                flex items-center justify-center
                group-hover:border-red-500/30 group-hover:bg-red-500/20
                transition-all duration-200
              ">
                <ArrowLeft className="w-5 h-5 text-white/40 group-hover:text-red-400 transition-colors" />
              </div>
              <span className="text-[11px] font-semibold text-white/30 uppercase tracking-widest group-hover:text-red-400 transition-colors">
                Skip
              </span>
            </button>
          </div>

          {/* ── Card area ───────────────────────────────────────── */}
          <div className="flex-1 flex justify-center min-w-0">
            {currentJob
              ? <JobCard job={currentJob} animating={animating} />
              : isWaiting ? <LoadingCard />
                : isEmpty ? <EmptyCard onBack={clearSession} />
                  : null}
          </div>

          {/* ── Apply button ────────────────────────────────────── */}
          <div className="flex-shrink-0 flex flex-col items-center justify-center">
            <button
              id="apply-btn"
              onClick={handleApply}
              aria-label="Apply"
              disabled={!currentJob}
              className="
                flex flex-col items-center gap-2
                group disabled:opacity-30 disabled:cursor-not-allowed
              "
            >
              <div className="
                w-14 h-14 rounded-full border-2 border-green-500/40 bg-green-500/10
                flex items-center justify-center
                group-hover:border-green-400/80 group-hover:bg-green-500/20
                transition-all duration-200
              ">
                <ArrowRight className="w-5 h-5 text-green-400 transition-colors" />
              </div>
              <span className="text-[11px] font-semibold text-green-500/70 uppercase tracking-widest group-hover:text-green-400 transition-colors">
                Apply
              </span>
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
