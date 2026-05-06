"""FastAPI service for XRTM forecasting.

This service provides a REST API for on-demand forecasting with XRTM.

Usage:
    python app.py

    # With custom provider
    XRTM_PROVIDER=gemini GEMINI_API_KEY=your-key python app.py
"""

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from xrtm.forecast import ForecastingAnalyst

from xrtm.product.providers import DeterministicProvider

# --- Configuration ---

PROVIDER = os.getenv("XRTM_PROVIDER", "mock")
MODEL = os.getenv("XRTM_MODEL")
RUNS_DIR = Path(os.getenv("XRTM_RUNS_DIR", "service-runs"))
HOST = os.getenv("XRTM_API_HOST", "127.0.0.1")
PORT = int(os.getenv("XRTM_API_PORT", "8000"))


# --- Models ---

class ForecastRequest(BaseModel):
    """Request to create a forecast."""
    question: str = Field(..., description="Question to forecast", min_length=10)
    resolution_date: str | None = Field(None, description="Expected resolution date (YYYY-MM-DD)")
    metadata: dict[str, Any] | None = Field(None, description="Optional metadata")


class ForecastResponse(BaseModel):
    """Response from creating a forecast."""
    forecast_id: str
    question: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    timestamp: str
    provider: str
    metadata: dict[str, Any] | None = None


class ForecastListResponse(BaseModel):
    """Response from listing forecasts."""
    total: int
    limit: int
    offset: int
    forecasts: list[ForecastResponse]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    provider: str
    version: str


# --- Storage ---

class ForecastStore:
    """In-memory forecast storage (replace with database in production)."""

    def __init__(self):
        self.forecasts: dict[str, ForecastResponse] = {}
        self.runs_dir = RUNS_DIR
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, forecast: ForecastResponse) -> None:
        """Save a forecast."""
        self.forecasts[forecast.forecast_id] = forecast

    def get(self, forecast_id: str) -> ForecastResponse | None:
        """Retrieve a forecast by ID."""
        return self.forecasts.get(forecast_id)

    def list(self, limit: int = 20, offset: int = 0) -> list[ForecastResponse]:
        """List forecasts with pagination."""
        all_forecasts = list(self.forecasts.values())
        # Sort by timestamp descending
        all_forecasts.sort(key=lambda f: f.timestamp, reverse=True)
        return all_forecasts[offset:offset + limit]

    def count(self) -> int:
        """Count total forecasts."""
        return len(self.forecasts)


# --- Application State ---

class AppState:
    """Application state."""
    analyst: ForecastingAnalyst | None = None
    store: ForecastStore = ForecastStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize analyst
    print(f"Initializing XRTM with provider: {PROVIDER}")

    if PROVIDER == "mock":
        provider = DeterministicProvider()
        app.state.analyst = ForecastingAnalyst(model=provider, name="APIAnalyst")
    else:
        from xrtm.forecast import create_forecasting_analyst
        model_id = f"{PROVIDER}:{MODEL or 'default'}"
        app.state.analyst = create_forecasting_analyst(model_id=model_id, name="APIAnalyst")

    print(f"Service ready on http://{HOST}:{PORT}")
    print(f"API docs available at http://{HOST}:{PORT}/docs")

    yield

    # Shutdown: Cleanup
    print("Shutting down service...")


# --- Application ---

app = FastAPI(
    title="XRTM Forecasting API",
    description="REST API for probabilistic forecasting with XRTM",
    version="0.3.1",
    lifespan=lifespan
)

# CORS middleware for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize store
app.state.store = ForecastStore()


# --- Endpoints ---

@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "service": "XRTM Forecasting API",
        "version": "0.3.1",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        provider=PROVIDER,
        version="0.3.1"
    )


@app.post("/api/v1/forecast", response_model=ForecastResponse, status_code=201)
async def create_forecast(request: ForecastRequest):
    """Create a new forecast."""
    if not app.state.analyst:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        # Generate forecast
        start_time = time.time()
        result = await app.state.analyst.run(request.question)
        duration = time.time() - start_time

        # Create response
        forecast_id = f"fc-{int(time.time())}-{uuid4().hex[:8]}"
        forecast = ForecastResponse(
            forecast_id=forecast_id,
            question=request.question,
            confidence=result.confidence,
            reasoning=result.reasoning,
            timestamp=datetime.now().isoformat(),
            provider=PROVIDER,
            metadata=request.metadata or {}
        )

        # Save to store
        app.state.store.save(forecast)

        print(f"Forecast created: {forecast_id} ({duration:.3f}s)")

        return forecast

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


@app.get("/api/v1/forecast/{forecast_id}", response_model=ForecastResponse)
async def get_forecast(forecast_id: str):
    """Retrieve a forecast by ID."""
    forecast = app.state.store.get(forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return forecast


@app.get("/api/v1/forecasts", response_model=ForecastListResponse)
async def list_forecasts(limit: int = 20, offset: int = 0):
    """List recent forecasts with pagination."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="Offset must be non-negative")

    forecasts = app.state.store.list(limit=limit, offset=offset)
    total = app.state.store.count()

    return ForecastListResponse(
        total=total,
        limit=limit,
        offset=offset,
        forecasts=forecasts
    )


# --- Main ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
