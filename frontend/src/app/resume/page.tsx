"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, FileText, Download, Loader2, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

type UserProfile = {
  name: string;
  email: string;
  phone: string;
  location: string;
  summary: string;
  github: string;
  linkedin: string;
  portfolio: string;
  skills: string[];
  education: Array<{
    degree: string;
    institution: string;
    startYear: string;
    endYear: string;
    gpa: string;
  }>;
  experience: Array<{
    company: string;
    role: string;
    duration: string;
    description: string;
  }>;
  projects: Array<{
    name: string;
    description: string;
    link: string;
  }>;
  certificates: Array<{
    name: string;
    issuer: string;
    issueDate: string;
    expiryDate?: string;
  }>;
};

type Template = {
  id: string;
  name: string;
  description: string;
  color: string;
};

const templates: Template[] = [
  {
    id: "modern",
    name: "Modern Pro",
    description: "Clean and professional design with accent colors",
    color: "from-blue-500 to-cyan-500"
  },
  {
    id: "classic",
    name: "Classic Formal",
    description: "Traditional layout perfect for corporate roles",
    color: "from-gray-700 to-gray-900"
  },
  {
    id: "creative",
    name: "Creative Bold",
    description: "Stand out with a vibrant, modern design",
    color: "from-purple-500 to-pink-500"
  },
  {
    id: "minimal",
    name: "Minimal Clean",
    description: "Simple and elegant with plenty of white space",
    color: "from-green-500 to-teal-500"
  }
];

export default function ResumePage() {
  const router = useRouter();
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUserProfile();
  }, []);

  const fetchUserProfile = async () => {
    try {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      
      if (!user) {
        setError("Please log in to view your resume");
        setLoading(false);
        return;
      }

      // Get onboarding form data from sessionStorage first
      const storedForm = sessionStorage.getItem('onboardingFormState');
      if (storedForm) {
        try {
          const formData = JSON.parse(storedForm);
          setUserProfile({
            name: formData.profile.name,
            email: formData.profile.email,
            phone: formData.profile.phone,
            location: formData.profile.location,
            summary: formData.profile.summary,
            github: formData.profile.github,
            linkedin: formData.profile.linkedin,
            portfolio: formData.profile.portfolio,
            skills: formData.skills || [],
            education: formData.education || [],
            experience: formData.experience || [],
            projects: formData.projects || [],
            certificates: formData.certificates ? [formData.certificates] : []
          });
          setLoading(false);
          return;
        } catch (e) {
          console.error('Error parsing form data:', e);
        }
      }

      // Fallback to backend if sessionStorage is not available
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      const response = await fetch(`${base}/user-profile/${user.id}`);
      
      if (response.ok) {
        const data = await response.json();
        setUserProfile(data.profile);
      } else {
        setError("No profile data found. Please complete the onboarding form first.");
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
      setError("Failed to load profile data");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadResume = async () => {
    if (!selectedTemplate || !userProfile) return;
    
    setDownloading(true);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      const response = await fetch(`${base}/generate-resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          template: selectedTemplate,
          profile: userProfile
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate resume');
      }

      // Get the PDF blob
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${userProfile.name.replace(/\s+/g, '_')}_Resume.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Error downloading resume:', err);
      alert('Failed to download resume. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-lg text-muted-foreground">Loading your profile...</p>
        </div>
      </div>
    );
  }

  if (error || !userProfile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">📄</div>
          <h1 className="text-2xl font-bold mb-2">Profile Not Found</h1>
          <p className="text-muted-foreground mb-4">{error || "No profile data available"}</p>
          <Link href="/onboarding" className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90">
            <ArrowLeft size={16} /> Complete Onboarding
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
          <Link href="/recommendations" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4">
            <ArrowLeft size={16} /> Back to Recommendations
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <FileText className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold">Create Your Resume</h1>
          </div>
          <p className="text-muted-foreground">
            Choose a template and download your professional resume
          </p>
        </div>

        {/* NEW: Resume Optimizer Feature Card */}
        <div className="mb-8 bg-gradient-to-r from-purple-500/10 via-pink-500/10 to-blue-500/10 border-2 border-purple-500/20 rounded-xl p-6 shadow-lg">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
            <div className="flex-shrink-0">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-xl font-bold">✨ New Feature: AI Resume Optimizer</h3>
                <span className="px-2 py-1 bg-purple-500 text-white text-xs font-semibold rounded-full">NEW</span>
              </div>
              <p className="text-muted-foreground mb-3">
                Optimize your resume for specific job postings using AI-powered recommendations. 
                Our smart system analyzes job descriptions and tailors your resume to match keywords, 
                highlights relevant skills, and rewrites experience bullets for maximum impact.
              </p>
              <div className="flex flex-wrap gap-2 mb-3 text-sm">
                <div className="flex items-center gap-1 text-green-600">
                  <TrendingUp className="w-4 h-4" />
                  <span>Metadata-filtered RAG</span>
                </div>
                <div className="flex items-center gap-1 text-blue-600">
                  <Sparkles className="w-4 h-4" />
                  <span>AI-powered optimization</span>
                </div>
                <div className="flex items-center gap-1 text-purple-600">
                  <FileText className="w-4 h-4" />
                  <span>Version tracking</span>
                </div>
              </div>
              <Link
                href="/resume-optimizer"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg"
              >
                <Sparkles className="w-5 h-5" />
                Try Resume Optimizer
              </Link>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Template Selection */}
          <div className="lg:col-span-1">
            <div className="bg-card border rounded-xl p-6 shadow-sm sticky top-8">
              <h2 className="text-xl font-bold mb-4">Select Template</h2>
              <div className="space-y-3">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => setSelectedTemplate(template.id)}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                      selectedTemplate === template.id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className={`w-full h-2 rounded-full bg-gradient-to-r ${template.color} mb-3`} />
                    <h3 className="font-semibold mb-1">{template.name}</h3>
                    <p className="text-xs text-muted-foreground">{template.description}</p>
                  </button>
                ))}
              </div>

              {selectedTemplate && (
                <button
                  onClick={handleDownloadResume}
                  disabled={downloading}
                  className="w-full mt-6 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg disabled:opacity-50"
                >
                  {downloading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      Download Resume
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Preview */}
          <div className="lg:col-span-2">
            <div className="bg-card border rounded-xl p-8 shadow-sm">
              <h2 className="text-xl font-bold mb-6">Preview</h2>
              
              {selectedTemplate ? (
                <ResumePreview profile={userProfile} template={selectedTemplate} />
              ) : (
                <div className="text-center py-20 text-muted-foreground">
                  <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p>Select a template to preview your resume</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResumePreview({ profile, template }: { profile: UserProfile; template: string }) {
  const templateColors: Record<string, { primary: string; secondary: string }> = {
    modern: { primary: "bg-blue-600", secondary: "bg-blue-100 text-blue-900" },
    classic: { primary: "bg-gray-800", secondary: "bg-gray-100 text-gray-900" },
    creative: { primary: "bg-purple-600", secondary: "bg-purple-100 text-purple-900" },
    minimal: { primary: "bg-green-600", secondary: "bg-green-100 text-green-900" }
  };

  const colors = templateColors[template] || templateColors.modern;

  return (
    <div className="bg-white text-black p-8 rounded-lg border-2 space-y-6 max-h-[800px] overflow-y-auto">
      {/* Header */}
      <div className={`${colors.primary} text-white p-6 rounded-lg -mx-8 -mt-8 mb-6`}>
        <h1 className="text-3xl font-bold mb-2">{profile.name}</h1>
        <div className="flex flex-wrap gap-3 text-sm">
          {profile.email && <span>📧 {profile.email}</span>}
          {profile.phone && <span>📱 {profile.phone}</span>}
          {profile.location && <span>📍 {profile.location}</span>}
        </div>
        {(profile.linkedin || profile.github || profile.portfolio) && (
          <div className="flex flex-wrap gap-3 text-sm mt-2">
            {profile.linkedin && <span>🔗 LinkedIn</span>}
            {profile.github && <span>💻 GitHub</span>}
            {profile.portfolio && <span>🌐 Portfolio</span>}
          </div>
        )}
      </div>

      {/* Summary */}
      {profile.summary && (
        <div>
          <h2 className="text-xl font-bold mb-2 text-gray-900">Professional Summary</h2>
          <p className="text-gray-700 text-sm leading-relaxed">{profile.summary}</p>
        </div>
      )}

      {/* Skills */}
      {profile.skills?.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-gray-900">Skills</h2>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((skill, idx) => (
              <span key={idx} className={`${colors.secondary} px-3 py-1 rounded-full text-xs font-medium`}>
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Experience */}
      {profile.experience?.length > 0 && profile.experience[0].company && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-gray-900">Experience</h2>
          <div className="space-y-4">
            {profile.experience.map((exp, idx) => (
              exp.company && (
                <div key={idx} className="border-l-4 border-gray-300 pl-4">
                  <h3 className="font-bold text-gray-900">{exp.role}</h3>
                  <p className="text-sm text-gray-600 mb-1">{exp.company} {exp.duration && `• ${exp.duration}`}</p>
                  {exp.description && <p className="text-sm text-gray-700">{exp.description}</p>}
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Education */}
      {profile.education?.length > 0 && profile.education[0].degree && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-gray-900">Education</h2>
          <div className="space-y-3">
            {profile.education.map((edu, idx) => (
              edu.degree && (
                <div key={idx}>
                  <h3 className="font-bold text-gray-900">{edu.degree}</h3>
                  <p className="text-sm text-gray-600">
                    {edu.institution}
                    {(edu.startYear || edu.endYear) && ` • ${edu.startYear || ''} - ${edu.endYear || ''}`}
                    {edu.gpa && ` • GPA: ${edu.gpa}`}
                  </p>
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Projects */}
      {profile.projects?.length > 0 && profile.projects[0].name && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-gray-900">Projects</h2>
          <div className="space-y-3">
            {profile.projects.map((proj, idx) => (
              proj.name && (
                <div key={idx}>
                  <h3 className="font-bold text-gray-900">
                    {proj.name}
                    {proj.link && <span className="text-xs text-gray-500 ml-2">🔗</span>}
                  </h3>
                  {proj.description && <p className="text-sm text-gray-700">{proj.description}</p>}
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Certificates */}
      {profile.certificates?.length > 0 && profile.certificates[0].name && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-gray-900">Certifications</h2>
          <div className="space-y-2">
            {profile.certificates.map((cert, idx) => (
              cert.name && (
                <div key={idx}>
                  <h3 className="font-bold text-gray-900">{cert.name}</h3>
                  <p className="text-sm text-gray-600">
                    {cert.issuer}
                    {cert.issueDate && ` • ${new Date(cert.issueDate).toLocaleDateString()}`}
                  </p>
                </div>
              )
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
