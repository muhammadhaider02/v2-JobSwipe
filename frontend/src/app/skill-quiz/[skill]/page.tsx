'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Loader2, Trophy, AlertCircle, CheckCircle2, XCircle,
  ArrowLeft, ArrowRight, BookOpen, RotateCcw, Star,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';

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

// ─── Result Modal ────────────────────────────────────────────────────────────

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
    /* Backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Blurred overlay */}
      <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" />

      {/* Modal card */}
      <div
        className="relative z-10 w-full max-w-md rounded-2xl bg-card shadow-2xl animate-in fade-in zoom-in-95 duration-200"
        style={{
          borderTop:    '1px solid rgba(255,255,255,0.07)',
          borderRight:  '1px solid rgba(255,255,255,0.07)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          borderLeft:   passed
            ? '4px solid rgba(34,197,94,0.85)'
            : '4px solid rgba(239,68,68,0.85)',
        }}
      >

        <div className="p-6">
          {/* Icon + title */}
          <div className="flex items-start gap-4 mb-5">
            <div
              className={`shrink-0 flex items-center justify-center w-12 h-12 rounded-full
                ${passed ? 'bg-green-500/15' : 'bg-red-500/15'}`}
            >
              {passed
                ? <CheckCircle2 className="w-6 h-6 text-green-400" />
                : <XCircle className="w-6 h-6 text-red-400" />}
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

          {/* Score display */}
          <div className={`rounded-xl p-4 mb-5 ${passed ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
            <div className="flex items-end justify-between mb-2">
              <span className="text-sm text-muted-foreground">Your score</span>
              <span
                className={`text-3xl font-bold tabular-nums
                  ${passed ? 'text-green-400' : 'text-red-400'}`}
              >
                {evaluation.score_percentage}%
              </span>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-700 ease-out
                  ${passed ? 'bg-green-500' : 'bg-red-500'}`}
                style={{ width: `${evaluation.score_percentage}%` }}
              />
            </div>

            <p className="text-xs text-muted-foreground mt-2 text-right">
              {evaluation.earned_points} / {evaluation.total_points} points
            </p>
          </div>

          {/* Message */}
          <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
            {passed
              ? 'Great work! You\'ve demonstrated solid knowledge of this skill. Mark it as learned to update your profile.'
              : 'Go through the resources below, then come back and try again.'}
          </p>

          {/* Action buttons */}
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
      </div>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

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
  const [evaluation, setEvaluation] = useState<QuizEvaluation | null>(null);

  useEffect(() => {
    fetchQuiz();
  }, [skill]);

  const fetchQuiz = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:5000/skill-quiz/${encodeURIComponent(skill)}`
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
    setAnswers(prev => ({ ...prev, [questionId]: answer }));
  };

  const handleSubmit = async () => {
    if (!quiz) return;
    try {
      setSubmitting(true);
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();

      const response = await fetch('http://localhost:5000/quiz-submit', {
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
      setError(err instanceof Error ? err.message : 'Failed to submit quiz');
    } finally {
      setSubmitting(false);
    }
  };

  /** Mark skill as learned → update localStorage → go to recommendations */
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
    sessionStorage.setItem('currentLearningSkills', JSON.stringify([skill]));
    router.push('/learning-preferences');
  };

  const renderQuestion = (question: QuizQuestion, index: number) => {
    const feedback = evaluation?.feedback[question.id];

    return (
      <Card
        key={question.id}
        className={`bg-card border rounded-xl shadow-sm ${feedback
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
            {feedback && (
              feedback.correct
                ? <CheckCircle2 className="h-5 w-5 text-green-500 ml-auto shrink-0" />
                : <XCircle className="h-5 w-5 text-red-500 ml-auto shrink-0" />
            )}
          </CardTitle>
          {feedback && (
            <CardDescription>
              <span className="text-sm">
                {feedback.points_earned}/{feedback.points_possible} points
              </span>
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {question.question_type === 'mcq' && question.options && (
            <RadioGroup
              value={answers[question.id] || ''}
              onValueChange={(value: string) => handleAnswerChange(question.id, value)}
              disabled={!!evaluation}
            >
              {question.options.map((option, idx) => (
                <div key={idx} className="flex items-center space-x-2 mb-2">
                  <RadioGroupItem value={String(idx)} id={`${question.id}-${idx}`} />
                  <Label htmlFor={`${question.id}-${idx}`} className="cursor-pointer">
                    {option}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          )}

          {(question.question_type === 'short_answer' || question.question_type === 'coding') && (
            <Textarea
              value={answers[question.id] || ''}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
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
              <p className="text-sm text-muted-foreground">{feedback.explanation}</p>
              {feedback.note && (
                <p className="text-sm text-amber-600 mt-2">{feedback.note}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex-1 w-full bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <div className="flex flex-col items-center justify-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Generating your quiz...</p>
        </div>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────
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
            <Button onClick={fetchQuiz} className="mt-4">Try Again</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!quiz) return null;

  const allQuestionsAnswered = quiz.questions.every(q => answers[q.id]?.trim());

  return (
    <div className="flex-1 w-full flex flex-col relative bg-gradient-to-br from-background to-muted/20">

      {/* Result modal overlay */}
      {evaluation && (
        <ResultModal
          evaluation={evaluation}
          skill={skill}
          onRetake={handleRetake}
          onLearningResources={handleLearningResources}
          onMarkAsLearned={handleMarkAsLearned}
        />
      )}

      {/* Back button */}
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

          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Trophy className="w-8 h-8 text-primary" />
              <h1 className="text-4xl font-bold">Quiz: {skill}</h1>
            </div>
            <p className="text-muted-foreground">
              Test your knowledge and validate your skills
            </p>
          </div>

          {/* Questions */}
          <div className="space-y-6 mb-8">
            {quiz.questions.map((question, index) => renderQuestion(question, index))}
          </div>

          {/* Submit button — hidden once submitted */}
          {!evaluation && (
            <div className="flex flex-col items-end w-full pb-0 mt-8">
              <button
                onClick={handleSubmit}
                disabled={!allQuestionsAnswered || submitting}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg font-medium transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
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
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}