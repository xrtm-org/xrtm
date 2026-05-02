# Python API Reference

This reference documents the key Python APIs for building with XRTM programmatically.

> **Note**: For provider-free testing (using XRTM without API keys), see the [Provider-Free Testing Guide](../../forecast/docs/provider-free-testing.md).

---

## Overview

XRTM exposes three API layers:

| Layer | Import Path | Use Case |
|-------|-------------|----------|
| **High-Level Assistants** | `from xrtm.forecast import create_forecasting_analyst, create_local_analyst` | Quick start with pre-configured agents |
| **Mid-Level Primitives** | `from xrtm.forecast import Orchestrator, Agent, ModelFactory` | Custom agent workflows and orchestration |
| **Low-Level Providers** | `from xrtm.forecast.providers.inference import InferenceProvider` | Custom provider implementations |

Most developers start with high-level assistants and drop down as needed.

---

## High-Level API: Forecasting Assistants

### Quick Start (Provider-Free)

The fastest way to get started without API keys:

```python
import asyncio
from xrtm.forecast import ForecastingAnalyst
from xrtm.product.providers import DeterministicProvider

async def main():
    # Provider-free backend (deterministic, no API calls)
    provider = DeterministicProvider()
    agent = ForecastingAnalyst(model=provider)
    
    # Run a forecast
    result = await agent.run("Will AGI be announced before 2030?")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Reasoning: {result.reasoning}")

asyncio.run(main())
```

**Key points:**
- `DeterministicProvider()` returns structured forecasts without network calls
- Perfect for learning, testing, and CI/CD pipelines
- See [Provider-Free Testing Guide](../../forecast/docs/provider-free-testing.md) for comprehensive examples

### Cloud-Backed Analyst

Use hosted LLM services (requires API keys):

```python
import asyncio
from xrtm.forecast import create_forecasting_analyst

async def main():
    # Factory creates analyst with specified model
    analyst = create_forecasting_analyst(
        model_id="gemini:gemini-2.0-flash",  # or "openai:gpt-4", etc.
        name="MarketAnalyst"
    )
    
    result = await analyst.run("Will inflation exceed 3% in 2026?")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Model: {result.metadata['model_id']}")

asyncio.run(main())
```

**Supported model prefixes:**
- `gemini:gemini-2.0-flash` (Google Gemini)
- `openai:gpt-4` (OpenAI)
- `openai:llama-3.3-70b-versatile` (via OpenAI-compatible endpoints)

Set API keys via environment:
```bash
export GEMINI_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

### Local/Private Analyst

Run entirely locally with Hugging Face models:

```python
import asyncio
from xrtm.forecast import create_local_analyst

async def main():
    # Load local model (downloads from HF if needed)
    analyst = create_local_analyst(
        model_path="meta-llama/Llama-3-8b-Instruct",
        name="PrivateResearcher"
    )
    
    result = await analyst.run("What is the capital of France?")
    print(f"Output: {result.reasoning}")

asyncio.run(main())
```

**Key points:**
- Air-gapped inference (no external API calls after download)
- Accepts local paths or Hugging Face repo IDs
- Supports quantization: `create_local_analyst(..., quantization="4bit")`

### ForecastingAnalyst Reference

#### Constructor

```python
ForecastingAnalyst(
    model: InferenceProvider,
    name: Optional[str] = None,
    memory: Optional[Memory] = None,
    tools: Optional[List[Tool]] = None
)
```

**Parameters:**
- `model`: Inference provider (from `ModelFactory`, `DeterministicProvider`, etc.)
- `name`: Logical identifier for this agent
- `memory`: Memory system for context retention
- `tools`: External tools the agent can invoke

#### Methods

**`async run(prompt: str) -> ForecastResult`**

Execute a forecasting task.

```python
result = await analyst.run("Will the S&P 500 close above 5,000 by end of 2026?")
```

**Returns:** `ForecastResult` with:
- `confidence`: Float probability (0.0–1.0)
- `reasoning`: String explanation
- `metadata`: Dict with model ID, timestamps, etc.

---

## Mid-Level API: Orchestration and Agents

### Orchestrator

The `Orchestrator` is a state machine engine for multi-step workflows.

```python
import asyncio
from xrtm.forecast import Orchestrator, BaseGraphState

async def step_one(state: BaseGraphState, progress=None):
    state.context["data"] = "processed"
    return "step_two"  # Next node name

async def step_two(state: BaseGraphState, progress=None):
    print(f"Data: {state.context['data']}")
    return None  # End execution

async def main():
    orch = Orchestrator[BaseGraphState]()
    orch.add_node("step_one", step_one)
    orch.add_node("step_two", step_two)
    orch.set_entry_point("step_one")
    
    initial_state = BaseGraphState(subject_id="task_001")
    final_state = await orch.run(initial_state)

asyncio.run(main())
```

#### Key Methods

**`add_node(name: str, func: Callable)`**
Register a node function. Node functions:
- Accept `(state, progress)` arguments
- Return the name of the next node or `None` to stop

**`set_entry_point(name: str)`**
Define where execution starts.

**`async run(state: StateT) -> StateT`**
Execute the graph from the entry point.

### Agent Primitives

For custom agent patterns:

```python
from xrtm.forecast import LLMAgent, ToolAgent, GraphAgent, RoutingAgent

# LLMAgent: Single-step LLM reasoning
agent = LLMAgent(
    model=model_instance,
    system_prompt="You are a forecasting expert."
)

# ToolAgent: Invoke external tools
tool_agent = ToolAgent(tools=[search_tool, data_tool])

# GraphAgent: Multi-node workflow with state
graph_agent = GraphAgent(orchestrator=orch)

# RoutingAgent: Route inputs to different agents
router = RoutingAgent(routes={"finance": finance_agent, "tech": tech_agent})
```

Refer to examples in `forecast/examples/` for detailed usage patterns.

### ModelFactory

Create inference providers from model IDs or configs.

```python
from xrtm.forecast import ModelFactory

# From string identifier
provider = ModelFactory.get_provider(model_id="gemini:gemini-2.0-flash")

# From config object
from xrtm.forecast.providers.inference import OpenAIConfig

config = OpenAIConfig(
    api_key="your-key",
    model_id="gpt-4",
    base_url="https://api.openai.com/v1"
)
provider = ModelFactory.get_provider(config=config)

# Provider-free (deterministic)
from xrtm.product.providers import DeterministicProvider
provider = DeterministicProvider()
```

---

## Low-Level API: Custom Providers

### InferenceProvider Interface

Implement custom inference backends:

```python
from xrtm.forecast.providers.inference import InferenceProvider, ModelResponse
from typing import List, Dict, Any

class MyCustomProvider(InferenceProvider):
    @property
    def model_id(self) -> str:
        return "my-custom-model"
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> ModelResponse:
        # Your inference logic here
        output_text = "..."
        
        return ModelResponse(
            content=output_text,
            model_id=self.model_id,
            usage={"prompt_tokens": 100, "completion_tokens": 50}
        )
```

Use with any agent:
```python
provider = MyCustomProvider()
agent = ForecastingAnalyst(model=provider)
```

### Provider Configs

For built-in providers:

```python
from xrtm.forecast.providers.inference import (
    OpenAIConfig,
    GeminiConfig,
    HFConfig,
    VLLMConfig
)

# OpenAI-compatible
openai_config = OpenAIConfig(
    api_key="sk-...",
    model_id="gpt-4",
    base_url="https://api.openai.com/v1"
)

# Google Gemini
gemini_config = GeminiConfig(
    api_key="...",
    model_id="gemini-2.0-flash"
)

# Hugging Face (local)
hf_config = HFConfig(
    model_path="meta-llama/Llama-3-8b-Instruct",
    quantization="4bit"
)
```

---

## Memory and Context

### Unified Memory

```python
from xrtm.forecast import Memory

memory = Memory()

# Store context
await memory.store("key", {"data": "value"})

# Retrieve context
data = await memory.retrieve("key")

# Use with agent
agent = ForecastingAnalyst(model=provider, memory=memory)
```

XRTM supports multiple memory backends (SQLite KG, Chroma vector store). See `forecast/docs/api/memory.md` for details.

---

## Tools and Skills

### Built-in Skills

```python
from xrtm.forecast import SQLSkill, PandasSkill, tool_registry

# Register skills with agent
agent = ForecastingAnalyst(
    model=provider,
    tools=[SQLSkill(), PandasSkill()]
)
```

### Custom Tools

```python
from xrtm.forecast.providers.tools import tool_registry

@tool_registry.register("search_web")
async def search_web(query: str) -> str:
    """Search the web for information."""
    # Your implementation
    return "search results"

# Use in agent
agent = ForecastingAnalyst(model=provider, tools=[search_web])
```

---

## Runtime and Execution

### AsyncRuntime

For advanced async execution patterns:

```python
from xrtm.forecast import AsyncRuntime

runtime = AsyncRuntime(concurrency_limit=5)

tasks = [
    agent.run("Question 1"),
    agent.run("Question 2"),
    agent.run("Question 3")
]

results = await runtime.execute_batch(tasks)
```

### Temporal Context

Enforce temporal integrity:

```python
from xrtm.forecast import TemporalContext

context = TemporalContext(
    as_of_date="2026-01-01",
    question_close_date="2026-12-31"
)

state = BaseGraphState(subject_id="forecast_001", temporal=context)
```

---

## Telemetry and Auditing

### Audit Trail

```python
from xrtm.forecast import auditor

# Auditor automatically tracks:
# - Inference requests/responses
# - Tool invocations
# - State transitions
# - Performance metrics

# Query audit log
events = auditor.query(subject_id="forecast_001")
```

---

## Common Patterns

### Provider-Free Testing

```python
import asyncio
from xrtm.forecast import ForecastingAnalyst
from xrtm.product.providers import DeterministicProvider

async def test_forecasting_logic():
    """Test without API calls."""
    provider = DeterministicProvider()
    agent = ForecastingAnalyst(model=provider)
    
    result = await agent.run("Test question")
    
    assert 0.0 <= result.confidence <= 1.0
    assert result.reasoning is not None

asyncio.run(test_forecasting_logic())
```

See [Provider-Free Testing Guide](../../forecast/docs/provider-free-testing.md) for comprehensive patterns.

### Local-First Pipeline

```python
import asyncio
from xrtm.forecast import create_local_analyst

async def private_pipeline():
    """Air-gapped forecasting pipeline."""
    analyst = create_local_analyst(
        model_path="meta-llama/Llama-3-8b-Instruct",
        quantization="4bit"  # Reduce memory
    )
    
    questions = [
        "Will the S&P 500 close above 5,000?",
        "Will inflation exceed 3%?"
    ]
    
    for q in questions:
        result = await analyst.run(q)
        print(f"{q}: {result.confidence:.3f}")

asyncio.run(private_pipeline())
```

### Batch Forecasting

```python
import asyncio
from xrtm.forecast import create_forecasting_analyst, AsyncRuntime

async def batch_forecast(questions: list):
    analyst = create_forecasting_analyst(model_id="gemini:gemini-2.0-flash")
    runtime = AsyncRuntime(concurrency_limit=3)
    
    tasks = [analyst.run(q) for q in questions]
    results = await runtime.execute_batch(tasks)
    
    return results

questions = ["Q1", "Q2", "Q3"]
results = asyncio.run(batch_forecast(questions))
```

### Custom Workflow

```python
import asyncio
from xrtm.forecast import Orchestrator, BaseGraphState, ModelFactory

async def research(state: BaseGraphState, progress=None):
    # Gather data
    state.context["data"] = "..."
    return "analyze"

async def analyze(state: BaseGraphState, progress=None):
    # Run analysis
    state.context["result"] = "..."
    return None

async def main():
    orch = Orchestrator[BaseGraphState]()
    orch.add_node("research", research)
    orch.add_node("analyze", analyze)
    orch.set_entry_point("research")
    
    state = BaseGraphState(subject_id="workflow_001")
    final_state = await orch.run(state)

asyncio.run(main())
```

---

## Error Handling

### Retry Logic

Built-in retry for transient failures:

```python
from xrtm.forecast import create_forecasting_analyst

analyst = create_forecasting_analyst(
    model_id="openai:gpt-4",
    max_retries=3,
    retry_delay=1.0
)
```

### Exception Handling

```python
import asyncio
from xrtm.forecast import ForecastingAnalyst
from xrtm.forecast.core.exceptions import InferenceError

async def safe_forecast():
    try:
        result = await agent.run("Question")
    except InferenceError as e:
        print(f"Inference failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(safe_forecast())
```

---

## Performance Optimization

### Caching

Provider-level caching is automatic:

```python
from xrtm.product.providers import DeterministicProvider

provider = DeterministicProvider()

# Repeated calls hit cache
await agent.run("Same question")
await agent.run("Same question")  # Cached

# Inspect cache
cache = provider.cache_snapshot
print(f"Hit rate: {cache['hit_rate']:.2%}")
```

### Concurrency Control

```python
from xrtm.forecast import AsyncRuntime

runtime = AsyncRuntime(
    concurrency_limit=5,  # Max parallel tasks
    timeout=30.0          # Task timeout in seconds
)
```

---

## Integration with Product Shell

Use library APIs alongside CLI:

```python
import asyncio
from xrtm.forecast import ForecastingAnalyst
from xrtm.product.providers import DeterministicProvider

async def library_forecast():
    """Generate forecasts programmatically."""
    provider = DeterministicProvider()
    agent = ForecastingAnalyst(model=provider)
    
    result = await agent.run("Will AGI be announced before 2030?")
    
    # Write to CLI-compatible format
    forecast = {
        "question": "Will AGI be announced before 2030?",
        "probability": result.confidence,
        "reasoning": result.reasoning
    }
    
    # Write to file for CLI inspection
    import json
    with open("forecasts.jsonl", "a") as f:
        f.write(json.dumps(forecast) + "\n")

asyncio.run(library_forecast())
```

Then inspect with CLI:
```bash
xrtm artifacts inspect .
```

---

## API Stability

XRTM follows semantic versioning:

- **High-Level Assistants** (stable): `create_forecasting_analyst`, `ForecastingAnalyst`
- **Mid-Level Primitives** (stable): `Orchestrator`, `ModelFactory`, `Agent`
- **Low-Level Internals** (evolving): Core engine modules may change between minor versions

Pin to a specific version for production:
```bash
pip install xrtm-forecast==0.6.6
```

---

## Integration Examples

For custom wrappers built on these APIs, see the [Integration Examples](../examples/integration/) directory.

These examples are **integration patterns**, not extra built-in XRTM product surfaces. For the shipped CLI path to a first local run, canonical artifacts, provider setup, and monitor lifecycle, see the [Getting Started Guide](getting-started.md) and [Operator Runbook](operator-runbook.md).

- **[Batch Processing](../examples/integration/batch-processing/)** — Bring your own CSV/JSON question list into a reusable Python batch script
- **[FastAPI Service](../examples/integration/fastapi-service/)** — Wrap the library in a sample HTTP service for other applications
- **[Scheduled Monitor](../examples/integration/scheduled-monitor/)** — Build a lightweight Python scheduling/reporting loop; for the shipped monitor lifecycle use the monitor commands from the [Operator Runbook](operator-runbook.md)
- **[Data Export](../examples/integration/data-export/)** — Build custom ETL on top of canonical run directories; for one-off CLI exports use `xrtm runs export` from the [Operator Runbook](operator-runbook.md)

Each example includes working code plus notes about where the pattern differs from the product workflow.

---

## Next Steps

- **Quick Start**: Run provider-free examples in `forecast/examples/providers/provider_free_analyst/`
- **Advanced Workflows**: Explore orchestration patterns in `forecast/examples/core/`
- **Provider-Free Testing**: See [Provider-Free Testing Guide](../../forecast/docs/provider-free-testing.md)
- **CLI Integration**: See [Getting Started Guide](getting-started.md)

---

## API Index

### High-Level
- `create_forecasting_analyst()` - Cloud-backed analyst factory
- `create_local_analyst()` - Local model analyst factory
- `ForecastingAnalyst` - Pre-configured specialist agent

### Mid-Level
- `Orchestrator` - State machine engine
- `ModelFactory` - Provider factory
- `Agent`, `LLMAgent`, `ToolAgent`, `GraphAgent`, `RoutingAgent` - Agent primitives
- `Memory` - Context storage
- `AsyncRuntime` - Async execution
- `BaseGraphState`, `TemporalContext` - State schemas

### Low-Level
- `InferenceProvider`, `ModelResponse` - Provider interfaces
- `OpenAIConfig`, `GeminiConfig`, `HFConfig`, `VLLMConfig` - Provider configs
- `SQLSkill`, `PandasSkill`, `tool_registry` - Tools and skills
- `auditor` - Telemetry and auditing

### Provider-Free
- `DeterministicProvider` - Deterministic mock provider (from `xrtm.product.providers`)
