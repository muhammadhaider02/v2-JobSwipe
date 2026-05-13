'use client';

import React, { useMemo, useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Button } from '@/components/ui/button';
import { StepIndicator } from './onboarding/step-indicator';
import { ResumeUpload } from './onboarding/resume-upload';
import { StepProfile } from './onboarding/step-profile';
import { StepCertificates } from './onboarding/step-certificates';
import { StepSkills } from './onboarding/step-skills';
import { StepProjects } from './onboarding/step-projects';
import { StepEducation } from './onboarding/step-education';
import { StepExperience } from './onboarding/step-experience';

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
  yearsOfExperience: number;
};

const steps = [
  { id: 1, label: 'Profile' },
  { id: 2, label: 'Certificates' },
  { id: 3, label: 'Skills' },
  { id: 4, label: 'Projects' },
  { id: 5, label: 'Education' },
  { id: 6, label: 'Experience' },
];

interface MultiStepResumeFormProps {
  userId: string;
}

export default function MultiStepResumeForm({
  userId,
}: MultiStepResumeFormProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [maxVisitedStep, setMaxVisitedStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const [form, setForm] = useState<FormState>({
    profile: {
      name: '',
      email: '',
      phone: '',
      location: '',
      summary: '',
      github: '',
      linkedin: '',
      portfolio: '',
      profilePictureUrl: undefined,
    },
    education: [
      { degree: '', institution: '', startYear: '', endYear: '', gpa: '' },
    ],
    experience: [{ company: '', role: '', duration: '', description: '' }],
    projects: [{ name: '', description: '', link: '' }],
    skills: [],
    certificates: { name: '', issuer: '', issueDate: '', expiryDate: '' },
    yearsOfExperience: 0,
  });

  function handleInput<K extends keyof FormState>(
    section: K,
    field: keyof FormState[K],
  ) {
    return (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => {
      setForm((prev) => ({
        ...prev,
        [section]: {
          ...(prev[section] as any),
          [field]: e.target.value,
        },
      }));
    };
  }

  function handleArrayInput<
    K extends 'education' | 'experience' | 'projects',
  >(section: K, index: number, field: keyof FormState[K][number]) {
    return (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => {
      setForm((prev) => ({
        ...prev,
        [section]: prev[section].map((item, i) =>
          i === index ? { ...item, [field]: e.target.value } : item,
        ),
      }));
    };
  }

  function addArrayItem<K extends 'education' | 'experience' | 'projects'>(
    section: K,
  ) {
    const emptyItem =
      section === 'education'
        ? { degree: '', institution: '', startYear: '', endYear: '', gpa: '' }
        : section === 'experience'
          ? { company: '', role: '', duration: '', description: '' }
          : { name: '', description: '', link: '' };

    setForm((prev) => ({
      ...prev,
      [section]: [...prev[section], emptyItem],
    }));
  }

  function removeArrayItem<
    K extends 'education' | 'experience' | 'projects',
  >(section: K, index: number) {
    setForm((prev) => ({
      ...prev,
      [section]: prev[section].filter((_, i) => i !== index),
    }));
  }

  function validateStep(stepIndex: number): Record<string, string> {
    const errs: Record<string, string> = {};
    if (stepIndex === 0) {
      if (!form.profile.name.trim()) errs.name = 'Name is required';
      if (!form.profile.email.trim()) errs.email = 'Email is required';
    } else if (stepIndex === 2) {
      if (form.skills.length === 0) errs.skills = 'Add at least one skill';
    } else if (stepIndex === 4) {
      if (form.education.length === 0 || !form.education[0].degree.trim())
        errs.degree = 'At least one degree is required';
      if (
        form.education.length === 0 ||
        !form.education[0].institution.trim()
      )
        errs.institution = 'Institution is required';
    } else if (stepIndex === 5) {
      if (
        form.experience.length === 0 ||
        !form.experience[0].company.trim()
      )
        errs.company = 'At least one company is required';
      if (form.experience.length === 0 || !form.experience[0].role.trim())
        errs.role = 'Role is required';
    }
    return errs;
  }

  function onNext() {
    const v = validateStep(currentStep);
    setErrors(v);
    if (Object.keys(v).length === 0) {
      setDirection(1);
      setCurrentStep((s) => Math.min(s + 1, steps.length - 1));
      setMaxVisitedStep((m) => Math.max(m, currentStep + 1));
    }
  }

  function onPrev() {
    setDirection(-1);
    setCurrentStep((s) => Math.max(s - 1, 0));
  }

  function onJump(to: number) {
    if (to <= maxVisitedStep) {
      setDirection(to > currentStep ? 1 : -1);
      setCurrentStep(to);
    }
  }

  async function onSubmit() {
    const v = validateStep(currentStep);
    setErrors(v);
    if (Object.keys(v).length === 0) {
      try {
        setIsSavingProfile(true);

        const yearsOfExperience = form.yearsOfExperience;

        const profileData = {
          name: form.profile.name,
          email: form.profile.email,
          phone: form.profile.phone,
          location: form.profile.location,
          summary: form.profile.summary,
          github: form.profile.github,
          linkedin: form.profile.linkedin,
          portfolio: form.profile.portfolio,
          profile_picture_url: form.profile.profilePictureUrl,
          skills: form.skills,
          previous_roles: form.experience
            .map((exp) => exp.role)
            .filter(Boolean),
          years_of_experience: yearsOfExperience,
          projects: form.projects.map((proj) => ({
            name: proj.name,
            description: proj.description,
            link: proj.link,
          })),
          certificates: form.certificates.name
            ? [
                {
                  name: form.certificates.name,
                  issuer: form.certificates.issuer,
                  issue_date: form.certificates.issueDate,
                  expiry_date: form.certificates.expiryDate,
                },
              ]
            : [],
          education: form.education.map((edu) => ({
            degree: edu.degree,
            institution: edu.institution,
            start_year: edu.startYear,
            end_year: edu.endYear,
            gpa: edu.gpa,
          })),
          experience: form.experience.map((exp) => ({
            company: exp.company,
            role: exp.role,
            duration: exp.duration,
            description: exp.description,
          })),
        };

        const response = await fetch('/api/save-profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            profile_data: profileData,
          }),
        });

        if (!response.ok) throw new Error('Failed to save profile');

        const result = await response.json();
        console.log('Profile saved:', result);

        sessionStorage.setItem(
          'userSkills',
          JSON.stringify(form.skills),
        );
        sessionStorage.setItem('resumeChanged', 'true');
        sessionStorage.removeItem('recommendations');
        sessionStorage.removeItem('cachedRecommendationSkills');
        window.location.href = '/recommendations';
      } catch (error) {
        console.error('Error saving profile:', error);
        alert('Failed to save profile. Please try again.');
      } finally {
        setIsSavingProfile(false);
      }
    }
  }

  function onSkillsInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const input = e.currentTarget.value;
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const token = input.trim().replace(/,$/, '');
      if (!token) return;
      setForm((prev) => ({
        ...prev,
        skills: Array.from(new Set([...prev.skills, token])),
      }));
      e.currentTarget.value = '';
    }
  }

  function removeSkill(skill: string) {
    setForm((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => s !== skill),
    }));
  }

  useEffect(() => {
    async function loadProfile() {
      if (!userId) {
        setIsLoadingProfile(false);
        return;
      }

      try {
        const response = await fetch(`/api/get-profile/${userId}`);

        if (response.ok) {
          const result = await response.json();
          if (result.success && result.profile) {
            const profile = result.profile;

            setForm({
              profile: {
                name: profile.name || '',
                email: profile.email || '',
                phone: profile.phone || '',
                location: profile.location || '',
                summary: profile.summary || '',
                github: profile.github || '',
                linkedin: profile.linkedin || '',
                portfolio: profile.portfolio || '',
                profilePictureUrl: profile.profile_picture_url,
              },
              education:
                profile.education && profile.education.length > 0
                  ? profile.education.map((edu: any) => ({
                      degree: edu.degree || '',
                      institution: edu.institution || '',
                      startYear: edu.start_year || '',
                      endYear: edu.end_year || '',
                      gpa: edu.gpa || '',
                    }))
                  : [
                      {
                        degree: '',
                        institution: '',
                        startYear: '',
                        endYear: '',
                        gpa: '',
                      },
                    ],
              experience:
                profile.experience && profile.experience.length > 0
                  ? profile.experience.map((exp: any) => ({
                      company: exp.company || '',
                      role: exp.role || '',
                      duration: exp.duration || '',
                      description: exp.description || '',
                    }))
                  : [
                      {
                        company: '',
                        role: '',
                        duration: '',
                        description: '',
                      },
                    ],
              projects:
                profile.projects && profile.projects.length > 0
                  ? profile.projects.map((proj: any) => ({
                      name: proj.name || '',
                      description: proj.description || '',
                      link: proj.link || '',
                    }))
                  : [{ name: '', description: '', link: '' }],
              skills: profile.skills || [],
              certificates:
                profile.certificates && profile.certificates.length > 0
                  ? {
                      name: profile.certificates[0].name || '',
                      issuer: profile.certificates[0].issuer || '',
                      issueDate:
                        profile.certificates[0].issue_date || '',
                      expiryDate:
                        profile.certificates[0].expiry_date || '',
                    }
                  : {
                      name: '',
                      issuer: '',
                      issueDate: '',
                      expiryDate: '',
                    },
              yearsOfExperience: Math.min(
                50,
                Math.max(
                  0,
                  typeof profile.years_of_experience === 'number'
                    ? profile.years_of_experience
                    : 0,
                ),
              ),
            });

            console.log('Profile loaded successfully');
          }
        }
      } catch (error) {
        console.error('Error loading profile:', error);
      } finally {
        setIsLoadingProfile(false);
      }
    }

    loadProfile();
  }, [userId]);

  function handleAutofill(data: any) {
    const preferred = data?.refined || data;
    setForm((prev) => applyAutofill(prev, preferred));
  }

  const stepVariants = {
    enter: (d: number) => ({
      opacity: 0,
      x: d * 40,
    }),
    center: {
      opacity: 1,
      x: 0,
      transition: { type: 'spring' as const, stiffness: 100, damping: 20 },
    },
    exit: (d: number) => ({
      opacity: 0,
      x: d * -40,
      transition: { duration: 0.2 },
    }),
  };

  if (isLoadingProfile) {
    return (
      <div className="w-full max-w-3xl mx-auto">
        <div className="space-y-6 py-8">
          <div className="flex items-center gap-3 mb-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center flex-1 last:flex-initial">
                <div className="w-9 h-9 rounded-full bg-muted animate-pulse" />
                {i < 5 && <div className="flex-1 mx-3 h-px bg-muted" />}
              </div>
            ))}
          </div>
          <div className="rounded-xl border bg-card p-6 space-y-4">
            <div className="h-5 w-32 bg-muted rounded animate-pulse" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 w-20 bg-muted rounded animate-pulse" />
                  <div className="h-9 bg-muted rounded-md animate-pulse" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        className="space-y-6"
      >
        <ResumeUpload onAutofill={handleAutofill} />

        <StepIndicator
          steps={steps}
          currentStep={currentStep}
          maxVisitedStep={maxVisitedStep}
          onJump={onJump}
        />

        <div className="rounded-xl border bg-card p-6 shadow-sm overflow-hidden">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={currentStep}
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
            >
              {currentStep === 0 && (
                <StepProfile
                  profile={form.profile}
                  errors={errors}
                  onInput={(field) =>
                    handleInput('profile', field as keyof Profile)
                  }
                />
              )}
              {currentStep === 1 && (
                <StepCertificates
                  certificates={form.certificates}
                  onInput={(field) =>
                    handleInput(
                      'certificates',
                      field as keyof Certificate,
                    )
                  }
                />
              )}
              {currentStep === 2 && (
                <StepSkills
                  skills={form.skills}
                  errors={errors}
                  onKeyDown={onSkillsInputKeyDown}
                  onRemove={removeSkill}
                />
              )}
              {currentStep === 3 && (
                <StepProjects
                  projects={form.projects}
                  onArrayInput={(index, field) =>
                    handleArrayInput(
                      'projects',
                      index,
                      field as keyof Project,
                    )
                  }
                  onAdd={() => addArrayItem('projects')}
                  onRemove={(index) => removeArrayItem('projects', index)}
                />
              )}
              {currentStep === 4 && (
                <StepEducation
                  education={form.education}
                  errors={errors}
                  onArrayInput={(index, field) =>
                    handleArrayInput(
                      'education',
                      index,
                      field as keyof Education,
                    )
                  }
                  onAdd={() => addArrayItem('education')}
                  onRemove={(index) =>
                    removeArrayItem('education', index)
                  }
                />
              )}
              {currentStep === 5 && (
                <StepExperience
                  experience={form.experience}
                  errors={errors}
                  onArrayInput={(index, field) =>
                    handleArrayInput(
                      'experience',
                      index,
                      field as keyof Experience,
                    )
                  }
                  onAdd={() => addArrayItem('experience')}
                  onRemove={(index) =>
                    removeArrayItem('experience', index)
                  }
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={onPrev}
            disabled={currentStep === 0}
          >
            Previous
          </Button>
          {currentStep < steps.length - 1 ? (
            <Button onClick={onNext}>Next</Button>
          ) : (
            <Button onClick={onSubmit} disabled={isSavingProfile}>
              {isSavingProfile ? 'Saving...' : 'Submit'}
            </Button>
          )}
        </div>
      </motion.div>
    </div>
  );
}

type BackendJson = {
  contact_info?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
  };
  profile?: {
    summary?: string;
    github?: string;
    linkedin?: string;
    portfolio?: string;
  };
  education?: Array<{
    degree?: string;
    institution?: string;
    duration?: string;
    location?: string;
  }>;
  experience?: Array<{
    company?: string;
    role?: string;
    duration?: string;
    location?: string;
    description?: string;
  }>;
  projects?: Array<{
    name?: string;
    description?: string;
    link?: string;
  }>;
  skills?: string[];
  years_of_experience?: number;
};

function applyAutofill(prev: FormState, data: BackendJson): FormState {
  const next: FormState = { ...prev };

  if (data.contact_info) {
    next.profile = { ...next.profile };
    next.profile.name = data.contact_info.name || next.profile.name;
    next.profile.email = data.contact_info.email || next.profile.email;
    next.profile.phone = data.contact_info.phone || next.profile.phone;
    next.profile.location =
      data.contact_info.location || next.profile.location;
  }

  if (data.profile) {
    next.profile = { ...next.profile };
    next.profile.summary =
      data.profile.summary !== undefined
        ? data.profile.summary
        : next.profile.summary;
    next.profile.github =
      data.profile.github !== undefined
        ? data.profile.github
        : next.profile.github;
    next.profile.linkedin =
      data.profile.linkedin !== undefined
        ? data.profile.linkedin
        : next.profile.linkedin;
    next.profile.portfolio =
      data.profile.portfolio !== undefined
        ? data.profile.portfolio
        : next.profile.portfolio;
  }

  if (data.education !== undefined) {
    if (data.education.length > 0) {
      next.education = data.education.map((edu, idx) => {
        const startYear = edu.duration
          ? edu.duration.match(/(\d{4})/g)?.[0] || ''
          : '';
        const endYear = edu.duration
          ? edu.duration.match(/(\d{4})/g)?.[1] || ''
          : '';
        return {
          degree: edu.degree || prev.education[idx]?.degree || '',
          institution:
            edu.institution || prev.education[idx]?.institution || '',
          startYear: startYear || prev.education[idx]?.startYear || '',
          endYear: endYear || prev.education[idx]?.endYear || '',
          gpa: prev.education[idx]?.gpa || '',
        };
      });
    } else {
      next.education = [
        {
          degree: '',
          institution: '',
          startYear: '',
          endYear: '',
          gpa: '',
        },
      ];
    }
  }

  if (data.experience !== undefined) {
    if (data.experience.length > 0) {
      next.experience = data.experience.map((exp, idx) => ({
        company: exp.company || prev.experience[idx]?.company || '',
        role: exp.role || prev.experience[idx]?.role || '',
        duration: exp.duration || prev.experience[idx]?.duration || '',
        description:
          exp.description || prev.experience[idx]?.description || '',
      }));
    } else {
      next.experience = [
        { company: '', role: '', duration: '', description: '' },
      ];
    }
  }

  if (data.projects !== undefined) {
    if (data.projects.length > 0) {
      next.projects = data.projects.map((proj, idx) => ({
        name: proj.name || prev.projects[idx]?.name || '',
        description:
          proj.description || prev.projects[idx]?.description || '',
        link:
          proj.link !== undefined
            ? proj.link
            : prev.projects[idx]?.link || '',
      }));
    } else {
      next.projects = [{ name: '', description: '', link: '' }];
    }
  }

  if (data.skills && data.skills.length) {
    next.skills = [...data.skills];
  }

  if (
    typeof data.years_of_experience === 'number' &&
    Number.isInteger(data.years_of_experience) &&
    data.years_of_experience >= 0 &&
    data.years_of_experience <= 50
  ) {
    next.yearsOfExperience = data.years_of_experience;
  }

  return next;
}
