"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  BookOpen,
  Clock,
  Target,
  Youtube,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  CheckCircle2
} from "lucide-react";
import Link from "next/link";

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

const KNOWLEDGE_LEVELS = [
  {
    id: "beginner",
    label: "Beginner",
    description: "New to this topic",
    icon: "🌱",
  },
  {
    id: "intermediate",
    label: "Intermediate",
    description: "Some experience",
    icon: "🌿",
  },
  {
    id: "advanced",
    label: "Advanced",
    description: "Deep dive content",
    icon: "🌳",
  },
];

const TIME_COMMITMENTS = [
  {
    id: "short",
    label: "Quick Learning",
    description: "1-2 hours",
    duration: "Short videos & articles",
    icon: "⚡",
  },
  {
    id: "medium",
    label: "Moderate Pace",
    description: "3-5 hours",
    duration: "Mini courses & tutorials",
    icon: "🎯",
  },
  {
    id: "long",
    label: "Deep Dive",
    description: "5+ hours",
    duration: "Full courses & comprehensive guides",
    icon: "🚀",
  },
];

const POPULAR_CHANNELS = [
  { name: "freeCodeCamp.org", category: "General Programming" },
  { name: "Traversy Media", category: "Web Development" },
  { name: "Corey Schafer", category: "Python & Data Science" },
  { name: "Programming with Mosh", category: "General Programming" },
  { name: "The Net Ninja", category: "Web Development" },
  { name: "CS50", category: "Computer Science" },
  { name: "Fireship", category: "Quick Tutorials" },
  { name: "Academind", category: "Web Development" },
  { name: "Sentdex", category: "Python & AI" },
  { name: "Tech With Tim", category: "Programming" },
];

export default function LearningPreferencesPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const missingSkills = searchParams.get("skills");

  const [skills, setSkills] = useState<string[]>([]);
  const [preferences, setPreferences] = useState<LearningPreferences>({
    knowledgeLevel: "beginner",
    timeCommitment: "medium",
    preferredChannels: [],
    contentTypes: {
      articles: true,
      videos: true,
      playlists: true,
    },
  });

  useEffect(() => {
    if (missingSkills) {
      try {
        const parsedSkills = JSON.parse(decodeURIComponent(missingSkills));
        setSkills(parsedSkills);
      } catch (e) {
        console.error("Error parsing skills:", e);
      }
    }
  }, [missingSkills]);

  const toggleChannel = (channelName: string) => {
    setPreferences((prev) => ({
      ...prev,
      preferredChannels: prev.preferredChannels.includes(channelName)
        ? prev.preferredChannels.filter((c) => c !== channelName)
        : [...prev.preferredChannels, channelName],
    }));
  };

  const handleContinue = () => {
    // Store preferences in session storage for use in learning resources page
    sessionStorage.setItem("learningPreferences", JSON.stringify(preferences));

    // Navigate to learning resources with skills
    const skillsParam = encodeURIComponent(JSON.stringify(skills));
    router.push(`/learning-resources?skills=${skillsParam}`);
  };

  if (!missingSkills || skills.length === 0) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <Card className="p-8 max-w-md text-center">
          <BookOpen className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">No Skills Selected</h2>
          <p className="text-muted-foreground mb-4">
            Please select skills from the recommendations page first.
          </p>
          <Button onClick={() => router.push("/recommendations")}>
            Go to Recommendations
          </Button>
        </Card>
      </div>
    );
  }

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
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Sparkles className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">
                Customize Your Learning Experience
              </h1>
            </div>
            <p className="text-muted-foreground">
              We'll find the best resources tailored to your goals and preferences
            </p>
          </div>

          {/* Selected Skills */}
          <Card className="p-6 mb-8 bg-card border rounded-xl shadow-sm">
            <h3 className="text-sm font-semibold text-muted-foreground mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-primary" />
              Skills You'll Learn ({skills.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {skills.map((skill, idx) => (
                <Badge
                  key={idx}
                  className="px-3 py-1 bg-primary/10 text-primary"
                >
                  {skill}
                </Badge>
              ))}
            </div>
          </Card>

          {/* Knowledge Level Selection */}
          <Card className="p-6 mb-6 bg-card border rounded-xl shadow-sm">
            <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
              <Target className="w-5 h-5 text-primary" />
              Your Knowledge Level
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              Help us find content that matches your current expertise
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {KNOWLEDGE_LEVELS.map((level) => (
                <button
                  key={level.id}
                  onClick={() =>
                    setPreferences((prev) => ({
                      ...prev,
                      knowledgeLevel: level.id as any,
                    }))
                  }
                  className={`p-4 rounded-xl border-2 transition-all text-left ${preferences.knowledgeLevel === level.id
                    ? "border-primary bg-primary/10 shadow-md"
                    : "border-border hover:border-primary/50 bg-card"
                    }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-3xl">{level.icon}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{level.label}</h3>
                        {preferences.knowledgeLevel === level.id && (
                          <CheckCircle2 className="w-4 h-4 text-primary" />
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{level.description}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* Time Commitment */}
          <Card className="p-6 mb-6 bg-card border rounded-xl shadow-sm">
            <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              Time Commitment
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              How much time can you dedicate to learning?
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {TIME_COMMITMENTS.map((time) => (
                <button
                  key={time.id}
                  onClick={() =>
                    setPreferences((prev) => ({
                      ...prev,
                      timeCommitment: time.id as any,
                    }))
                  }
                  className={`p-4 rounded-xl border-2 transition-all text-left ${preferences.timeCommitment === time.id
                    ? "border-primary bg-primary/10 shadow-md"
                    : "border-border hover:border-primary/50 bg-card"
                    }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-3xl">{time.icon}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{time.label}</h3>
                        {preferences.timeCommitment === time.id && (
                          <CheckCircle2 className="w-4 h-4 text-primary" />
                        )}
                      </div>
                      <p className="text-sm text-primary font-medium">{time.description}</p>
                      <p className="text-xs text-muted-foreground mt-1">{time.duration}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* Content Types */}
          <Card className="p-6 mb-6 bg-card border rounded-xl shadow-sm">
            <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary" />
              Content Preferences
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              What types of learning materials do you prefer?
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() =>
                  setPreferences((prev) => ({
                    ...prev,
                    contentTypes: {
                      ...prev.contentTypes,
                      articles: !prev.contentTypes.articles,
                    },
                  }))
                }
                className={`p-4 rounded-xl border-2 transition-all ${preferences.contentTypes.articles
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/50 bg-card"
                  }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${preferences.contentTypes.articles ? "bg-primary/20" : "bg-muted"}`}>
                    <BookOpen className={`w-5 h-5 ${preferences.contentTypes.articles ? "text-primary" : "text-muted-foreground"}`} />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="font-semibold">Articles & Docs</h3>
                    <p className="text-xs text-muted-foreground">Written tutorials</p>
                  </div>
                  {preferences.contentTypes.articles && (
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                  )}
                </div>
              </button>

              <button
                onClick={() =>
                  setPreferences((prev) => ({
                    ...prev,
                    contentTypes: {
                      ...prev.contentTypes,
                      videos: !prev.contentTypes.videos,
                    },
                  }))
                }
                className={`p-4 rounded-xl border-2 transition-all ${preferences.contentTypes.videos
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/50 bg-card"
                  }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${preferences.contentTypes.videos ? "bg-primary/20" : "bg-muted"}`}>
                    <Youtube className={`w-5 h-5 ${preferences.contentTypes.videos ? "text-primary" : "text-muted-foreground"}`} />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="font-semibold">Videos</h3>
                    <p className="text-xs text-muted-foreground">Single tutorials</p>
                  </div>
                  {preferences.contentTypes.videos && (
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                  )}
                </div>
              </button>

              <button
                onClick={() =>
                  setPreferences((prev) => ({
                    ...prev,
                    contentTypes: {
                      ...prev.contentTypes,
                      playlists: !prev.contentTypes.playlists,
                    },
                  }))
                }
                className={`p-4 rounded-xl border-2 transition-all ${preferences.contentTypes.playlists
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/50 bg-card"
                  }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${preferences.contentTypes.playlists ? "bg-primary/20" : "bg-muted"}`}>
                    <Youtube className={`w-5 h-5 ${preferences.contentTypes.playlists ? "text-primary" : "text-muted-foreground"}`} />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="font-semibold">Playlists</h3>
                    <p className="text-xs text-muted-foreground">Full courses</p>
                  </div>
                  {preferences.contentTypes.playlists && (
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                  )}
                </div>
              </button>
            </div>
          </Card>

          {/* Preferred Channels (Optional) */}
          <Card className="p-6 mb-4 bg-card border rounded-xl shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Youtube className="w-5 h-5 text-red-600" />
              <h2 className="text-xl font-bold">Preferred YouTube Channels</h2>
              <Badge variant="secondary" className="text-xs">Optional</Badge>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Select channels you'd like to prioritize in your results
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {POPULAR_CHANNELS.map((channel) => (
                <button
                  key={channel.name}
                  onClick={() => toggleChannel(channel.name)}
                  className={`p-3 rounded-lg border text-left transition-all ${preferences.preferredChannels.includes(channel.name)
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/50 bg-card"
                    }`}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {channel.name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{channel.category}</p>
                    </div>
                    {preferences.preferredChannels.includes(channel.name) && (
                      <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* Continue Button */}
          <div className="flex justify-end w-full pb-0">
            <button
              onClick={handleContinue}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md"
            >
              Continue to Resources
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
