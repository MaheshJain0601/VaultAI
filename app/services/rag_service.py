"""RAG (Retrieval-Augmented Generation) service using LangChain for document Q&A."""
import logging
import time
from typing import List, Dict, Optional, Tuple
from uuid import UUID

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import Document as LangChainDocument
from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.chat import ChatSession, ChatMessage, MessageRole
from app.services.ai_service import ai_service
from app.services.rate_limiter import get_rate_limiter
from app.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG service using LangChain for document Q&A.
    
    This service implements Retrieval-Augmented Generation using:
    - LangChain for orchestration and prompt management
    - Google Gemini embeddings for semantic search
    - FAISS for in-memory vector similarity (with DB-stored embeddings as source)
    - ChatGoogleGenerativeAI for response generation
    
    Key LangChain components used:
    - GoogleGenerativeAIEmbeddings: Generate query embeddings
    - ChatGoogleGenerativeAI: LLM for generating answers
    - ChatPromptTemplate: Structured prompts with context
    - FAISS: Vector store for similarity search
    """
    
    def __init__(self):
        self.ai_service = ai_service
        self.max_context_tokens = settings.max_context_tokens
        
        # Initialize LangChain components with Google Gemini
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model=settings.chat_model,
            temperature=settings.temperature,
            google_api_key=settings.google_api_key
        )
        
        # Text splitter for chunking (used in document processing)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Rate limiter for LLM API calls
        self._rate_limiter = get_rate_limiter()
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    async def retrieve_relevant_chunks(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        num_chunks: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Retrieve the most relevant chunks using LangChain embeddings.
        
        Uses GoogleGenerativeAIEmbeddings from LangChain to generate query embedding,
        then performs similarity search against stored chunk embeddings.
        Rate-limited to prevent quota exceeded errors.
        """
        # Generate query embedding using LangChain (rate-limited)
        await self._rate_limiter.wait_async()
        query_embedding = await self.embeddings.aembed_query(query)
        
        # Get all chunks for the document from database
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        
        # Calculate similarity scores
        scored_chunks = []
        for chunk in chunks:
            if chunk.embedding:
                score = self.cosine_similarity(query_embedding, chunk.embedding)
                if score >= similarity_threshold:
                    scored_chunks.append((chunk, score))
        
        # Sort by similarity and return top chunks
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:num_chunks]
    
    async def retrieve_from_multiple_documents(
        self,
        db: AsyncSession,
        document_ids: List[UUID],
        query: str,
        num_chunks_per_doc: int = 3,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[DocumentChunk, float, UUID]]:
        """
        Retrieve relevant chunks from multiple documents.
        
        Returns:
            List of (chunk, score, document_id) tuples
        """
        all_chunks = []
        
        for doc_id in document_ids:
            chunks = await self.retrieve_relevant_chunks(
                db, doc_id, query, num_chunks_per_doc, similarity_threshold
            )
            for chunk, score in chunks:
                all_chunks.append((chunk, score, doc_id))
        
        # Sort by similarity across all documents
        all_chunks.sort(key=lambda x: x[1], reverse=True)
        return all_chunks
    
    def _chunks_to_langchain_docs(
        self,
        chunks: List[Tuple[DocumentChunk, float]]
    ) -> List[LangChainDocument]:
        """Convert database chunks to LangChain Document objects."""
        docs = []
        for chunk, score in chunks:
            metadata = {
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "relevance_score": score,
                "source": f"Page {chunk.page_number}" if chunk.page_number else f"Chunk {chunk.chunk_index}"
            }
            docs.append(LangChainDocument(
                page_content=chunk.content,
                metadata=metadata
            ))
        return docs
    
    def build_context(
        self,
        chunks: List[Tuple[DocumentChunk, float]],
        max_tokens: Optional[int] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Build context string from retrieved chunks.
        
        Returns:
            Tuple of (context_string, citations_list)
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        context_parts = []
        citations = []
        current_tokens = 0
        
        for chunk, score in chunks:
            chunk_tokens = chunk.token_count or self.ai_service.count_tokens(chunk.content)
            
            if current_tokens + chunk_tokens > max_tokens:
                break
            
            # Add to context
            page_ref = f" (Page {chunk.page_number})" if chunk.page_number else ""
            context_parts.append(f"[Source {len(citations) + 1}{page_ref}]:\n{chunk.content}")
            
            # Add citation
            citations.append({
                "chunk_id": str(chunk.id),
                "content_snippet": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                "page_number": chunk.page_number,
                "relevance_score": score
            })
            
            current_tokens += chunk_tokens
        
        context = "\n\n".join(context_parts)
        return context, citations
    
    def build_chat_history(
        self,
        messages: List[ChatMessage],
        context_window: int = 5
    ) -> List:
        """
        Build chat history for multi-turn context using LangChain message types.
        """
        # Get last N message pairs
        recent_messages = messages[-context_window * 2:] if len(messages) > context_window * 2 else messages
        
        history = []
        for msg in recent_messages:
            role = msg.role.value if hasattr(msg.role, 'value') else msg.role
            if role == "user":
                history.append(HumanMessage(content=msg.content))
            elif role == "assistant":
                history.append(AIMessage(content=msg.content))
        
        return history
    
    def _get_qa_prompt(self, include_citations: bool) -> ChatPromptTemplate:
        """
        Create LangChain prompt template for Q&A.
        
        This is where prompt engineering happens - the template defines
        how context and questions are presented to the LLM.
        """
        system_template = """You are an intelligent document assistant. Your role is to answer questions about documents accurately and helpfully.

Guidelines:
1. Answer questions based ONLY on the provided context from the document
2. If the context doesn't contain enough information to answer, say so clearly
3. Be precise and accurate - don't make up information
4. Keep answers concise but comprehensive
5. Use a professional and helpful tone"""

        if include_citations:
            system_template += """
6. When referencing specific information, mention the source (e.g., "According to Source 1..." or "As stated on Page 3...")
7. If information comes from multiple sources, acknowledge that"""

        human_template = """Based on the following document excerpts, please answer my question.

DOCUMENT CONTEXT:
{context}

MY QUESTION: {question}

Please provide a helpful and accurate answer based on the context provided."""

        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", human_template)
        ])
    
    async def answer_question(
        self,
        db: AsyncSession,
        session: ChatSession,
        question: str,
        num_context_chunks: int = 5,
        similarity_threshold: float = 0.7,
        include_citations: bool = True,
        include_suggestions: bool = True,
        max_response_tokens: int = 1000
    ) -> Dict:
        """
        Answer a question about the document using LangChain RAG.
        
        This method orchestrates the full RAG pipeline:
        1. Retrieve relevant chunks using semantic search (LangChain embeddings)
        2. Build context from retrieved documents
        3. Use LangChain ChatPromptTemplate for structured prompting
        4. Generate response using ChatGoogleGenerativeAI
        5. Optionally generate follow-up suggestions
        """
        start_time = time.time()
        
        # Step 1: Retrieve relevant chunks using LangChain embeddings
        relevant_chunks = await self.retrieve_relevant_chunks(
            db, session.document_id, question, num_context_chunks, similarity_threshold
        )
        
        # Step 2: Build context and citations
        context, citations = self.build_context(relevant_chunks)
        
        # Step 3: Get chat history for multi-turn context
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        chat_history = self.build_chat_history(messages, session.context_window)
        
        # Step 4: Create LangChain prompt and generate response (rate-limited)
        prompt = self._get_qa_prompt(include_citations)
        
        # Use LangChain's invoke with the prompt
        chain = prompt | self.llm
        
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({
            "context": context if context else "No relevant context found in the document.",
            "question": question,
            "chat_history": chat_history
        })
        
        answer = response.content
        
        # Step 5: Generate follow-up suggestions if requested
        suggestions = []
        if include_suggestions and context:
            suggestions = await self._generate_follow_up_questions(context, question, answer)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Estimate token usage (LangChain doesn't always provide this directly)
        prompt_tokens = self.ai_service.count_tokens(context + question)
        completion_tokens = self.ai_service.count_tokens(answer)
        
        return {
            "answer": answer,
            "citations": citations if include_citations else [],
            "suggestions": suggestions,
            "context_used": len(relevant_chunks),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "model_used": settings.chat_model,
            "response_time_ms": response_time_ms
        }
    
    async def _generate_follow_up_questions(
        self,
        context: str,
        question: str,
        answer: str
    ) -> List[str]:
        """
        Generate follow-up question suggestions using LangChain. Rate-limited.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Based on the document context, the user's question, and the answer provided,
suggest 3 relevant follow-up questions the user might want to ask.
Make questions specific and directly related to the document content.
Return ONLY a JSON array of question strings, nothing else.
Example: ["Question 1?", "Question 2?", "Question 3?"]"""),
            ("human", """Document context: {context}

User question: {question}

Answer provided: {answer}

Suggest 3 follow-up questions:""")
        ])
        
        chain = prompt | self.llm
        
        try:
            await self._rate_limiter.wait_async()
            response = await chain.ainvoke({
                "context": context[:3000],  # Limit context length
                "question": question,
                "answer": answer
            })
            
            import json
            questions = json.loads(response.content)
            return questions[:3]
        except Exception:
            return []
    
    async def answer_multi_document_question(
        self,
        db: AsyncSession,
        document_ids: List[UUID],
        question: str,
        num_chunks_per_doc: int = 3
    ) -> Dict:
        """
        Answer a question across multiple documents using LangChain.
        
        Retrieves context from all specified documents and synthesizes
        a comprehensive answer that references multiple sources.
        """
        start_time = time.time()
        
        # Retrieve from all documents
        all_chunks = await self.retrieve_from_multiple_documents(
            db, document_ids, question, num_chunks_per_doc
        )
        
        # Build context with document references
        context_parts = []
        citations = []
        
        for chunk, score, doc_id in all_chunks[:10]:  # Limit total chunks
            doc_result = await db.execute(
                select(Document.filename).where(Document.id == doc_id)
            )
            filename = doc_result.scalar()
            
            page_ref = f", Page {chunk.page_number}" if chunk.page_number else ""
            context_parts.append(f"[From: {filename}{page_ref}]:\n{chunk.content}")
            
            citations.append({
                "chunk_id": str(chunk.id),
                "document_id": str(doc_id),
                "document_name": filename,
                "content_snippet": chunk.content[:200] + "...",
                "page_number": chunk.page_number,
                "relevance_score": score
            })
        
        context = "\n\n".join(context_parts)
        
        # Create multi-document prompt using LangChain
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a document analyst comparing and synthesizing information from multiple documents.
When answering, reference which document the information comes from.
If documents contain conflicting information, point that out.
Be comprehensive but concise."""),
            ("human", """Context from documents:
{context}

Question: {question}

Please provide a comprehensive answer based on all relevant documents.""")
        ])
        
        chain = prompt | self.llm
        
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({
            "context": context,
            "question": question
        })
        
        return {
            "answer": response.content,
            "citations": citations,
            "documents_used": list(set(str(c["document_id"]) for c in citations)),
            "response_time_ms": int((time.time() - start_time) * 1000)
        }
    
    async def create_in_memory_vectorstore(
        self,
        db: AsyncSession,
        document_id: UUID
    ) -> Optional[FAISS]:
        """
        Create an in-memory FAISS vector store from document chunks.
        
        This is useful for faster repeated queries on the same document.
        Uses LangChain's FAISS integration.
        """
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return None
        
        # Convert to LangChain documents
        docs = []
        for chunk in chunks:
            if chunk.embedding:
                docs.append(LangChainDocument(
                    page_content=chunk.content,
                    metadata={
                        "chunk_id": str(chunk.id),
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number
                    }
                ))
        
        if not docs:
            return None
        
        # Create FAISS index from documents (rate-limited embedding call)
        await self._rate_limiter.wait_async()
        vectorstore = await FAISS.afrom_documents(docs, self.embeddings)
        return vectorstore


# Singleton instance
rag_service = RAGService()
