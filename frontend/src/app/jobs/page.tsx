"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";

type VettedJob = {
  job_id: string;
  match_score?: number;
  confidence?: string;
  job_data?: Record<string, any>;
  [key: string]: any;
};

function readJobField(job: VettedJob, key: string): string {
  const root = job[key];
  if (typeof root === "string" && root.trim()) return root;

  const nested = job.job_data?.[key];
  if (typeof nested === "string" && nested.trim()) return nested;

  // Backend can store job title with different keys.
  if (key === "title") {
    const altRoot = job["job_title"];
    const altNested = job.job_data?.["job_title"];
    if (typeof altRoot === "string" && altRoot.trim()) return altRoot;
    if (typeof altNested === "string" && altNested.trim()) return altNested;
  }

  return "-";
}

export default function JobsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [userId, setUserId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<VettedJob[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryFromUrl = useMemo(() => searchParams.get("q") || "", [searchParams]);

  useEffect(() => {
    async function loadUser() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user?.id) {
        setUserId(user.id);
      } else {
        setError("Please login first.");
      }
    }

    loadUser();
  }, []);

  useEffect(() => {
    if (!userId) return;

    async function loadDefaultQueryAndJobs() {
      setLoading(true);
      setError(null);

      try {
        let searchQuery = queryFromUrl;

        if (!searchQuery) {
          const profileRes = await fetch(`${BACKEND_BASE}/user-profile/${userId}`);
          if (profileRes.ok) {
            const profileData = await profileRes.json();
            const recommendedRoles: string[] = profileData?.profile?.recommended_roles || [];
            searchQuery = recommendedRoles[0] || "software engineer";
          } else {
            searchQuery = "software engineer";
          }
        }

        setQuery(searchQuery);
        await fetchJobs(searchQuery, userId);
      } catch (e: any) {
        setError(e?.message || "Failed to load jobs.");
      } finally {
        setLoading(false);
      }
    }

    loadDefaultQueryAndJobs();
  }, [userId, queryFromUrl]);

  async function fetchJobs(searchQuery: string, activeUserId = userId) {
    if (!activeUserId) return;

    const res = await fetch(`${BACKEND_BASE}/api/jobs/vetted`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: activeUserId,
        search_query: searchQuery,
        mode: "db",
        limit: 10,
      }),
    });

    if (!res.ok) {
      throw new Error(`Job fetch failed (${res.status})`);
    }

    const data = await res.json();
    const vettedJobs: VettedJob[] = data?.vetted_jobs || [];
    setJobs(vettedJobs);

    sessionStorage.setItem("vettedJobs", JSON.stringify(vettedJobs));
  }

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await fetchJobs(query.trim());
    } catch (e: any) {
      setError(e?.message || "Failed to load jobs.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-10">
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Top Matched Jobs</h1>
          <p className="text-sm text-muted-foreground">
            Select a job to open application materials.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search query (for example: backend python developer)"
          />
          <Button onClick={handleSearch} disabled={loading || !userId}>
            {loading ? "Loading..." : "Fetch Jobs"}
          </Button>
        </div>

        {error && (
          <Card>
            <CardContent className="pt-6 text-sm text-red-600">{error}</CardContent>
          </Card>
        )}

        {!loading && jobs.length === 0 && !error && (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">
              No jobs found for this query yet.
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {jobs.map((job) => {
            const title = readJobField(job, "title");
            const company = readJobField(job, "company");
            const location = readJobField(job, "location");
            const industry = readJobField(job, "industry");
            const score = typeof job.match_score === "number" ? `${Math.round(job.match_score * 100)}%` : "-";

            return (
              <Card key={job.job_id} className="h-full">
                <CardHeader>
                  <CardTitle className="text-lg">{title}</CardTitle>
                  <CardDescription>{company}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>
                    <span className="font-medium">Location:</span> {location}
                  </p>
                  <p>
                    <span className="font-medium">Industry:</span> {industry}
                  </p>
                  <p>
                    <span className="font-medium">Match:</span> {score}
                  </p>
                  <Button
                    className="mt-3"
                    onClick={() => router.push(`/jobs/${encodeURIComponent(job.job_id)}`)}
                  >
                    Open Application Material
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </main>
  );
}
