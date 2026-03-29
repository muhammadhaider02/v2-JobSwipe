"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, BookOpen, Youtube, Loader2, Search, Filter, ArrowLeft, ArrowRight } from "lucide-react";

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
  knowledgeLevel: "beginner" | "intermediate" | "advanced";
  timeCommitment: "short" | "medium" | "long";
  preferredChannels: string[];
  contentTypes: {
    articles: boolean;
    videos: boolean;
    playlists: boolean;
  };
};

export default function LearningResourcesPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const missingSkills = searchParams.get("skills");

  const [resources, setResources] = useState<SkillResources[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<LearningPreferences | null>(null);

  useEffect(() => {
    // Load preferences from session storage
    const missingSkills = searchParams.get("skills");
    const prefsParam = searchParams.get("preferences");

    // Try to get skills from URL first, then from sessionStorage
    let skills: string[] | null = null;

    if (missingSkills) {
      skills = JSON.parse(decodeURIComponent(missingSkills));
      // Store in sessionStorage
      sessionStorage.setItem('learningResourcesSkills', JSON.stringify(skills));
    } else {
      // Try to restore from sessionStorage
      const stored = sessionStorage.getItem('learningResourcesSkills');
      if (stored) {
        skills = JSON.parse(stored);
      }
    }

    // Handle preferences
    if (prefsParam) {
      const prefs = JSON.parse(decodeURIComponent(prefsParam));
      setPreferences(prefs);
      sessionStorage.setItem('learningPreferences', JSON.stringify(prefs));
    } else {
      // Try to restore preferences from sessionStorage
      const storedPrefs = sessionStorage.getItem('learningPreferences');
      if (storedPrefs) {
        setPreferences(JSON.parse(storedPrefs));
      }
    }

    // Check if we have cached resources
    const cachedResources = sessionStorage.getItem('learningResources');
    if (cachedResources && skills) {
      const cached = JSON.parse(cachedResources);

      // Check if cached skills match current skills
      const cachedSkills = cached.skills || [];
      const skillsMatch =
        skills.length === cachedSkills.length &&
        skills.every((skill: string) => cachedSkills.includes(skill));

      if (skillsMatch) {
        // Use cached data if skills match
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
  }, [searchParams]);

  const fetchLearningResources = async (skills: string[]) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:5000/learning-resources", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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

      const firstSkill = data.resources.length > 0 ? data.resources[0].skill : null;
      if (firstSkill) {
        setSelectedSkill(firstSkill);
      }

      // Cache resources, selected skill, AND the skills array
      sessionStorage.setItem('learningResources', JSON.stringify({
        skills: skills,
        resources: data.resources,
        selectedSkill: firstSkill
      }));
    } catch (err) {
      console.error("Error fetching learning resources:", err);
      setError(err instanceof Error ? err.message : "Failed to load resources");
    } finally {
      setLoading(false);
    }
  };

  // Update cache when selected skill changes
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

  // Filter resources based on preferences
  const filterResourcesByPreferences = (resource: SkillResources): SkillResources => {
    if (!preferences) return resource;

    let filteredGoogleResults = [...resource.google_results];
    let filteredYoutubeResults = [...resource.youtube_playlists];

    // Filter by content type preferences
    if (!preferences.contentTypes.articles) {
      filteredGoogleResults = [];
    }

    if (!preferences.contentTypes.videos && !preferences.contentTypes.playlists) {
      filteredYoutubeResults = [];
    } else if (!preferences.contentTypes.playlists) {
      // Only show videos (filter out playlists with high video count)
      filteredYoutubeResults = filteredYoutubeResults.filter(
        video => !video.video_count || video.video_count <= 3
      );
    } else if (!preferences.contentTypes.videos) {
      // Only show playlists
      filteredYoutubeResults = filteredYoutubeResults.filter(
        video => video.video_count && video.video_count > 3
      );
    }

    // Filter YouTube results by preferred channels
    if (preferences.preferredChannels.length > 0) {
      const preferredVideos = filteredYoutubeResults.filter(video =>
        preferences.preferredChannels.some(channel =>
          video.channel.toLowerCase().includes(channel.toLowerCase())
        )
      );

      // If we have preferred channel matches, prioritize them
      if (preferredVideos.length > 0) {
        const otherVideos = filteredYoutubeResults.filter(video =>
          !preferences.preferredChannels.some(channel =>
            video.channel.toLowerCase().includes(channel.toLowerCase())
          )
        );
        // Show preferred channels first, then others
        filteredYoutubeResults = [...preferredVideos, ...otherVideos];
      }
    }

    // Filter by time commitment (based on video count for playlists)
    if (preferences.timeCommitment === "short") {
      // Prefer shorter content
      filteredGoogleResults = filteredGoogleResults.slice(0, 5);
      filteredYoutubeResults = filteredYoutubeResults
        .filter(video => !video.video_count || video.video_count <= 10)
        .slice(0, 3);
    } else if (preferences.timeCommitment === "medium") {
      filteredGoogleResults = filteredGoogleResults.slice(0, 7);
      filteredYoutubeResults = filteredYoutubeResults
        .filter(video => !video.video_count || video.video_count <= 30)
        .slice(0, 4);
    } else {
      // long - show comprehensive content
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
  const filteredResource = selectedResource ? filterResourcesByPreferences(selectedResource) : null;

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) return "bg-green-100 text-green-800";
    if (confidence >= 0.6) return "bg-yellow-100 text-yellow-800";
    return "bg-orange-100 text-orange-800";
  };

  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-lg text-muted-foreground">Finding the best learning resources for you...</p>
          <p className="text-sm text-muted-foreground mt-2">This may take a few moments</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <Card className="p-8 max-w-md">
          <div className="text-center">
            <div className="text-red-500 text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-semibold mb-2">Error Loading Resources</h2>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Button onClick={() => window.location.reload()}>Try Again</Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!loading && resources.length === 0) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <Card className="p-8 max-w-md text-center">
          <Search className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">No Skills Provided</h2>
          <p className="text-muted-foreground mb-4">
            Please select a role to view learning resources for missing skills.
          </p>
          <Button onClick={() => (window.location.href = "/recommendations")}>
            Go to Recommendations
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full flex flex-col relative bg-gradient-to-br from-background to-muted/20">
      <div className="absolute top-4 left-6 z-10">
        <button
          onClick={() => {
            const storedSkills = sessionStorage.getItem('learningResourcesSkills');
            if (storedSkills) {
              const skills = JSON.parse(storedSkills);
              const skillsParam = encodeURIComponent(JSON.stringify(skills));
              window.location.href = `/learning-preferences?skills=${skillsParam}`;
            } else {
              router.back();
            }
          }}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <BookOpen className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">
                Learning Resources
              </h1>
            </div>
            <p className="text-muted-foreground">
              Curated learning materials tailored to your preferences
            </p>

            {/* Show active filters */}
            {preferences && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Filter className="w-4 h-4 text-primary" />
                <span className="text-sm text-muted-foreground">Active filters:</span>
                <Badge variant="secondary" className="bg-primary/10 text-primary">
                  {preferences.knowledgeLevel.charAt(0).toUpperCase() + preferences.knowledgeLevel.slice(1)}
                </Badge>
                <Badge variant="secondary" className="bg-primary/10 text-primary">
                  {preferences.timeCommitment === "short" ? "Quick Learning" :
                    preferences.timeCommitment === "medium" ? "Moderate Pace" : "Deep Dive"}
                </Badge>
                {(preferences?.preferredChannels?.length ?? 0) > 0 && (
                  <Badge variant="secondary" className="bg-primary/10 text-primary">
                    {preferences.preferredChannels.length} Preferred Channels
                  </Badge>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-1">
              <Card className="p-4 sticky top-4 bg-card border rounded-xl shadow-sm">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-primary" />
                  Skills to Learn ({resources.length})
                </h3>
                <div className="space-y-2">
                  {resources.map((resource) => {
                    const filtered = filterResourcesByPreferences(resource);
                    const totalResources = filtered.google_results.length + filtered.youtube_playlists.length;

                    return (
                      <button
                        key={resource.skill}
                        onClick={() => setSelectedSkill(resource.skill)}
                        className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${selectedSkill === resource.skill
                          ? "bg-primary text-primary-foreground shadow-md"
                          : "bg-muted hover:bg-muted/80"
                          }`}
                      >
                        <div className="font-medium capitalize">{resource.skill}</div>
                        <div className="text-xs mt-1 opacity-80">
                          {totalResources} resources
                        </div>
                      </button>
                    );
                  })}
                </div>
              </Card>
            </div>

            <div className="lg:col-span-4">
              {filteredResource && (
                <div className="space-y-6">
                  <Card className="p-6 bg-card border rounded-xl shadow-sm">
                    <h2 className="text-3xl font-bold capitalize mb-2">
                      {filteredResource.skill}
                    </h2>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>
                        📊 Confidence: {(filteredResource.total_confidence * 100).toFixed(0)}%
                      </span>
                      <span>
                        📖 {filteredResource.google_results.length} Articles
                      </span>
                      <span>
                        🎥 {filteredResource.youtube_playlists.length} Videos
                      </span>
                    </div>
                  </Card>

                  {/* Articles Section */}
                  {filteredResource.google_results.length > 0 && (
                    <div>
                      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <BookOpen className="w-6 h-6 text-primary" />
                        Articles & Tutorials
                      </h3>
                      <div className="space-y-4">
                        {filteredResource.google_results.map((result, index) => (
                          <Card key={index} className="p-5 bg-card border rounded-xl shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1">
                                <a
                                  href={result.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-lg font-semibold text-primary hover:underline flex items-center gap-2"
                                >
                                  {result.title}
                                  <ExternalLink className="w-4 h-4" />
                                </a>
                                <p className="text-sm text-muted-foreground mt-1">{result.domain}</p>
                                <p className="text-sm mt-2 leading-relaxed">
                                  {result.snippet}
                                </p>
                              </div>
                              <Badge className={getConfidenceBadge(result.confidence)}>
                                {(result.confidence * 100).toFixed(0)}%
                              </Badge>
                            </div>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Videos Section */}
                  {filteredResource.youtube_playlists.length > 0 && (
                    <div>
                      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <Youtube className="w-6 h-6 text-red-600" />
                        Video Courses & Playlists
                        {(preferences?.preferredChannels?.length ?? 0) > 0 && (
                          <span className="text-sm text-muted-foreground font-normal">
                            (Prioritizing your preferred channels)
                          </span>
                        )}
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {filteredResource.youtube_playlists.map((video, index) => {
                          const isPreferred = preferences?.preferredChannels.some(channel =>
                            video.channel.toLowerCase().includes(channel.toLowerCase())
                          );

                          return (
                            <div
                              key={index}
                              onClick={() => window.open(video.url, '_blank', 'noopener,noreferrer')}
                              className="cursor-pointer"
                            >
                              <Card className={`overflow-hidden bg-card border rounded-xl shadow-sm hover:shadow-md transition-shadow ${isPreferred ? 'ring-2 ring-green-500' : ''
                                }`}>
                                {video.thumbnail_url && (
                                  <div className="relative h-48 bg-gray-200">
                                    <img
                                      src={video.thumbnail_url}
                                      alt={video.title}
                                      className="w-full h-full object-cover"
                                    />
                                    <div className="absolute top-2 right-2">
                                      <Badge className={getConfidenceBadge(video.confidence)}>
                                        {(video.confidence * 100).toFixed(0)}%
                                      </Badge>
                                    </div>
                                    {isPreferred && (
                                      <div className="absolute top-2 left-2">
                                        <Badge className="bg-green-600 text-white">
                                          ⭐ Preferred
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
                                    <span className="font-medium">{video.channel}</span>
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
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Navigation Buttons */}
          <div className="mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Empty space to align with sidebar */}
            <div className="lg:col-span-1 hidden lg:block"></div>

            {/* Buttons aligned with main content */}
            <div className="lg:col-span-4">
              {selectedSkill && (
                <div className="flex justify-end w-full pb-0">
                  <button
                    onClick={() => (window.location.href = `/skill-quiz/${encodeURIComponent(selectedSkill)}?from=/learning-resources`)}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md"
                  >
                    Ready to Take Quiz?
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
