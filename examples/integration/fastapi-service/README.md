# FastAPI Service Integration

HTTP REST API for on-demand forecasting with request validation, async processing, and run history.

## Overview

This example demonstrates how to integrate XRTM into a FastAPI web service, enabling:
- RESTful HTTP API for forecasting requests
- Async processing for concurrent requests
- Request validation with Pydantic models
- Forecast retrieval endpoints backed by an in-memory store
- Swagger/OpenAPI documentation

This is **sample application code**, not a shipped XRTM API server. Use it as a starting point for your own service layer around the XRTM Python package.

## Use Cases

- **Web Applications**: Integrate forecasting into React/Vue/Angular apps
- **Microservices**: Forecasting service in distributed architecture
- **Team Platforms**: Multi-user forecasting with shared infrastructure
- **Mobile Apps**: Backend API for iOS/Android forecast clients

## Quick Start

### 1. Install Dependencies

```bash
pip install xrtm fastapi uvicorn
```

### 2. Start the Service (Provider-Free)

```bash
python app.py
```

This starts a FastAPI server on `http://localhost:8000` using the mock provider (no API keys).

### 3. View API Documentation

Open `http://localhost:8000/docs` in your browser for interactive API documentation.

### 4. Make a Forecast Request

```bash
curl -X POST http://localhost:8000/api/v1/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Will Bitcoin exceed $100k by end of 2027?",
    "resolution_date": "2027-12-31"
  }'
```

Response:
```json
{
  "forecast_id": "fc-1735747200-abc123",
  "question": "Will Bitcoin exceed $100k by end of 2027?",
  "confidence": 0.42,
  "reasoning": "Based on historical volatility...",
  "timestamp": "2026-05-01T12:30:00Z",
  "provider": "mock"
}
```

`forecast_id` values are opaque unique identifiers. Treat them as lookup keys rather than parsing semantics from the suffix.

## API Endpoints

### POST /api/v1/forecast

Create a new forecast.

**Request Body:**
```json
{
  "question": "Will unemployment exceed 5% in 2027?",
  "resolution_date": "2027-12-31",
  "metadata": {
    "user": "analyst@example.com",
    "category": "economics"
  }
}
```

**Response:**
```json
{
  "forecast_id": "fc-1735747200-xyz789",
  "question": "Will unemployment exceed 5% in 2027?",
  "confidence": 0.38,
  "reasoning": "Economic indicators suggest...",
  "timestamp": "2026-05-01T12:30:00Z",
  "provider": "mock",
  "metadata": {
    "user": "analyst@example.com",
    "category": "economics"
  }
}
```

### GET /api/v1/forecast/{forecast_id}

Retrieve a specific forecast by ID.

**Response:**
```json
{
  "forecast_id": "fc-1735747200-xyz789",
  "question": "Will unemployment exceed 5% in 2027?",
  "confidence": 0.38,
  "reasoning": "Economic indicators suggest...",
  "timestamp": "2026-05-01T12:30:00Z",
  "provider": "mock"
}
```

### GET /api/v1/forecasts

List recent forecasts with pagination.

**Query Parameters:**
- `limit` (default: 20): Number of results
- `offset` (default: 0): Pagination offset

**Response:**
```json
{
  "total": 45,
  "limit": 20,
  "offset": 0,
  "forecasts": [...]
}
```

### GET /api/v1/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "provider": "mock",
  "version": "0.3.1"
}
```

## Configuration

### Environment Variables

```bash
# Provider configuration
export XRTM_PROVIDER=mock           # or gemini, openai, local-llm
export XRTM_MODEL=gemini-2.0-flash  # model for cloud providers
export GEMINI_API_KEY=your-key      # API key for cloud providers

# Service configuration
export XRTM_API_HOST=0.0.0.0        # bind address
export XRTM_API_PORT=8000           # port
export XRTM_RUNS_DIR=service-runs   # directory for XRTM runs
```

### Run with Real LLM Provider

```bash
export XRTM_PROVIDER=gemini
export GEMINI_API_KEY=your-key
python app.py
```

## Production Deployment

### With Gunicorn (multiple workers)

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000
```

### With Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t xrtm-api .
docker run -p 8000:8000 -e GEMINI_API_KEY=$GEMINI_API_KEY xrtm-api
```

### Behind Nginx Reverse Proxy

```nginx
upstream xrtm_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name forecasts.example.com;
    
    location /api/ {
        proxy_pass http://xrtm_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Advanced Features

### Request Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/forecast")
@limiter.limit("10/minute")
async def create_forecast(request: Request, ...):
    ...
```

### Authentication

```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.post("/api/v1/forecast")
async def create_forecast(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Validate token
    ...
```

### Background Tasks

```python
from fastapi import BackgroundTasks

async def log_forecast(forecast_id: str):
    # Log to database, analytics, etc.
    ...

@app.post("/api/v1/forecast")
async def create_forecast(background_tasks: BackgroundTasks, ...):
    # Process forecast
    background_tasks.add_task(log_forecast, forecast_id)
    ...
```

## Smoke test

```bash
python app.py &
pid=$!

curl http://localhost:8000/api/v1/health
curl -X POST http://localhost:8000/api/v1/forecast \
  -H "Content-Type: application/json" \
  -d '{"question":"Will AI coding assistants be used by most developers by 2027?"}'

kill "$pid"
```

## Performance

- **Mock provider**: ~10ms per forecast, 100+ req/sec
- **Local LLM**: Varies by model and hardware
- **Cloud providers**: Limited by API rate limits and latency

## Monitoring extension

The example does not ship with Prometheus metrics by default, but you can add them with standard FastAPI middleware:

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

Access metrics at `http://localhost:8000/metrics`.

## Next Steps

- Read the [Integration Examples index](../) to choose other patterns by user job
- Read the [Python API Reference](../../../docs/python-api-reference.md) for the library surfaces used here
- Read the [Operator Runbook](../../../docs/operator-runbook.md) for provider configuration and shipped CLI workflows
- See [Batch Processing](../batch-processing/) for bulk operations
- See [Data Export](../data-export/) for extracting forecast data
- See [Scheduled Monitor](../scheduled-monitor/) for automated pipelines
