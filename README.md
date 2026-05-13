<div align="center">

# JobSwipe

**APPLY LESS, LAND MORE**

[![Frontend](https://img.shields.io/badge/Frontend-Next.js_15-000000?logo=next.js&logoColor=white)](/frontend)
[![Backend](https://img.shields.io/badge/Backend-Flask_3.1-000000?logo=flask&logoColor=white)](/backend)
[![LangGraph](https://img.shields.io/badge/Agents-LangGraph-1C3C3C)](https://langchain-ai.github.io/langgraph)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A multi-agent AI-powered career acceleration platform that helps computing professionals land a job. Upload your resume, swipe right on the roles that fit and let the agents handle the rest.

[Frontend Docs](/frontend) · [Backend Docs](/backend) · [Scraper Agent](https://github.com/muhammadhaider02/Scrapling-Job-Boards-Scrapper) · [Getting Started](#getting-started)

</div>

---

## How It Works

1. **Upload your resume** - AI extracts your skills, experience and education into a structured profile
2. **Get role recommendations** - The platform recommends suitable roles based on your profile
3. **Identify skill gaps** - See what skills you're missing, access learning resources and verify competencies through quizzes
4. **Swipe through jobs** - The Matching Agent ranks jobs by semantic similarity, skill overlap, experience alignment and location fit
5. **Apply with one swipe** - The Optimization Agent tailors your resume and cover letter, then the Application Agent auto-applies on your behalf

---

## The Four Agents

| Agent | Role |
|:---|:---|
| **Scraper Agent** | Crawls Indeed, LinkedIn, Rozee and Mustakbil. Evaluates each posting's relevance to computing roles and decides to store or discard it. [Deployed separately](https://github.com/muhammadhaider02/Scrapling-Job-Boards-Scrapper). |
| **Matching Agent** | Determines best-fit jobs through semantic similarity, skill overlap, experience alignment and location fit |
| **Optimization Agent** | Tailors the resume to the job description using Retrieval-Augmented Generation and generates a personalized cover letter |
| **Application Agent** | Auto-applies on the user's behalf with a right swipe on the Tinder-style interface |

---

## Features

- Role Recommendations
- Skill Gap Analysis and Learning Resources
- Skill Assessment and Verification
- Intelligent Job Matching and Swipe UI
- Resume Optimization and Cover Letter Generation

---

## Architecture

| Component | Stack | Description |
|:---|:---|:---|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS 4 | Swipe UI, auth, skill quizzes, learning dashboard |
| **Backend** | Flask, LangGraph, Llama 3.3 70B (SambaNova) | Multi-agent pipeline for job matching, resume optimization, cover letter generation |
| **Scraper** | Scrapling, Playwright, Camoufox | Standalone agent crawling four job boards. [Separate repo](https://github.com/muhammadhaider02/Scrapling-Job-Boards-Scrapper). |
| **Search** | FAISS, Sentence Transformers (all-MiniLM-L6-v2) | Semantic role matching and skill gap analysis |
| **Database** | Supabase (PostgreSQL) | User profiles, job listings, application history |
| **Cache** | Redis | Job queue and processing state |

---

## Getting Started

### Prerequisites

- Node.js 22+ and pnpm 9+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Redis
- Supabase project

### Quick Start

```bash
git clone https://github.com/muhammadhaider02/JobSwipe.git
cd JobSwipe
```

**Backend:**

```bash
cd backend
uv sync
cp .env.example .env.local   # fill in API keys
python app.py                 # http://localhost:5000
```

**Frontend:**

```bash
cd frontend
pnpm install
cp .env.example .env.local    # fill in Supabase + backend URL
pnpm dev                      # http://localhost:3000
```
