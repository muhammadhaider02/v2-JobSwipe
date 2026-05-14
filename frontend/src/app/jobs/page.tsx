'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'motion/react';
import { createClient } from '@/lib/supabase/client';
import Link from 'next/link';
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  MapPin,
  Building2,
  User,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SkillBadge } from '@/components/shared/skill-badge';
import { EmptyState } from '@/components/shared/empty-state';

const POLL_INTERVAL_MS = 2000;
const REFILL_THRESHOLD = 10;

const SS_CARDS = 'jobs_cards';
const SS_INDEX = 'jobs_index';
const SS_SINCE = 'jobs_since';
const SS_STATUS = 'jobs_status';

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
  confidence: 'high' | 'medium' | 'low';
  matching_skills: string[];
  skill_gaps: string[];
  job_data: JobData;
};
type PollStatus = 'processing' | 'buffered' | 'done' | 'idle';

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

function getField(job: VettedJob, key: keyof JobData): string {
  const d = job.job_data;
  if (key === 'title') return d?.title || d?.job_title || '';
  if (key === 'employment_type')
    return d?.employment_type || d?.job_type || '';
  if (key === 'description')
    return d?.description || d?.job_description || '';
  return (d?.[key] as string) || '';
}

function saveSession(
  cards: VettedJob[],
  index: number,
  since: number,
  status: PollStatus,
) {
  try {
    sessionStorage.setItem(SS_CARDS, JSON.stringify(cards));
    sessionStorage.setItem(SS_INDEX, String(index));
    sessionStorage.setItem(SS_SINCE, String(since));
    sessionStorage.setItem(SS_STATUS, status);
  } catch {
    /* storage full / unavailable */
  }
}

function restoreSession(): {
  cards: VettedJob[];
  index: number;
  since: number;
  status: PollStatus;
} | null {
  try {
    const raw = sessionStorage.getItem(SS_CARDS);
    if (!raw) return null;
    const cards: VettedJob[] = JSON.parse(raw);
    if (!cards.length) return null;
    return {
      cards,
      index: parseInt(sessionStorage.getItem(SS_INDEX) || '0', 10),
      since: parseInt(sessionStorage.getItem(SS_SINCE) || '0', 10),
      status: (sessionStorage.getItem(SS_STATUS) ||
        'processing') as PollStatus,
    };
  } catch {
    return null;
  }
}

function clearSession() {
  [SS_CARDS, SS_INDEX, SS_SINCE, SS_STATUS].forEach((k) =>
    sessionStorage.removeItem(k),
  );
}

function renderDescription(text: string): React.ReactNode {
  const cleaned0 = text.replace(/show more/gi, '');
  const lines = cleaned0
    .split('\n')
    .filter((line) => !/^[-–—_\s]{3,}$/.test(line.trim()));

  const paragraphs = lines
    .join('\n')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <>
      {paragraphs.map((para, i) => {
        const parts = para.split(/(\*\*[^*]+\*\*)/g);
        return (
          <p key={i} className={i > 0 ? 'mt-2' : ''}>
            {parts.map((part, j) =>
              part.startsWith('**') && part.endsWith('**') ? (
                <strong
                  key={j}
                  className="text-foreground/80 font-semibold"
                >
                  {part.slice(2, -2)}
                </strong>
              ) : (
                <span key={j}>{part}</span>
              ),
            )}
          </p>
        );
      })}
    </>
  );
}

interface JobCardProps {
  job: VettedJob;
  animating: 'left' | 'right' | null;
}

function JobCard({ job, animating }: JobCardProps) {
  const [descExpanded, setDescExpanded] = useState(false);

  const title = getField(job, 'title');
  const company = getField(job, 'company');
  const location = getField(job, 'location');
  const empType = getField(job, 'employment_type');
  const description = getField(job, 'description');
  const expRaw = job.job_data?.experience_required;
  const experience = expRaw != null ? `${expRaw} yrs exp` : null;
  const pct = Math.round(job.match_score * 100);

  const matchingSet = new Set(
    (job.matching_skills || []).map((s) => s.toLowerCase()),
  );
  const rawSkills = job.job_data?.skills_required ?? [
    ...(job.matching_skills || []),
    ...(job.skill_gaps || []),
  ];

  const isHighMatch = pct >= 80;
  const matchBadgeCls = isHighMatch
    ? 'bg-green-500/20 text-green-600 dark:text-green-400 border-green-500/30'
    : 'bg-green-500/10 text-green-700 dark:text-green-600 border-green-500/20';
  const leftBorderColor = isHighMatch
    ? 'rgba(34,197,94,0.85)'
    : 'rgba(34,197,94,0.3)';

  const slideClass =
    animating === 'left'
      ? 'translate-x-[-110%] opacity-0'
      : animating === 'right'
        ? 'translate-x-[110%] opacity-0'
        : 'translate-x-0 opacity-100';

  return (
    <div
      className={`
        relative w-full h-[70vh] bg-card border border-border
        rounded-2xl shadow-2xl flex flex-col overflow-hidden
        transition-all duration-300 ease-in-out ${slideClass}
      `}
      style={{
        borderLeft: `4px solid ${leftBorderColor}`,
      }}
    >
      <div className="relative p-5 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-muted/30 border border-border flex items-center justify-center">
            <Briefcase className="w-5 h-5 text-green-500/80" />
          </div>
          <div className="min-w-0">
            <h2 className="text-[17px] font-bold leading-snug text-foreground">
              {title || 'Untitled Role'}
            </h2>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-[13px] text-muted-foreground">
              {company && (
                <span className="flex items-center gap-1">
                  <Building2 className="w-3.5 h-3.5" />
                  {company}
                </span>
              )}
              {company && (location || empType || experience) && (
                <span className="opacity-40">*</span>
              )}
              {location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  {location}
                </span>
              )}
              {location && (empType || experience) && (
                <span className="opacity-40">*</span>
              )}
              {empType && (
                <span className="text-green-600 dark:text-green-400/70 font-medium">
                  {empType}
                </span>
              )}
              {empType && experience && (
                <span className="opacity-40">*</span>
              )}
              {experience && (
                <span className="flex items-center gap-1">
                  <User className="w-3.5 h-3.5" />
                  {experience}
                </span>
              )}
            </div>
          </div>
        </div>

        <div
          className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-bold border ${matchBadgeCls}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
          {pct}% match
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
        {description && (
          <div className="px-5 pb-4">
            <div className="relative">
              <div
                className="text-[13.5px] text-muted-foreground leading-relaxed overflow-hidden transition-all duration-300"
                style={{
                  maxHeight: descExpanded ? 'none' : '18em',
                }}
              >
                {renderDescription(description)}
              </div>
              {!descExpanded && (
                <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-card to-transparent pointer-events-none" />
              )}
            </div>
            <button
              onClick={() => setDescExpanded((v) => !v)}
              className="mt-1.5 text-green-600 dark:text-green-400/70 text-[12px] font-medium hover:text-green-500 dark:hover:text-green-400 transition-colors"
            >
              {descExpanded ? 'View less...' : 'View more...'}
            </button>
          </div>
        )}

        {rawSkills.length > 0 && (
          <div className="px-5 pb-5">
            <p className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest mb-2.5">
              Required Skills
            </p>
            <div className="flex flex-wrap gap-2">
              {rawSkills.map((s) => {
                const has = matchingSet.has(s.toLowerCase());
                return (
                  <SkillBadge
                    key={s}
                    variant={has ? 'existing' : 'neutral'}
                  >
                    {has && (
                      <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                    )}
                    {s}
                  </SkillBadge>
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
    <div className="w-full max-w-6xl bg-card border border-border rounded-2xl shadow-xl p-8 min-h-[340px] animate-pulse">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 bg-muted rounded-lg" />
        <div className="flex-1">
          <div className="h-6 w-3/4 bg-muted rounded mb-2" />
          <div className="h-4 w-1/2 bg-muted rounded mb-1" />
          <div className="flex gap-2 mt-2">
            <div className="h-5 w-20 bg-muted rounded-full" />
            <div className="h-5 w-24 bg-muted rounded-full" />
            <div className="h-5 w-16 bg-muted rounded-full" />
          </div>
        </div>
        <div className="w-16 h-16 bg-muted rounded-full" />
      </div>
      <div className="space-y-2 mb-6">
        <div className="h-3.5 bg-muted rounded w-full" />
        <div className="h-3.5 bg-muted rounded w-full" />
        <div className="h-3.5 bg-muted rounded w-5/6" />
        <div className="h-3.5 bg-muted rounded w-4/6" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-6 bg-muted rounded-full"
            style={{ width: `${50 + Math.random() * 40}px` }}
          />
        ))}
      </div>
    </div>
  );
}

function EmptyCard({ onBack }: { onBack: () => void }) {
  return (
    <div className="w-full max-w-6xl">
      <EmptyState
        icon={Briefcase}
        title="No more matching jobs"
        description="You've seen all available matches. Go back and try different roles."
        action={{ label: 'Back to Select Jobs', href: '/select-jobs' }}
      />
    </div>
  );
}

export default function JobsPage() {
  const router = useRouter();

  const [userId, setUserId] = useState<string | null>(null);
  const [cards, setCards] = useState<VettedJob[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [status, setStatus] = useState<PollStatus>('processing');
  const [animating, setAnimating] = useState<'left' | 'right' | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const sinceRef = useRef(0);
  const indexRef = useRef(0);
  const statusRef = useRef<PollStatus>('processing');
  const cardsRef = useRef<VettedJob[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animRef = useRef(false);
  const appliedIdsRef = useRef<Set<string>>(new Set());
  const emptyPollCountRef = useRef(0);
  const isRestoredRef = useRef(false);

  useEffect(() => {
    indexRef.current = currentIndex;
  }, [currentIndex]);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);
  useEffect(() => {
    cardsRef.current = cards;
  }, [cards]);

  useEffect(() => {
    async function loadUser() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user?.id) {
        try {
          const res = await fetch(
            `/api/user-applications?user_id=${user.id}`,
          );
          if (res.ok) {
            const data = await res.json();
            appliedIdsRef.current = new Set(
              (data.applications || []).map(
                (a: { job_id: string }) => a.job_id,
              ),
            );
          }
        } catch {
          /* ignore */
        }
        setUserId(user.id);
      } else {
        setError('Please log in first.');
      }
    }
    loadUser();
  }, []);

  useEffect(() => {
    if (cards.length > 0) {
      saveSession(cards, currentIndex, sinceRef.current, status);
    }
  }, [cards, currentIndex, status]);

  const poll = useCallback(async (uid: string) => {
    try {
      const since = sinceRef.current;
      const consumed = indexRef.current;
      const res = await fetch(
        `/api/jobs/results?user_id=${uid}&since=${since}&consumed=${consumed}`,
      );
      if (!res.ok) return;

      const data: { jobs: VettedJob[]; total: number; status: string } =
        await res.json();

      if (data.jobs?.length) {
        sinceRef.current = data.total;
        emptyPollCountRef.current = 0;
        const newJobs = data.jobs.filter(
          (j: VettedJob) => !appliedIdsRef.current.has(j.job_id),
        );
        if (newJobs.length) {
          setCards((prev) => [...prev, ...newJobs]);
        }
      } else if (isRestoredRef.current) {
        emptyPollCountRef.current += 1;
        if (emptyPollCountRef.current >= 5) {
          isRestoredRef.current = false;
          emptyPollCountRef.current = 0;
          stopPolling();
          clearSession();
          setCards([]);
          setCurrentIndex(0);
          sinceRef.current = 0;
          indexRef.current = 0;
          cardsRef.current = [];

          const raw = sessionStorage.getItem('selectedRoles');
          let roles: string[] = [];
          try { if (raw) roles = JSON.parse(raw); } catch { /* ignore */ }
          if (roles.length) {
            fetch('/api/jobs/start-vetting', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ user_id: uid, roles }),
            }).then((r) => {
              if (r.ok) {
                setStatus('processing');
                statusRef.current = 'processing';
                startPolling(uid);
              }
            });
          }
          return;
        }
      }

      const newStatus = data.status as PollStatus;

      if (newStatus === 'done') {
        setStatus('done');
        statusRef.current = 'done';
        stopPolling();
      } else if (newStatus === 'buffered') {
        setStatus('buffered');
        statusRef.current = 'buffered';
        stopPolling();
      }
    } catch {
      /* transient */
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(uid: string) {
    stopPolling();
    pollRef.current = setInterval(() => poll(uid), POLL_INTERVAL_MS);
  }

  useEffect(() => {
    if (!userId) return;

    const restored = restoreSession();

    if (restored) {
      const filteredCards = restored.cards.filter(
        (c) => !appliedIdsRef.current.has(c.job_id),
      );
      setCards(filteredCards);
      setCurrentIndex(restored.index);
      sinceRef.current = restored.since;
      indexRef.current = restored.index;
      cardsRef.current = filteredCards;
      const st = restored.status;
      setStatus(st);
      statusRef.current = st;

      if (st === 'processing') {
        isRestoredRef.current = true;
        emptyPollCountRef.current = 0;
        startPolling(userId);
      }
    } else {
      const raw = sessionStorage.getItem('selectedRoles');
      let roles: string[] = [];
      try {
        if (raw) roles = JSON.parse(raw);
      } catch {
        /* ignore */
      }

      if (!roles.length) {
        setError(
          'No roles selected. Go back and pick at least one role.',
        );
        setStatus('idle');
        return;
      }

      async function begin() {
        const res = await fetch(`/api/jobs/start-vetting`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId, roles }),
        });
        if (!res.ok) {
          setError('Failed to start job search.');
          setStatus('idle');
          return;
        }

        sinceRef.current = 0;
        setStatus('processing');
        statusRef.current = 'processing';
        startPolling(userId!);
      }
      begin();
    }

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    const remaining = cardsRef.current.length - currentIndex;
    const canRefill =
      statusRef.current !== 'done' && statusRef.current !== 'idle';

    if (
      remaining >= 0 &&
      remaining < REFILL_THRESHOLD &&
      canRefill &&
      cardsRef.current.length > 0
    ) {
      setStatus('processing');
      statusRef.current = 'processing';
      startPolling(userId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex]);

  const handleSkip = useCallback(() => {
    if (indexRef.current >= cardsRef.current.length || animRef.current)
      return;
    animRef.current = true;
    setAnimating('left');
    setTimeout(() => {
      setCurrentIndex((i) => i + 1);
      setAnimating(null);
      animRef.current = false;
    }, 300);
  }, []);

  const handleApply = useCallback(() => {
    const idx = indexRef.current;
    const job = cardsRef.current[idx];
    if (!job || animRef.current) return;
    animRef.current = true;
    setAnimating('right');
    saveSession(
      cardsRef.current,
      idx + 1,
      sinceRef.current,
      statusRef.current,
    );
    setTimeout(() => {
      router.push(`/jobs/${encodeURIComponent(job.job_id)}`);
    }, 200);
  }, [router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') handleSkip();
      if (e.key === 'ArrowRight') handleApply();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handleSkip, handleApply]);

  const currentJob = cards[currentIndex] ?? null;
  const isWaiting =
    !currentJob &&
    (status === 'processing' ||
      (status === 'buffered' && cards.length === 0));
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
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={spring}
          className="mt-16 mx-auto w-full max-w-6xl text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-3 flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </motion.div>
      )}

      <div className="flex-1 w-full flex items-center justify-center px-4 py-1 overflow-hidden">
        <div className="w-[90%] flex items-center justify-center gap-6">
          <div className="flex-shrink-0 flex flex-col items-center justify-center">
            <button
              id="skip-btn"
              onClick={handleSkip}
              aria-label="Skip"
              disabled={!currentJob}
              className="flex flex-col items-center gap-2 group disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <div className="w-14 h-14 rounded-full border-2 border-border bg-muted/20 flex items-center justify-center group-hover:border-destructive/30 group-hover:bg-destructive/10 transition-all duration-200">
                <ArrowLeft className="w-5 h-5 text-muted-foreground group-hover:text-destructive transition-colors" />
              </div>
              <span className="text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-widest group-hover:text-destructive transition-colors">
                Skip
              </span>
            </button>
          </div>

          <div className="flex-1 flex justify-center min-w-0">
            {currentJob ? (
              <motion.div
                key={currentJob.job_id}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={spring}
                className="w-full"
              >
                <JobCard job={currentJob} animating={animating} />
              </motion.div>
            ) : isWaiting ? (
              <LoadingCard />
            ) : isEmpty ? (
              <EmptyCard onBack={clearSession} />
            ) : null}
          </div>

          <div className="flex-shrink-0 flex flex-col items-center justify-center">
            <button
              id="apply-btn"
              onClick={handleApply}
              aria-label="Apply"
              disabled={!currentJob}
              className="flex flex-col items-center gap-2 group disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <div className="w-14 h-14 rounded-full border-2 border-green-500/40 bg-green-500/10 flex items-center justify-center group-hover:border-green-400/80 group-hover:bg-green-500/20 transition-all duration-200">
                <ArrowRight className="w-5 h-5 text-green-500 transition-colors" />
              </div>
              <span className="text-[11px] font-semibold text-green-600/70 dark:text-green-500/70 uppercase tracking-widest group-hover:text-green-500 transition-colors">
                Apply
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
