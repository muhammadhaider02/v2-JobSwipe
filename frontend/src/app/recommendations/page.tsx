'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Briefcase,
  Sparkles,
  ArrowLeft,
  BookOpen,
  Check,
  Clock,
  Search,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'motion/react';
import { createClient } from '@/lib/supabase/client';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';
import { SkillBadge } from '@/components/shared/skill-badge';

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

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

function RecommendationsSkeleton() {
  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <div className="h-4 w-12 bg-muted rounded animate-pulse" />
      </div>
      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2 animate-pulse">
          <div className="mb-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-11 h-11 rounded-xl bg-muted" />
              <div>
                <div className="h-7 w-56 bg-muted rounded mb-1" />
                <div className="h-4 w-72 bg-muted rounded" />
              </div>
            </div>
          </div>

          <div className="mb-5 p-4 bg-card border rounded-xl">
            <div className="h-5 w-24 bg-muted rounded mb-3" />
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="h-7 bg-muted rounded-full"
                  style={{ width: `${60 + Math.random() * 40}px` }}
                />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="bg-card border rounded-xl p-6 shadow-sm"
              >
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-10 h-10 bg-muted rounded-lg" />
                  <div className="flex-1">
                    <div className="h-5 bg-muted rounded w-3/4 mb-2" />
                  </div>
                  <div className="w-8 h-8 bg-muted rounded-full" />
                </div>
                <div className="mb-3">
                  <div className="flex justify-between mb-1">
                    <div className="h-3 w-16 bg-muted rounded" />
                    <div className="h-3 w-8 bg-muted rounded" />
                  </div>
                  <div className="h-1.5 bg-muted rounded-full w-full" />
                </div>
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <div
                      key={j}
                      className="h-6 bg-muted rounded-full"
                      style={{ width: `${50 + Math.random() * 40}px` }}
                    />
                  ))}
                </div>
                <div className="h-9 bg-muted rounded-lg w-full mt-4" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RoleCard({
  recommendation,
  rank,
  index,
  learnedSkills,
  onMarkAsLearned,
  onViewLearningResources,
}: {
  recommendation: Recommendation;
  rank: number;
  index: number;
  learnedSkills: Set<string>;
  onMarkAsLearned: (skill: string) => void;
  onViewLearningResources: (skills: string[]) => void;
}) {
  const [selectedMissingSkill, setSelectedMissingSkill] = useState<
    string | null
  >(null);

  const allRequiredSkills = recommendation.skillGapData
    ? [
        ...recommendation.skillGapData.existing_skills,
        ...recommendation.skillGapData.required_skills,
      ]
    : recommendation.skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

  const existingSkills = recommendation.skillGapData?.existing_skills || [];
  const missingSkills = recommendation.skillGapData?.required_skills || [];

  const actualMissingSkills = missingSkills.filter(
    (skill) => !learnedSkills.has(skill.toLowerCase()),
  );

  const totalRequiredSkills = allRequiredSkills.length;
  const learnedCount = missingSkills.filter((skill) =>
    learnedSkills.has(skill.toLowerCase()),
  ).length;
  const matchedCount = existingSkills.length + learnedCount;
  const dynamicCompletionPercentage =
    totalRequiredSkills > 0
      ? Math.round((matchedCount / totalRequiredSkills) * 100)
      : recommendation.skillGapData?.completion_percentage || 0;

  const displaySkills = allRequiredSkills.slice(0, 15);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...spring, delay: index * 0.08 }}
    >
      <Card className="p-6 shadow-sm hover:shadow-md transition-all hover:border-primary/50 relative overflow-hidden flex flex-col h-full">
        <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
          {rank}
        </div>

        <div className="mb-4 pr-10">
          <div className="flex items-start gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <Briefcase className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-bold leading-tight">
                {recommendation.role}
              </h3>
            </div>
          </div>
        </div>

        {recommendation.skillGapData && (
          <div className="mb-3">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground">Skill Match</span>
              <span className="font-semibold text-primary">
                {dynamicCompletionPercentage}%
              </span>
            </div>
            <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${dynamicCompletionPercentage}%` }}
                transition={{ ...spring, delay: index * 0.08 + 0.2 }}
                className="bg-primary h-1.5 rounded-full"
              />
            </div>
          </div>
        )}

        <div className="flex-grow">
          <h4 className="text-xs font-semibold text-muted-foreground mb-2 uppercase">
            Required Skills
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {displaySkills.map((skill, idx) => {
              const isExisting = existingSkills.some(
                (s) => s.toLowerCase() === skill.toLowerCase(),
              );
              const isMissing = missingSkills.some(
                (s) => s.toLowerCase() === skill.toLowerCase(),
              );
              const isLearned = learnedSkills.has(skill.toLowerCase());

              let variant: 'existing' | 'missing' | 'learned' | 'neutral';
              if (isExisting || isLearned) variant = 'existing';
              else if (isMissing) variant = 'missing';
              else variant = 'neutral';

              return (
                <SkillBadge
                  key={idx}
                  variant={variant}
                  onClick={
                    isMissing && !isLearned
                      ? () =>
                          setSelectedMissingSkill(
                            selectedMissingSkill === skill ? null : skill,
                          )
                      : undefined
                  }
                >
                  {skill}
                </SkillBadge>
              );
            })}
          </div>
        </div>

        <AnimatePresence>
          {selectedMissingSkill && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={spring}
              className="overflow-hidden"
            >
              <div className="mt-4 p-3 bg-muted/50 rounded-lg border border-dashed">
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Actions for:{' '}
                  <span className="text-foreground">
                    {selectedMissingSkill}
                  </span>
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 text-xs gap-1.5"
                    onClick={() => {
                      onMarkAsLearned(selectedMissingSkill);
                      setSelectedMissingSkill(null);
                    }}
                  >
                    <Check className="w-3 h-3" />
                    Mark as Learned
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1 text-xs gap-1.5"
                    onClick={() => {
                      onViewLearningResources([selectedMissingSkill]);
                      setSelectedMissingSkill(null);
                    }}
                  >
                    <BookOpen className="w-3 h-3" />
                    Learn This
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {actualMissingSkills.length > 0 && (
          <div className="mt-auto pt-4">
            <Button
              className="w-full gap-2"
              onClick={() => onViewLearningResources(actualMissingSkills)}
            >
              <BookOpen className="w-4 h-4" />
              Learn All Missing Skills ({actualMissingSkills.length})
            </Button>
          </div>
        )}
      </Card>
    </motion.div>
  );
}

function RecommendationsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userSkills, setUserSkills] = useState<string[]>([]);
  const [learnedSkills, setLearnedSkills] = useState<Set<string>>(
    new Set(),
  );
  const [userId, setUserId] = useState<string | null>(null);

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

  useEffect(() => {
    const fetchUserId = async () => {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
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
        const skillsParam = searchParams.get('skills');

        let skills: string[];
        if (skillsParam) {
          skills = JSON.parse(decodeURIComponent(skillsParam));
        } else {
          const storedSkills = sessionStorage.getItem('userSkills');
          if (storedSkills) {
            skills = JSON.parse(storedSkills);
          } else {
            setError('No skills provided');
            setLoading(false);
            return;
          }
        }

        setUserSkills(skills);

        const cachedRecommendations =
          sessionStorage.getItem('recommendations');
        const cachedSkills = sessionStorage.getItem(
          'cachedRecommendationSkills',
        );
        const skillsUnchanged = cachedSkills === JSON.stringify(skills);
        const resumeChanged = sessionStorage.getItem('resumeChanged');

        if (cachedRecommendations && skillsUnchanged && !resumeChanged) {
          setRecommendations(JSON.parse(cachedRecommendations));
          setLoading(false);
          return;
        }

        sessionStorage.removeItem('resumeChanged');
        sessionStorage.setItem('userSkills', JSON.stringify(skills));

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);

        try {
          const res = await fetch(`/api/recommend-roles`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ skills, user_id: userId }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (!res.ok) {
            throw new Error(
              `Failed to fetch recommendations: ${res.status}`,
            );
          }

          const data = await res.json();
          const recommendations = data.recommendations || [];

          const recommendationsWithGapData = await Promise.all(
            recommendations.map(async (rec: Recommendation) => {
              if (rec.skillGapData) {
                return rec;
              }

              try {
                const gapRes = await fetch(`/api/analyze-skill-gap`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    role: rec.role,
                    skills,
                  }),
                });

                if (gapRes.ok) {
                  const gapData = await gapRes.json();
                  return {
                    ...rec,
                    skillGapData: {
                      existing_skills: gapData.existing_skills || [],
                      required_skills: gapData.required_skills || [],
                      completion_percentage:
                        gapData.completion_percentage || 0,
                    },
                  };
                }
              } catch (error) {
                console.error(
                  `Failed to fetch skill gap for ${rec.role}:`,
                  error,
                );
              }
              return rec;
            }),
          );

          setRecommendations(recommendationsWithGapData);
          if (recommendationsWithGapData.length > 0) {
            sessionStorage.setItem(
              'recommendations',
              JSON.stringify(recommendationsWithGapData),
            );
            sessionStorage.setItem(
              'cachedRecommendationSkills',
              JSON.stringify(skills),
            );
          }
        } catch (fetchError: any) {
          clearTimeout(timeoutId);
          if (fetchError.name === 'AbortError') {
            throw new Error(
              'Backend server is not responding. Please make sure the backend is running.',
            );
          }
          throw fetchError;
        }
      } catch (err: any) {
        console.error('Recommendation fetch error:', err);
        setError(
          err?.message ||
            'Failed to load recommendations. Please ensure the backend server is running.',
        );
      } finally {
        setLoading(false);
      }
    }

    fetchRecommendations();
  }, [searchParams]);

  const handleMarkAsLearned = (skill: string) => {
    setLearnedSkills((prev) => {
      const newSet = new Set(prev);
      newSet.add(skill.toLowerCase());
      localStorage.setItem(
        'learnedSkills',
        JSON.stringify(Array.from(newSet)),
      );
      return newSet;
    });
  };

  const handleBrowseJobs = async () => {
    if (!userId) {
      router.push('/select-jobs');
      return;
    }

    try {
      const profileResponse = await fetch(`/api/user-profile/${userId}`);

      if (profileResponse.ok) {
        const profileData = await profileResponse.json();
        const existingProfile = profileData.profile;

        const recommendedRoleNames = recommendations.map((rec) => rec.role);

        await fetch(`/api/user-profile`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ...existingProfile,
            recommended_roles: recommendedRoleNames,
          }),
        });
      } else {
        const recommendedRoleNames = recommendations.map((rec) => rec.role);
        await fetch(`/api/user-profile`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: userId,
            recommended_roles: recommendedRoleNames,
          }),
        });
      }

      router.push('/select-jobs');
    } catch (error) {
      console.error('Error saving recommended roles:', error);
      router.push('/select-jobs');
    }
  };

  const handleViewLearningResources = (missingSkills: string[]) => {
    sessionStorage.setItem(
      'currentLearningSkills',
      JSON.stringify(missingSkills),
    );
    router.push('/learning-preferences');
  };

  if (loading) {
    return <RecommendationsSkeleton />;
  }

  if (error) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <Card className="border-destructive max-w-md p-6">
          <div className="flex items-start gap-4">
            <div className="shrink-0 flex items-center justify-center w-12 h-12 rounded-full bg-destructive/15">
              <AlertCircle className="w-6 h-6 text-destructive" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold mb-1">
                Something went wrong
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                {error}
              </p>
              <Button asChild variant="outline">
                <Link href="/onboarding" className="gap-2">
                  <ArrowLeft className="w-4 h-4" />
                  Go Back
                </Link>
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
      <div className="absolute top-4 left-6 z-10">
        <Link
          href="/onboarding"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          <PageHeader
            icon={Sparkles}
            title="Recommended Roles"
            subtitle={`Based on your ${userSkills.length} skill${userSkills.length !== 1 ? 's' : ''}, we found ${recommendations.length} matching roles`}
          />

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.08 }}
          >
            <Card className="mb-5 p-4">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h2 className="text-base font-semibold text-foreground">
                  Your Skills
                </h2>
                <div className="flex items-center gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link href="/jobs-applied" className="gap-2">
                      <Clock className="w-4 h-4" />
                      Jobs Applied
                    </Link>
                  </Button>
                  <Button size="sm" onClick={handleBrowseJobs} className="gap-2">
                    <Search className="w-4 h-4" />
                    View Matching Jobs
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {userSkills.map((skill, idx) => (
                  <SkillBadge key={idx} variant="neutral">
                    {skill}
                  </SkillBadge>
                ))}
              </div>
            </Card>
          </motion.div>

          {recommendations.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No recommendations found"
              description="Try adding more skills or check back later"
              action={{
                label: 'Go Back',
                href: '/onboarding',
              }}
            />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {recommendations.map((rec, idx) => (
                <RoleCard
                  key={idx}
                  recommendation={rec}
                  rank={idx + 1}
                  index={idx}
                  learnedSkills={learnedSkills}
                  onMarkAsLearned={handleMarkAsLearned}
                  onViewLearningResources={handleViewLearningResources}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  return (
    <Suspense fallback={<RecommendationsSkeleton />}>
      <RecommendationsContent />
    </Suspense>
  );
}
