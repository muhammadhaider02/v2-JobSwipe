"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText, ArrowRight } from "lucide-react";
import Link from "next/link";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";

type JobData = Record<string, any>;

type TemplateItem = {
  name: string;
  display_name: string;
};

const OPTIMIZABLE_SECTIONS = [
  { key: "summary", label: "Summary" },
  { key: "experience", label: "Experience" },
  { key: "skills", label: "Skills" },
  { key: "projects", label: "Projects" },
  { key: "education", label: "Education" },
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
  const router = useRouter();
  const jobId = decodeURIComponent(params.jobId || "");

  const [userId, setUserId] = useState<string | null>(null);
  const [job, setJob] = useState<JobData | null>(null);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [coverLetterTemplate, setCoverLetterTemplate] = useState("");
  const [resumeTemplate, setResumeTemplate] = useState("generic-classic");

  const [applicationId, setApplicationId] = useState<number | null>(null);
  const [resumeJsonText, setResumeJsonText] = useState("{}");
  const [coverLetterText, setCoverLetterText] = useState("");
  const [selectedSections, setSelectedSections] = useState<string[]>(["summary", "experience", "skills"]);

  const [loading, setLoading] = useState(true);
  const [preparing, setPreparing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const title = useMemo(() => {
    if (!job) return "Job";
    return job.title || job.job_title || "Job";
  }, [job]);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
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

        setUserId(user.id);

        const [jobRes, templatesRes] = await Promise.all([
          fetch(`${BACKEND_BASE}/api/jobs/${encodeURIComponent(jobId)}`),
          fetch(`${BACKEND_BASE}/cover-letter-templates`),
        ]);

        if (jobRes.ok) {
          const jobData = await jobRes.json();
          setJob(jobData?.job || null);
        } else {
          // Fallback to cached list from jobs page.
          const cached = sessionStorage.getItem("vettedJobs");
          const parsed = cached ? JSON.parse(cached) : [];
          const fallback = parsed.find((item: any) => item?.job_id === jobId);
          if (fallback?.job_data) {
            setJob(fallback.job_data);
          }
        }

        if (templatesRes.ok) {
          const templateData = await templatesRes.json();
          const templateList: TemplateItem[] = templateData?.templates || [];
          setTemplates(templateList);
          if (templateList.length > 0) {
            setCoverLetterTemplate(templateList[0].name);
          }
        }

      } catch (e: any) {
        setError(e?.message || "Failed to load application materials.");
      } finally {
        setLoading(false);
      }
    }

    if (jobId) {
      bootstrap();
    }
  }, [jobId]);

  function toggleSection(sectionKey: string) {
    setSelectedSections((prev) => {
      if (prev.includes(sectionKey)) {
        return prev.filter((item) => item !== sectionKey);
      }
      return [...prev, sectionKey];
    });
  }

  async function prepareMaterials() {
    if (!userId) return;
    if (selectedSections.length === 0) {
      setError("Select at least one section to optimize.");
      return;
    }

    setPreparing(true);
    setError(null);
    setMessage(null);

    try {
      const prepareRes = await fetch(`${BACKEND_BASE}/prepare-application-materials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          job_id: jobId,
          sections_to_optimize: selectedSections,
        }),
      });

      if (!prepareRes.ok) {
        throw new Error(`Failed to prepare materials (${prepareRes.status})`);
      }

      const prepareData = await prepareRes.json();
      setApplicationId(prepareData?.application_id || null);
      setResumeJsonText(stringifyResume(prepareData?.materials?.optimized_resume));
      setCoverLetterText(prepareData?.materials?.cover_letter || "");

      const backendTemplate = prepareData?.materials?.metadata?.template_used;
      if (typeof backendTemplate === "string" && backendTemplate.trim()) {
        setCoverLetterTemplate(backendTemplate);
      }

      if (!prepareData?.application_id) {
        setMessage("Materials prepared. Note: application record is missing, so draft save may be unavailable until DB table is created.");
      } else {
        setMessage("Materials prepared successfully.");
      }
    } catch (e: any) {
      setError(e?.message || "Failed to prepare application materials.");
    } finally {
      setPreparing(false);
    }
  }

  async function regenerateCoverLetter() {
    if (!userId || !coverLetterTemplate) return;

    setError(null);
    setMessage(null);

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

      if (!res.ok) {
        throw new Error(`Failed to regenerate cover letter (${res.status})`);
      }

      const data = await res.json();
      setCoverLetterText(data?.cover_letter || "");
      setMessage("Cover letter regenerated.");
    } catch (e: any) {
      setError(e?.message || "Failed to regenerate cover letter.");
    }
  }

  async function saveDraft() {
    if (!userId || !applicationId) return;

    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const parsedResume = JSON.parse(resumeJsonText || "{}");
      const templateName = `${resumeTemplate}|${coverLetterTemplate || "default"}`;

      const res = await fetch(`${BACKEND_BASE}/application-materials/save-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          application_id: applicationId,
          user_id: userId,
          optimized_resume: parsedResume,
          cover_letter: coverLetterText,
          template_name: templateName,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to save draft (${res.status})`);
      }

      setMessage("Draft saved to database.");
    } catch (e: any) {
      if (e instanceof SyntaxError) {
        setError("Resume JSON is not valid. Please fix formatting before saving.");
      } else {
        setError(e?.message || "Failed to save draft.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative items-center justify-center min-h-[50vh]">
        <div className="text-sm text-muted-foreground">Loading application materials...</div>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2 space-y-6">
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">Application Materials</h1>
            </div>
            <p className="text-muted-foreground">
              {title}
            </p>
          </div>

          {error && (
            <Card>
              <CardContent className="pt-6 text-sm text-red-600">{error}</CardContent>
            </Card>
          )}

          {message && (
            <Card>
              <CardContent className="pt-6 text-sm text-green-700">{message}</CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>1. Resume Template Selection (Generic)</CardTitle>
              <CardDescription>Minimal selection saved with your draft.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <p className="text-sm font-medium">Select sections to optimize</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {OPTIMIZABLE_SECTIONS.map((section) => (
                    <label key={section.key} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedSections.includes(section.key)}
                        onChange={() => toggleSection(section.key)}
                      />
                      <span>{section.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <select
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={resumeTemplate}
                onChange={(e) => setResumeTemplate(e.target.value)}
              >
                <option value="generic-classic">Generic Classic</option>
                <option value="generic-modern">Generic Modern</option>
                <option value="generic-compact">Generic Compact</option>
              </select>

              <Button onClick={prepareMaterials} disabled={!userId || preparing || selectedSections.length === 0}>
                {preparing ? "Preparing..." : "Prepare Materials"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>2. Optimized Resume (Editable)</CardTitle>
              <CardDescription>Edit the JSON directly for now.</CardDescription>
            </CardHeader>
            <CardContent>
              <textarea
                className="min-h-[260px] w-full rounded-md border bg-background p-3 font-mono text-xs"
                value={resumeJsonText}
                onChange={(e) => setResumeJsonText(e.target.value)}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>3. Cover Letter (Editable)</CardTitle>
              <CardDescription>Pick template and edit content.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
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
                <Button variant="outline" onClick={regenerateCoverLetter} disabled={!coverLetterTemplate || !userId}>
                  Regenerate
                </Button>
              </div>

              <textarea
                className="min-h-[220px] w-full rounded-md border bg-background p-3 text-sm"
                value={coverLetterText}
                onChange={(e) => setCoverLetterText(e.target.value)}
              />
            </CardContent>
          </Card>

          <div className="flex justify-end w-full pb-0 -mt-2">
            <button
              onClick={saveDraft}
              disabled={saving || !applicationId || !userId}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {saving ? "Saving..." : "Save Draft"}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
