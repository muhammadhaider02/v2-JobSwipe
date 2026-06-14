<div align="center">

# JobSwipe Backend

**Multi-Agent Job Matching and Application Automation Pipeline**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C)](https://langchain-ai.github.io/langgraph)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-Chat-4D6BFF)](https://deepseek.com)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-4285F4?logo=meta&logoColor=white)](https://github.com/facebookresearch/faiss)

Upload a resume, get AI-matched jobs, receive tailored application materials and auto-apply with a swipe. Three of the four agents in the JobSwipe pipeline live here.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Pipeline](#pipeline)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Docker](#docker)

---

## Overview

The backend is a Flask API backed by a LangGraph multi-agent system. It hosts three of the four JobSwipe agents. The fourth, the Scraper Agent, is [deployed separately](https://github.com/muhammadhaider02/Scrapling-Job-Boards-Scrapper) and feeds job data into the shared Supabase database.

The **Matching Agent** (Vetting Officer node) scores every job across five weighted factors: skill match, query relevance, experience alignment, location fit and title similarity. The **Optimization Agent** (Campaign Manager node) generates a tailored resume via RAG (rendered to PDF with LaTeX) and a personalized cover letter. The **Application Agent** auto-applies on the user's behalf after human-in-the-loop approval, handling form filling and submission through a managed browser session.

---

## Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  Scraper Agent (separate repo)                          │
│  Crawls Indeed, LinkedIn, Rozee, Mustakbil              │
│  Stores relevant computing jobs in Supabase             │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Resume Upload (PDF or DOCX)                            │
│  DeepSeek extracts education, experience,               │
│  skills and projects into structured JSON               │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Role Recommendation (FAISS + ONNX Embeddings)          │
│  Resume embedded via all-MiniLM-L6-v2 (ONNX Runtime)    │
│  Cosine similarity search against role embeddings       │
└──────────────────────────┬──────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌────────────────────────┐  ┌─────────────────────────────┐
│  Matching Agent        │  │  Skill Gap Analysis         │
│  (LangGraph Node)      │  │  Cosine similarity against  │
│  Multi-factor scoring: │  │  curated skill-role matrix  │
│  • Skill match (30%)   │  │  Identifies missing skills  │
│  • Query match (25%)   │  │  per recommended role       │
│  • Location fit (25%)  │  └──────────────┬──────────────┘
│  • Experience (15%)    │                 │
│  • Title sim (5%)      │                 ▼
└────────────┬───────────┘  ┌─────────────────────────────┐
             │              │  Learning Resources         │
             ▼              │  YouTube API + Google Search│
┌────────────────────────┐  │  AI-generated skill quizzes │
│  Optimization Agent    │  └─────────────────────────────┘
│  (LangGraph Node)      │
│  RAG-tailored resume   │
│  + cover letter per job│
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│  Application Agent     │
│  HITL approval gate    │
│  Auto-fill + submit    │
└────────────────────────┘
```

---

## Features

| Feature | Description |
|:---|:---|
| **Resume Parsing** | DeepSeek extracts structured education, experience, skills and projects from PDF/DOCX |
| **Role Recommendation** | FAISS vector search with ONNX embeddings matches resumes to 20 career roles |
| **Matching Agent** | Scores jobs across 5 weighted factors (skill match, query relevance, experience, location, title similarity) with configurable thresholds |
| **Optimization Agent** | RAG-enhanced resume tailoring with LaTeX PDF generation and personalized cover letter |
| **Application Agent** | Auto-applies to jobs after human-in-the-loop approval via managed browser session |
| **Skill Gap Analysis** | Cosine similarity against a curated skill-role matrix identifies missing competencies |
| **Skill Enrichment** | Expands abbreviated or partial skill names into standardized forms |
| **AI Quiz Generation** | LLM-generated MCQ and short-answer quizzes to validate skill proficiency |
| **Learning Resources** | YouTube API and Google Custom Search surface articles, videos and courses per skill |
| **Application Tracking** | Stores swipe history and application status in Supabase |
| **Auth Gate** | LangGraph conditional edges pause the campaign flow until the user authenticates |

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Framework | Flask 3.1, Gunicorn |
| Multi-Agent | LangGraph 0.2, LangChain Core 0.3 |
| LLM | DeepSeek API (OpenAI-compatible) |
| Embeddings | ONNX Runtime (all-MiniLM-L6-v2, 384-dim) |
| Vector Search | FAISS (faiss-cpu) |
| Database | Supabase (PostgreSQL) |
| Resume PDF | LaTeX (texlive) |
| Caching | Redis 5 |
| ML / Data | scikit-learn, pandas, NumPy |
| Package Manager | uv |

---

## Prerequisites

- Python 3.12+
- uv (Astral package manager)
- Redis server
- Supabase project
- DeepSeek API key
- Google API key + Custom Search Engine ID (for learning resources)
- YouTube API key

---

## Getting Started

```bash
cd backend
```

```bash
uv sync
```

```bash
cp .env.example .env.local
# Fill in your API keys
```

```bash
python app.py
```

Backend runs at `http://localhost:5000`.

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env.local
```

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# DeepSeek LLM
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Google APIs (learning resources)
YOUTUBE_API_KEY=your-youtube-api-key
GOOGLE_API_KEY=your-google-api-key
GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id

# CORS - set to your frontend domain in production
CORS_ALLOWED_ORIGIN=http://localhost:3000
```

---

## Docker

```bash
docker build -t jobswipe-backend .
```

```bash
docker run -p 5000:5000 --env-file .env.local jobswipe-backend
```

The Docker image downloads the ONNX embedding model at build time for instant startup.
