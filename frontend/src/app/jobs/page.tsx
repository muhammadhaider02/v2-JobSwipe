"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  Briefcase, 
  MapPin, 
  Building2, 
  Loader2, 
  ExternalLink,
  Clock,
  TrendingUp,
  Star,
  Award,
  Target,
  CheckCircle2,
  XCircle,
  Mail
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

type MatchedJob = {
  job_id: string;
  job_title: string;
  job_description: string;
  company_name: string;
  location: string;
  is_remote: boolean;
  job_type: string;
  experience_required: number;
  skills_required: string[];
  final_score: number;
  fit_percentage: string;
  component_scores: {
    title_similarity: number;
    skill_match: number;
    quiz_score: number;
    experience_alignment: number;
    location_fit: number;
  };
  matched_skills: string[];
  missing_skills: string[];
  url: string;
  source: string;
  date_posted: string;
  compensation_min: number | null;
  compensation_max: number | null;
  compensation_currency: string;
};

export default function JobsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [matchedJobs, setMatchedJobs] = useState<MatchedJob[]>([]);
  const [showMatched, setShowMatched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [hasProfile, setHasProfile] = useState(false);

  useEffect(() => {
    checkUserProfile();
  }, []);

  const checkUserProfile = async () => {
    try {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      
      if (user) {
        setUserId(user.id);
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/user-profile/${user.id}`
        );
        if (response.ok) {
          setHasProfile(true);
        }
      }
    } catch (err) {
      console.error("Error checking user profile:", err);
    }
  };

  const loadMatchedJobs = async () => {
    if (!userId) {
      setError("Please log in to see matched jobs");
      return;
    }

    if (!hasProfile) {
      setError("Please complete your onboarding to see matched jobs");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const profileResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/user-profile/${userId}`
      );
      
      if (!profileResponse.ok) {
        setError("Failed to load your profile");
        return;
      }
      
      const profileData = await profileResponse.json();
      const { profile, quiz_scores } = profileData;
      
      const matchResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/match-jobs`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            skills: profile.skills || [],
            previous_roles: profile.previous_roles || [],
            years_of_experience: profile.years_of_experience || 0,
            preferred_location: profile.location || null,
            quiz_scores: quiz_scores || null,
            top_k: 20,
          }),
        }
      );
      
      if (!matchResponse.ok) {
        const errorData = await matchResponse.json();
        setError(errorData.error || "Failed to match jobs");
        return;
      }
      
      const matchData = await matchResponse.json();
      setMatchedJobs(matchData.matches || []);
      setShowMatched(true);
      
    } catch (err) {
      console.error("Error loading matched jobs:", err);
      setError("An error occurred while matching jobs");
    } finally {
      setLoading(false);
    }
  };

  const getFitScoreColor = (score: number) => {
    if (score >= 0.8) return "text-green-600 bg-green-100";
    if (score >= 0.6) return "text-blue-600 bg-blue-100";
    if (score >= 0.4) return "text-yellow-600 bg-yellow-100";
    return "text-orange-600 bg-orange-100";
  };

  const getSourceBadgeColor = (source: string) => {
    switch (source) {
      case "rozee": return "bg-blue-100 text-blue-800";
      case "greenhouse": return "bg-green-100 text-green-800";
      case "lever": return "bg-purple-100 text-purple-800";
      case "glassdoor": return "bg-orange-100 text-orange-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "Recently posted";
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-blue-600 rounded-lg">
              <Briefcase className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Browse Jobs
              </h1>
              <p className="text-gray-600 mt-1">
                Find jobs that match your skills and preferences
              </p>
            </div>
          </div>
        </div>

        <Card className="p-6 mb-8 shadow-lg border-t-4 border-blue-600">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-blue-600" />
            <h2 className="text-xl font-semibold">AI-Powered Job Matching</h2>
          </div>

          <div className="mb-6 space-y-3">
            <div className="flex items-start gap-3 text-gray-700">
              <div className="p-2 bg-blue-100 rounded-lg mt-1">
                <Star className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="font-medium">5-Component Scoring</p>
                <p className="text-sm text-gray-600">
                  Title (35%), Skills (25%), Quiz (20%), Experience (15%), Location (5%)
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 text-gray-700">
              <div className="p-2 bg-green-100 rounded-lg mt-1">
                <Award className="w-4 h-4 text-green-600" />
              </div>
              <div>
                <p className="font-medium">Personalized Rankings</p>
                <p className="text-sm text-gray-600">
                  Jobs ranked by fit score based on your profile and quiz performance
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 text-gray-700">
              <div className="p-2 bg-purple-100 rounded-lg mt-1">
                <CheckCircle2 className="w-4 h-4 text-purple-600" />
              </div>
              <div>
                <p className="font-medium">Skills Analysis</p>
                <p className="text-sm text-gray-600">
                  See matched skills and identify missing skills for each role
                </p>
              </div>
            </div>
          </div>

          {userId && hasProfile ? (
            <Button
              onClick={loadMatchedJobs}
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Finding Matches...
                </>
              ) : (
                <>
                  <Target className="w-5 h-5 mr-2" />
                  Browse Matched Jobs
                </>
              )}
            </Button>
          ) : (
            <div className="space-y-3">
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  {!userId 
                    ? "Please log in to see personalized job matches"
                    : "Complete your onboarding to unlock job matching"}
                </p>
              </div>
              <Button
                onClick={() => router.push(userId ? '/onboarding' : '/auth/login')}
                className="w-full"
              >
                {userId ? 'Complete Onboarding' : 'Log In'}
              </Button>
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700">
              {error}
            </div>
          )}
        </Card>

        {showMatched && (
          <div className="mb-6">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-blue-600" />
              {matchedJobs.length > 0 
                ? `Top ${matchedJobs.length} Matched Jobs` 
                : "No Matches Found"}
            </h2>

            {matchedJobs.length === 0 ? (
              <Card className="p-12 text-center">
                <Briefcase className="w-16 h-16 mx-auto text-gray-400 mb-4" />
                <h3 className="text-xl font-semibold text-gray-700 mb-2">
                  No Matched Jobs
                </h3>
                <p className="text-gray-500 mb-4">
                  No jobs found. The system may need more job data or your profile might need updating.
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 gap-6">
                {matchedJobs.map((job, index) => (
                  <Card
                    key={job.job_id}
                    className="p-6 hover:shadow-xl transition-shadow border-l-4 border-blue-600"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-2xl font-bold text-gray-400">
                            #{index + 1}
                          </span>
                          <span className={`px-3 py-1 rounded-full text-sm font-bold ${getFitScoreColor(job.final_score)}`}>
                            {job.fit_percentage} Match
                          </span>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSourceBadgeColor(job.source)}`}>
                            {job.source.toUpperCase()}
                          </span>
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 mb-1">
                          {job.job_title}
                        </h3>
                        {job.company_name && (
                          <p className="text-md text-gray-700 flex items-center gap-2 mb-2">
                            <Building2 className="w-4 h-4" />
                            {job.company_name}
                          </p>
                        )}
                      </div>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <ExternalLink className="w-5 h-5 text-gray-600" />
                      </a>
                    </div>

                    <div className="mb-4">
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {job.job_description || "No description available"}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-3 text-sm text-gray-600 mb-4">
                      <div className="flex items-center gap-1">
                        <MapPin className="w-4 h-4" />
                        <span>{job.is_remote ? "Remote" : job.location || "Location not specified"}</span>
                      </div>
                      {job.job_type && (
                        <div className="flex items-center gap-1">
                          <Briefcase className="w-4 h-4" />
                          <span>{job.job_type}</span>
                        </div>
                      )}
                      {job.experience_required > 0 && (
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          <span>{job.experience_required} years exp</span>
                        </div>
                      )}
                      {job.date_posted && (
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          <span>{formatDate(job.date_posted)}</span>
                        </div>
                      )}
                      {job.compensation_max && (
                        <div className="flex items-center gap-1 text-green-600 font-medium">
                          <TrendingUp className="w-4 h-4" />
                          <span>
                            {job.compensation_currency} {job.compensation_min ? `${job.compensation_min}-` : ''}
                            {job.compensation_max}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                      <p className="text-xs font-semibold text-gray-600 mb-2">SCORE BREAKDOWN</p>
                      <div className="grid grid-cols-5 gap-2 text-xs">
                        <div className="text-center">
                          <div className="font-bold text-blue-600">{Math.round(job.component_scores.title_similarity * 100)}%</div>
                          <div className="text-gray-500">Title</div>
                        </div>
                        <div className="text-center">
                          <div className="font-bold text-green-600">{Math.round(job.component_scores.skill_match * 100)}%</div>
                          <div className="text-gray-500">Skills</div>
                        </div>
                        <div className="text-center">
                          <div className="font-bold text-purple-600">{Math.round(job.component_scores.quiz_score * 100)}%</div>
                          <div className="text-gray-500">Quiz</div>
                        </div>
                        <div className="text-center">
                          <div className="font-bold text-orange-600">{Math.round(job.component_scores.experience_alignment * 100)}%</div>
                          <div className="text-gray-500">Experience</div>
                        </div>
                        <div className="text-center">
                          <div className="font-bold text-pink-600">{Math.round(job.component_scores.location_fit * 100)}%</div>
                          <div className="text-gray-500">Location</div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {job.matched_skills.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3 text-green-600" />
                            MATCHED SKILLS ({job.matched_skills.length})
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {job.matched_skills.slice(0, 10).map((skill, idx) => (
                              <span key={idx} className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                                {skill}
                              </span>
                            ))}
                            {job.matched_skills.length > 10 && (
                              <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                                +{job.matched_skills.length - 10} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                      {job.missing_skills.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1">
                            <XCircle className="w-3 h-3 text-orange-600" />
                            SKILLS TO LEARN ({job.missing_skills.length})
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {job.missing_skills.slice(0, 10).map((skill, idx) => (
                              <span key={idx} className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
                                {skill}
                              </span>
                            ))}
                            {job.missing_skills.length > 10 && (
                              <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                                +{job.missing_skills.length - 10} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="mt-4 pt-4 border-t border-gray-200 flex gap-3">
                      <button
                        onClick={() => router.push(`/cover-letter?jobId=${job.job_id}`)}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white rounded-lg font-medium transition-all shadow-sm hover:shadow-md"
                      >
                        <Mail className="w-4 h-4" />
                        Generate Cover Letter
                      </button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
