"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, FileText, Loader2, Download, Copy, Check, Briefcase, Mail } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

type Job = {
  job_id: string;
  job_title: string;
  company_name: string;
  location: string;
  job_description?: string;
};

type Template = {
  id: string;
  name: string;
  description: string;
  color: string;
};

const templates: Template[] = [
  {
    id: "template1.txt",
    name: "Professional Standard",
    description: "A clean, professional cover letter focusing on commitment and reliability",
    color: "from-blue-500 to-cyan-500"
  },
  {
    id: "template2.txt",
    name: "Achievement Focused",
    description: "Emphasizes motivation and practical results from experience",
    color: "from-purple-500 to-pink-500"
  },
  {
    id: "template3.txt",
    name: "Portfolio Highlight",
    description: "Professional tone with emphasis on project work and expertise",
    color: "from-green-500 to-teal-500"
  },
  {
    id: "template4.txt",
    name: "Skills Showcase",
    description: "Highlights technical skills and collaborative experience",
    color: "from-orange-500 to-red-500"
  },
  {
    id: "template5.txt",
    name: "Results Driven",
    description: "Focuses on outcomes, innovation, and value contribution",
    color: "from-indigo-500 to-purple-500"
  }
];

export default function CoverLetterPage() {
  const searchParams = useSearchParams();
  const preSelectedJobId = searchParams.get('jobId');
  
  console.log(`[Cover Letter] Page loaded - preSelectedJobId from URL: ${preSelectedJobId}`);
  
  const [userId, setUserId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [generatedLetter, setGeneratedLetter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(true);

  useEffect(() => {
    console.log('[Cover Letter] Initial useEffect - fetching user');
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user?.id) {
        console.log(`[Cover Letter] User authenticated: ${data.user.id}`);
        setUserId(data.user.id);
        fetchJobs(data.user.id);
      } else {
        console.log('[Cover Letter] No user authenticated');
        setError("Please log in to generate cover letters");
        setLoadingJobs(false);
      }
    });
  }, []);

  // Fetch specific job if jobId is provided in URL
  useEffect(() => {
    console.log(`[Cover Letter] useEffect - preSelectedJobId: ${preSelectedJobId}, userId: ${userId}`);
    if (preSelectedJobId && userId) {
      console.log(`[Cover Letter] Triggering fetchSpecificJob for jobId: ${preSelectedJobId}`);
      fetchSpecificJob(preSelectedJobId);
    }
  }, [preSelectedJobId, userId]);

  // Pre-select job if jobId is provided in URL (backup in case it's in the matched jobs list)
  useEffect(() => {
    console.log(`[Cover Letter] Backup selection - preSelectedJobId: ${preSelectedJobId}, selectedJob: ${selectedJob?.job_id}, jobs.length: ${jobs.length}`);
    
    // Skip if we don't have a jobId or if job is already selected
    if (!preSelectedJobId || selectedJob) {
      if (selectedJob) {
        console.log(`[Cover Letter] Job already selected: ${selectedJob.job_title}`);
      }
      return;
    }
    
    // If jobs are loaded and we haven't selected yet, try to find it in the list
    if (jobs.length > 0) {
      const job = jobs.find(j => j.job_id === preSelectedJobId);
      if (job) {
        console.log(`[Cover Letter] Found job in matched jobs list, selecting: ${job.job_title}`);
        setSelectedJob(job);
      } else {
        console.log(`[Cover Letter] Job ${preSelectedJobId} not found in matched jobs list`);
      }
    }
  }, [preSelectedJobId, jobs, selectedJob]);

  const fetchJobs = async (uid: string) => {
    try {
      console.log(`[Cover Letter] Fetching jobs for user: ${uid}`);
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      const response = await fetch(`${base}/match-jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: uid }),
      });

      console.log(`[Cover Letter] Match jobs response status: ${response.status}`);

      if (response.ok) {
        const data = await response.json();
        const jobList = data.matches || [];
        console.log(`[Cover Letter] Retrieved ${jobList.length} matched jobs`);
        setJobs(jobList.slice(0, 20)); // Limit to 20 jobs for performance
      } else {
        const errorText = await response.text();
        console.error(`[Cover Letter] Failed to fetch matched jobs:`, {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        });
      }
    } catch (err) {
      console.error("[Cover Letter] Error fetching jobs:", {
        error: err,
        message: err instanceof Error ? err.message : String(err)
      });
    } finally {
      setLoadingJobs(false);
    }
  };

  const fetchSpecificJob = async (jobId: string) => {
    try {
      console.log(`[Cover Letter] Fetching specific job: ${jobId}`);
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      const response = await fetch(`${base}/job-details/${jobId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      console.log(`[Cover Letter] Response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Cover Letter] Failed to fetch job details:`, {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        });
        return;
      }

      const data = await response.json();
      console.log(`[Cover Letter] Successfully fetched job:`, {
        job_id: data.job_id,
        job_title: data.job_title,
        company: data.company_name
      });

      if (data) {
        // Add this job to the jobs list if not already there
        setJobs(prevJobs => {
          const exists = prevJobs.some(j => j.job_id === data.job_id);
          if (!exists) {
            console.log(`[Cover Letter] Adding job to list`);
            return [data, ...prevJobs];
          }
          console.log(`[Cover Letter] Job already in list`);
          return prevJobs;
        });
        
        // Select this job
        setSelectedJob(data);
        console.log(`[Cover Letter] Job selected successfully`);
      }
    } catch (err) {
      console.error("[Cover Letter] Error fetching specific job:", {
        error: err,
        message: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack : undefined
      });
    }
  };

  const handleGenerateLetter = async () => {
    if (!selectedTemplate || !selectedJob || !userId) {
      setError("Please select both a template and a job");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      console.log('[Cover Letter] Generating cover letter:', {
        userId,
        jobId: selectedJob.job_id,
        templateId: selectedTemplate.id
      });

      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      const response = await fetch(`${base}/generate-cover-letter`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: userId,
          job_id: selectedJob.job_id,
          template_name: selectedTemplate.id,
        }),
      });

      console.log(`[Cover Letter] Generate response status: ${response.status}`);

      if (!response.ok) {
        // Try to get error details from response
        let errorMessage = `Failed to generate cover letter: ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.error) {
            errorMessage = errorData.error;
          }
        } catch (e) {
          // If we can't parse JSON, use default message
        }
        console.error('[Cover Letter] Generation failed:', errorMessage);
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('[Cover Letter] Successfully generated cover letter');
      setGeneratedLetter(data.cover_letter);
    } catch (err) {
      console.error("[Cover Letter] Error generating cover letter:", {
        error: err,
        message: err instanceof Error ? err.message : String(err)
      });
      setError(err instanceof Error ? err.message : "Failed to generate cover letter");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (generatedLetter) {
      navigator.clipboard.writeText(generatedLetter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (generatedLetter) {
      const blob = new Blob([generatedLetter], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cover-letter-${selectedJob?.company_name || "job"}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  if (error && !userId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">🔒</div>
          <h1 className="text-2xl font-bold mb-2">Authentication Required</h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Link href="/onboarding" className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90">
            <ArrowLeft size={16} /> Go to Onboarding
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 py-12 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link 
            href={preSelectedJobId ? "/jobs" : "/recommendations"} 
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft size={16} /> Back to {preSelectedJobId ? "Jobs" : "Recommendations"}
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <Mail className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold">Generate Cover Letter</h1>
          </div>
          <p className="text-muted-foreground">
            Create a personalized cover letter for your job applications
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left Column: Template Selection */}
          <div className="lg:col-span-1">
            <div className="bg-card border rounded-xl p-6 shadow-sm">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Choose Template
              </h2>
              <div className="space-y-3">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => setSelectedTemplate(template)}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                      selectedTemplate?.id === template.id
                        ? "border-primary bg-primary/5 shadow-md"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <div className={`w-full h-2 rounded-full bg-gradient-to-r ${template.color} mb-3`} />
                    <h3 className="font-semibold mb-1">{template.name}</h3>
                    <p className="text-xs text-muted-foreground">{template.description}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Middle Column: Job Selection */}
          <div className="lg:col-span-1">
            <div className="bg-card border rounded-xl p-6 shadow-sm">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Briefcase className="w-5 h-5" />
                Select Job
              </h2>
              
              {preSelectedJobId && selectedJob && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800 font-medium">
                    ✓ Pre-selected: {selectedJob.job_title}
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    {selectedJob.company_name}
                  </p>
                </div>
              )}
              
              {preSelectedJobId && !selectedJob && loadingJobs && (
                <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                  <p className="text-sm text-gray-600">
                    <Loader2 className="w-3 h-3 inline animate-spin mr-2" />
                    Loading job information...
                  </p>
                </div>
              )}
              
              {loadingJobs ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
              ) : jobs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p className="mb-4">No jobs found. Browse jobs first!</p>
                  <Link href="/jobs" className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90">
                    <Briefcase size={16} /> Browse Jobs
                  </Link>
                </div>
              ) : (
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                  {jobs.length === 0 && selectedJob && (
                    <p className="text-xs text-muted-foreground mb-2">
                      Showing selected job only. {preSelectedJobId ? 'Other matched jobs may appear below if available.' : ''}
                    </p>
                  )}
                  {jobs.length > 0 && preSelectedJobId && (
                    <p className="text-xs text-muted-foreground mb-2">
                      {jobs.length} job{jobs.length !== 1 ? 's' : ''} available
                    </p>
                  )}
                  {jobs.map((job) => (
                    <button
                      key={job.job_id}
                      onClick={() => setSelectedJob(job)}
                      className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                        selectedJob?.job_id === job.job_id
                          ? "border-primary bg-primary/5 shadow-md"
                          : "border-border hover:border-primary/50"
                      }`}
                    >
                      <h3 className="font-semibold mb-1 line-clamp-1">{job.job_title}</h3>
                      <p className="text-sm text-muted-foreground line-clamp-1">{job.company_name}</p>
                      {job.location && (
                        <p className="text-xs text-muted-foreground mt-1">{job.location}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Preview & Actions */}
          <div className="lg:col-span-1">
            <div className="bg-card border rounded-xl p-6 shadow-sm sticky top-6">
              <h2 className="text-xl font-bold mb-4">Preview</h2>
              
              {/* Selection Status */}
              <div className="mb-4 space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Template:</span>
                  <span className={selectedTemplate ? "font-medium text-green-600" : "text-gray-400"}>
                    {selectedTemplate ? selectedTemplate.name : "Not selected"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Job:</span>
                  <span className={selectedJob ? "font-medium text-green-600" : "text-gray-400"}>
                    {selectedJob ? selectedJob.job_title : "Not selected"}
                  </span>
                </div>
              </div>
              
              {!generatedLetter ? (
                <div className="text-center py-12">
                  {selectedTemplate && selectedJob ? (
                    <div className="space-y-4">
                      <Mail className="w-16 h-16 mx-auto mb-4 opacity-50 text-primary" />
                      <p className="text-muted-foreground mb-4">
                        Ready to generate your cover letter
                      </p>
                      <button
                        onClick={handleGenerateLetter}
                        disabled={loading}
                        className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md disabled:opacity-50"
                      >
                        {loading ? (
                          <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <FileText className="w-5 h-5" />
                            Generate Cover Letter
                          </>
                        )}
                      </button>
                      {error && (
                        <p className="text-sm text-red-500 mt-2">{error}</p>
                      )}
                    </div>
                  ) : (
                    <div>
                      <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                      <p className="text-muted-foreground">
                        Select a template and a job to generate your cover letter
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-muted/50 p-4 rounded-lg max-h-[500px] overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm font-mono">{generatedLetter}</pre>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleCopy}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-card border rounded-lg hover:bg-accent transition-colors"
                    >
                      {copied ? (
                        <>
                          <Check className="w-4 h-4" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4" />
                          Copy
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleDownload}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-all"
                    >
                      <Download className="w-4 h-4" />
                      Download
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      setGeneratedLetter("");
                      setSelectedTemplate(null);
                      setSelectedJob(null);
                    }}
                    className="w-full px-4 py-2 border rounded-lg hover:bg-accent transition-colors"
                  >
                    Generate Another
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
