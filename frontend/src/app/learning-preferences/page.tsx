'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  BookOpen,
  Clock,
  Target,
  Youtube,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Sprout,
  Leaf,
  TreeDeciduous,
  Zap,
  Rocket,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';
import { SelectionCard } from '@/components/shared/selection-card';

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

const KNOWLEDGE_LEVELS: {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    id: 'beginner',
    label: 'Beginner',
    description: 'New to this topic',
    icon: Sprout,
  },
  {
    id: 'intermediate',
    label: 'Intermediate',
    description: 'Some experience',
    icon: Leaf,
  },
  {
    id: 'advanced',
    label: 'Advanced',
    description: 'Deep dive content',
    icon: TreeDeciduous,
  },
];

const TIME_COMMITMENTS: {
  id: string;
  label: string;
  description: string;
  duration: string;
  icon: LucideIcon;
}[] = [
  {
    id: 'short',
    label: 'Quick Learning',
    description: '1-2 hours',
    duration: 'Short videos and articles',
    icon: Zap,
  },
  {
    id: 'medium',
    label: 'Moderate Pace',
    description: '3-5 hours',
    duration: 'Mini courses and tutorials',
    icon: Target,
  },
  {
    id: 'long',
    label: 'Deep Dive',
    description: '5+ hours',
    duration: 'Full courses and comprehensive guides',
    icon: Rocket,
  },
];

const POPULAR_CHANNELS = [
  { name: 'freeCodeCamp.org', category: 'General Programming' },
  { name: 'Traversy Media', category: 'Web Development' },
  { name: 'Corey Schafer', category: 'Python and Data Science' },
  { name: 'Programming with Mosh', category: 'General Programming' },
  { name: 'The Net Ninja', category: 'Web Development' },
  { name: 'CS50', category: 'Computer Science' },
  { name: 'Fireship', category: 'Quick Tutorials' },
  { name: 'Academind', category: 'Web Development' },
  { name: 'Sentdex', category: 'Python and AI' },
  { name: 'Tech With Tim', category: 'Programming' },
];

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

export default function LearningPreferencesPage() {
  const router = useRouter();

  const [skills, setSkills] = useState<string[]>([]);
  const [skillsLoaded, setSkillsLoaded] = useState(false);
  const [preferences, setPreferences] = useState<LearningPreferences>({
    knowledgeLevel: 'beginner',
    timeCommitment: 'medium',
    preferredChannels: [],
    contentTypes: {
      articles: true,
      videos: true,
      playlists: true,
    },
  });

  useEffect(() => {
    const stored = sessionStorage.getItem('currentLearningSkills');
    if (stored) {
      try {
        setSkills(JSON.parse(stored));
      } catch (e) {
        console.error('Error parsing skills from sessionStorage:', e);
      }
    }
    setSkillsLoaded(true);
  }, []);

  const toggleChannel = (channelName: string) => {
    setPreferences((prev) => ({
      ...prev,
      preferredChannels: prev.preferredChannels.includes(channelName)
        ? prev.preferredChannels.filter((c) => c !== channelName)
        : [...prev.preferredChannels, channelName],
    }));
  };

  const handleContinue = () => {
    sessionStorage.setItem(
      'learningPreferences',
      JSON.stringify(preferences),
    );
    sessionStorage.setItem(
      'learningResourcesSkills',
      JSON.stringify(skills),
    );
    router.push('/learning-resources');
  };

  if (skillsLoaded && skills.length === 0) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <EmptyState
          icon={BookOpen}
          title="No Skills Selected"
          description="Please select skills from the recommendations page first."
          action={{ label: 'Go to Recommendations', href: '/recommendations' }}
        />
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
          <PageHeader
            icon={Sparkles}
            title="Customize Your Learning"
            subtitle="We'll find the best resources tailored to your goals and preferences"
          />

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.08 }}
          >
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
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.16 }}
          >
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
                  <SelectionCard
                    key={level.id}
                    selected={preferences.knowledgeLevel === level.id}
                    onClick={() =>
                      setPreferences((prev) => ({
                        ...prev,
                        knowledgeLevel: level.id as any,
                      }))
                    }
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 rounded-lg bg-primary/10">
                        <level.icon className="w-5 h-5 text-primary" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold">{level.label}</h3>
                        <p className="text-sm text-muted-foreground">
                          {level.description}
                        </p>
                      </div>
                    </div>
                  </SelectionCard>
                ))}
              </div>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.24 }}
          >
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
                  <SelectionCard
                    key={time.id}
                    selected={preferences.timeCommitment === time.id}
                    onClick={() =>
                      setPreferences((prev) => ({
                        ...prev,
                        timeCommitment: time.id as any,
                      }))
                    }
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 rounded-lg bg-primary/10">
                        <time.icon className="w-5 h-5 text-primary" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold">{time.label}</h3>
                        <p className="text-sm text-primary font-medium">
                          {time.description}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {time.duration}
                        </p>
                      </div>
                    </div>
                  </SelectionCard>
                ))}
              </div>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.32 }}
          >
            <Card className="p-6 mb-6 bg-card border rounded-xl shadow-sm">
              <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary" />
                Content Preferences
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                What types of learning materials do you prefer?
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {([
                  {
                    key: 'articles' as const,
                    label: 'Articles and Docs',
                    sub: 'Written tutorials',
                    icon: BookOpen,
                  },
                  {
                    key: 'videos' as const,
                    label: 'Videos',
                    sub: 'Single tutorials',
                    icon: Youtube,
                  },
                  {
                    key: 'playlists' as const,
                    label: 'Playlists',
                    sub: 'Full courses',
                    icon: Youtube,
                  },
                ] as const).map((ct) => (
                  <SelectionCard
                    key={ct.key}
                    selected={preferences.contentTypes[ct.key]}
                    onClick={() =>
                      setPreferences((prev) => ({
                        ...prev,
                        contentTypes: {
                          ...prev.contentTypes,
                          [ct.key]: !prev.contentTypes[ct.key],
                        },
                      }))
                    }
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2 rounded-lg ${preferences.contentTypes[ct.key] ? 'bg-primary/20' : 'bg-muted'}`}
                      >
                        <ct.icon
                          className={`w-5 h-5 ${preferences.contentTypes[ct.key] ? 'text-primary' : 'text-muted-foreground'}`}
                        />
                      </div>
                      <div className="flex-1 text-left">
                        <h3 className="font-semibold">{ct.label}</h3>
                        <p className="text-xs text-muted-foreground">
                          {ct.sub}
                        </p>
                      </div>
                    </div>
                  </SelectionCard>
                ))}
              </div>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring, delay: 0.4 }}
          >
            <Card className="p-6 mb-4 bg-card border rounded-xl shadow-sm">
              <div className="flex items-center gap-2 mb-2">
                <Youtube className="w-5 h-5 text-red-600" />
                <h2 className="text-xl font-bold">
                  Preferred YouTube Channels
                </h2>
                <Badge variant="secondary" className="text-xs">
                  Optional
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-4">
                Select channels you'd like to prioritize in your results
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {POPULAR_CHANNELS.map((channel) => (
                  <SelectionCard
                    key={channel.name}
                    selected={preferences.preferredChannels.includes(
                      channel.name,
                    )}
                    onClick={() => toggleChannel(channel.name)}
                    className="p-3"
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {channel.name}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">
                          {channel.category}
                        </p>
                      </div>
                    </div>
                  </SelectionCard>
                ))}
              </div>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...spring, delay: 0.48 }}
            className="flex justify-end w-full pb-0"
          >
            <Button onClick={handleContinue}>
              Continue to Resources
              <ArrowRight className="w-4 h-4" />
            </Button>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
