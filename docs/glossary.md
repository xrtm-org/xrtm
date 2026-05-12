# XRTM glossary

Keep the public vocabulary small:

| Term | Definition |
| --- | --- |
| Workflow | A named forecasting process a user can run. |
| Profile | A saved set of runtime and user settings for running a workflow. |
| Run | One execution of a workflow, producing artifacts and reports. |
| Benchmark | An offline scored evaluation set or suite. |
| Runtime | The backend used by a workflow, such as an OpenAI-compatible endpoint, a coding-agent CLI contract, or the provider-free demo/baseline mode. |
| Report | The human-readable review surface for a run. |

Advanced terms stay behind the product terms:

| Term | Definition |
| --- | --- |
| Blueprint | The machine-readable specification behind a workflow. |
| Graph | The execution structure inside a blueprint. |
| Node | One executable unit in the graph. |
| Agent | A node that reasons, transforms, or decides. It does not have to be an LLM. |
| Tool | A callable capability used by a node or exposed as a node. |
| Memory | Shared state, fact store, or retrieval context used by graph nodes. |

Rule of thumb:

> Every workflow has a blueprint. Every blueprint contains a graph. A graph contains nodes. Some nodes are agents, but nodes may also be tools, models, scorers, routers, aggregators, retrievers, or human gates.
