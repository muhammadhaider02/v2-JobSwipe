'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Loader2,
  Trophy,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  RotateCcw,
  Star,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { PageHeader } from '@/components/shared/page-header';

interface QuizQuestion {
  id: string;
  question_type: string;
  question: string;
  options?: string[];
  explanation?: string;
  difficulty: string;
}

interface Quiz {
  id: string;
  skill: string;
  questions: QuizQuestion[];
  created_at: string;
  total_points: number;
}

interface QuizResponse {
  quiz: Quiz;
  status: string;
  cached: boolean;
}

interface QuizEvaluation {
  earned_points: number;
  total_points: number;
  score_percentage: number;
  passed: boolean;
  feedback: Record<string, any>;
}

const spring = { type: 'spring' as const, stiffness: 100, damping: 20 };

function ResultModal({
  evaluation,
  skill,
  onRetake,
  onLearningResources,
  onMarkAsLearned,
}: {
  evaluation: QuizEvaluation;
  skill: string;
  onRetake: () => void;
  onLearningResources: () => void;
  onMarkAsLearned: () => void;
}) {
  const passed = evaluation.passed;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="absolute inset-0 bg-background/70 backdrop-blur-sm"
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={spring}
        className={`relative z-10 w-full max-w-md rounded-2xl bg-card shadow-2xl border-l-4 border ${
          passed
            ? 'border-l-green-500 border-border'
            : 'border-l-red-500 border-border'
        }`}
      >
        <div className="p-6">
          <div className="flex items-start gap-4 mb-5">
            <div
              className={`shrink-0 flex items-center justify-center w-12 h-12 rounded-full ${
                passed ? 'bg-green-500/15' : 'bg-red-500/15'
              }`}
            >
              {passed ? (
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              ) : (
                <XCircle className="w-6 h-6 text-red-500" />
              )}
            </div>

            <div>
              <h2 className="text-xl font-bold leading-tight">
                {passed ? 'You Passed!' : 'Room to Grow'}
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                {skill} Quiz Results
              </p>
            </div>
          </div>

          <div
            className={`rounded-xl p-4 mb-5 ${
              passed ? 'bg-green-500/10' : 'bg-red-500/10'
            }`}
          >
            <div className="flex items-end justify-between mb-2">
              <span className="text-sm text-muted-foreground">
                Your score
              </span>
              <span
                className={`text-3xl font-bold tabular-nums ${
                  passed ? 'text-green-500' : 'text-red-500'
                }`}
              >
                {evaluation.score_percentage}%
              </span>
            </div>

            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${evaluation.score_percentage}%` }}
                transition={{ ...spring, delay: 0.3 }}
                className={`h-2 rounded-full ${
                  passed ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
            </div>

            <p className="text-xs text-muted-foreground mt-2 text-right">
              {evaluation.earned_points} / {evaluation.total_points}{' '}
              points
            </p>
          </div>

          <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
            {passed
              ? "Great work! You've demonstrated solid knowledge of this skill. Mark it as learned to update your profile."
              : 'Go through the resources below then come back and try again.'}
          </p>

          <div className="flex flex-col gap-2">
            {passed ? (
              <Button
                onClick={onMarkAsLearned}
                className="w-full bg-green-600 hover:bg-green-700 text-white gap-2"
              >
                <Star className="w-4 h-4" />
                Mark as Learned
              </Button>
            ) : (
              <>
                <Button
                  onClick={onLearningResources}
                  className="w-full gap-2"
                >
                  <BookOpen className="w-4 h-4" />
                  Learning Resources
                </Button>
                <Button
                  variant="outline"
                  onClick={onRetake}
                  className="w-full gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  Retake Quiz
                </Button>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function SkillQuizPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const skill = decodeURIComponent(params.skill as string);

  const referrer = searchParams.get('from') || '/recommendations';

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [evaluation, setEvaluation] = useState<QuizEvaluation | null>(
    null,
  );

  useEffect(() => {
    fetchQuiz();
  }, [skill]);

  const fetchQuiz = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/skill-quiz/${encodeURIComponent(skill)}`,
      );
      if (!response.ok) throw new Error('Failed to fetch quiz');
      const data: QuizResponse = await response.json();
      setQuiz(data.quiz);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (questionId: string, answer: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: answer }));
  };

  const handleSubmit = async () => {
    if (!quiz) return;
    try {
      setSubmitting(true);
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      const response = await fetch('/api/quiz-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quiz_id: quiz.id,
          answers,
          user_id: user?.id,
        }),
      });

      if (!response.ok) throw new Error('Failed to submit quiz');

      const data = await response.json();
      setEvaluation({
        earned_points: data.earned_points,
        total_points: data.total_points,
        score_percentage: data.score_percentage,
        passed: data.passed,
        feedback: data.feedback,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to submit quiz',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleMarkAsLearned = () => {
    try {
      const stored = localStorage.getItem('learnedSkills');
      const existing: string[] = stored ? JSON.parse(stored) : [];
      const normalized = skill.toLowerCase();
      if (!existing.includes(normalized)) {
        existing.push(normalized);
        localStorage.setItem('learnedSkills', JSON.stringify(existing));
      }
    } catch (e) {
      console.error('Failed to persist learned skill:', e);
    }
    router.push('/recommendations');
  };

  const handleRetake = () => {
    setEvaluation(null);
    setAnswers({});
    fetchQuiz();
  };

  const handleLearningResources = () => {
    sessionStorage.setItem(
      'currentLearningSkills',
      JSON.stringify([skill]),
    );
    router.push('/learning-preferences');
  };

  const renderQuestion = (question: QuizQuestion, index: number) => {
    const feedback = evaluation?.feedback[question.id];

    return (
      <motion.div
        key={question.id}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: index * 0.08 }}
      >
        <Card
          className={`bg-card border rounded-xl shadow-sm ${
            feedback
              ? feedback.correct
                ? 'border-green-500/50'
                : 'border-red-500/50'
              : ''
          }`}
        >
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <span className="text-primary">Q{index + 1}.</span>
              {question.question}
              {feedback &&
                (feedback.correct ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 ml-auto shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 ml-auto shrink-0" />
                ))}
            </CardTitle>
            {feedback && (
              <CardDescription>
                <span className="text-sm">
                  {feedback.points_earned}/{feedback.points_possible}{' '}
                  points
                </span>
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {question.question_type === 'mcq' && question.options && (
              <RadioGroup
                value={answers[question.id] || ''}
                onValueChange={(value: string) =>
                  handleAnswerChange(question.id, value)
                }
                disabled={!!evaluation}
              >
                {question.options.map((option, idx) => (
                  <div
                    key={idx}
                    className="flex items-center space-x-2 mb-2"
                  >
                    <RadioGroupItem
                      value={String(idx)}
                      id={`${question.id}-${idx}`}
                    />
                    <Label
                      htmlFor={`${question.id}-${idx}`}
                      className="cursor-pointer"
                    >
                      {option}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            )}

            {(question.question_type === 'short_answer' ||
              question.question_type === 'coding') && (
              <Textarea
                value={answers[question.id] || ''}
                onChange={(
                  e: React.ChangeEvent<HTMLTextAreaElement>,
                ) =>
                  handleAnswerChange(question.id, e.target.value)
                }
                placeholder={
                  question.question_type === 'coding'
                    ? 'Write your code here...'
                    : 'Type your answer here...'
                }
                disabled={!!evaluation}
                className="font-mono"
                rows={question.question_type === 'coding' ? 8 : 4}
              />
            )}

            {feedback?.explanation && (
              <div className="mt-4 p-3 bg-muted rounded-lg">
                <p className="text-sm font-medium mb-1">Explanation:</p>
                <p className="text-sm text-muted-foreground">
                  {feedback.explanation}
                </p>
                {feedback.note && (
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                    {feedback.note}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex flex-col">
        <div className="flex-1 w-full pb-8 pt-0 px-4">
          <div className="max-w-3xl mx-auto mt-0 lg:mt-2 animate-pulse">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-11 h-11 rounded-xl bg-muted" />
              <div>
                <div className="h-6 w-48 bg-muted rounded mb-1" />
                <div className="h-4 w-64 bg-muted rounded" />
              </div>
            </div>
            <div className="space-y-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader>
                    <div className="h-5 w-16 bg-muted rounded mb-2" />
                    <div className="h-5 w-full bg-muted rounded" />
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {Array.from({ length: 4 }).map((_, j) => (
                        <div
                          key={j}
                          className="flex items-center gap-3"
                        >
                          <div className="w-4 h-4 bg-muted rounded-full" />
                          <div className="h-4 bg-muted rounded flex-1" />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <Card className="border-destructive max-w-md">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p>{error}</p>
            <Button onClick={fetchQuiz} className="mt-4">
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!quiz) return null;

  const allQuestionsAnswered = quiz.questions.every(
    (q) => answers[q.id]?.trim(),
  );

  return (
    <div className="flex-1 w-full flex flex-col relative bg-gradient-to-br from-background to-muted/20">
      <AnimatePresence>
        {evaluation && (
          <ResultModal
            evaluation={evaluation}
            skill={skill}
            onRetake={handleRetake}
            onLearningResources={handleLearningResources}
            onMarkAsLearned={handleMarkAsLearned}
          />
        )}
      </AnimatePresence>

      <div className="absolute top-4 left-6 z-10">
        <button
          onClick={() => router.push(referrer)}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
      </div>

      <div className="flex-1 w-full pb-8 pt-0 px-4">
        <div className="max-w-6xl mx-auto mt-0 lg:mt-2">
          <PageHeader
            icon={Trophy}
            title={`Quiz: ${skill}`}
            subtitle="Test your knowledge and validate your skills"
          />

          <div className="space-y-6 mb-8">
            {quiz.questions.map((question, index) =>
              renderQuestion(question, index),
            )}
          </div>

          {!evaluation && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ ...spring, delay: 0.3 }}
              className="flex flex-col items-end w-full pb-0 mt-8"
            >
              <Button
                onClick={handleSubmit}
                disabled={!allQuestionsAnswered || submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Evaluating...
                  </>
                ) : (
                  <>
                    Submit Quiz
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </Button>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
