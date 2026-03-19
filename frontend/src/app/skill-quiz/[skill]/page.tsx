'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Trophy, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
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

export default function SkillQuizPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const skill = decodeURIComponent(params.skill as string);

  // Get the referrer from URL params, default to recommendations if not provided
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
      const response = await fetch(`http://localhost:5000/skill-quiz/${encodeURIComponent(skill)}`);

      if (!response.ok) {
        throw new Error('Failed to fetch quiz');
      }

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
      
      // Get user ID from Supabase auth
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      
      const response = await fetch('http://localhost:5000/quiz-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quiz_id: quiz.id,
          answers: answers,
          user_id: user?.id // Include user ID for saving quiz scores
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit quiz');
      }

      const data = await response.json();
      setEvaluation(data.evaluation);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit quiz');
    } finally {
      setSubmitting(false);
    }
  };

  const renderQuestion = (question: QuizQuestion, index: number) => {
    const feedback = evaluation?.feedback[question.id];

    return (
      <Card key={question.id} className={`bg-card border rounded-xl shadow-sm ${feedback ? (feedback.correct ? 'border-green-500' : 'border-red-500') : ''
        }`}>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <span className="text-primary">Q{index + 1}.</span>
            {question.question}
            {feedback && (
              feedback.correct ?
                <CheckCircle2 className="h-5 w-5 text-green-500 ml-auto" /> :
                <XCircle className="h-5 w-5 text-red-500 ml-auto" />
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
              onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              placeholder={question.question_type === 'coding' ? 'Write your code here...' : 'Type your answer here...'}
              disabled={!!evaluation}
              className="font-mono"
              rows={question.question_type === 'coding' ? 8 : 4}
            />
          )}

          {feedback && feedback.explanation && (
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
        <div className="flex flex-col items-center justify-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Generating your quiz...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 flex items-center justify-center">
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

  if (!quiz) {
    return null;
  }

  const allQuestionsAnswered = quiz.questions.every(q => answers[q.id]?.trim());

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 py-12">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Trophy className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold">Quiz: {skill}</h1>
          </div>
          <p className="text-muted-foreground">
            {evaluation ? 'Review your results' : 'Test your knowledge and validate your skills'}
          </p>
        </div>

        {/* Results Summary */}
        {evaluation && (
          <Card className={`mb-8 bg-card border rounded-xl shadow-sm ${evaluation.passed ? 'border-green-500' : 'border-red-500'
            }`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className={`h-6 w-6 ${evaluation.passed ? 'text-green-600' : 'text-red-600'}`} />
                {evaluation.passed ? 'Congratulations! You Passed!' : 'Keep Learning!'}
              </CardTitle>
              <CardDescription>
                Your Score: {evaluation.score_percentage}%
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-2xl font-bold">
                    {evaluation.earned_points} / {evaluation.total_points} points
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {evaluation.passed ? 'You have demonstrated proficiency in this skill!' : 'Review the feedback below and try again.'}
                  </p>
                </div>
                {!evaluation.passed && (
                  <Button onClick={() => {
                    setEvaluation(null);
                    setAnswers({});
                    fetchQuiz();
                  }}>
                    Retake Quiz
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Questions */}
        <div className="space-y-6 mb-8">
          {quiz.questions.map((question, index) => renderQuestion(question, index))}
        </div>

        {/* Submit and Navigation Buttons */}
        {!evaluation && (
          <Card className="bg-card border rounded-xl shadow-sm">
            <CardContent className="pt-6">
              <div className="flex gap-4">
                <Button onClick={() => router.push(referrer)} variant="outline" size="lg" className="flex-1">
                  Back
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={!allQuestionsAnswered || submitting}
                  className="flex-1"
                  size="lg"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Evaluating...
                    </>
                  ) : (
                    'Submit Quiz'
                  )}
                </Button>
              </div>
              {!allQuestionsAnswered && (
                <p className="text-sm text-muted-foreground text-center mt-2">
                  Please answer all questions before submitting
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Navigation for completed quiz */}
        {evaluation && (
          <div className="flex gap-4">
            <Button onClick={() => router.push(referrer)} variant="outline" size="lg" className="flex-1">
              Back
            </Button>
            {evaluation.passed && (
              <Button onClick={() => router.push('/recommendations')} size="lg" className="flex-1">
                View More Skills
              </Button>
            )}
          </div>
        )}      </div>
    </div>
  );
}