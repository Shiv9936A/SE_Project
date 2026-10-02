"""FastAPI application entry point."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Requirements Studio API",
    description="Project questionnaire, document ingestion, vector search, and grounded RAG APIs for Requirements Studio.",
    version="0.5.0",
    contact={"name": "Requirements Studio"},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router)


@app.on_event("startup")
async def log_runtime_configuration() -> None:
    llm_model = settings.gemini_model if settings.llm_provider.lower() == "gemini" else settings.llm_model
    logger.info(
        "Language model configuration: provider=%s model=%s fallback_model=%s api_key_configured=%s",
        settings.llm_provider,
        llm_model,
        settings.gemini_fallback_model if settings.llm_provider.lower() == "gemini" else "disabled",
        bool(settings.gemini_api_key if settings.llm_provider.lower() == "gemini" else settings.openai_api_key),
    )
    logger.info(
        "Embedding configuration: provider=%s model=%s chroma_directory=%s chroma_collection=%s",
        settings.embedding_provider,
        settings.embedding_model,
        settings.chroma_persist_directory,
        settings.chroma_collection_name,
    )


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, exc: SQLAlchemyError):
    logger.exception("Database operation failed (exception_type=%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database operation failed."})
