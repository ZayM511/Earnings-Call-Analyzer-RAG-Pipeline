# Voyage Embeddings — Reference

Use Voyage AI for embeddings. Get an API key at voyageai.com and set it as `VOYAGE_API_KEY`.

**Important:** the official `voyageai` Python SDK does not import on Python 3.14 (pydantic-v1 + `min_items` issue in `multimodal_embeddings`). This project uses Voyage's REST API directly. See `src/embed/voyage_rest_client.py`.

## Which model

| Model | Dimensions | Context | Use when |
|---|---|---|---|
| `voyage-finance-2` | 1024 | 32K tokens | **This project's default.** Domain-tuned for finance. Outperforms general embeddings on earnings-call language. |
| `voyage-3-large` | 1024 | 32K tokens | General-purpose, strongest non-domain model. Use as the A/B comparison baseline. |
| `voyage-3` | 1024 | 32K tokens | If cost matters more than accuracy. Roughly 75% the quality of `voyage-3-large` at lower price. |
| `voyage-3-lite` | 512 | 32K tokens | Fast and cheap. For dev and smoke tests. |
| `voyage-code-3` | 1024 | 32K tokens | Code-specific. Not relevant here. |

The Earnings Call project uses **`voyage-finance-2`**. Earnings calls are saturated with finance terminology (free cash flow, operating leverage, gross margin, capex, guidance) where a domain-tuned model meaningfully outperforms a general one. Expect a measurable recall@5 lift over `voyage-3-large` on this corpus — capture that in Braintrust as one of the three README experiments.

## Free tier (as of 2026)

- General-purpose models (`voyage-3-large`, `voyage-3`, `voyage-3-lite`): 200M tokens lifetime.
- Domain models (`voyage-finance-2`, `voyage-code-3`): **50M tokens lifetime per model.**

For this project, embedding ~6000 chunks at ~500 tokens each (raw) plus the contextual prefix (~50 extra tokens) = ~3.3M tokens — about 6.5% of the finance-model free tier. Headroom is plenty.

## REST API call shape

The voyageai SDK is unavailable on Python 3.14, so use REST directly:

```python
import os
import requests

def embed_batch(
    texts: list[str],
    model: str = "voyage-finance-2",
    input_type: str = "document",  # "document" for ingestion, "query" at retrieve time
) -> list[list[float]]:
    response = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={"input": texts, "model": model, "input_type": input_type},
        timeout=60,
    )
    response.raise_for_status()
    return [item["embedding"] for item in response.json()["data"]]
```

Two important details:

1. **`input_type` matters.** Voyage models are asymmetric: documents and queries get embedded slightly differently to improve retrieval. Use `"document"` at ingest, `"query"` at retrieval. Forgetting to switch costs roughly 5–10% recall.
2. **Batching.** Up to 128 texts per call, up to 320K total tokens. Larger batches are cheaper per token and dramatically faster.

## Batching pattern

```python
def embed_chunks(
    chunks: list[str],
    model: str = "voyage-finance-2",
    batch_size: int = 128,
) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        out.extend(embed_batch(batch, model=model, input_type="document"))
    return out
```

Add token counting upstream if any individual chunk could exceed 32K tokens. For this project's 600-token-ceiling chunks, this is never the case.

## Retry pattern

The Voyage API is reliable but transient 429s and 5xxs happen. Wrap calls with exponential backoff:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.HTTPError, requests.Timeout)),
)
def embed_with_retry(batch, model, input_type):
    return embed_batch(batch, model=model, input_type=input_type)
```

Inside `embed_batch`, treat HTTP 429 and 5xx as retryable; treat 4xx (other than 429) as a real error and don't retry.

## Reranker

Voyage also ships rerankers (`rerank-2`, `rerank-2-lite`), but this project uses **Cohere Rerank 3.5** instead because it has slightly better latency at the top of the retrieval set. Either is defensible; the choice is a project preference, not a quality verdict.

## Cost (as of 2026)

- `voyage-finance-2`: $0.12 per 1M tokens
- `voyage-3-large`: $0.18 per 1M tokens
- `voyage-3`: $0.06 per 1M tokens

Embedding 6000 chunks at ~550 tokens each = ~3.3M tokens = ~$0.40 with `voyage-finance-2`. One-time cost.

## Anti-patterns

- **Calling the API one chunk at a time.** Batch by 128.
- **Mixing input types.** Always set `input_type="document"` for ingest and `"query"` at retrieval.
- **Embedding raw chunks without contextual-retrieval prefix.** See `chunking-strategies.md` — prepending the source/quarter/speaker context before embedding is one of the largest free wins.
- **Storing embeddings without a content hash.** Add a `content_sha256` column so you can detect when the underlying transcript text changed and the embedding is stale.
- **Embedding with `voyage-3-lite` for production.** It's a dev model. Use `voyage-finance-2` for the real corpus.
- **Importing the voyageai SDK on Python 3.14.** It will error at import time. The REST client is the workaround; don't try to "fix" it by pinning to an older voyageai.
