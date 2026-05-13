'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowLeft,
  Briefcase,
  ArrowRight,
  Check,
  SearchX,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';

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

export default function SelectJobsPage() {
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>(
    [],
  );
  const [learnedSkills, setLearnedSkills] = useState<Set<string>>(new Set());
  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(new Set());
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const storedLearned = localStorage.getItem('learnedSkills');
    if (storedLearned) {
      try {
        setLearnedSkills(new Set(JSON.parse(storedLearned)));
      } catch (e) {
        console.error('Error loading learned skills:', e);
      }
    }

    const cachedRecommendations = sessionStorage.getItem('recommendations');
    if (cachedRecommendations) {
      try {
        setRecommendations(JSON.parse(cachedRecommendations));
      } catch (e) {
        console.error('Error loading cached recommendations:', e);
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
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);

    const existingSkills = rec.skillGapData?.existing_skills || [];
    const missingSkills = rec.skillGapData?.required_skills || [];
    const totalRequiredSkills = allRequiredSkills.length;
    const learnedCount = missingSkills.filter((skill) =>
      learnedSkills.has(skill.toLowerCase()),
    ).length;
    const matchedCount = existingSkills.length + learnedCount;

    return totalRequiredSkills > 0
      ? Math.round((matchedCount / totalRequiredSkills) * 100)
      : rec.skillGapData?.completion_percentage ??
          Math.round(rec.score * 100);
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
    sessionStorage.setItem(
      'selectedRoles',
      JSON.stringify(Array.from(selectedRoles)),
    );
    router.push('/jobs');
  };

  if (!isLoaded) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col relative">
        <div className="flex-1 w-full pb-8 pt-0 px-4">
          <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
            <div className="mb-6 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-muted" />
                <div>
                  <div className="h-6 w-48 bg-muted rounded mb-1" />
                  <div className="h-4 w-64 bg-muted rounded" />
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-3 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-card border rounded-xl py-2.5 px-4 flex items-center gap-4"
                >
                  <div className="w-6 h-6 rounded bg-muted" />
                  <div className="p-2.5 bg-muted rounded-lg hidden sm:block">
                    <div className="w-5 h-5" />
                  </div>
                  <div className="flex-grow">
                    <div className="h-5 bg-muted rounded w-52" />
                  </div>
                  <div className="h-7 bg-muted rounded w-14" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

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
          <PageHeader
            icon={Briefcase}
            title="Top Matched Roles"
            subtitle="Select the roles you want to find jobs for"
          />

          {qualifiedRoles.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="No highly matched roles found"
              description="Try returning to the previous page and learning more skills!"
              action={{
                label: 'Back to Recommendations',
                href: '/recommendations',
              }}
            />
          ) : (
            <>
              <div className="flex flex-col gap-3 mb-5">
                {qualifiedRoles.map((rec, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ ...spring, delay: idx * 0.06 }}
                    whileHover={{ x: 4 }}
                    onClick={() => toggleRoleSelection(rec.role)}
                    className={`bg-card border-2 rounded-xl py-2.5 px-4 shadow-sm hover:shadow-md transition-colors flex items-center gap-4 cursor-pointer ${
                      selectedRoles.has(rec.role)
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/30'
                    }`}
                  >
                    <div className="flex-shrink-0 flex items-center justify-center">
                      <div
                        className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                          selectedRoles.has(rec.role)
                            ? 'bg-primary border-primary text-primary-foreground'
                            : 'border-2 border-input bg-background'
                        }`}
                      >
                        {selectedRoles.has(rec.role) && (
                          <Check className="w-3.5 h-3.5" />
                        )}
                      </div>
                    </div>

                    <div className="p-2.5 bg-primary/10 rounded-lg hidden sm:block">
                      <Briefcase className="w-5 h-5 text-primary" />
                    </div>

                    <div className="flex-grow">
                      <h3 className="text-lg font-semibold leading-tight">
                        {rec.role}
                      </h3>
                    </div>

                    <div className="flex-shrink-0 text-right">
                      <div className="text-xs text-muted-foreground mb-0.5">
                        Match
                      </div>
                      <div className="font-bold text-primary text-xl">
                        {rec.matchPercentage}%
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ ...spring, delay: 0.3 }}
                className="flex justify-end w-full pb-0"
              >
                <Button
                  onClick={handleFetchJobs}
                  disabled={selectedRoles.size === 0}
                >
                  Fetch Jobs
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </motion.div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
