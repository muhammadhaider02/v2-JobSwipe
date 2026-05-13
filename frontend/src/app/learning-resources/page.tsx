'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'motion/react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ExternalLink,
  BookOpen,
  Youtube,
  Search,
  Filter,
  ArrowLeft,
  ArrowRight,
  AlertCircle,
  Star,
} from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';

type GoogleResult = {
  title: string;
  url: string;
  snippet: string;
  domain: string;
  confidence: number;
};

type YouTubeResult = {
  title: string;
  channel: string;
  url: string;
  video_count?: number;
  description: string;
  confidence: number;
  thumbnail_url?: string;
};

type SkillResources = {
  skill: string;
  google_results: GoogleResult[];
  youtube_playlists: YouTubeResult[];
  total_confidence: number;
};

type LearningPreferences = {
  knowledgeLevel: 'beginner' | 'intermediate' | 'advanced';
  timeCommitment: 'short' | 'medium' | 'long';
  preferredChannels: string[];
  contentTypes: {
    articles: boolean;
    videos: boolean;
    playlists: boolean;
  };
};

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

function getConfidenceBadgeClasses(confidence: number) {
  if (confidence >= 0.8)
    return 'bg-green-500/15 text-green-700 dark:text-green-400';
  if (confidence >= 0.6)
    return 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400';
  return 'bg-orange-500/15 text-orange-700 dark:text-orange-400';
}

function ResourcesSkeleton() {
  return (
    <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col">
      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2 animate-pulse">
          <div className="mb-6">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-muted" />
              <div>
                <div className="h-7 w-56 bg-muted rounded mb-1" />
                <div className="h-4 w-72 bg-muted rounded" />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-1">
              <Card className="p-4">
                <div className="h-5 w-32 bg-muted rounded mb-4" />
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-12 bg-muted rounded-lg" />
                  ))}
                </div>
              </Card>
            </div>
            <div className="lg:col-span-4 space-y-6">
              <Card className="p-6">
                <div className="h-8 w-40 bg-muted rounded mb-2" />
              </Card>
              {Array.from({ length: 3 }).map((_, i) => (
                <Card key={i} className="p-5">
                  <div className="h-5 w-3/4 bg-muted rounded mb-2" />
                  <div className="h-3 w-24 bg-muted rounded mb-2" />
                  <div className="h-4 w-full bg-muted rounded" />
                </Card>
              ))}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Card key={i} className="overflow-hidden">
                    <div className="h-48 bg-muted" />
                    <div className="p-4">
                      <div className="h-5 w-3/4 bg-muted rounded mb-2" />
                      <div className="h-3 w-1/2 bg-muted rounded" />
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LearningResourcesPage() {
  const router = useRouter();

  const [resources, setResources] = useState<SkillResources[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [preferences, setPreferences] =
    useState<LearningPreferences | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem('learningResourcesSkills');
    const skills: string[] | null = stored ? JSON.parse(stored) : null;

    const storedPrefs = sessionStorage.getItem('learningPreferences');
    if (storedPrefs) {
      setPreferences(JSON.parse(storedPrefs));
    }

    const cachedResources = sessionStorage.getItem('learningResources');
    if (cachedResources && skills) {
      const cached = JSON.parse(cachedResources);

      const cachedSkills = cached.skills || [];
      const skillsMatch =
        skills.length === cachedSkills.length &&
        skills.every((skill: string) => cachedSkills.includes(skill));

      if (skillsMatch) {
        setResources(cached.resources);
        if (cached.selectedSkill) {
          setSelectedSkill(cached.selectedSkill);
        }
        setLoading(false);
        return;
      }
    }

    if (skills) {
      fetchLearningResources(skills);
    }
  }, []);

  const fetchLearningResources = async (skills: string[]) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/learning-resources`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          skills: skills,
          num_google_results: 10,
          num_youtube_results: 5,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResources(data.resources);

      const firstSkill =
        data.resources.length > 0 ? data.resources[0].skill : null;
      if (firstSkill) {
        setSelectedSkill(firstSkill);
      }

      sessionStorage.setItem(
        'learningResources',
        JSON.stringify({
          skills: skills,
          resources: data.resources,
          selectedSkill: firstSkill,
        }),
      );
    } catch (err) {
      console.error('Error fetching learning resources:', err);
      setError(
        err instanceof Error ? err.message : 'Failed to load resources',
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (resources.length > 0 && selectedSkill) {
      const cached = sessionStorage.getItem('learningResources');
      if (cached) {
        const data = JSON.parse(cached);
        data.selectedSkill = selectedSkill;
        sessionStorage.setItem('learningResources', JSON.stringify(data));
      }
    }
  }, [selectedSkill, resources]);

  const filterResourcesByPreferences = (
    resource: SkillResources,
  ): SkillResources => {
    if (!preferences) return resource;

    let filteredGoogleResults = [...resource.google_results];
    let filteredYoutubeResults = [...resource.youtube_playlists];

    if (!preferences.contentTypes.articles) {
      filteredGoogleResults = [];
    }

    if (
      !preferences.contentTypes.videos &&
      !preferences.contentTypes.playlists
    ) {
      filteredYoutubeResults = [];
    } else if (!preferences.contentTypes.playlists) {
      filteredYoutubeResults = filteredYoutubeResults.filter(
        (video) => !video.video_count || video.video_count <= 3,
      );
    } else if (!preferences.contentTypes.videos) {
      filteredYoutubeResults = filteredYoutubeResults.filter(
        (video) => video.video_count && video.video_count > 3,
      );
    }

    if (preferences.preferredChannels.length > 0) {
      const preferredVideos = filteredYoutubeResults.filter((video) =>
        preferences.preferredChannels.some((channel) =>
          video.channel.toLowerCase().includes(channel.toLowerCase()),
        ),
      );

      if (preferredVideos.length > 0) {
        const otherVideos = filteredYoutubeResults.filter(
          (video) =>
            !preferences.preferredChannels.some((channel) =>
              video.channel
                .toLowerCase()
                .includes(channel.toLowerCase()),
            ),
        );
        filteredYoutubeResults = [...preferredVideos, ...otherVideos];
      }
    }

    if (preferences.timeCommitment === 'short') {
      filteredGoogleResults = filteredGoogleResults.slice(0, 5);
      filteredYoutubeResults = filteredYoutubeResults
        .filter((video) => !video.video_count || video.video_count <= 10)
        .slice(0, 3);
    } else if (preferences.timeCommitment === 'medium') {
      filteredGoogleResults = filteredGoogleResults.slice(0, 7);
      filteredYoutubeResults = filteredYoutubeResults
        .filter((video) => !video.video_count || video.video_count <= 30)
        .slice(0, 4);
    } else {
      filteredGoogleResults = filteredGoogleResults.slice(0, 10);
      filteredYoutubeResults = filteredYoutubeResults.slice(0, 5);
    }

    return {
      ...resource,
      google_results: filteredGoogleResults,
      youtube_playlists: filteredYoutubeResults,
    };
  };

  const selectedResource = resources.find((r) => r.skill === selectedSkill);
  const filteredResource = selectedResource
    ? filterResourcesByPreferences(selectedResource)
    : null;

  if (loading) {
    return <ResourcesSkeleton />;
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
                Error Loading Resources
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                {error}
              </p>
              <Button onClick={() => window.location.reload()}>
                Try Again
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  if (!loading && resources.length === 0) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <EmptyState
          icon={Search}
          title="No Skills Provided"
          description="Please select a role to view learning resources for missing skills."
          action={{
            label: 'Go to Recommendations',
            href: '/recommendations',
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 w-full flex flex-col relative bg-gradient-to-br from-background to-muted/20">
      <div className="absolute top-4 left-6 z-10">
        <button
          onClick={() => router.push('/learning-preferences')}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          <PageHeader
            icon={BookOpen}
            title="Learning Resources"
            subtitle="Curated learning materials tailored to your preferences"
          />

          {preferences && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...spring, delay: 0.08 }}
              className="mb-6 flex flex-wrap items-center gap-2"
            >
              <Filter className="w-4 h-4 text-primary" />
              <span className="text-sm text-muted-foreground">
                Active filters:
              </span>
              <Badge
                variant="secondary"
                className="bg-primary/10 text-primary"
              >
                {preferences.knowledgeLevel.charAt(0).toUpperCase() +
                  preferences.knowledgeLevel.slice(1)}
              </Badge>
              <Badge
                variant="secondary"
                className="bg-primary/10 text-primary"
              >
                {preferences.timeCommitment === 'short'
                  ? 'Quick Learning'
                  : preferences.timeCommitment === 'medium'
                    ? 'Moderate Pace'
                    : 'Deep Dive'}
              </Badge>
              {(preferences?.preferredChannels?.length ?? 0) > 0 && (
                <Badge
                  variant="secondary"
                  className="bg-primary/10 text-primary"
                >
                  {preferences.preferredChannels.length} Preferred
                  Channels
                </Badge>
              )}
            </motion.div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-1">
              <motion.div
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ ...spring, delay: 0.12 }}
              >
                <Card className="p-4 sticky top-4 shadow-sm">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-primary" />
                    Skills to Learn ({resources.length})
                  </h3>
                  <div className="space-y-2">
                    {resources.map((resource, idx) => {
                      const filtered =
                        filterResourcesByPreferences(resource);
                      const totalResources =
                        filtered.google_results.length +
                        filtered.youtube_playlists.length;

                      return (
                        <motion.button
                          key={resource.skill}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{
                            ...spring,
                            delay: 0.16 + idx * 0.06,
                          }}
                          onClick={() =>
                            setSelectedSkill(resource.skill)
                          }
                          className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
                            selectedSkill === resource.skill
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted hover:bg-muted/80'
                          }`}
                        >
                          <div className="font-medium capitalize">
                            {resource.skill}
                          </div>
                          <div className="text-xs mt-1 opacity-80">
                            {totalResources} resources
                          </div>
                        </motion.button>
                      );
                    })}
                  </div>
                </Card>
              </motion.div>
            </div>

            <div className="lg:col-span-4">
              <AnimatePresence mode="wait">
                {filteredResource && (
                  <motion.div
                    key={filteredResource.skill}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -12 }}
                    transition={spring}
                    className="space-y-6"
                  >
                    <Card className="p-6 shadow-sm">
                      <h2 className="text-3xl font-bold capitalize">
                        {filteredResource.skill}
                      </h2>
                    </Card>

                    {filteredResource.google_results.length > 0 && (
                      <div>
                        <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                          <BookOpen className="w-6 h-6 text-primary" />
                          Articles and Tutorials
                        </h3>
                        <div className="space-y-4">
                          {filteredResource.google_results.map(
                            (result, index) => (
                              <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{
                                  ...spring,
                                  delay: index * 0.06,
                                }}
                              >
                                <Card className="p-5 shadow-sm hover:shadow-md transition-shadow">
                                  <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1">
                                      <a
                                        href={result.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-lg font-semibold text-primary hover:underline flex items-center gap-2"
                                      >
                                        {result.title}
                                        <ExternalLink className="w-4 h-4 shrink-0" />
                                      </a>
                                      <p className="text-sm text-muted-foreground mt-1">
                                        {result.domain}
                                      </p>
                                      <p className="text-sm mt-2 leading-relaxed">
                                        {result.snippet}
                                      </p>
                                    </div>
                                    <Badge
                                      className={getConfidenceBadgeClasses(
                                        result.confidence,
                                      )}
                                    >
                                      {(
                                        result.confidence * 100
                                      ).toFixed(0)}
                                      %
                                    </Badge>
                                  </div>
                                </Card>
                              </motion.div>
                            ),
                          )}
                        </div>
                      </div>
                    )}

                    {filteredResource.youtube_playlists.length > 0 && (
                      <div>
                        <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                          <Youtube className="w-6 h-6 text-red-600" />
                          Video Courses and Playlists
                          {(preferences?.preferredChannels?.length ??
                            0) > 0 && (
                            <span className="text-sm text-muted-foreground font-normal">
                              (Prioritizing your preferred channels)
                            </span>
                          )}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {filteredResource.youtube_playlists.map(
                            (video, index) => {
                              const isPreferred =
                                preferences?.preferredChannels.some(
                                  (channel) =>
                                    video.channel
                                      .toLowerCase()
                                      .includes(
                                        channel.toLowerCase(),
                                      ),
                                );

                              return (
                                <motion.div
                                  key={index}
                                  initial={{ opacity: 0, y: 10 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{
                                    ...spring,
                                    delay: index * 0.08,
                                  }}
                                  whileHover={{ y: -2 }}
                                  onClick={() =>
                                    window.open(
                                      video.url,
                                      '_blank',
                                      'noopener,noreferrer',
                                    )
                                  }
                                  className="cursor-pointer"
                                >
                                  <Card
                                    className={`overflow-hidden shadow-sm hover:shadow-md transition-shadow ${
                                      isPreferred
                                        ? 'ring-2 ring-green-500'
                                        : ''
                                    }`}
                                  >
                                    {video.thumbnail_url && (
                                      <div className="relative h-48 bg-muted">
                                        <img
                                          src={video.thumbnail_url}
                                          alt={video.title}
                                          className="w-full h-full object-cover"
                                        />
                                        <div className="absolute top-2 right-2">
                                          <Badge
                                            className={getConfidenceBadgeClasses(
                                              video.confidence,
                                            )}
                                          >
                                            {(
                                              video.confidence * 100
                                            ).toFixed(0)}
                                            %
                                          </Badge>
                                        </div>
                                        {isPreferred && (
                                          <div className="absolute top-2 left-2">
                                            <Badge className="bg-green-600 text-white gap-1">
                                              <Star className="w-3 h-3" />
                                              Preferred
                                            </Badge>
                                          </div>
                                        )}
                                      </div>
                                    )}
                                    <div className="p-4">
                                      <h3 className="text-lg font-semibold hover:text-primary line-clamp-2">
                                        {video.title}
                                      </h3>
                                      <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
                                        <span className="font-medium">
                                          {video.channel}
                                        </span>
                                        {video.video_count && (
                                          <span className="text-xs bg-muted px-2 py-1 rounded">
                                            {video.video_count} videos
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-sm mt-2 line-clamp-2">
                                        {video.description}
                                      </p>
                                      <div className="mt-3 inline-flex items-center gap-2 text-sm text-primary font-medium">
                                        Watch on YouTube
                                        <ExternalLink className="w-4 h-4" />
                                      </div>
                                    </div>
                                  </Card>
                                </motion.div>
                              );
                            },
                          )}
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-1 hidden lg:block" />
            <div className="lg:col-span-4">
              {selectedSkill && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ ...spring, delay: 0.3 }}
                  className="flex justify-end w-full pb-0"
                >
                  <Button
                    onClick={() =>
                      router.push(
                        `/skill-quiz/${encodeURIComponent(selectedSkill)}?from=/learning-resources`,
                      )
                    }
                    className="gap-2"
                  >
                    Ready to Take Quiz?
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </motion.div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
