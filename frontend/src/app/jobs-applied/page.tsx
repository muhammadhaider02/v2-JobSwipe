"use client";

import React from "react";
import { ArrowLeft, Clock, Briefcase } from "lucide-react";
import Link from "next/link";

type AppliedJob = {
  title: string;
  company: string;
  location: string;
  type: string;
  dateApplied: string;
};

const DUMMY_JOBS: AppliedJob[] = [
  {
    title: "Software Engineer I",
    company: "Company A",
    location: "Islamabad, Pakistan",
    type: "Full-time",
    dateApplied: "Mar 27, 2026",
  },
  {
    title: "Software Engineer II",
    company: "Company B",
    location: "Islamabad, Pakistan",
    type: "Full-time",
    dateApplied: "Mar 28, 2026",
  },
  {
    title: "Software Engineer III",
    company: "Company C",
    location: "Islamabad, Pakistan",
    type: "Full-time",
    dateApplied: "Mar 29, 2026",
  },
  {
    title: "Software Engineer IV",
    company: "Company D",
    location: "Islamabad, Pakistan",
    type: "Full-time",
    dateApplied: "Mar 30, 2026",
  },
  {
    title: "Software Engineer V",
    company: "Company E",
    location: "Islamabad, Pakistan",
    type: "Full-time",
    dateApplied: "Mar 31, 2026",
  },
];

export default function JobsAppliedPage() {
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
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">Applied Jobs</h1>
            </div>
            <p className="text-muted-foreground">
              A record of every role you&apos;ve sent out.
            </p>
          </div>

          {/* Applied Jobs List */}
          <div className="flex flex-col gap-3 mb-5">
            {DUMMY_JOBS.map((job, idx) => (
              <div
                key={idx}
                className="bg-card border rounded-xl py-2.5 px-4 shadow-sm hover:shadow-md transition-all flex items-center gap-4 hover:border-primary/50"
              >
                {/* Icon */}
                <div className="p-2.5 bg-primary/10 rounded-lg hidden sm:block flex-shrink-0">
                  <Briefcase className="w-5 h-5 text-primary" />
                </div>

                {/* Job details */}
                <div className="flex-grow">
                  <h3 className="text-lg font-semibold leading-tight">
                    {job.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-sm text-muted-foreground">
                    <span>{job.company}</span>
                    <span className="hidden sm:inline text-muted-foreground/40">•</span>
                    <span>{job.location}</span>
                    <span className="hidden sm:inline text-muted-foreground/40">•</span>
                    <span>{job.type}</span>
                  </div>
                </div>

                {/* Date Applied */}
                <div className="flex-shrink-0 text-right">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    Applied
                  </div>
                  <div className="font-semibold text-sm text-foreground">
                    {job.dateApplied}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
