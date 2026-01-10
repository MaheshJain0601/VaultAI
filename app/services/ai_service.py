"""AI service using LangChain for embeddings and LLM interactions."""
import json
import logging
from typing import List, Dict, Tuple

import google.generativeai as genai

# LangChain imports
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema import HumanMessage, SystemMessage

from app.config import settings
from app.services.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class AIService:
    """
    Service for AI operations using LangChain with Google Gemini.
    
    This service provides AI capabilities using LangChain for:
    - Embeddings generation (GoogleGenerativeAIEmbeddings)
    - Chat completions (ChatGoogleGenerativeAI)
    - Structured prompts (ChatPromptTemplate)
    
    All LLM API calls are rate-limited based on the configured
    llm_requests_per_minute setting to prevent quota exceeded errors.
    
    LangChain components used:
    - GoogleGenerativeAIEmbeddings: For generating document and query embeddings
    - ChatGoogleGenerativeAI: For LLM interactions (summarization, analysis, etc.)
    - ChatPromptTemplate: For structured prompt engineering
    """
    
    def __init__(self):
        # Configure Google Generative AI
        genai.configure(api_key=settings.google_api_key)
        
        self.embedding_model = settings.embedding_model
        self.chat_model = settings.chat_model
        self.temperature = settings.temperature
        
        # LangChain components with Google Gemini
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model=settings.chat_model,
            temperature=settings.temperature,
            google_api_key=settings.google_api_key
        )
        
        # Rate limiter for LLM API calls
        self._rate_limiter = get_rate_limiter()
        logger.info(f"AIService initialized with rate limit: {settings.llm_requests_per_minute} requests/minute")
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count for text (approximate for Gemini)."""
        # Gemini uses a different tokenizer; approximate with ~4 chars per token
        return len(text) // 4
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text using LangChain.
        
        Uses GoogleGenerativeAIEmbeddings from LangChain for consistency
        with the RAG service. Rate-limited to prevent quota exceeded errors.
        """
        await self._rate_limiter.wait_async()
        return await self.embeddings.aembed_query(text)
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using LangChain.
        
        LangChain's GoogleGenerativeAIEmbeddings handles batching internally.
        Rate-limited to prevent quota exceeded errors.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # Apply rate limiting before each batch API call
            await self._rate_limiter.wait_async()
            # Use LangChain's async batch embedding
            batch_embeddings = await self.embeddings.aembed_documents(batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    async def generate_summary(
        self,
        text: str,
        length: str = "medium",
        focus_areas: List[str] = None,
        tone: str = "professional"
    ) -> Tuple[str, Dict]:
        """
        Generate a summary using LangChain ChatGoogleGenerativeAI.
        
        Uses ChatPromptTemplate for structured prompt engineering.
        """
        length_instructions = {
            "short": "Provide a concise 2-3 sentence summary.",
            "medium": "Provide a comprehensive single paragraph summary.",
            "long": "Provide a detailed multi-paragraph summary covering all key points."
        }
        
        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"\nPay special attention to these topics: {', '.join(focus_areas)}"
        
        # Create LangChain prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an expert document analyst. Your task is to summarize documents accurately and {tone}ly.
{length_instructions.get(length, length_instructions['medium'])}{focus_instruction}

Guidelines:
- Capture the main ideas and key points
- Be accurate and factual - don't add information not in the document
- Use clear, accessible language
- Maintain the document's original intent and meaning"""),
            ("human", "Please summarize the following document:\n\n{text}")
        ])
        
        # Create chain and invoke with rate limiting
        chain = prompt | self.llm
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({"text": text[:15000]})
        
        summary = response.content
        
        # Estimate tokens (LangChain doesn't always provide usage)
        metadata = {
            "prompt_tokens": self.count_tokens(text[:15000]),
            "completion_tokens": self.count_tokens(summary),
            "total_tokens": self.count_tokens(text[:15000]) + self.count_tokens(summary),
            "model": self.chat_model
        }
        
        return summary, metadata
    
    async def extract_key_topics(self, text: str) -> Tuple[List[str], Dict]:
        """Extract key topics using LangChain. Rate-limited."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at identifying key topics in documents.
Extract 5-10 main topics or themes from the document.
Return ONLY a JSON array of topic strings, nothing else.
Example: ["machine learning", "data privacy", "cloud computing"]"""),
            ("human", "Extract key topics from:\n\n{text}")
        ])
        
        chain = prompt | self.llm
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({"text": text[:10000]})
        
        try:
            topics = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback parsing
            content = response.content
            topics = [t.strip().strip('"').strip("'") for t in content.strip("[]").split(",")]
        
        metadata = {
            "prompt_tokens": self.count_tokens(text[:10000]),
            "completion_tokens": self.count_tokens(response.content),
            "total_tokens": self.count_tokens(text[:10000]) + self.count_tokens(response.content)
        }
        
        return topics[:10], metadata
    
    async def categorize_document(self, text: str, summary: str) -> Tuple[List[str], Dict]:
        """Categorize document using LangChain. Rate-limited."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert document classifier.
Categorize the document into 1-3 of these categories:
- Business & Finance
- Technology & Software
- Legal & Compliance
- Healthcare & Medical
- Education & Research
- Marketing & Sales
- Human Resources
- Operations & Logistics
- Science & Engineering
- Creative & Design
- Government & Policy
- Other

Return ONLY a JSON array of category strings."""),
            ("human", "Categorize this document:\n\nSummary: {summary}\n\nExcerpt: {text}")
        ])
        
        chain = prompt | self.llm
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({"summary": summary, "text": text[:5000]})
        
        try:
            categories = json.loads(response.content)
        except json.JSONDecodeError:
            categories = ["Other"]
        
        metadata = {
            "prompt_tokens": self.count_tokens(summary + text[:5000]),
            "completion_tokens": self.count_tokens(response.content),
            "total_tokens": self.count_tokens(summary + text[:5000]) + self.count_tokens(response.content)
        }
        
        return categories[:3], metadata
    
    async def analyze_sentiment(self, text: str) -> Tuple[str, float, Dict]:
        """Analyze document sentiment using LangChain. Rate-limited."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze the overall sentiment/tone of this document.
Return a JSON object with:
- sentiment: one of "positive", "negative", "neutral", "mixed"
- score: a number from -1 (very negative) to 1 (very positive)
- explanation: brief explanation of the sentiment

Example: {{"sentiment": "positive", "score": 0.7, "explanation": "The document has an optimistic tone about future growth."}}"""),
            ("human", "Analyze sentiment:\n\n{text}")
        ])
        
        chain = prompt | self.llm
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({"text": text[:8000]})
        
        try:
            result = json.loads(response.content)
            sentiment = result.get("sentiment", "neutral")
            score = result.get("score", 0.0)
        except json.JSONDecodeError:
            sentiment = "neutral"
            score = 0.0
        
        metadata = {
            "prompt_tokens": self.count_tokens(text[:8000]),
            "completion_tokens": self.count_tokens(response.content),
            "total_tokens": self.count_tokens(text[:8000]) + self.count_tokens(response.content)
        }
        
        return sentiment, score, metadata
    
    async def extract_key_insights(self, text: str, summary: str) -> Tuple[Dict, Dict]:
        """Extract key insights using LangChain. Rate-limited."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert document analyst.
Extract key insights from the document including:
1. Key points (main arguments or findings)
2. Named entities (people, organizations, locations)
3. Important dates or numbers
4. Action items or recommendations (if any)

Return a JSON object with:
{{
  "key_points": ["point1", "point2", ...],
  "entities": [{{"name": "Entity Name", "type": "person|org|location|other"}}],
  "important_data": [{{"value": "Q1 2024", "context": "Release date"}}],
  "action_items": ["action1", "action2"]
}}"""),
            ("human", "Extract insights from:\n\nSummary: {summary}\n\nFull text excerpt: {text}")
        ])
        
        chain = prompt | self.llm
        await self._rate_limiter.wait_async()
        response = await chain.ainvoke({"summary": summary, "text": text[:10000]})
        
        try:
            insights = json.loads(response.content)
        except json.JSONDecodeError:
            insights = {
                "key_points": [],
                "entities": [],
                "important_data": [],
                "action_items": []
            }
        
        metadata = {
            "prompt_tokens": self.count_tokens(summary + text[:10000]),
            "completion_tokens": self.count_tokens(response.content),
            "total_tokens": self.count_tokens(summary + text[:10000]) + self.count_tokens(response.content)
        }
        
        return insights, metadata
    
    async def generate_follow_up_questions(
        self, 
        document_context: str, 
        question: str, 
        answer: str
    ) -> List[str]:
        """Generate follow-up questions using LangChain. Rate-limited."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Based on the document context, the user's question, and the answer provided,
suggest 3 relevant follow-up questions the user might want to ask.
Make questions specific and directly related to the document content.
Return ONLY a JSON array of question strings."""),
            ("human", """Document context: {context}

User question: {question}

Answer provided: {answer}

Suggest 3 follow-up questions:""")
        ])
        
        chain = prompt | self.llm
        
        try:
            await self._rate_limiter.wait_async()
            response = await chain.ainvoke({
                "context": document_context[:3000],
                "question": question,
                "answer": answer
            })
            questions = json.loads(response.content)
            return questions[:3]
        except (json.JSONDecodeError, Exception):
            return []


# Singleton instance
ai_service = AIService()
