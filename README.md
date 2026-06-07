# MSP Client Portal

A multi-tenant managed service provider (MSP) client portal built on AWS serverless infrastructure.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Browser                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Next.js 14 (App Router)                       │
│                Vercel / AWS Amplify Hosting                     │
│                                                                 │
│  /frontend                                                      │
│  ├── src/app          – page routes & layouts                   │
│  ├── src/components   – shared UI components                    │
│  ├── src/hooks        – custom React hooks                      │
│  ├── src/lib          – API clients, auth helpers               │
│  └── src/types        – shared TypeScript types                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ REST / JSON
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              AWS API Gateway (HTTP API)                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           AWS Lambda  (Python 3.12)                             │
│           FastAPI + Mangum adapter                              │
│                                                                 │
│  /backend                                                       │
│  ├── app/api          – route handlers (routers)               │
│  ├── app/core         – config, middleware, auth                │
│  ├── app/models       – Pydantic request/response models        │
│  ├── app/services     – business logic                          │
│  └── app/utils        – shared helpers                          │
└──────┬──────────────────────────────────────────┬──────────────┘
       │                                          │
       ▼                                          ▼
┌──────────────┐                        ┌─────────────────────┐
│  DynamoDB    │                        │  ElastiCache Redis  │
│  (per-tenant │                        │  (session cache,    │
│   tables)    │                        │   rate limiting)    │
└──────────────┘                        └─────────────────────┘
       │
       ▼
┌──────────────┐      ┌─────────────────────┐
│  Amazon S3   │      │  AWS EventBridge    │
│  (reports,  │      │  (scheduled jobs,   │
│   assets)   │      │   notifications)    │
└──────────────┘      └─────────────────────┘

Authentication
──────────────
  AWS Cognito User Pools — one pool per tenant (or shared pool with tenant
  claims). JWTs are validated inside the FastAPI middleware layer.
```

---

## Monorepo Layout

```
msp-client-portal/
├── README.md
├── .gitignore
│
├── frontend/                  # Next.js 14 application
│   ├── .gitignore
│   ├── public/                # Static assets
│   └── src/
│       ├── app/               # App Router pages & layouts
│       ├── components/        # Reusable UI components
│       ├── hooks/             # Custom React hooks
│       ├── lib/               # API clients, auth utilities
│       ├── styles/            # Global CSS / Tailwind config
│       └── types/             # Shared TypeScript interfaces
│
├── backend/                   # Python FastAPI application
│   ├── .gitignore
│   ├── app/
│   │   ├── api/               # FastAPI routers
│   │   ├── core/              # Config, middleware, Cognito auth
│   │   ├── models/            # Pydantic models
│   │   ├── services/          # Business logic (DynamoDB, S3, Redis)
│   │   └── utils/             # Shared helpers
│   └── tests/                 # Pytest test suite
│
├── infrastructure/            # AWS infrastructure definitions
│   ├── cloudformation/        # CloudFormation / SAM templates
│   └── scripts/               # Deployment & utility scripts
│
└── .github/
    └── workflows/             # CI/CD pipelines
```

---

## Key AWS Services

| Service | Purpose |
|---|---|
| **AWS Cognito** | Authentication & multi-tenant user management |
| **AWS Lambda** | Serverless compute for the FastAPI backend (via Mangum) |
| **API Gateway** | HTTP API fronting Lambda |
| **DynamoDB** | Primary database; tenant-isolated via partition key strategy |
| **ElastiCache (Redis)** | Session caching, rate limiting, pub/sub |
| **S3** | Report storage, static asset uploads |
| **EventBridge** | Scheduled report generation, automated notifications |
| **CloudWatch** | Logging, metrics, and alarms |

---

## Multi-Tenancy Strategy

- Each tenant is identified by a `tenant_id` claim embedded in the Cognito JWT.
- All DynamoDB operations include `tenant_id` as the partition key prefix to ensure data isolation.
- Redis keys are namespaced by `tenant_id`.
- S3 objects are stored under a `{tenant_id}/` prefix with bucket policies enforcing access boundaries.

---

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.12+
- AWS CLI configured with appropriate credentials
- Docker (for local Redis / DynamoDB emulation)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## Contributing

1. Branch from `main` using the convention `feature/<short-description>`.
2. Open a pull request; CI must pass before merge.
3. All secrets must be stored in AWS Secrets Manager — never committed to the repo.
