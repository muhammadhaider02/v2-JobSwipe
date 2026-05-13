'use client';

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type PipelineStatus = 'idle' | 'polling' | 'completed' | 'failed';

interface ResumeUploadProps {
  onAutofill: (data: any) => void;
}

export function ResumeUpload({ onAutofill }: ResumeUploadProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const llmDoneRef = useRef(false);
  const skillDoneRef = useRef(false);
  const projectDoneRef = useRef(false);

  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [llmStatus, setLlmStatus] = useState<PipelineStatus>('idle');
  const [skillStatus, setSkillStatus] = useState<PipelineStatus>('idle');
  const [projectStatus, setProjectStatus] = useState<PipelineStatus>('idle');
  const [dismissedStages, setDismissedStages] = useState<Set<string>>(new Set());

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, []);

  const isProcessing =
    uploading ||
    llmStatus === 'polling' ||
    skillStatus === 'polling' ||
    projectStatus === 'polling';

  const isComplete =
    llmStatus === 'completed' &&
    skillStatus === 'completed' &&
    projectStatus === 'completed';

  const hasPartialFailure =
    (llmStatus === 'failed' ||
      skillStatus === 'failed' ||
      projectStatus === 'failed') &&
    !isProcessing;

  function pollLLMResults(jobId: string) {
    const poll = async () => {
      try {
        const res = await fetch(`/api/get-llm-results/${jobId}`);
        if (!res.ok) {
          if (res.status === 404) {
            setLlmStatus('failed');
            setSkillStatus('failed');
            setProjectStatus('failed');
            setError('Job not found');
            if (pollingIntervalRef.current)
              clearInterval(pollingIntervalRef.current);
            return;
          }
          throw new Error(`Failed to poll: ${res.status}`);
        }

        const data = await res.json();

        const stopIfAllDone = () => {
          if (
            llmDoneRef.current &&
            skillDoneRef.current &&
            projectDoneRef.current
          ) {
            if (pollingIntervalRef.current)
              clearInterval(pollingIntervalRef.current);
          }
        };

        if (data.skill_enrichment) {
          if (
            data.skill_enrichment.status === 'completed' &&
            !skillDoneRef.current
          ) {
            skillDoneRef.current = true;
            setSkillStatus('completed');
            if (data.skill_enrichment.skills) {
              onAutofill({ skills: data.skill_enrichment.skills });
            }
            stopIfAllDone();
          } else if (
            data.skill_enrichment.status === 'failed' &&
            !skillDoneRef.current
          ) {
            skillDoneRef.current = true;
            setSkillStatus('failed');
            stopIfAllDone();
          }
        }

        if (data.project_llm) {
          if (
            data.project_llm.status === 'completed' &&
            !projectDoneRef.current
          ) {
            projectDoneRef.current = true;
            setProjectStatus('completed');
            if (data.project_llm.projects) {
              onAutofill({ projects: data.project_llm.projects });
            }
            stopIfAllDone();
          } else if (
            data.project_llm.status === 'failed' &&
            !projectDoneRef.current
          ) {
            projectDoneRef.current = true;
            setProjectStatus('failed');
            stopIfAllDone();
          }
        }

        if (data.status === 'completed' && !llmDoneRef.current) {
          llmDoneRef.current = true;
          setLlmStatus('completed');
          if (data.result) onAutofill(data.result);
          stopIfAllDone();
        } else if (data.status === 'failed' && !llmDoneRef.current) {
          llmDoneRef.current = true;
          setLlmStatus('failed');
          let errMessage = data.error || 'LLM processing failed';
          if (
            errMessage.includes('429') ||
            errMessage.includes('TOO MANY REQUESTS')
          ) {
            errMessage =
              'Server limits reached. Please try again in a minute.';
          } else if (
            errMessage.includes('500') ||
            errMessage.includes('INTERNAL SERVER ERROR')
          ) {
            errMessage = 'Server error. Please try uploading again.';
          } else if (errMessage.length > 100) {
            errMessage = errMessage.substring(0, 100) + '...';
          }
          setError(errMessage);
          stopIfAllDone();
        }
      } catch (err: any) {
        console.error('Polling error:', err instanceof Error ? err.message : 'Unknown error');
      }
    };

    llmDoneRef.current = false;
    skillDoneRef.current = false;
    projectDoneRef.current = false;
    setLlmStatus('polling');
    setSkillStatus('polling');
    setProjectStatus('polling');
    pollingIntervalRef.current = setInterval(poll, 2000);
    poll();
  }

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    setFileName(file.name);
    setLlmStatus('idle');
    setSkillStatus('idle');
    setProjectStatus('idle');
    setDismissedStages(new Set());

    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/upload', { method: 'POST', body: form });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const json = await res.json();
      onAutofill(json);
      if (json.job_id) pollLLMResults(json.job_id);
    } catch (err: any) {
      setError(err?.message || 'Failed to upload resume');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  }

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (
        f &&
        (f.type === 'application/pdf' ||
          f.name.endsWith('.docx'))
      ) {
        handleFile(f);
      } else {
        setError('Please upload a PDF or DOCX file');
      }
    },
    [],
  );

  const pipelineSteps = [
    { label: 'Skills', status: skillStatus },
    { label: 'Projects', status: projectStatus },
    { label: 'Education & Experience', status: llmStatus },
  ];

  useEffect(() => {
    const timers: NodeJS.Timeout[] = [];
    for (const step of pipelineSteps) {
      if (step.status === 'completed' && !dismissedStages.has(step.label)) {
        const t = setTimeout(() => {
          setDismissedStages((prev) => new Set(prev).add(step.label));
        }, 800);
        timers.push(t);
      }
    }
    return () => timers.forEach(clearTimeout);
  }, [skillStatus, projectStatus, llmStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleSteps = pipelineSteps.filter(
    (step) => !dismissedStages.has(step.label),
  );

  const showPipeline =
    (llmStatus !== 'idle' || skillStatus !== 'idle' || projectStatus !== 'idle') &&
    visibleSteps.length > 0;

  return (
    <div className="w-full space-y-3">
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx"
        className="hidden"
        onChange={onPickFile}
      />

      <motion.div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !isProcessing && fileRef.current?.click()}
        className={cn(
          'relative w-full rounded-xl border-2 border-dashed p-6 transition-colors cursor-pointer',
          'flex flex-col items-center justify-center gap-3 text-center',
          isDragging && 'border-primary bg-primary/5',
          !isDragging && !isProcessing && 'border-border hover:border-primary/50 hover:bg-accent/30',
          isProcessing && 'border-primary/30 bg-primary/5 cursor-wait',
          isComplete && 'border-green-500/50 bg-green-500/5',
          hasPartialFailure && !isProcessing && 'border-amber-500/50 bg-amber-500/5',
        )}
        animate={isDragging ? { scale: 1.01 } : { scale: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      >
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.div
              key="processing"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="flex flex-col items-center gap-2"
            >
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
              <p className="text-sm font-medium">Processing your resume...</p>
              {fileName && (
                <p className="text-xs text-muted-foreground">{fileName}</p>
              )}
            </motion.div>
          ) : isComplete ? (
            <motion.div
              key="complete"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="flex flex-col items-center gap-2"
            >
              <CheckCircle2 className="w-8 h-8 text-green-500" />
              <p className="text-sm font-medium">Resume processed successfully</p>
              <p className="text-xs text-muted-foreground">
                Drop another file to replace, or click to browse
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="flex flex-col items-center gap-2"
            >
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Upload className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">
                  Drop your resume here or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  PDF or DOCX, up to 10 MB
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence>
        {showPipeline && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-1.5 rounded-lg bg-muted/50 p-3">
              <AnimatePresence initial={false}>
                {visibleSteps.map((step) => (
                  <motion.div
                    key={step.label}
                    initial={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                    transition={{ type: 'spring' as const, stiffness: 100, damping: 20 }}
                    className="overflow-hidden"
                  >
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-muted-foreground">{step.label}</span>
                      <PipelineStatusBadge status={step.status} />
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-xs text-destructive"
          >
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function PipelineStatusBadge({ status }: { status: PipelineStatus }) {
  switch (status) {
    case 'polling':
      return (
        <span className="flex items-center gap-1 text-primary">
          <Loader2 className="w-3 h-3 animate-spin" />
          Processing
        </span>
      );
    case 'completed':
      return (
        <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
          <CheckCircle2 className="w-3 h-3" />
          Done
        </span>
      );
    case 'failed':
      return (
        <span className="flex items-center gap-1 text-destructive">
          <AlertCircle className="w-3 h-3" />
          Failed
        </span>
      );
    default:
      return (
        <span className="text-muted-foreground">Waiting</span>
      );
  }
}
