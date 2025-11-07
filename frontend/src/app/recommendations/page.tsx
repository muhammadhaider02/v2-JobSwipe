"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Briefcase, Sparkles, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

type Recommendation = {
  role: string;
  score: number;
  skills: string;
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
            body: JSON.stringify({ skills, top_k: 10 }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (!res.ok) {
            throw new Error(`Failed to fetch recommendations: ${res.status}`);
          }

          const data = await res.json();
          setRecommendations(data.recommendations || []);
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
  const skillsArray = recommendation.skills.split(',').map(s => s.trim()).filter(Boolean);

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

      {/* Required Skills */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground mb-2 uppercase">Required Skills</h4>
        <div className="flex flex-wrap gap-1.5">
          {skillsArray.slice(0, 6).map((skill, idx) => (
            <span key={idx} className="px-2 py-0.5 bg-muted text-foreground rounded text-xs">
              {skill}
            </span>
          ))}
          {skillsArray.length > 6 && (
            <span className="px-2 py-0.5 text-muted-foreground text-xs">
              +{skillsArray.length - 6} more
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
