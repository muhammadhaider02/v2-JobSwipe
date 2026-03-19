"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Briefcase, Sparkles, ArrowLeft, Loader2, BookOpen, Check, FileText, Mail } from "lucide-react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

type Recommendation = {
  role: string;
  score: number;
  skills: string;
  skillGapData?: {
    existing_skills: string[];
    required_skills: string[];
    completion_percentage: number;
  };
};

export default function RecommendationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userSkills, setUserSkills] = useState<string[]>([]);
  const [learnedSkills, setLearnedSkills] = useState<Set<string>>(new Set());
  const [userId, setUserId] = useState<string | null>(null);

  // Load learned skills from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('learnedSkills');
    if (stored) {
      try {
        setLearnedSkills(new Set(JSON.parse(stored)));
      } catch (e) {
        console.error('Error loading learned skills:', e);
      }
    }
  }, []);

  // Fetch user ID from Supabase
  useEffect(() => {
    const fetchUserId = async () => {
      try {
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
          setUserId(user.id);
        }
      } catch (e) {
        console.error('Error fetching user ID:', e);
      }
    };
    fetchUserId();
  }, []);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const skillsParam = searchParams.get("skills");

        // Try to get skills from URL params first, then from sessionStorage
        let skills: string[];
        if (skillsParam) {
          skills = JSON.parse(decodeURIComponent(skillsParam));
          // Store in sessionStorage for later use
          sessionStorage.setItem('userSkills', JSON.stringify(skills));
        } else {
          // Try to restore from sessionStorage
          const storedSkills = sessionStorage.getItem('userSkills');
          if (storedSkills) {
            skills = JSON.parse(storedSkills);
          } else {
            setError("No skills provided");
            setLoading(false);
            return;
          }
        }

        setUserSkills(skills);

        // Check if we have cached recommendations
        const cachedRecommendations = sessionStorage.getItem('recommendations');
        if (cachedRecommendations && !skillsParam) {
          // Use cached data if returning to page
          setRecommendations(JSON.parse(cachedRecommendations));
          setLoading(false);
          return;
        }

        const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

        // Add timeout to avoid hanging forever
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        try {
          const res = await fetch(`${base}/recommend-roles`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ skills, user_id: userId }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (!res.ok) {
            throw new Error(`Failed to fetch recommendations: ${res.status}`);
          }

          const data = await res.json();
          const recommendations = data.recommendations || [];

          // Fetch skill gap analysis for each recommendation ONLY if not already provided
          const recommendationsWithGapData = await Promise.all(
            recommendations.map(async (rec: Recommendation) => {
              // If backend already provided skill gap data, use it
              if (rec.skillGapData) {
                return rec;
              }

              // Fallback: fetch it if missing (legacy support)
              try {
                const gapRes = await fetch(`${base}/analyze-skill-gap`, {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    role: rec.role,
                    skills
                  }),
                });

                if (gapRes.ok) {
                  const gapData = await gapRes.json();
                  return {
                    ...rec,
                    skillGapData: {
                      existing_skills: gapData.existing_skills || [],
                      required_skills: gapData.required_skills || [],
                      completion_percentage: gapData.completion_percentage || 0,
                    }
                  };
                }
              } catch (error) {
                console.error(`Failed to fetch skill gap for ${rec.role}:`, error);
              }
              return rec;
            })
          );

          setRecommendations(recommendationsWithGapData);
          // Cache recommendations in sessionStorage
          sessionStorage.setItem('recommendations', JSON.stringify(recommendationsWithGapData));
        } catch (fetchError: any) {
          clearTimeout(timeoutId);
          if (fetchError.name === 'AbortError') {
            throw new Error('Backend server is not responding. Please make sure the backend is running.');
          }
          throw fetchError;
        }
      } catch (err: any) {
        console.error('Recommendation fetch error:', err);
        setError(err?.message || "Failed to load recommendations. Please ensure the backend server is running.");
      } finally {
        setLoading(false);
      }
    }

    fetchRecommendations();
  }, [searchParams]);

  const handleMarkAsLearned = (skill: string) => {
    setLearnedSkills(prev => {
      const newSet = new Set(prev);
      newSet.add(skill.toLowerCase());
      // Persist to localStorage
      localStorage.setItem('learnedSkills', JSON.stringify(Array.from(newSet)));
      return newSet;
    });
  };

  const handleBrowseJobs = async () => {
    if (!userId) {
      router.push('/jobs');
      return;
    }

    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      // First, fetch the existing user profile
      const profileResponse = await fetch(`${base}/user-profile/${userId}`);
      
      if (profileResponse.ok) {
        const profileData = await profileResponse.json();
        const existingProfile = profileData.profile;

        // Extract recommended role names
        const recommendedRoleNames = recommendations.map(rec => rec.role);

        // Merge recommended roles with existing profile
        await fetch(`${base}/user-profile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ...existingProfile,
            recommended_roles: recommendedRoleNames,
          }),
        });
      } else {
        // If no existing profile, just save the recommended roles
        const recommendedRoleNames = recommendations.map(rec => rec.role);
        await fetch(`${base}/user-profile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: userId,
            recommended_roles: recommendedRoleNames,
          }),
        });
      }

      // Navigate to jobs page
      router.push('/jobs');
    } catch (error) {
      console.error('Error saving recommended roles:', error);
      // Navigate anyway
      router.push('/jobs');
    }
  };

  const handleViewLearningResources = (missingSkills: string[]) => {
    // Store the skills being learned in sessionStorage
    sessionStorage.setItem('currentLearningSkills', JSON.stringify(missingSkills));

    // Always go through preferences page first, then to learning-resources
    const skillsParam = encodeURIComponent(JSON.stringify(missingSkills));
    router.push(`/learning-preferences?skills=${skillsParam}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-lg text-muted-foreground">Finding your perfect roles...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold mb-2">Oops!</h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Link href="/onboarding" className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90">
            <ArrowLeft size={16} /> Go Back
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link href="/onboarding" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4">
            <ArrowLeft size={16} /> Back to Form
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <Sparkles className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold">Recommended Roles</h1>
          </div>
          <p className="text-muted-foreground">
            Based on your {userSkills.length} skill{userSkills.length !== 1 ? 's' : ''}, we found {recommendations.length} matching roles
          </p>
        </div>

        {/* User Skills Display */}
        <div className="mb-8 p-4 bg-card border rounded-lg">
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground">Your Skills</h2>
          <div className="flex flex-wrap gap-2">
            {userSkills.map((skill, idx) => (
              <span key={idx} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                {skill}
              </span>
            ))}
          </div>
        </div>

        {/* Recommendations Grid */}
        {recommendations.length === 0 ? (
          <div className="text-center py-12">
            <Briefcase className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h2 className="text-xl font-semibold mb-2">No recommendations found</h2>
            <p className="text-muted-foreground">Try adding more skills or check back later</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recommendations.map((rec, idx) => (
              <RoleCard
                key={idx}
                recommendation={rec}
                rank={idx + 1}
                learnedSkills={learnedSkills}
                onMarkAsLearned={handleMarkAsLearned}
                onViewLearningResources={handleViewLearningResources}
              />
            ))}
          </div>
        )}

        {/* Browse Jobs Section */}
        {recommendations.length > 0 && (
          <div className="mt-12 border-t border-border pt-8">
            <div className="max-w-2xl mx-auto text-center">
              <div className="inline-flex p-3 bg-primary/10 rounded-full mb-4">
                <Briefcase className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-2xl font-bold mb-3">Ready to Apply?</h2>
              <p className="text-muted-foreground mb-6">
                Browse real job listings that match your recommended roles and skill level. 
                Start applying to positions that align with your expertise.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-4">
                <button
                  onClick={handleBrowseJobs}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg"
                >
                  <Briefcase className="w-5 h-5" />
                  Browse Job Listings
                </button>
                <Link href="/resume" className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg">
                  <FileText className="w-5 h-5" />
                  Create Resume
                </Link>
                <Link href="/cover-letter" className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white rounded-lg font-medium transition-all shadow-md hover:shadow-lg">
                  <Mail className="w-5 h-5" />
                  Generate Cover Letter
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RoleCard({
  recommendation,
  rank,
  learnedSkills,
  onMarkAsLearned,
  onViewLearningResources
}: {
  recommendation: Recommendation;
  rank: number;
  learnedSkills: Set<string>;
  onMarkAsLearned: (skill: string) => void;
  onViewLearningResources: (skills: string[]) => void;
}) {
  const [selectedMissingSkill, setSelectedMissingSkill] = useState<string | null>(null);

  // Get all required skills from skill gap data if available
  const allRequiredSkills = recommendation.skillGapData
    ? [
      ...recommendation.skillGapData.existing_skills,
      ...recommendation.skillGapData.required_skills
    ]
    : recommendation.skills.split(',').map(s => s.trim()).filter(Boolean);

  const existingSkills = recommendation.skillGapData?.existing_skills || [];
  const missingSkills = recommendation.skillGapData?.required_skills || [];

  // Filter out learned skills from missing skills
  const actualMissingSkills = missingSkills.filter(
    skill => !learnedSkills.has(skill.toLowerCase())
  );

  // Recalculate completion percentage based on learned skills
  const totalRequiredSkills = allRequiredSkills.length;
  const learnedCount = missingSkills.filter(
    skill => learnedSkills.has(skill.toLowerCase())
  ).length;
  const matchedCount = existingSkills.length + learnedCount;
  const dynamicCompletionPercentage = totalRequiredSkills > 0 
    ? Math.round((matchedCount / totalRequiredSkills) * 100)
    : (recommendation.skillGapData?.completion_percentage || 0);

  // Take first 15 skills
  const displaySkills = allRequiredSkills.slice(0, 15);

  return (
    <div className="bg-card border rounded-xl p-6 shadow-sm hover:shadow-md transition-all hover:border-primary/50 relative overflow-hidden flex flex-col">
      {/* Rank Badge */}
      <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
        {rank}
      </div>

      {/* Role Title */}
      <div className="mb-4 pr-10">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Briefcase className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-bold leading-tight">{recommendation.role}</h3>
          </div>
        </div>
      </div>

      {/* Completion Percentage (if available) */}
      {recommendation.skillGapData && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-muted-foreground">Skill Match</span>
            <span className="font-semibold text-primary">
              {dynamicCompletionPercentage}%
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-1.5">
            <div
              className="bg-primary h-1.5 rounded-full transition-all"
              style={{ width: `${dynamicCompletionPercentage}%` }}
            />
          </div>
        </div>
      )}

      {/* Required Skills with Color Coding */}
      <div className="flex-grow">
        <h4 className="text-xs font-semibold text-muted-foreground mb-2 uppercase">Required Skills</h4>
        <div className="flex flex-wrap gap-1.5">
          {displaySkills.map((skill, idx) => {
            const isExisting = existingSkills.some(
              s => s.toLowerCase() === skill.toLowerCase()
            );
            const isMissing = missingSkills.some(
              s => s.toLowerCase() === skill.toLowerCase()
            );
            const isLearned = learnedSkills.has(skill.toLowerCase());

            return (
              <button
                key={idx}
                onClick={() => {
                  if (isMissing && !isLearned) {
                    setSelectedMissingSkill(selectedMissingSkill === skill ? null : skill);
                  }
                }}
                className={`px-2 py-0.5 rounded text-xs transition-all ${isExisting || isLearned
                  ? 'bg-green-500/20 text-green-700 dark:text-green-400 border border-green-500/30'
                  : isMissing
                    ? 'bg-red-500/20 text-red-700 dark:text-red-400 border border-red-500/30 cursor-pointer hover:bg-red-500/30'
                    : 'bg-muted text-foreground'
                  }`}
              >
                {skill}
              </button>
            );
          })}
        </div>
      </div>

      {/* Action Buttons for Selected Missing Skill */}
      {selectedMissingSkill && (
        <div className="mt-4 p-3 bg-muted/50 rounded-lg border border-dashed">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Actions for: <span className="text-foreground">{selectedMissingSkill}</span>
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onMarkAsLearned(selectedMissingSkill);
                setSelectedMissingSkill(null);
              }}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-card border rounded-md text-xs hover:bg-accent transition-colors"
            >
              <Check className="w-3 h-3" />
              Mark as Learned
            </button>
            <button
              onClick={() => {
                onViewLearningResources([selectedMissingSkill]);
                setSelectedMissingSkill(null);
              }}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs hover:bg-primary/90 transition-colors"
            >
              <BookOpen className="w-3 h-3" />
              Learn This
            </button>
          </div>
        </div>
      )}

      {/* View All Learning Resources Button - Fixed at bottom */}
      {actualMissingSkills.length > 0 && (
        <div className="mt-auto pt-4">
          <button
            onClick={() => onViewLearningResources(actualMissingSkills)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg transition-all shadow-sm hover:shadow-md"
          >
            <BookOpen className="w-4 h-4" />
            Learn All Missing Skills ({actualMissingSkills.length})
          </button>
        </div>
      )}
    </div>
  );
}
