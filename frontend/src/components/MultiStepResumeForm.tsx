"use client";

import React, { useMemo, useState, useRef, useEffect } from "react";
import { Upload, Plus, Trash2 } from "lucide-react";

type Profile = {
  name: string;
  email: string;
  phone: string;
  location: string;
  summary: string;
  github: string;
  linkedin: string;
  portfolio: string;
  profilePictureUrl?: string;
};

type Education = {
  degree: string;
  institution: string;
  startYear: string;
  endYear: string;
  gpa: string;
};

type Experience = {
  company: string;
  role: string;
  duration: string;
  description: string;
};

type Project = {
  name: string;
  description: string;
  link: string;
};

type Certificate = {
  name: string;
  issuer: string;
  issueDate: string;
  expiryDate?: string;
};

type FormState = {
  profile: Profile;
  education: Education[];
  experience: Experience[];
  projects: Project[];
  skills: string[];
  certificates: Certificate;
};

const steps = [
  { id: 1, label: "Profile" },
  { id: 2, label: "Projects" },
  { id: 3, label: "Skills" },
  { id: 4, label: "Certificates" },
  { id: 5, label: "Education" },
  { id: 6, label: "Experience" },
];

export default function MultiStepResumeForm() {
  const [currentStep, setCurrentStep] = useState(0);
  const [maxVisitedStep, setMaxVisitedStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [rawJson, setRawJson] = useState<any | null>(null);
  const [refinedJson, setRefinedJson] = useState<BackendJson | null>(null);

  const [form, setForm] = useState<FormState>({
    profile: {
      name: "",
      email: "",
      phone: "",
      location: "",
      summary: "",
      github: "",
      linkedin: "",
      portfolio: "",
      profilePictureUrl: undefined,
    },
    education: [{
      degree: "",
      institution: "",
      startYear: "",
      endYear: "",
      gpa: "",
    }],
    experience: [{
      company: "",
      role: "",
      duration: "",
      description: "",
    }],
    projects: [{
      name: "",
      description: "",
      link: "",
    }],
    skills: [],
    certificates: {
      name: "",
      issuer: "",
      issueDate: "",
      expiryDate: "",
    },
  });

  const progress = useMemo(() => ((currentStep + 1) / steps.length) * 100, [currentStep]);

  function handleInput<K extends keyof FormState>(section: K, field: keyof FormState[K]) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setForm((prev) => ({
        ...prev,
        [section]: {
          ...(prev[section] as any),
          [field]: e.target.value,
        },
      }));
    };
  }

  function handleArrayInput<K extends "education" | "experience" | "projects">(
    section: K,
    index: number,
    field: keyof FormState[K][number]
  ) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setForm((prev) => ({
        ...prev,
        [section]: prev[section].map((item, i) =>
          i === index ? { ...item, [field]: e.target.value } : item
        ),
      }));
    };
  }

  function addArrayItem<K extends "education" | "experience" | "projects">(section: K) {
    const emptyItem = section === "education"
      ? { degree: "", institution: "", startYear: "", endYear: "", gpa: "" }
      : section === "experience"
      ? { company: "", role: "", duration: "", description: "" }
      : { name: "", description: "", link: "" };

    setForm((prev) => ({
      ...prev,
      [section]: [...prev[section], emptyItem],
    }));
  }

  function removeArrayItem<K extends "education" | "experience" | "projects">(section: K, index: number) {
    setForm((prev) => ({
      ...prev,
      [section]: prev[section].filter((_, i) => i !== index),
    }));
  }

  function validateStep(stepIndex: number): Record<string, string> {
    const errs: Record<string, string> = {};
    if (stepIndex === 0) {
      if (!form.profile.name.trim()) errs.name = "Name is required";
      if (!form.profile.email.trim()) errs.email = "Email is required";
    } else if (stepIndex === 4) {
      if (form.education.length === 0 || !form.education[0].degree.trim()) errs.degree = "At least one degree is required";
      if (form.education.length === 0 || !form.education[0].institution.trim()) errs.institution = "Institution is required";
    } else if (stepIndex === 5) {
      if (form.experience.length === 0 || !form.experience[0].company.trim()) errs.company = "At least one company is required";
      if (form.experience.length === 0 || !form.experience[0].role.trim()) errs.role = "Role is required";
    } else if (stepIndex === 2) {
      if (form.skills.length === 0) errs.skills = "Add at least one skill";
    }
    return errs;
  }

  function onNext() {
    const v = validateStep(currentStep);
    setErrors(v);
    if (Object.keys(v).length === 0) {
      setCurrentStep((s) => Math.min(s + 1, steps.length - 1));
      setMaxVisitedStep((m) => Math.max(m, currentStep + 1));
    }
  }

  function onPrev() {
    setCurrentStep((s) => Math.max(s - 1, 0));
  }

  function onJump(to: number) {
    if (to <= maxVisitedStep) {
      setCurrentStep(to);
    }
  }

  function onSubmit() {
    const v = validateStep(currentStep);
    setErrors(v);
    if (Object.keys(v).length === 0) {
      // Navigate to recommendations page with skills data
      const skillsParam = encodeURIComponent(JSON.stringify(form.skills));
      window.location.href = `/recommendations?skills=${skillsParam}`;
    }
  }

  function onSkillsInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const input = e.currentTarget.value;
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const token = input.trim().replace(/,$/, "");
      if (!token) return;
      setForm((prev) => ({ ...prev, skills: Array.from(new Set([...prev.skills, token])) }));
      e.currentTarget.value = "";
    }
  }

  function removeSkill(skill: string) {
    setForm((prev) => ({ ...prev, skills: prev.skills.filter((s) => s !== skill) }));
  }

  function onProfilePicChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const url = URL.createObjectURL(f);
    setForm((prev) => ({ ...prev, profile: { ...prev.profile, profilePictureUrl: url } }));
  }

  useEffect(() => {
    return () => {
      if (form.profile.profilePictureUrl) {
        URL.revokeObjectURL(form.profile.profilePictureUrl);
      }
    };
  }, [form.profile.profilePictureUrl]);

  return (
    <div className="w-full flex flex-col items-center">
      <div className="w-full max-w-3xl">
        {/* Global Autofill Button */}
        <div className="w-full flex items-center justify-center mb-4">
          <ResumeAutofillButton
            onAutofill={(data) => {
              // Prefer refined for autofill, fallback to raw
              const preferred = (data as any)?.refined || data;
              setRawJson(data);
              setRefinedJson((data as any)?.refined || null);
              setForm((prev) => applyAutofill(prev, preferred));
            }}
          />
        </div>

        {/* JSON Preview: Raw and Refined */}
        {(rawJson || refinedJson) && (
          <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-medium mb-2">Raw JSON</div>
              <pre className="p-3 rounded border max-h-64 overflow-auto text-xs bg-muted/30">
                {JSON.stringify(rawJson, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-sm font-medium mb-2">Refined JSON</div>
              {refinedJson ? (
                <pre className="p-3 rounded border max-h-64 overflow-auto text-xs bg-muted/30">
                  {JSON.stringify(refinedJson, null, 2)}
                </pre>
              ) : (
                <div className="text-xs text-muted-foreground">No refined output (check backend refinement_error).</div>
              )}
            </div>
          </div>
        )}

        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex gap-2 items-center text-sm text-muted-foreground">
              <span className="font-medium">Step {currentStep + 1} of {steps.length}</span>
            </div>
            <div className="text-sm font-semibold">{steps[currentStep].label}</div>
          </div>
          <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <div className="flex justify-between mt-3">
            {steps.map((s, idx) => (
              <button
                key={s.id}
                onClick={() => onJump(idx)}
                className={`text-xs rounded-full w-8 h-8 flex items-center justify-center border transition-colors ${
                  idx === currentStep
                    ? "bg-primary text-primary-foreground border-primary"
                    : idx <= maxVisitedStep
                      ? "bg-background border-primary text-primary hover:bg-primary/10"
                      : "bg-background border-muted text-muted-foreground cursor-not-allowed"
                }`}
                disabled={idx > maxVisitedStep}
                aria-label={`Go to step ${s.id}`}
              >
                {s.id}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-card border rounded-xl p-6 shadow-sm transition-all">
          {currentStep === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="text-sm font-medium">Profile Picture</label>
                <div className="mt-2 flex items-center gap-3">
                  {form.profile.profilePictureUrl ? (
                    <img src={form.profile.profilePictureUrl} alt="profile" className="w-14 h-14 rounded-full object-cover" />
                  ) : (
                    <div className="w-14 h-14 rounded-full bg-muted" />
                  )}
                  <div>
                    <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={onProfilePicChange} />
                    <button type="button" className="px-3 py-1.5 text-sm border rounded-md hover:bg-accent" onClick={() => fileInputRef.current?.click()}>
                      Upload
                    </button>
                  </div>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Name *</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.name} onChange={handleInput("profile", "name")} />
                {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name}</p>}
              </div>
              <div>
                <label className="text-sm font-medium">Email *</label>
                <input type="email" className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.email} onChange={handleInput("profile", "email")} />
                {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email}</p>}
              </div>
              <div>
                <label className="text-sm font-medium">Phone</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.phone} onChange={handleInput("profile", "phone")} />
              </div>
              <div>
                <label className="text-sm font-medium">Location</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.location} onChange={handleInput("profile", "location")} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">Summary</label>
                <textarea className="mt-1 w-full border rounded-md px-3 py-2 min-h-[80px]" value={form.profile.summary} onChange={handleInput("profile", "summary")} />
              </div>
              <div>
                <label className="text-sm font-medium">GitHub</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.github} onChange={handleInput("profile", "github")} />
              </div>
              <div>
                <label className="text-sm font-medium">LinkedIn</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.linkedin} onChange={handleInput("profile", "linkedin")} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium">Portfolio</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.profile.portfolio} onChange={handleInput("profile", "portfolio")} />
              </div>
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-6">
              {form.education.map((edu, index) => (
                <div key={index} className="border rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold">Education {index + 1}</h3>
                    {form.education.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem("education", index)}
                        className="text-red-600 hover:text-red-700 p-1"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium">Degree *</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={edu.degree}
                        onChange={handleArrayInput("education", index, "degree")}
                      />
                      {index === 0 && errors.degree && <p className="text-xs text-red-600 mt-1">{errors.degree}</p>}
                    </div>
                    <div>
                      <label className="text-sm font-medium">Institution *</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={edu.institution}
                        onChange={handleArrayInput("education", index, "institution")}
                      />
                      {index === 0 && errors.institution && <p className="text-xs text-red-600 mt-1">{errors.institution}</p>}
                    </div>
                    <div>
                      <label className="text-sm font-medium">Start Year</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={edu.startYear}
                        onChange={handleArrayInput("education", index, "startYear")}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">End Year</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={edu.endYear}
                        onChange={handleArrayInput("education", index, "endYear")}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-sm font-medium">GPA</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={edu.gpa}
                        onChange={handleArrayInput("education", index, "gpa")}
                      />
                    </div>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => addArrayItem("education")}
                className="w-full py-2 border-2 border-dashed rounded-lg hover:bg-accent flex items-center justify-center gap-2 text-sm"
              >
                <Plus size={16} /> Add Education
              </button>
            </div>
          )}

          {currentStep === 5 && (
            <div className="space-y-6">
              {form.experience.map((exp, index) => (
                <div key={index} className="border rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold">Experience {index + 1}</h3>
                    {form.experience.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem("experience", index)}
                        className="text-red-600 hover:text-red-700 p-1"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium">Company *</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={exp.company}
                        onChange={handleArrayInput("experience", index, "company")}
                      />
                      {index === 0 && errors.company && <p className="text-xs text-red-600 mt-1">{errors.company}</p>}
                    </div>
                    <div>
                      <label className="text-sm font-medium">Role *</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={exp.role}
                        onChange={handleArrayInput("experience", index, "role")}
                      />
                      {index === 0 && errors.role && <p className="text-xs text-red-600 mt-1">{errors.role}</p>}
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-sm font-medium">Duration</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={exp.duration}
                        onChange={handleArrayInput("experience", index, "duration")}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-sm font-medium">Description</label>
                      <textarea
                        className="mt-1 w-full border rounded-md px-3 py-2 min-h-[80px]"
                        value={exp.description}
                        onChange={handleArrayInput("experience", index, "description")}
                      />
                    </div>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => addArrayItem("experience")}
                className="w-full py-2 border-2 border-dashed rounded-lg hover:bg-accent flex items-center justify-center gap-2 text-sm"
              >
                <Plus size={16} /> Add Experience
              </button>
            </div>
          )}

          {currentStep === 2 && (
            <div>
              <label className="text-sm font-medium">Skills</label>
              <input
                className="mt-1 w-full border rounded-md px-3 py-2"
                placeholder="Type a skill and press Enter or ,"
                onKeyDown={onSkillsInputKeyDown}
              />
              {errors.skills && <p className="text-xs text-red-600 mt-1">{errors.skills}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                {form.skills.map((skill) => (
                  <span key={skill} className="px-2 py-1 bg-primary/10 text-primary rounded-full text-xs flex items-center gap-2">
                    {skill}
                    <button type="button" onClick={() => removeSkill(skill)} className="text-primary/70 hover:text-primary">×</button>
                  </span>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">You can also paste comma-separated skills.</p>
            </div>
          )}

          {currentStep === 3 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Certificate Name</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.certificates.name} onChange={handleInput("certificates", "name")} />
              </div>
              <div>
                <label className="text-sm font-medium">Issuer</label>
                <input className="mt-1 w-full border rounded-md px-3 py-2" value={form.certificates.issuer} onChange={handleInput("certificates", "issuer")} />
              </div>
              <div>
                <label className="text-sm font-medium">Issue Date</label>
                <input type="date" className="mt-1 w-full border rounded-md px-3 py-2" value={form.certificates.issueDate} onChange={handleInput("certificates", "issueDate")} />
              </div>
              <div>
                <label className="text-sm font-medium">Expiry Date (optional)</label>
                <input type="date" className="mt-1 w-full border rounded-md px-3 py-2" value={form.certificates.expiryDate} onChange={handleInput("certificates", "expiryDate")} />
              </div>
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-6">
              {form.projects.map((proj, index) => (
                <div key={index} className="border rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold">Project {index + 1}</h3>
                    {form.projects.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem("projects", index)}
                        className="text-red-600 hover:text-red-700 p-1"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium">Project Name</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={proj.name}
                        onChange={handleArrayInput("projects", index, "name")}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Link</label>
                      <input
                        className="mt-1 w-full border rounded-md px-3 py-2"
                        value={proj.link}
                        onChange={handleArrayInput("projects", index, "link")}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-sm font-medium">Description</label>
                      <textarea
                        className="mt-1 w-full border rounded-md px-3 py-2 min-h-[80px]"
                        value={proj.description}
                        onChange={handleArrayInput("projects", index, "description")}
                      />
                    </div>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => addArrayItem("projects")}
                className="w-full py-2 border-2 border-dashed rounded-lg hover:bg-accent flex items-center justify-center gap-2 text-sm"
              >
                <Plus size={16} /> Add Project
              </button>
            </div>
          )}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <button className="px-4 py-2 border rounded-md hover:bg-accent disabled:opacity-50" onClick={onPrev} disabled={currentStep === 0}>
            Previous
          </button>
          <div className="flex-1" />
          {currentStep < steps.length - 1 ? ( 
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90" onClick={onNext}>
              Next
            </button>
          ) : (
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90" onClick={onSubmit}>
              Submit
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

type BackendJson = {
  contact_info?: { name?: string; email?: string; phone?: string };
  profile?: { summary?: string; github?: string; linkedin?: string };
  education?: Array<{ degree?: string; institution?: string; duration?: string; location?: string }>;
  experience?: Array<{ company?: string; role?: string; duration?: string; location?: string; description?: string }>;
  projects?: Array<{ name?: string; description?: string }>;
  skills?: string[];
};

function applyAutofill(prev: FormState, data: BackendJson): FormState {
  const next = { ...prev };
  
  // Contact
  if (data.contact_info) {
    next.profile.name = data.contact_info.name || next.profile.name;
    next.profile.email = data.contact_info.email || next.profile.email;
    next.profile.phone = data.contact_info.phone || next.profile.phone;
  }
  
  // Profile
  if (data.profile) {
    next.profile.summary = data.profile.summary || next.profile.summary;
    next.profile.github = data.profile.github || next.profile.github;
    next.profile.linkedin = data.profile.linkedin || next.profile.linkedin;
  }
  
  // Education (all entries)
  if (data.education && data.education.length > 0) {
    next.education = data.education.map(edu => {
      const startYear = edu.duration ? (edu.duration.match(/(\d{4})/g)?.[0] || "") : "";
      const endYear = edu.duration ? (edu.duration.match(/(\d{4})/g)?.[1] || "") : "";
      return {
        degree: edu.degree || "",
        institution: edu.institution || "",
        startYear,
        endYear,
        gpa: "",
      };
    });
  }
  
  // Experience (all entries)
  if (data.experience && data.experience.length > 0) {
    next.experience = data.experience.map(exp => ({
      company: exp.company || "",
      role: exp.role || "",
      duration: exp.duration || "",
      description: exp.description || "",
    }));
  }
  
  // Projects (all entries)
  if (data.projects && data.projects.length > 0) {
    next.projects = data.projects.map(proj => ({
      name: proj.name || "",
      description: proj.description || "",
      link: "",
    }));
  }
  
  // Skills (all skills, not just 10)
  if (data.skills && data.skills.length) {
    next.skills = Array.from(new Set([...(next.skills || []), ...data.skills]));
  }
  
  return next;
}

function ResumeAutofillButton({ onAutofill }: { onAutofill: (data: BackendJson) => void }) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<'idle' | 'polling' | 'completed' | 'failed'>('idle');
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const jobIdRef = useRef<string | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  async function pollLLMResults(jobId: string) {
    const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
    
    const poll = async () => {
      try {
        const res = await fetch(`${base}/get-llm-results/${jobId}`);
        if (!res.ok) {
          if (res.status === 404) {
            setLlmStatus('failed');
            setError('Job not found');
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
            return;
          }
          throw new Error(`Failed to poll: ${res.status}`);
        }
        
        const data = await res.json();
        
        if (data.status === 'completed') {
          setLlmStatus('completed');
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          
          // Merge LLM results (education & experience) with existing autofill data
          if (data.result) {
            onAutofill(data.result);
          }
        } else if (data.status === 'failed') {
          setLlmStatus('failed');
          setError(data.error || 'LLM processing failed');
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
        }
        // If status is 'processing', continue polling
      } catch (err: any) {
        console.error('Polling error:', err);
        // Don't stop polling on network errors, just log
      }
    };
    
    // Start polling every 2 seconds
    setLlmStatus('polling');
    pollingIntervalRef.current = setInterval(poll, 2000);
    
    // Also poll immediately
    poll();
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setLoading(true);
    setError(null);
    setLlmStatus('idle');
    
    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    
    try {
      const form = new FormData();
      form.append("file", f);
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      const res = await fetch(`${base}/upload`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const json = await res.json();
      
      // Immediately autofill NLP-extracted data (contact, profile, skills, projects)
      onAutofill(json);
      
      // Start polling for LLM results (education & experience)
      if (json.job_id) {
        jobIdRef.current = json.job_id;
        pollLLMResults(json.job_id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to autofill");
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const getButtonText = () => {
    if (loading) return "Uploading...";
    if (llmStatus === 'polling') return "Processing Education & Experience...";
    if (llmStatus === 'completed') return "✓ Autofill Complete";
    if (llmStatus === 'failed') return "⚠ Autofill (partial)";
    return "Autofill from Resume";
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-2">
        <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden" onChange={onPick} />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-2 text-xs px-3 py-1.5 border rounded-md hover:bg-accent disabled:opacity-50"
          disabled={loading || llmStatus === 'polling'}
        >
          <Upload size={14} /> {getButtonText()}
        </button>
      </div>
      {llmStatus === 'polling' && (
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <span className="inline-block w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          LLM is processing Education & Experience in the background...
        </div>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}


