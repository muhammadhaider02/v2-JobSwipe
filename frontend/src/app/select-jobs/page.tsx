"use client";

import React, { useEffect, useState } from "react";
import { ArrowLeft, Briefcase, FileText, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

export default function SelectJobsPage() {
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [learnedSkills, setLearnedSkills] = useState<Set<string>>(new Set());
  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(new Set());
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const storedLearned = localStorage.getItem("learnedSkills");
    if (storedLearned) {
      try {
        setLearnedSkills(new Set(JSON.parse(storedLearned)));
      } catch (e) {
        console.error("Error loading learned skills:", e);
      }
    }

    const cachedRecommendations = sessionStorage.getItem("recommendations");
    if (cachedRecommendations) {
      try {
        setRecommendations(JSON.parse(cachedRecommendations));
      } catch (e) {
        console.error("Error loading cached recommendations:", e);
      }
    }

    setIsLoaded(true);
  }, []);

  const calculateMatchPercentage = (rec: Recommendation): number => {
    const allRequiredSkills = rec.skillGapData
      ? [
        ...rec.skillGapData.existing_skills,
        ...rec.skillGapData.required_skills,
      ]
      : rec.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

    const existingSkills = rec.skillGapData?.existing_skills || [];
    const missingSkills = rec.skillGapData?.required_skills || [];
    const totalRequiredSkills = allRequiredSkills.length;
    const learnedCount = missingSkills.filter((skill) =>
      learnedSkills.has(skill.toLowerCase())
    ).length;
    const matchedCount = existingSkills.length + learnedCount;

    return totalRequiredSkills > 0
      ? Math.round((matchedCount / totalRequiredSkills) * 100)
      : rec.skillGapData?.completion_percentage ?? Math.round(rec.score * 100);
  };

  const toggleRoleSelection = (role: string) => {
    setSelectedRoles((prev) => {
      const next = new Set(prev);
      if (next.has(role)) {
        next.delete(role);
      } else {
        next.add(role);
      }
      return next;
    });
  };

  const handleFetchJobs = () => {
    if (selectedRoles.size === 0) return;
    // Write selected roles to sessionStorage so /jobs page can read them
    sessionStorage.setItem(
      "selectedRoles",
      JSON.stringify(Array.from(selectedRoles))
    );
    router.push("/jobs");
  };

  if (!isLoaded) return null;

  const qualifiedRoles = recommendations
    .map((rec) => ({
      ...rec,
      matchPercentage: calculateMatchPercentage(rec),
    }))
    .filter((rec) => rec.matchPercentage >= 70)
    .sort((a, b) => b.matchPercentage - a.matchPercentage);

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/recommendations"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-3 mb-2">
              <Briefcase className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">Top Matched Roles</h1>
            </div>
            <p className="text-muted-foreground">
              Select the roles you want to find jobs for
            </p>
          </div>

          {/* Roles List */}
          <div className="flex flex-col gap-3 mb-5">
            {qualifiedRoles.length === 0 ? (
              <div className="text-center py-12 bg-card border rounded-xl shadow-sm">
                <h2 className="text-xl font-semibold mb-2">
                  No highly matched roles found
                </h2>
                <p className="text-muted-foreground">
                  Try returning to the previous page and learning more skills!
                </p>
              </div>
            ) : (
              qualifiedRoles.map((rec, idx) => (
                <div
                  key={idx}
                  className={`bg-card border rounded-xl py-2.5 px-4 shadow-sm hover:shadow-md transition-all flex items-center gap-4 cursor-pointer ${
                    selectedRoles.has(rec.role)
                      ? "border-primary ring-1 ring-primary bg-primary/5"
                      : "hover:border-primary/50"
                  }`}
                  onClick={() => toggleRoleSelection(rec.role)}
                >
                  {/* Checkbox */}
                  <div className="flex-shrink-0 flex items-center justify-center">
                    <div
                      className={`w-6 h-6 rounded border flex items-center justify-center ${
                        selectedRoles.has(rec.role)
                          ? "bg-primary border-primary text-primary-foreground"
                          : "border-input bg-background"
                      }`}
                    >
                      {selectedRoles.has(rec.role) && (
                        <span className="text-xs font-bold">✓</span>
                      )}
                    </div>
                  </div>

                  {/* Icon */}
                  <div className="p-2.5 bg-primary/10 rounded-lg hidden sm:block">
                    <Briefcase className="w-5 h-5 text-primary" />
                  </div>

                  {/* Role name */}
                  <div className="flex-grow">
                    <h3 className="text-lg font-semibold leading-tight">
                      {rec.role}
                    </h3>
                  </div>

                  {/* Match % */}
                  <div className="flex-shrink-0 text-right">
                    <div className="text-xs text-muted-foreground mb-0.5">
                      Match
                    </div>
                    <div className="font-bold text-primary text-xl">
                      {rec.matchPercentage}%
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Fetch Jobs button */}
          {qualifiedRoles.length > 0 && (
            <div className="flex justify-end w-full pb-0">
              <button
                id="fetch-jobs-btn"
                onClick={handleFetchJobs}
                disabled={selectedRoles.size === 0}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Fetch Jobs
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
