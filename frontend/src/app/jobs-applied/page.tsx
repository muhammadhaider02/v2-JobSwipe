'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowLeft,
  Clock,
  Briefcase,
  ExternalLink,
  Inbox,
} from 'lucide-react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';

type AppliedJob = {
  job_id: string;
  title: string;
  company: string;
  location: string;
  type: string;
  url: string;
  applied_at: string | null;
};

function formatDate(iso: string | null): string {
  if (!iso) return '--';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

export default function JobsAppliedPage() {
  const [jobs, setJobs] = useState<AppliedJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchApplied() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user?.id) return;

        const res = await fetch(
          `/api/user-applications?user_id=${user.id}`,
        );
        if (!res.ok) return;
        const data = await res.json();
        setJobs(data.applications || []);
      } finally {
        setLoading(false);
      }
    }
    fetchApplied();
  }, []);

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/recommendations"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          <PageHeader
            icon={Clock}
            title="Applied Jobs"
            subtitle="A record of every role you've sent out."
          />

          {loading ? (
            <div className="flex flex-col gap-3 mb-5 animate-pulse">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-card border rounded-xl py-2.5 px-4 shadow-sm flex items-center gap-4"
                >
                  <div className="p-2.5 bg-muted rounded-lg hidden sm:block">
                    <div className="w-5 h-5" />
                  </div>
                  <div className="flex-grow">
                    <div className="h-5 bg-muted rounded w-48 mb-1.5" />
                    <div className="h-3.5 bg-muted rounded w-64" />
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <div className="h-3 bg-muted rounded w-12 mb-1" />
                    <div className="h-4 bg-muted rounded w-20" />
                  </div>
                </div>
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No applications yet"
              description="Start swiping to find your next role!"
              action={{ label: 'Browse Jobs', href: '/select-jobs' }}
            />
          ) : (
            <div className="flex flex-col gap-3 mb-5">
              {jobs.map((job, i) => (
                <motion.a
                  key={job.job_id}
                  href={job.url || undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ ...spring, delay: i * 0.06 }}
                  whileHover={{ x: 4 }}
                  className={`bg-card border rounded-xl py-2.5 px-4 shadow-sm hover:shadow-md transition-colors flex items-center gap-4 hover:border-primary/50${job.url ? ' cursor-pointer' : ' cursor-default'}`}
                >
                  <div className="p-2.5 bg-primary/10 rounded-lg hidden sm:block flex-shrink-0">
                    <Briefcase className="w-5 h-5 text-primary" />
                  </div>

                  <div className="flex-grow min-w-0">
                    <h3 className="text-lg font-semibold leading-tight truncate">
                      {job.title}
                    </h3>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-sm text-muted-foreground">
                      <span>{job.company}</span>
                      {job.location && (
                        <>
                          <span className="hidden sm:inline text-muted-foreground/40">
                            *
                          </span>
                          <span>{job.location}</span>
                        </>
                      )}
                      {job.type && (
                        <>
                          <span className="hidden sm:inline text-muted-foreground/40">
                            *
                          </span>
                          <span>{job.type}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex-shrink-0 flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground mb-0.5">
                        Applied
                      </div>
                      <div className="font-semibold text-sm text-foreground">
                        {formatDate(job.applied_at)}
                      </div>
                    </div>
                    {job.url && (
                      <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    )}
                  </div>
                </motion.a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
