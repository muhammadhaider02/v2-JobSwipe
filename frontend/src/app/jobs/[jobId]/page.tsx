"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText, ChevronDown, Check, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";

type JobData = Record<string, any>;

type TemplateItem = {
  name: string;
  display_name: string;
};

// Fix #1: multi-step loading messages that cycle every 3 seconds
const LOADING_STEPS = [
  "Analyzing job requirements…",
  "Optimizing resume bullets…",
  "Writing tailored cover letter…",
  "Finalizing your materials…",
];

function stringifyResume(value: any): string {
  if (!value) return "{}";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "{}";
  }
}

export default function JobApplicationMaterialsPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = decodeURIComponent(params.jobId || "");

  const [userId, setUserId] = useState<string | null>(null);
  const [job, setJob] = useState<JobData | null>(null);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [coverLetterTemplate, setCoverLetterTemplate] = useState("");

  const [applicationId, setApplicationId] = useState<number | null>(null);
  const [resumeJsonText, setResumeJsonText] = useState("{}");
  const [coverLetterText, setCoverLetterText] = useState("");

  const [loading, setLoading] = useState(true);
  const [loadingStep, setLoadingStep] = useState(0); // Fix #1
  const [error, setError] = useState<string | null>(null);

  // Fix #3: debounce auto-save refs and state
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const savedFadeRef = useRef<NodeJS.Timeout | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");

  // Fix #4: regenerate resume loading state
  const [regenResumeLoading, setRegenResumeLoading] = useState(false);

  const title = useMemo(() => {
    if (!job) return "Job";
    return job.title || job.job_title || "Job";
  }, [job]);

  // Fix #1: cycle loading messages while the LLM is running
  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % LOADING_STEPS.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [loading]);

  // Fix #3: auto-save with 3-second debounce
  const triggerAutoSave = useCallback(
    (resume: string, coverLetter: string) => {
      // No application record yet — nothing to save to
      if (!applicationId || !userId) return;

      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);

      debounceRef.current = setTimeout(async () => {
        setSaveStatus("saving");
        try {
          // Don't save if the resume textarea has broken JSON (user is mid-edit)
          let parsedResume: any = null;
          try {
            parsedResume = JSON.parse(resume);
          } catch {
            setSaveStatus("idle");
            return;
          }

          await fetch(`${BACKEND_BASE}/application-materials/save-draft`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              application_id: applicationId,
              user_id: userId,
              optimized_resume: parsedResume,
              cover_letter: coverLetter,
            }),
          });

          setSaveStatus("saved");
          // Fade the "Saved" indicator out after 2 seconds
          savedFadeRef.current = setTimeout(() => setSaveStatus("idle"), 2000);
        } catch {
          setSaveStatus("idle");
        }
      }, 3000);
    },
    [applicationId, userId]
  );

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
    };
  }, []);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      setLoadingStep(0);
      setError(null);

      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user?.id) {
          setError("Please login first.");
          return;
        }

        const uid = user.id;
        setUserId(uid);

        // Fetch job info and templates in parallel
        const [jobRes, templatesRes] = await Promise.all([
          fetch(`${BACKEND_BASE}/api/jobs/${encodeURIComponent(jobId)}`),
          fetch(`${BACKEND_BASE}/cover-letter-templates`),
        ]);

        if (jobRes.ok) {
          const jobData = await jobRes.json();
          setJob(jobData?.job || null);
        } else {
          // Fall back to session storage if the API call fails
          const cached = sessionStorage.getItem("vettedJobs");
          const parsed = cached ? JSON.parse(cached) : [];
          const fallback = parsed.find((item: any) => item?.job_id === jobId);
          if (fallback?.job_data) setJob(fallback.job_data);
        }

        if (templatesRes.ok) {
          const templateData = await templatesRes.json();
          const templateList: TemplateItem[] = templateData?.templates || [];
          setTemplates(templateList);
          if (templateList.length > 0) setCoverLetterTemplate(templateList[0].name);
        }

        // Fix #2: Check the DB first — skip the 15-second LLM call if materials exist
        const existingRes = await fetch(
          `${BACKEND_BASE}/application-materials/${encodeURIComponent(jobId)}?user_id=${uid}`
        );

        if (existingRes.ok) {
          const existingData = await existingRes.json();
          if (existingData?.has_materials) {
            setApplicationId(existingData.application_id ?? null);
            setResumeJsonText(stringifyResume(existingData.optimized_resume));
            setCoverLetterText(existingData.cover_letter || "");
            return; // Done — no LLM call needed ✓
          }
        }

        // No saved materials — trigger full AI generation
        const defaultSections = ["summary", "experience", "skills"];
        const prepareRes = await fetch(`${BACKEND_BASE}/prepare-application-materials`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: uid,
            job_id: jobId,
            sections_to_optimize: defaultSections,
          }),
        });

        if (!prepareRes.ok) {
          throw new Error(`Failed to prepare materials (${prepareRes.status})`);
        }

        const prepareData = await prepareRes.json();
        setApplicationId(prepareData?.application_id ?? null);
        setResumeJsonText(stringifyResume(prepareData?.materials?.optimized_resume));
        setCoverLetterText(prepareData?.materials?.cover_letter || "");

        const backendTemplate = prepareData?.materials?.metadata?.template_used;
        if (typeof backendTemplate === "string" && backendTemplate.trim()) {
          setCoverLetterTemplate(backendTemplate);
        }
      } catch (e: any) {
        setError(e?.message || "Failed to load application materials.");
      } finally {
        setLoading(false);
      }
    }

    if (jobId) bootstrap();
  }, [jobId]);

  // Regenerate cover letter with selected template
  async function regenerateCoverLetter() {
    if (!userId || !coverLetterTemplate) return;
    setError(null);

    try {
      const res = await fetch(`${BACKEND_BASE}/generate-cover-letter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          job_id: jobId,
          template_name: coverLetterTemplate,
        }),
      });

      if (!res.ok) throw new Error(`Failed to regenerate cover letter (${res.status})`);

      const data = await res.json();
      const newCoverLetter = data?.cover_letter || "";
      setCoverLetterText(newCoverLetter);
      triggerAutoSave(resumeJsonText, newCoverLetter);
    } catch (e: any) {
      setError(e?.message || "Failed to regenerate cover letter.");
    }
  }

  // Fix #4: Force a fresh LLM re-generation of the resume only
  async function regenerateResume() {
    if (!userId || regenResumeLoading) return;
    setRegenResumeLoading(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND_BASE}/prepare-application-materials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          job_id: jobId,
          sections_to_optimize: ["summary", "experience", "skills"],
        }),
      });

      if (!res.ok) throw new Error(`Failed to regenerate resume (${res.status})`);

      const data = await res.json();
      if (data?.application_id) setApplicationId(data.application_id);
      const newResume = stringifyResume(data?.materials?.optimized_resume);
      setResumeJsonText(newResume);
      // Persist the fresh version immediately via auto-save
      triggerAutoSave(newResume, coverLetterText);
    } catch (e: any) {
      setError(e?.message || "Failed to regenerate resume.");
    } finally {
      setRegenResumeLoading(false);
    }
  }

  // Fix #1: multi-step loading screen
  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative items-center justify-center min-h-[50vh]">
        <Loader2 className="w-6 h-6 animate-spin text-primary mb-3" />
        <div className="text-sm text-muted-foreground transition-all duration-500">
          {LOADING_STEPS[loadingStep]}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      {/* Back button */}
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      {/* Fix #3: Save status indicator — top-right corner */}
      {saveStatus !== "idle" && (
        <div className="absolute top-4 right-6 z-10 flex items-center gap-1.5 text-xs text-muted-foreground">
          {saveStatus === "saving" ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <Check className="w-3 h-3 text-green-500" />
              Saved
            </>
          )}
        </div>
      )}

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2 space-y-6">
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">Application Materials</h1>
            </div>
            <p className="text-muted-foreground">{title}</p>
          </div>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 rounded-md px-4 py-3">
              {error}
            </div>
          )}

          {/* Resume Card — Fix #4: Regenerate button in card header */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle>Optimized Resume</CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={regenerateResume}
                disabled={regenResumeLoading || !userId}
                className="flex items-center gap-1.5"
              >
                {regenResumeLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5" />
                )}
                Regenerate
              </Button>
            </CardHeader>
            <CardContent>
              <textarea
                className="min-h-[260px] w-full rounded-md border bg-background p-3 font-mono text-xs"
                value={resumeJsonText}
                onChange={(e) => {
                  setResumeJsonText(e.target.value);
                  triggerAutoSave(e.target.value, coverLetterText); // Fix #3
                }}
              />
            </CardContent>
          </Card>

          {/* Cover Letter Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Optimized Cover Letter</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="relative w-full">
                  <select
                    className="h-10 w-full appearance-none rounded-md border bg-background pl-3 pr-10 text-sm"
                    value={coverLetterTemplate}
                    onChange={(e) => setCoverLetterTemplate(e.target.value)}
                  >
                    {templates.length === 0 && <option value="">No templates found</option>}
                    {templates.map((template) => (
                      <option key={template.name} value={template.name}>
                        {template.display_name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-50 pointer-events-none" />
                </div>
                <Button
                  variant="outline"
                  onClick={regenerateCoverLetter}
                  disabled={!coverLetterTemplate || !userId}
                >
                  Generate
                </Button>
              </div>

              <textarea
                className="min-h-[220px] w-full rounded-md border bg-background p-3 text-sm"
                value={coverLetterText}
                onChange={(e) => {
                  setCoverLetterText(e.target.value);
                  triggerAutoSave(resumeJsonText, e.target.value); // Fix #3
                }}
              />
            </CardContent>
          </Card>

          <div className="flex justify-end gap-3 w-full pb-0 -mt-2">
            <button
              onClick={() => {}}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md"
            >
              Self Apply
            </button>
            <button
              onClick={() => {}}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md"
            >
              Auto Apply
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
