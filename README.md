# 🗄️ Vault AI - AI-Powered Document Management System

An intelligent document management system that enables users to upload documents, get AI-powered insights, and chat with their documents using natural language. Think of it as **"ChatGPT for your documents"** - users can ask questions about uploaded documents and get contextual, accurate answers with source citations.

## 🌟 Features

### Core Features
- **📤 Document Upload & Processing**: Support for PDF, DOCX, TXT, and Markdown files
- **🤖 AI-Powered Analysis**: Automatic summarization, topic extraction, categorization, and sentiment analysis
- **💬 Document Chat (RAG)**: Ask questions about documents and get accurate, cited answers
- **🔄 Multi-turn Conversations**: Maintain context across multiple questions in a session
- **📊 Metrics & Monitoring**: Track processing metrics, costs, and system health

### Bonus Features
- **📚 Multi-document Chat**: Ask questions across multiple documents simultaneously
- **💡 Follow-up Suggestions**: AI generates relevant follow-up questions
- **📝 Custom Summaries**: Generate summaries with customizable length, focus areas, and tone
- **💰 Cost Tracking**: Monitor AI API usage and estimated costs
- **🔄 Streaming Support**: Ready for SSE/WebSocket streaming responses

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Document │  │   Chat   │  │ Metrics  │  │  Health  │        │
│  │   API    │  │   API    │  │   API    │  │   API    │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐         │
│  │                   Service Layer                    │         │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │         │
│  │  │ Storage │ │Document │ │   AI    │ │   RAG   │  │         │
│  │  │ Service │ │Processor│ │ Service │ │ Service │  │         │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │         │
│  └───────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ PostgreSQL  │      │    Redis    │      │   Celery    │
│  Database   │      │   (Queue)   │      │   Workers   │
└─────────────┘      └─────────────┘      └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │  OpenAI API │
                                          │ (GPT-4 + ε) │
                                          └─────────────┘
```

### Component Overview

| Component | Purpose |
|-----------|---------|
| **FastAPI** | Async REST API framework |
| **PostgreSQL/Supabase** | Document metadata, chat history, metrics storage (with pgvector) |
| **Redis** | Task queue broker, caching |
| **Celery** | Async document processing workers |
| **OpenAI API** | Embeddings (text-embedding-3-small) + Chat (GPT-4-turbo) |
| **Supabase** | Optional: Managed database, storage, auth |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (local) **OR** Supabase account (recommended)
- Redis 7+ (local or cloud like Upstash)
- OpenAI API Key

### Option 1: Using Supabase (Recommended for Production)

Supabase provides a managed PostgreSQL database with built-in pgvector support, perfect for our RAG implementation.

#### Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Wait for the project to be provisioned

#### Step 2: Get Connection Strings

1. Go to **Settings** → **Database** → **Connection string**
2. Copy the **URI** format connection strings
3. Note: Replace `[YOUR-PASSWORD]` with your database password

#### Step 3: Configure Environment

```bash
# Clone the repository
git clone <repository-url>
cd vault-ai

# Set up environment variables
cp env.example .env
```

Edit `.env` with your Supabase credentials:

```env
# Async connection (for FastAPI)
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Sync connection (for Celery)
SYNC_DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Supabase client (optional - for storage and additional features)
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Redis (use local or cloud Redis like Upstash)
REDIS_URL=redis://localhost:6379/0
```

#### Step 4: Start Services

```bash
# Using Docker with Supabase (no local PostgreSQL)
docker-compose -f docker-compose.supabase.yml up -d

# Check logs
docker-compose -f docker-compose.supabase.yml logs -f api
```

#### Optional: Enable pgvector in Supabase

pgvector is usually enabled by default in Supabase. If not, run this in the SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

### Option 2: Docker Compose with Local Database

```bash
# Clone the repository
git clone <repository-url>
cd vault-ai

# Set up environment variables
cp env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start all services (including local PostgreSQL)
docker-compose --profile local-db up -d

# Check logs
docker-compose logs -f api
```

The API will be available at `http://localhost:8000`

---

### Option 3: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env with your configuration

# Start PostgreSQL and Redis (if not using Docker)
# ... your local setup ...

# Initialize database
alembic upgrade head

# Start the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

## 📖 API Documentation

Once the application is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Key Endpoints

#### Document Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/documents/upload` | POST | Upload a new document |
| `/api/v1/documents/` | GET | List all documents |
| `/api/v1/documents/{id}` | GET | Get document details |
| `/api/v1/documents/{id}/status` | GET | Get processing status |
| `/api/v1/documents/{id}/insights` | GET | Get AI-generated insights |
| `/api/v1/documents/{id}/analysis` | GET | Get comprehensive analysis |
| `/api/v1/documents/{id}/summarize` | POST | Generate custom summary |
| `/api/v1/documents/{id}` | DELETE | Delete a document |

#### Chat (RAG)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/sessions` | POST | Start a new chat session |
| `/api/v1/chat/sessions` | GET | List chat sessions |
| `/api/v1/chat/sessions/{id}` | GET | Get session details |
| `/api/v1/chat/sessions/{id}/history` | GET | Get chat history |
| `/api/v1/chat/sessions/{id}/ask` | POST | Ask a question |
| `/api/v1/chat/multi-document` | POST | Multi-document chat |

#### Metrics & Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/metrics/documents` | GET | Document statistics |
| `/api/v1/metrics/processing` | GET | Processing metrics |
| `/api/v1/metrics/costs` | GET | AI cost tracking |
| `/api/v1/health/` | GET | Health check |
| `/api/v1/health/ready` | GET | Readiness check |
| `/api/v1/health/detailed` | GET | Detailed system status |

## 💬 Usage Examples

### 1. Upload a Document

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "title=My Document" \
  -F "description=A sample document"
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_type": "pdf",
  "file_size": 102400,
  "status": "pending",
  "message": "Document uploaded successfully. Processing started.",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 2. Check Processing Status

```bash
curl "http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/status"
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "processing_started_at": "2024-01-15T10:30:01Z",
  "processing_completed_at": "2024-01-15T10:30:45Z",
  "processing_duration_ms": 44000
}
```

### 3. Start a Chat Session

```bash
curl -X POST "http://localhost:8000/api/v1/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Q&A about my document"
  }'
```

### 4. Ask a Question

```bash
curl -X POST "http://localhost:8000/api/v1/chat/sessions/{session_id}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main topics covered in this document?",
    "num_context_chunks": 5,
    "include_citations": true,
    "include_suggestions": true
  }'
```

**Response:**
```json
{
  "message": {
    "id": "msg-uuid",
    "role": "assistant",
    "content": "Based on the document, the main topics covered are...",
    "citations": [
      {
        "chunk_id": "chunk-uuid",
        "content_snippet": "...relevant text excerpt...",
        "page_number": 3,
        "relevance_score": 0.92
      }
    ],
    "suggested_questions": [
      "Can you elaborate on the first topic?",
      "What conclusions are drawn about...?"
    ]
  },
  "context_used": 5,
  "response_time_ms": 1234
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection URL | `postgresql+asyncpg://...` |
| `SYNC_DATABASE_URL` | PostgreSQL sync connection URL | `postgresql://...` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `STORAGE_PATH` | Document storage path | `./storage/documents` |
| `EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `CHAT_MODEL` | OpenAI chat model | `gpt-4-turbo-preview` |
| `CHUNK_SIZE` | Text chunk size | `1000` |
| `CHUNK_OVERLAP` | Chunk overlap | `200` |
| `MAX_FILE_SIZE_MB` | Max upload size | `50` |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_documents.py -v

# Run with logging
pytest -v --log-cli-level=INFO
```

## 📁 Project Structure

```
vault-ai/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── api/                  # API routes
│   │   ├── documents.py     # Document endpoints
│   │   ├── chat.py          # Chat endpoints
│   │   ├── metrics.py       # Metrics endpoints
│   │   └── health.py        # Health checks
│   ├── models/              # SQLAlchemy models
│   │   ├── document.py      # Document, Chunk, Insight
│   │   ├── chat.py          # Session, Message
│   │   └── metrics.py       # Processing, System metrics
│   ├── schemas/             # Pydantic schemas
│   │   ├── document.py
│   │   ├── chat.py
│   │   └── metrics.py
│   ├── services/            # Business logic
│   │   ├── storage.py       # File storage
│   │   ├── document_processor.py  # Text extraction & chunking
│   │   ├── ai_service.py    # OpenAI interactions
│   │   ├── rag_service.py   # RAG implementation
│   │   └── metrics_service.py
│   └── workers/             # Celery workers
│       ├── celery_app.py    # Celery configuration
│       └── tasks.py         # Async processing tasks
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── storage/                 # Document storage
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── AI_USAGE.md
```

## 🎯 Design Decisions

### RAG Implementation
- **Chunking Strategy**: Smart paragraph-aware chunking with overlap for context preservation
- **Embedding Model**: text-embedding-3-small for cost-effective semantic search
- **Similarity Search**: Cosine similarity with configurable threshold
- **Context Building**: Dynamic context assembly respecting token limits

### Async Processing
- **Why Celery?**: Reliable task queue with retry support, rate limiting, and monitoring
- **Pipeline Design**: Modular stages (extract → chunk → embed → analyze)
- **Idempotency**: Tasks can be safely retried on failure

### Database Design
- **Documents**: Core metadata, AI-generated content, processing status
- **Chunks**: RAG-ready segments with embeddings
- **Chat Sessions**: Multi-turn conversation support
- **Metrics**: Comprehensive tracking for observability

## 🔒 Security Considerations

- File type validation before processing
- File size limits enforced
- SQL injection prevention via SQLAlchemy ORM
- CORS configuration for API access control
- Rate limiting on AI API calls

## 🚧 Scalability Considerations

- **Horizontal Scaling**: Stateless API servers behind load balancer
- **Worker Scaling**: Multiple Celery workers for parallel processing
- **Database**: Connection pooling, read replicas for heavy read loads
- **Caching**: Redis for embeddings and frequent queries
- **Storage**: S3-compatible object storage for production

## 📈 Future Improvements

- [ ] Vector database integration (pgvector, Pinecone)
- [ ] Streaming responses via SSE
- [ ] Batch document processing
- [ ] Document versioning
- [ ] User authentication & authorization
- [ ] Advanced caching strategies
- [ ] GraphQL API option

## 🎬 Demo

<video src="https://github.com/MaheshJain0601/VaultAI/raw/main/assets/demo.mp4" controls="controls" style="max-width: 100%;"></video>

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ using FastAPI, LangChain concepts, and OpenAI

