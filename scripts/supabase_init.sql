-- =============================================
-- Vault AI - Supabase Database Initialization
-- =============================================
-- Run this script in the Supabase SQL Editor to create all tables
-- Go to: Supabase Dashboard > SQL Editor > New Query
-- 
-- This script:
-- 1. Enables pgvector extension for embeddings
-- 2. Creates all required tables
-- 3. Sets up indexes for performance
-- 4. Creates RLS policies (optional)

-- =============================================
-- Enable Extensions
-- =============================================

-- pgvector for embedding similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID generation (usually already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- Enum Types
-- =============================================

-- Document status enum
DO $$ BEGIN
    CREATE TYPE document_status AS ENUM (
        'pending', 'processing', 'chunking', 'embedding', 
        'analyzing', 'completed', 'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Document type enum
DO $$ BEGIN
    CREATE TYPE document_type AS ENUM ('pdf', 'docx', 'txt', 'md');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Message role enum
DO $$ BEGIN
    CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Metric type enum
DO $$ BEGIN
    CREATE TYPE metric_type AS ENUM (
        'document_upload', 'document_processing', 'text_extraction',
        'chunking', 'embedding', 'ai_analysis', 'chat_query', 'retrieval'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- =============================================
-- Documents Table
-- =============================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Basic metadata
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type document_type NOT NULL,
    file_size INTEGER NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    
    -- Content metadata
    title VARCHAR(500),
    description TEXT,
    page_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    
    -- Processing status
    status document_status DEFAULT 'pending' NOT NULL,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_error TEXT,
    processing_duration_ms INTEGER,
    
    -- AI-generated content
    summary TEXT,
    key_topics TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{}',
    sentiment VARCHAR(50),
    language VARCHAR(50) DEFAULT 'en',
    
    -- Embeddings metadata
    embedding_model VARCHAR(100),
    chunk_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);

-- =============================================
-- Document Chunks Table (with embeddings)
-- =============================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    
    -- Chunk content
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    
    -- Position metadata
    page_number INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    
    -- Embedding (1536 dimensions for text-embedding-3-small)
    embedding vector(1536),
    embedding_model VARCHAR(100),
    
    -- Token count
    token_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for chunks
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON document_chunks(chunk_index);

-- Vector similarity search index (IVFFlat for fast approximate nearest neighbors)
-- Adjust 'lists' parameter based on expected data size:
-- - Small (<10k chunks): lists = 10-50
-- - Medium (10k-100k chunks): lists = 100-200
-- - Large (>100k chunks): lists = sqrt(num_chunks)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
ON document_chunks USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- =============================================
-- Document Insights Table
-- =============================================

CREATE TABLE IF NOT EXISTS document_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    
    -- Insight details
    insight_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,
    confidence_score FLOAT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for insights
CREATE INDEX IF NOT EXISTS idx_insights_document_id ON document_insights(document_id);
CREATE INDEX IF NOT EXISTS idx_insights_type ON document_insights(insight_type);

-- =============================================
-- Chat Sessions Table
-- =============================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    
    -- Session metadata
    title VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    
    -- Multi-document support
    document_ids UUID[] DEFAULT '{}',
    
    -- Context configuration
    context_window INTEGER DEFAULT 5,
    
    -- Statistics
    message_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ
);

-- Indexes for sessions
CREATE INDEX IF NOT EXISTS idx_sessions_document_id ON chat_sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON chat_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_is_active ON chat_sessions(is_active);

-- =============================================
-- Chat Messages Table
-- =============================================

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE NOT NULL,
    
    -- Message content
    role message_role NOT NULL,
    content TEXT NOT NULL,
    
    -- Citations and context
    citations JSONB DEFAULT '[]',
    context_chunks JSONB DEFAULT '[]',
    
    -- Token usage
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- Response metadata
    model_used VARCHAR(100),
    response_time_ms INTEGER,
    confidence_score FLOAT,
    
    -- Follow-up suggestions
    suggested_questions TEXT[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON chat_messages(role);

-- =============================================
-- Processing Metrics Table
-- =============================================

CREATE TABLE IF NOT EXISTS processing_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- References
    document_id UUID,
    session_id UUID,
    
    -- Metric details
    metric_type metric_type NOT NULL,
    operation_name VARCHAR(100) NOT NULL,
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    
    -- Status
    success INTEGER DEFAULT 1,
    error_message TEXT,
    
    -- Resource usage
    tokens_used INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    estimated_cost FLOAT DEFAULT 0.0,
    
    -- Additional data
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for metrics
CREATE INDEX IF NOT EXISTS idx_metrics_type ON processing_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON processing_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_success ON processing_metrics(success);
CREATE INDEX IF NOT EXISTS idx_metrics_document_id ON processing_metrics(document_id);

-- =============================================
-- System Metrics Table
-- =============================================

CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Metric identification
    metric_name VARCHAR(100) NOT NULL,
    metric_category VARCHAR(50) NOT NULL,
    
    -- Values
    value FLOAT NOT NULL,
    unit VARCHAR(50),
    
    -- Context
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INTEGER,
    
    -- Additional data
    tags JSONB DEFAULT '{}',
    
    -- Timestamps
    recorded_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for system metrics
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_category ON system_metrics(metric_category);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at DESC);

-- =============================================
-- Helper Functions
-- =============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for documents
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for chat_sessions
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- Similarity Search Function
-- =============================================

-- Function to find similar chunks using cosine similarity
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_document_id UUID,
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    chunk_index INT,
    page_number INT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.chunk_index,
        dc.page_number,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE dc.document_id = match_document_id
        AND dc.embedding IS NOT NULL
        AND 1 - (dc.embedding <=> query_embedding) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================
-- Row Level Security (Optional)
-- =============================================
-- Uncomment these if you want to enable RLS for multi-tenant support

-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_insights ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- =============================================
-- Grant Permissions
-- =============================================

-- Grant usage to authenticated and anon roles (Supabase default)
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;

-- =============================================
-- Verification
-- =============================================

-- Check that everything was created
SELECT 
    'Tables' as type,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('documents', 'document_chunks', 'document_insights', 
                   'chat_sessions', 'chat_messages', 'processing_metrics', 'system_metrics')
UNION ALL
SELECT 
    'Extensions' as type,
    COUNT(*) as count
FROM pg_extension 
WHERE extname IN ('vector', 'uuid-ossp');

