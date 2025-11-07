-- PostgreSQL initialization script for Emotional RAG Backend
-- Creates pgvector extension and initial schema

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create messages table with vector embeddings
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    chat_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
    content TEXT NOT NULL,
    embedding vector(384),  -- 384 dimensions for all-MiniLM-L6-v2
    emotion VARCHAR(50),
    importance REAL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Create index on chat_id for fast session queries
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);

-- Create index on timestamp for chronological queries
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);

-- Create HNSW index on embeddings for vector similarity search
-- Using cosine distance as it's normalized
CREATE INDEX IF NOT EXISTS idx_messages_embedding_hnsw 
ON messages USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (faster build, slower query)
-- Uncomment if HNSW is too slow to build
-- CREATE INDEX IF NOT EXISTS idx_messages_embedding_ivfflat 
-- ON messages USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- Create personas table
CREATE TABLE IF NOT EXISTS personas (
    id BIGSERIAL PRIMARY KEY,
    chat_id VARCHAR(255) NOT NULL UNIQUE,
    persona TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on chat_id for fast lookups
CREATE INDEX IF NOT EXISTS idx_personas_chat_id ON personas(chat_id);

-- Create summaries table
CREATE TABLE IF NOT EXISTS summaries (
    id BIGSERIAL PRIMARY KEY,
    chat_id VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    message_range_start INTEGER NOT NULL,
    message_range_end INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on chat_id for summaries
CREATE INDEX IF NOT EXISTS idx_summaries_chat_id ON summaries(chat_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for personas table
CREATE TRIGGER update_personas_updated_at
BEFORE UPDATE ON personas
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Create materialized view for emotion statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS emotion_stats AS
SELECT 
    chat_id,
    emotion,
    COUNT(*) as count,
    AVG(importance) as avg_importance,
    MAX(timestamp) as last_occurrence
FROM messages
WHERE emotion IS NOT NULL
GROUP BY chat_id, emotion;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_emotion_stats_chat_id ON emotion_stats(chat_id);

-- Refresh materialized view function
CREATE OR REPLACE FUNCTION refresh_emotion_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY emotion_stats;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed for production)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- Create helper function for vector similarity search
CREATE OR REPLACE FUNCTION search_similar_messages(
    p_chat_id VARCHAR(255),
    p_query_embedding vector(384),
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    emotion VARCHAR(50),
    importance REAL,
    distance REAL,
    timestamp TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.content,
        m.emotion,
        m.importance,
        (m.embedding <=> p_query_embedding)::REAL as distance,
        m.timestamp
    FROM messages m
    WHERE m.chat_id = p_chat_id 
        AND m.embedding IS NOT NULL
    ORDER BY m.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Insert example data (for testing only)
-- DELETE FROM messages;
-- INSERT INTO messages (chat_id, role, content, emotion, importance) VALUES
-- ('test_session', 'user', 'Hello, how are you?', 'neutral', 0.3),
-- ('test_session', 'assistant', 'I''m doing great! How can I help you today?', 'joy', 0.5);

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Emotional RAG Backend database initialized successfully';
    RAISE NOTICE 'pgvector extension enabled';
    RAISE NOTICE 'HNSW indices created for fast vector search';
END $$;
