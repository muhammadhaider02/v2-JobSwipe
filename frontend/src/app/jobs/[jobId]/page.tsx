'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'motion/react';
import { createClient } from '@/lib/supabase/client';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  ArrowLeft,
  FileText,
  ChevronDown,
  Check,
  Loader2,
  X,
  Download,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/shared/page-header';

type JobData = Record<string, any>;

type TemplateItem = {
  name: string;
  display_name: string;
};

const LOADING_STEPS = [
  'Analyzing job requirements...',
  'Optimizing resume bullets...',
  'Writing tailored cover letter...',
  'Finalizing your materials...',
];

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

function stringifyResume(value: any): string {
  if (!value) return '{}';
  try {
    if (typeof value === 'object' && !Array.isArray(value)) {
      const preferredOrder = [
        'personal_info',
        'personal_information',
        'contact',
        'education',
        'experience',
        'projects',
        'certifications',
        'skills',
      ];

      const orderedObj: Record<string, any> = {};

      for (const key of preferredOrder) {
        if (key in value) {
          orderedObj[key] = value[key];
        }
      }

      for (const key in value) {
        if (!(key in orderedObj)) {
          orderedObj[key] = value[key];
        }
      }
      return JSON.stringify(orderedObj, null, 2);
    }

    return JSON.stringify(value, null, 2);
  } catch {
    return '{}';
  }
}

export default function JobApplicationMaterialsPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = decodeURIComponent(params.jobId || '');

  const [userId, setUserId] = useState<string | null>(null);
  const [job, setJob] = useState<JobData | null>(null);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [coverLetterTemplate, setCoverLetterTemplate] = useState('');

  const [applicationId, setApplicationId] = useState<number | null>(null);
  const [resumeJsonText, setResumeJsonText] = useState('{}');
  const [coverLetterText, setCoverLetterText] = useState('');

  const [loading, setLoading] = useState(true);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const savedFadeRef = useRef<NodeJS.Timeout | null>(null);
  const [saveStatus, setSaveStatus] = useState<
    'idle' | 'saving' | 'saved'
  >('idle');
  const [applyLoading, setApplyLoading] = useState(false);

  const [regenResumeLoading, setRegenResumeLoading] = useState(false);

  const [pdfModalOpen, setPdfModalOpen] = useState(false);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfFileName, setPdfFileName] = useState('Resume.pdf');
  const [pdfLoading, setPdfLoading] = useState(false);
  const pdfBlobRef = useRef<string | null>(null);

  const title = useMemo(() => {
    if (!job) return 'Job';
    return job.title || job.job_title || 'Job';
  }, [job]);

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % LOADING_STEPS.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [loading]);

  const triggerAutoSave = useCallback(
    (resume: string, coverLetter: string) => {
      if (!applicationId || !userId) return;

      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);

      debounceRef.current = setTimeout(async () => {
        setSaveStatus('saving');
        try {
          let parsedResume: any = null;
          try {
            parsedResume = JSON.parse(resume);
          } catch {
            setSaveStatus('idle');
            return;
          }

          await fetch(`/api/application-materials/save-draft`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              application_id: applicationId,
              user_id: userId,
              optimized_resume: parsedResume,
              cover_letter: coverLetter,
            }),
          });

          setSaveStatus('saved');
          savedFadeRef.current = setTimeout(
            () => setSaveStatus('idle'),
            2000,
          );
        } catch {
          setSaveStatus('idle');
        }
      }, 3000);
    },
    [applicationId, userId],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
      if (pdfBlobRef.current) URL.revokeObjectURL(pdfBlobRef.current);
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
          setError('Please login first.');
          return;
        }

        const uid = user.id;
        setUserId(uid);

        const [jobRes, templatesRes] = await Promise.all([
          fetch(`/api/jobs/${encodeURIComponent(jobId)}`),
          fetch(`/api/cover-letter-templates`),
        ]);

        if (jobRes.ok) {
          const jobData = await jobRes.json();
          setJob(jobData?.job || null);
        } else {
          const cached = sessionStorage.getItem('vettedJobs');
          const parsed = cached ? JSON.parse(cached) : [];
          const fallback = parsed.find(
            (item: any) => item?.job_id === jobId,
          );
          if (fallback?.job_data) setJob(fallback.job_data);
        }

        if (templatesRes.ok) {
          const templateData = await templatesRes.json();
          const templateList: TemplateItem[] =
            templateData?.templates || [];
          setTemplates(templateList);
          if (templateList.length > 0)
            setCoverLetterTemplate(templateList[0].name);
        }

        const existingRes = await fetch(
          `/api/application-materials/${encodeURIComponent(jobId)}?user_id=${uid}`,
        );

        if (existingRes.ok) {
          const existingData = await existingRes.json();
          if (existingData?.has_materials) {
            setApplicationId(existingData.application_id ?? null);
            setResumeJsonText(
              stringifyResume(existingData.optimized_resume),
            );
            setCoverLetterText(existingData.cover_letter || '');
            return;
          }
        }

        const defaultSections = ['summary', 'experience', 'skills'];
        const prepareRes = await fetch(
          `/api/prepare-application-materials`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: uid,
              job_id: jobId,
              sections_to_optimize: defaultSections,
            }),
          },
        );

        if (!prepareRes.ok) {
          throw new Error(
            `Failed to prepare materials (${prepareRes.status})`,
          );
        }

        const prepareData = await prepareRes.json();
        setApplicationId(prepareData?.application_id ?? null);
        setResumeJsonText(
          stringifyResume(prepareData?.materials?.optimized_resume),
        );
        setCoverLetterText(
          prepareData?.materials?.cover_letter || '',
        );

        const backendTemplate =
          prepareData?.materials?.metadata?.template_used;
        if (
          typeof backendTemplate === 'string' &&
          backendTemplate.trim()
        ) {
          setCoverLetterTemplate(backendTemplate);
        }
      } catch (e: any) {
        setError(
          e?.message || 'Failed to load application materials.',
        );
      } finally {
        setLoading(false);
      }
    }

    if (jobId) bootstrap();
  }, [jobId]);

  async function regenerateCoverLetter() {
    if (!userId || !coverLetterTemplate) return;
    setError(null);

    try {
      const res = await fetch(`/api/generate-cover-letter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          job_id: jobId,
          template_name: coverLetterTemplate,
        }),
      });

      if (!res.ok)
        throw new Error(
          `Failed to regenerate cover letter (${res.status})`,
        );

      const data = await res.json();
      const newCoverLetter = data?.cover_letter || '';
      setCoverLetterText(newCoverLetter);
      triggerAutoSave(resumeJsonText, newCoverLetter);
    } catch (e: any) {
      setError(e?.message || 'Failed to regenerate cover letter.');
    }
  }

  async function regenerateResume() {
    if (!userId || regenResumeLoading) return;
    setRegenResumeLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/prepare-application-materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          job_id: jobId,
          sections_to_optimize: [
            'summary',
            'experience',
            'skills',
          ],
        }),
      });

      if (!res.ok)
        throw new Error(
          `Failed to regenerate resume (${res.status})`,
        );

      const data = await res.json();
      if (data?.application_id)
        setApplicationId(data.application_id);
      const newResume = stringifyResume(
        data?.materials?.optimized_resume,
      );
      setResumeJsonText(newResume);
      triggerAutoSave(newResume, coverLetterText);
    } catch (e: any) {
      setError(e?.message || 'Failed to regenerate resume.');
    } finally {
      setRegenResumeLoading(false);
    }
  }

  async function viewPdf() {
    setPdfLoading(true);
    setError(null);
    try {
      let parsedResume: any;
      try {
        parsedResume = JSON.parse(resumeJsonText);
      } catch {
        setError(
          'The resume JSON is not valid. Please fix any syntax errors before generating a PDF.',
        );
        return;
      }

      const toPascalCase = (s: string) =>
        s
          .toLowerCase()
          .split(/[\s_\-]+/)
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join('');

      let userName = 'User';
      const pInfo =
        parsedResume.personal_info ||
        parsedResume.contact ||
        parsedResume.personal_information ||
        {};
      if (pInfo.name) {
        userName = toPascalCase(pInfo.name.trim());
      }
      const companyName = job?.company
        ? toPascalCase(job.company.trim())
        : 'Company';
      const fileName = `${companyName}-${userName}-Resume.pdf`;
      setPdfFileName(fileName);

      const res = await fetch(`/api/generate-resume-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_json: parsedResume }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.error || `Server returned ${res.status}`,
        );
      }

      const blob = await res.blob();

      let fileToURL: Blob | File = blob;
      try {
        fileToURL = new File([blob], fileName, {
          type: 'application/pdf',
        });
      } catch {
        /* fallback for older browsers */
      }

      if (pdfBlobRef.current) URL.revokeObjectURL(pdfBlobRef.current);
      const url = URL.createObjectURL(fileToURL);
      pdfBlobRef.current = url;
      setPdfBlobUrl(url);
      setPdfModalOpen(true);
    } catch (e: any) {
      setError(e?.message || 'Failed to generate PDF.');
    } finally {
      setPdfLoading(false);
    }
  }

  async function handleApply() {
    setApplyLoading(true);
    setError(null);
    try {
      let parsedResume: any;
      try {
        parsedResume = JSON.parse(resumeJsonText);
      } catch {
        setError(
          'The resume JSON is not valid. Please fix any syntax errors before applying.',
        );
        return;
      }

      if (!parsedResume || Object.keys(parsedResume).length === 0) {
        setError(
          'Resume has not been generated yet. Please ensure the job is scraped and saved before applying.',
        );
        return;
      }

      const toPascalCase = (s: string) =>
        s
          .toLowerCase()
          .split(/[\s_\-]+/)
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join('');

      let userName = 'User';
      const pInfo =
        parsedResume.personal_info ||
        parsedResume.contact ||
        parsedResume.personal_information ||
        {};
      if (pInfo.name) {
        userName = toPascalCase(pInfo.name.trim());
      }
      const companyName = job?.company
        ? toPascalCase(job.company.trim())
        : 'Company';
      const fileName = `${companyName}-${userName}-Resume.pdf`;

      const res = await fetch(`/api/generate-resume-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_json: parsedResume }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.error || `Server returned ${res.status}`,
        );
      }

      const blob = await res.blob();

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      const jobUrl = job?.url;
      if (jobUrl) {
        window.open(jobUrl, '_blank');
      } else {
        window.open('about:blank', '_blank');
      }

      if (userId && jobId) {
        fetch(`/api/mark-applied`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            job_id: jobId,
            application_id: applicationId,
          }),
        }).catch(() => {});
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to generate PDF for apply.');
    } finally {
      setApplyLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
        <div className="flex-1 w-full pb-8 pt-0 px-4">
          <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
            <div className="mb-5 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-muted" />
                <div>
                  <div className="h-7 w-56 bg-muted rounded mb-1" />
                  <div className="h-4 w-40 bg-muted rounded" />
                </div>
              </div>
            </div>

            <div className="text-center py-4 mb-4">
              <AnimatePresence mode="wait">
                <motion.p
                  key={loadingStep}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={spring}
                  className="text-sm text-muted-foreground"
                >
                  {LOADING_STEPS[loadingStep]}
                </motion.p>
              </AnimatePresence>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-pulse">
              <div className="bg-card border rounded-xl p-6">
                <div className="h-6 w-40 bg-muted rounded mb-4" />
                <div className="h-[260px] bg-muted rounded" />
                <div className="flex gap-2 mt-4">
                  <div className="h-9 w-32 bg-muted rounded-lg" />
                  <div className="h-9 w-28 bg-muted rounded-lg" />
                </div>
              </div>
              <div className="bg-card border rounded-xl p-6">
                <div className="h-6 w-44 bg-muted rounded mb-4" />
                <div className="h-9 w-full bg-muted rounded mb-4" />
                <div className="h-[220px] bg-muted rounded" />
                <div className="h-9 w-28 bg-muted rounded-lg mt-4" />
              </div>
            </div>
            <div className="h-10 w-full bg-muted rounded-lg mt-6 animate-pulse" />
          </div>
        </div>
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

      <AnimatePresence>
        {saveStatus !== 'idle' && (
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={spring}
            className="absolute top-4 right-6 z-10 flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            {saveStatus === 'saving' ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check className="w-3 h-3 text-green-500" />
                Saved
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2 space-y-6">
          <PageHeader
            icon={FileText}
            title="Application Materials"
            subtitle={title}
          />

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={spring}
                className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-3 flex items-center gap-2"
              >
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...spring, delay: 0.08 }}
            >
              <Card>
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <CardTitle>Optimized Resume</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={viewPdf}
                      disabled={pdfLoading}
                    >
                      {pdfLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileText className="w-3.5 h-3.5" />
                      )}
                      Generate PDF
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={regenerateResume}
                      disabled={regenResumeLoading || !userId}
                      className="gap-1.5"
                    >
                      {regenResumeLoading && (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      )}
                      Regenerate
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Textarea
                    className="min-h-[260px] font-mono text-xs"
                    value={resumeJsonText}
                    onChange={(e) => {
                      setResumeJsonText(e.target.value);
                      triggerAutoSave(
                        e.target.value,
                        coverLetterText,
                      );
                    }}
                  />
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...spring, delay: 0.16 }}
            >
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle>Optimized Cover Letter</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <div className="relative w-full">
                      <select
                        className="h-10 w-full appearance-none rounded-md border border-input bg-background pl-3 pr-10 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        value={coverLetterTemplate}
                        onChange={(e) =>
                          setCoverLetterTemplate(e.target.value)
                        }
                      >
                        {templates.length === 0 && (
                          <option value="">
                            No templates found
                          </option>
                        )}
                        {templates.map((template) => (
                          <option
                            key={template.name}
                            value={template.name}
                          >
                            {template.display_name}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-50 pointer-events-none" />
                    </div>
                    <Button
                      variant="outline"
                      onClick={regenerateCoverLetter}
                      disabled={
                        !coverLetterTemplate || !userId
                      }
                    >
                      Regenerate
                    </Button>
                  </div>

                  <Textarea
                    className="min-h-[220px] text-sm"
                    value={coverLetterText}
                    onChange={(e) => {
                      setCoverLetterText(e.target.value);
                      triggerAutoSave(
                        resumeJsonText,
                        e.target.value,
                      );
                    }}
                  />
                </CardContent>
              </Card>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...spring, delay: 0.24 }}
            className="flex justify-end gap-3 w-full pb-0"
          >
            <Button
              onClick={handleApply}
              disabled={applyLoading}
              className="gap-2"
            >
              {applyLoading && (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              )}
              Apply
            </Button>
          </motion.div>
        </div>
      </div>

      <AnimatePresence>
        {pdfModalOpen && pdfBlobUrl && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm"
            onClick={(e) => {
              if (e.target === e.currentTarget)
                setPdfModalOpen(false);
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={spring}
              className="relative w-[90vw] max-w-4xl h-[90vh] bg-background rounded-xl shadow-2xl border flex flex-col overflow-hidden"
            >
              <div className="flex items-center justify-between px-5 py-3 border-b shrink-0 bg-muted/30">
                <span className="font-semibold text-sm">
                  Preview:{' '}
                  {pdfFileName.replace(/_/g, ' ')}
                </span>
                <div className="flex items-center gap-2">
                  <Button asChild size="sm" className="gap-1.5">
                    <a
                      href={pdfBlobUrl}
                      download={pdfFileName}
                      title="Download PDF"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download
                    </a>
                  </Button>
                  <button
                    onClick={() => setPdfModalOpen(false)}
                    className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                    aria-label="Close PDF preview"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <iframe
                src={pdfBlobUrl}
                className="flex-1 w-full border-0"
                title="Resume PDF Preview"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
