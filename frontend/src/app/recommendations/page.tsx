"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Briefcase, Sparkles, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

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
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userSkills, setUserSkills] = useState<string[]>([]);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const skillsParam = searchParams.get("skills");
        if (!skillsParam) {
          setError("No skills provided");
          setLoading(false);
          return;
        }

        const skills = JSON.parse(decodeURIComponent(skillsParam));
        setUserSkills(skills);

        const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

        // Add timeout to avoid hanging forever
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

        try {
          const res = await fetch(`${base}/recommend-roles`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ skills }),
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
              <RoleCard key={idx} recommendation={rec} rank={idx + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RoleCard({ recommendation, rank }: { recommendation: Recommendation; rank: number }) {
  // Get all required skills from skill gap data if available
  const allRequiredSkills = recommendation.skillGapData
    ? [
      ...recommendation.skillGapData.existing_skills,
      ...recommendation.skillGapData.required_skills
    ]
    : recommendation.skills.split(',').map(s => s.trim()).filter(Boolean);

  const existingSkills = recommendation.skillGapData?.existing_skills || [];
  const missingSkills = recommendation.skillGapData?.required_skills || [];

  // Take first 10 skills
  const displaySkills = allRequiredSkills.slice(0, 10);

  return (
    <div className="bg-card border rounded-xl p-6 shadow-sm hover:shadow-md transition-all hover:border-primary/50 relative overflow-hidden">
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
              {recommendation.skillGapData.completion_percentage}%
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-1.5">
            <div
              className="bg-primary h-1.5 rounded-full transition-all"
              style={{ width: `${recommendation.skillGapData.completion_percentage}%` }}
            />
          </div>
        </div>
      )}

      {/* Required Skills with Color Coding */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground mb-2 uppercase">Required Skills</h4>
        <div className="flex flex-wrap gap-1.5">
          {displaySkills.map((skill, idx) => {
            const isExisting = existingSkills.some(
              s => s.toLowerCase() === skill.toLowerCase()
            );
            const isMissing = missingSkills.some(
              s => s.toLowerCase() === skill.toLowerCase()
            );

            return (
              <span
                key={idx}
                className={`px-2 py-0.5 rounded text-xs ${isExisting
                  ? 'bg-green-500/20 text-green-700 dark:text-green-400 border border-green-500/30'
                  : isMissing
                    ? 'bg-red-500/20 text-red-700 dark:text-red-400 border border-red-500/30'
                    : 'bg-muted text-foreground'
                  }`}
              >
                {skill}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
