"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Loader2, FileText, Sparkles, ArrowRight, CheckCircle2, AlertCircle, Save } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { createClient } from "@/lib/supabase/client";

interface OptimizationResult {
  success: boolean;
  original: any;
  optimized: any;
  metadata: {
    detected_roles: string[];
    jd_keywords: string[];
    sections_optimized: string[];
    optimization_details: any;
  };
}

export default function ResumeOptimizerPage() {
  const [jobDescription, setJobDescription] = useState("");
  const [resumeJson, setResumeJson] = useState<any>(null);
  const [sectionsToOptimize, setSectionsToOptimize] = useState<string[]>(["experience", "skills", "summary"]);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedVersionId, setSavedVersionId] = useState<number | null>(null);
  
  // Editable optimized resume state
  const [editableOptimized, setEditableOptimized] = useState<any>(null);
  
  // Authenticated user ID
  const [userId, setUserId] = useState<string | null>(null);
  
  // Fetch authenticated user on mount
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
          setUserId(user.id);
        }
      } catch (err) {
        console.error("Error fetching user:", err);
      }
    };
    fetchUser();
  }, []);

  // For demo purposes - in production, this would fetch from user's profile
  const loadSampleResume = () => {
    const sampleResume = {
      name: "Jane Doe",
      email: "jane.doe@email.com",
      summary: "Software developer with experience in web development and databases.",
      skills: ["JavaScript", "Python", "React", "SQL", "Git"],
      experience: [
        {
          company: "TechCorp",
          role: "Software Developer",
          duration: "2021 - Present",
          description: "Worked on web applications\nHelped with database design\nParticipated in code reviews"
        },
        {
          company: "StartupXYZ",
          role: "Junior Developer",
          duration: "2019 - 2021",
          description: "Built features for main product\nFixed bugs\nWorked with team on projects"
        }
      ],
      education: [
        {
          degree: "B.S. Computer Science",
          institution: "University of Technology",
          startYear: "2015",
          endYear: "2019"
        }
      ]
    };
    setResumeJson(sampleResume);
  };

  const handleOptimize = async () => {
    if (!resumeJson) {
      setError("Please load or paste your resume data first");
      return;
    }

    if (!jobDescription.trim()) {
      setError("Please paste a job description");
      return;
    }

    setIsOptimizing(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:5000/optimize-resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_json: resumeJson,
          job_description: jobDescription,
          sections_to_optimize: sectionsToOptimize,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResult(data);
        setEditableOptimized(JSON.parse(JSON.stringify(data.optimized))); // Deep copy for editing
        setShowComparison(true);
      } else {
        setError(data.error || "Optimization failed");
      }
    } catch (err) {
      setError("Failed to connect to backend. Make sure the server is running.");
      console.error(err);
    } finally {
      setIsOptimizing(false);
    }
  };

  const toggleSection = (section: string) => {
    setSectionsToOptimize((prev) =>
      prev.includes(section) ? prev.filter((s) => s !== section) : [...prev, section]
    );
  };

  const handleSaveOptimizedResume = async () => {
    if (!result) return;
    
    if (!userId) {
      setError("Please log in to save your resume");
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:5000/save-optimized-resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          original_json: result.original,
          optimized_json: editableOptimized || result.optimized,  // Use edited version
          job_title: "Extracted from JD", // Could parse from JD
          optimization_metadata: result.metadata,
          sections_optimized: result.metadata.sections_optimized,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setSavedVersionId(data.version_id);
        alert(`Resume saved successfully! Version ${data.version}`);
      } else {
        setError(data.error || "Failed to save resume");
      }
    } catch (err) {
      setError("Failed to save resume");
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Resume Optimizer</h1>
        <p className="text-muted-foreground">
          Optimize your resume for specific job postings using AI-powered recommendations
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!showComparison && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Left Column: Resume Input */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Your Resume
              </CardTitle>
              <CardDescription>Load your resume data or use sample</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button onClick={loadSampleResume} variant="outline" className="w-full">
                Load Sample Resume
              </Button>

              {resumeJson && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="text-sm font-medium">Resume loaded</span>
                  </div>
                  <div className="p-4 bg-muted rounded-lg max-h-60 overflow-auto">
                    <pre className="text-xs">{JSON.stringify(resumeJson, null, 2)}</pre>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>Sections to Optimize</Label>
                <div className="space-y-2">
                  {["experience", "skills", "summary"].map((section) => (
                    <div key={section} className="flex items-center space-x-2">
                      <Checkbox
                        id={section}
                        checked={sectionsToOptimize.includes(section)}
                        onCheckedChange={() => toggleSection(section)}
                      />
                      <label
                        htmlFor={section}
                        className="text-sm font-medium capitalize cursor-pointer"
                      >
                        {section}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Right Column: Job Description */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                Target Job Description
              </CardTitle>
              <CardDescription>Paste the job posting you're applying for</CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                placeholder="Paste the full job description here..."
                className="min-h-[400px] font-mono text-sm"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Optimize Button */}
      {!showComparison && (
        <div className="mt-6 flex justify-center">
          <Button
            size="lg"
            onClick={handleOptimize}
            disabled={isOptimizing || !resumeJson || !jobDescription.trim()}
            className="gap-2"
          >
            {isOptimizing ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Optimizing...
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" />
                Optimize Resume
                <ArrowRight className="h-5 w-5" />
              </>
            )}
          </Button>
        </div>
      )}

      {/* Results Comparison */}
      {showComparison && result && (
        <div className="space-y-6">
          {/* Placeholder Notice */}
          {result.metadata.optimization_details?.experience?.llm_response?.validation?.enforcement_applied?.placeholders_added > 0 && (
            <Alert className="border-amber-500 bg-amber-50">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-900">
                <strong>Action Required:</strong> {result.metadata.optimization_details.experience.llm_response.validation.enforcement_applied.placeholders_added} metric placeholder(s) have been added to experience bullets. 
                Please replace text in <code className="bg-amber-200 px-1 rounded">[brackets]</code> with your actual numbers before saving.
              </AlertDescription>
            </Alert>
          )}
          
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Optimization Results</h2>
            <div className="flex gap-2">
              <Button
                variant="default"
                onClick={handleSaveOptimizedResume}
                disabled={isSaving || savedVersionId !== null}
                className="gap-2"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : savedVersionId ? (
                  <>
                    <CheckCircle2 className="h-4 w-4" />
                    Saved
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    Save Version
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={() => {
                setShowComparison(false);
                setSavedVersionId(null);
              }}>
                Optimize Another
              </Button>
            </div>
          </div>

          {/* Metadata */}
          <Card>
            <CardHeader>
              <CardTitle>Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Detected Roles</Label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {result.metadata.detected_roles.map((role) => (
                    <Badge key={role} variant="secondary">
                      {role}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <Label className="text-sm font-medium">Key Skills Matched</Label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {result.metadata.jd_keywords.slice(0, 15).map((keyword) => (
                    <Badge key={keyword} variant="outline">
                      {keyword}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Side-by-side comparison */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Original Resume */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Original Resume</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {sectionsToOptimize.includes("summary") && (
                  <div>
                    <Label className="font-semibold">Summary</Label>
                    <p className="text-sm mt-1">{result.original.summary}</p>
                  </div>
                )}

                {sectionsToOptimize.includes("skills") && (
                  <div>
                    <Label className="font-semibold">Skills</Label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {result.original.skills?.map((skill: string) => (
                        <Badge key={skill} variant="secondary" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {sectionsToOptimize.includes("experience") &&
                  result.original.experience?.map((exp: any, idx: number) => (
                    <div key={idx} className="border-l-2 pl-3">
                      <p className="font-semibold text-sm">{exp.role}</p>
                      <p className="text-xs text-muted-foreground">{exp.company}</p>
                      <p className="text-xs whitespace-pre-line mt-1">{exp.description}</p>
                    </div>
                  ))}
              </CardContent>
            </Card>

            {/* Optimized Resume - EDITABLE */}
            <Card className="border-green-500">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  Optimized Resume (Editable)
                </CardTitle>
                <CardDescription>
                  Edit the optimized content below. Placeholders in [brackets] should be replaced with actual metrics.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {sectionsToOptimize.includes("summary") && (
                  <div>
                    <Label className="font-semibold">Summary</Label>
                    <Textarea
                      value={editableOptimized?.summary || ""}
                      onChange={(e) => setEditableOptimized({
                        ...editableOptimized,
                        summary: e.target.value
                      })}
                      className="mt-1 bg-green-50 border-green-200 min-h-[80px]"
                      placeholder="Edit your summary..."
                    />
                  </div>
                )}

                {sectionsToOptimize.includes("skills") && (
                  <div>
                    <Label className="font-semibold">Skills (comma-separated)</Label>
                    <Textarea
                      value={editableOptimized?.skills?.join(", ") || ""}
                      onChange={(e) => setEditableOptimized({
                        ...editableOptimized,
                        skills: e.target.value.split(",").map(s => s.trim()).filter(s => s)
                      })}
                      className="mt-1 bg-green-50 border-green-200 min-h-[60px]"
                      placeholder="Edit your skills..."
                    />
                  </div>
                )}

                {sectionsToOptimize.includes("experience") &&
                  editableOptimized?.experience?.map((exp: any, idx: number) => (
                    <div key={idx} className="border-l-2 border-green-500 pl-3 space-y-2">
                      <p className="font-semibold text-sm">{exp.role}</p>
                      <p className="text-xs text-muted-foreground">{exp.company} • {exp.duration}</p>
                      <div>
                        <Label className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
                          <span>Experience Bullets (replace [placeholders] with actual numbers)</span>
                          {exp.description.includes('[') && (
                            <Badge variant="outline" className="text-xs bg-amber-50 text-amber-700 border-amber-300">
                              Contains placeholders
                            </Badge>
                          )}
                        </Label>
                        <Textarea
                          value={exp.description}
                          onChange={(e) => {
                            const updatedExperience = [...editableOptimized.experience];
                            updatedExperience[idx] = {
                              ...updatedExperience[idx],
                              description: e.target.value
                            };
                            setEditableOptimized({
                              ...editableOptimized,
                              experience: updatedExperience
                            });
                          }}
                          className="mt-1 bg-green-50 border-green-200 min-h-[120px] font-mono text-xs"
                          placeholder="Edit experience bullets..."
                        />
                        {exp.description.includes('[') && (
                          <p className="text-xs text-amber-600 mt-1">
                            💡 Example: Replace "[X%]" with "35%" or "[X users]" with "10,000 users"
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </div>

          {/* Reasoning Details */}
          {result.metadata.optimization_details && (
            <Card>
              <CardHeader>
                <CardTitle>Optimization Reasoning</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs overflow-auto max-h-96 bg-muted p-4 rounded">
                  {JSON.stringify(result.metadata.optimization_details, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
