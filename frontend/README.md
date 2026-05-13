<div align="center">

# JobSwipe Frontend

**AI-Powered Job Discovery with Swipe-Based UX**

[![Next.js](https://img.shields.io/badge/Next.js-15.5-000000?logo=next.js&logoColor=white)](https://nextjs.org)
[![React](https://img.shields.io/badge/React-19.1-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Supabase](https://img.shields.io/badge/Supabase-Auth-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com)

Swipe through AI-matched jobs, get tailored resumes and cover letters, take skill quizzes and access personalized learning resources.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Docker](#docker)

---

## Overview

The frontend is a Next.js 15 app using the App Router with Turbopack for development. Users onboard by uploading a resume, which the backend parses into a structured profile. From there they receive role recommendations, identify skill gaps, verify competencies through quizzes, swipe through AI-matched jobs and auto-apply with tailored application materials. All through a responsive, dark-themed UI built on the Tinder-style swipe interface.

Authentication is handled by Supabase Auth with SSR cookie-based sessions.

---

## Features

| Feature | Description |
|:---|:---|
| **Resume Onboarding** | Upload PDF/DOCX resume; AI extracts education, experience and skills into a structured profile |
| **Intelligent Job Matching** | Tinder-style swipe interface to accept or skip AI-matched jobs |
| **Resume Optimization** | Generate job-tailored resume PDFs with LaTeX typesetting |
| **Cover Letter Generation** | Templated cover letters customized per job description |
| **Skill Gap Analysis** | Visual breakdown of matched vs missing skills for each role |
| **Skill Assessment** | AI-generated MCQ and short-answer quizzes to validate skill proficiency |
| **Learning Resources** | Curated articles, videos and courses for skills you need to develop |
| **Application Tracking** | History of all jobs you've applied to with dates and links |
| **Dark Theme** | Full dark mode UI with `next-themes` |

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Framework | Next.js 15.5 (App Router, Turbopack) |
| Language | TypeScript 5 |
| UI | React 19, Tailwind CSS 4, Radix UI primitives |
| Auth | Supabase Auth (SSR with `@supabase/ssr`) |
| State | React Query (TanStack Query 5) |
| Icons | Lucide React |
| Skeleton Loaders | boneyard-js |
| Package Manager | pnpm |

---

## Prerequisites

- Node.js 22+
- pnpm 9+
- Running backend server (default `http://localhost:5000`)
- Supabase project with Auth enabled

---

## Getting Started

```bash
cd frontend
```

```bash
nvm install 22.19.0
nvm use 22.19.0
```

```bash
pnpm install
pnpm dev
```

Frontend runs at `http://localhost:3000`.

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env.local
```

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY=your-anon-key

# Backend URL - set to your Railway backend domain in production
NEXT_PUBLIC_BACKEND_URL=http://localhost:5000
```

---

## Docker

Multi-stage build for production:

```bash
docker build \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co \
  --build-arg NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY=your-anon-key \
  --build-arg NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app \
  -t jobswipe-frontend .
```

```bash
docker run -p 3000:3000 jobswipe-frontend
```
