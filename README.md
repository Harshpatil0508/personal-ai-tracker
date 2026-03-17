# REFLECTA (Personal AI Tracker)

An AI-powered personal tracking and self-improvement system that goes beyond dashboards by detecting real behavior changes, 
generating explainable recommendations, and validating whether AI advice actually works.

## Why This Project
Most habit trackers show averages.
Most AI apps generate generic advice.

This system:
- Detects *when* behavior actually changes
- Explains *why* advice is given
- Learns from user feedback
- Validates advice using real outcome data

## Core Features
- Daily personal data tracking (sleep, work, mood, goals)
- Automated analytics & scheduled jobs
- Explainable AI recommendations
- Behavior Change Detection Engine
- Human-in-the-loop feedback
- Delayed validation of AI advice effectiveness
- RAG-based AI memory using pgvector
- Admin-level AI effectiveness metrics

## Architecture Overview
Daily Logs → Analytics → Behavior Change Detection → Explainable AI → Feedback & Validation → Adaptive AI Prompts

## Tech Stack
- FastAPI
- PostgreSQL + pgvector
- Celery + Redis
- GROQ API to generate daily motivation and monthly recommendations
- JINA API to generate the embeddings
- Docker

## Key Design Principles
- AI is accountable, not trusted blindly
- Intelligence lives in backend, not prompts
- All AI decisions are explainable
- Systems improve via feedback, not retraining

## Status
🚧 In active development

## Code Access

- The `dev` branch contains the latest working version of the project
- The `main` branch is reserved for stable releases

👉 Always create PRs against the `dev` branch
