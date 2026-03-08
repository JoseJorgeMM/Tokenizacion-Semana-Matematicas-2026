"""
Taller IA · Backend FastAPI
Cadena de Markov (bigramas) + corpus persistente via Vercel KV
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, json, re, random
from typing import Optional

# ── Vercel KV (Redis) client ──────────────────────────────────────────────────
# Vercel inyecta KV_REST_API_URL y KV_REST_API_TOKEN automáticamente
# cuando conectas una KV store en el dashboard de Vercel.
import httpx

KV_URL   = os.getenv("KV_REST_API_URL", "")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN", "")
CORPUS_KEY = "taller:corpus"

async def kv_get(key: str) -> Optional[list]:
    """Lee una lista del store KV de Vercel."""
    if not KV_URL:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{KV_URL}/get/{key}",
            headers={"Authorization": f"Bearer {KV_TOKEN}"},
            timeout=5,
        )
    if r.status_code == 200:
        data = r.json()
        raw = data.get("result")
        if raw:
            return json.loads(raw)
    return None

async def kv_set(key: str, value: list) -> bool:
    """Escribe una lista en el store KV de Vercel."""
    if not KV_URL:
        return False
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{KV_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {KV_TOKEN}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"value": json.dumps(value)}),
            timeout=5,
        )
    return r.status_code == 200

# ── In-memory fallback (desarrollo local sin KV) ──────────────────────────────
_local_corpus: list[str] = []

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Taller IA · API",
    description="Backend del taller 'Abriendo la caja negra de la IA generativa'",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción puedes restringir a tu dominio Vercel
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Servir frontend estático ──────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"status": "API activa", "docs": "/docs"}

# ── Modelos Pydantic ──────────────────────────────────────────────────────────
class PhraseIn(BaseModel):
    phrase: str

class GenerateIn(BaseModel):
    seed: str
    length: int = 8

# ── Helpers: tokenización y modelo ───────────────────────────────────────────
def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[.,;:!?()\"\"'']", "", text)
    return [w for w in text.split() if w]

def build_model(corpus: list[str]) -> dict:
    """Construye la cadena de Markov bigrama a partir del corpus."""
    model: dict[str, dict[str, int]] = {}
    for phrase in corpus:
        words = tokenize(phrase)
        for i in range(len(words) - 1):
            cur, nxt = words[i], words[i + 1]
            model.setdefault(cur, {})
            model[cur][nxt] = model[cur].get(nxt, 0) + 1
    return model

def compute_probs(model: dict) -> dict:
    """Convierte conteos a probabilidades condicionales."""
    probs = {}
    for word, nexts in model.items():
        total = sum(nexts.values())
        probs[word] = {
            nxt: {"count": cnt, "total": total, "prob": round(cnt / total, 4)}
            for nxt, cnt in sorted(nexts.items(), key=lambda x: -x[1])
        }
    return probs

def weighted_choice(nexts: dict[str, int]) -> str:
    """Selección aleatoria ponderada por frecuencia."""
    words  = list(nexts.keys())
    counts = list(nexts.values())
    total  = sum(counts)
    r = random.random() * total
    for w, c in zip(words, counts):
        r -= c
        if r <= 0:
            return w
    return words[-1]

async def get_corpus() -> list[str]:
    """Obtiene corpus desde KV o memoria local."""
    kv_data = await kv_get(CORPUS_KEY)
    if kv_data is not None:
        return kv_data
    return _local_corpus

async def save_corpus(corpus: list[str]):
    """Guarda corpus en KV y en memoria local."""
    global _local_corpus
    _local_corpus = corpus
    await kv_set(CORPUS_KEY, corpus)

# ═══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/corpus")
async def get_corpus_endpoint():
    """Devuelve el corpus actual y estadísticas básicas."""
    corpus = await get_corpus()
    all_words = []
    for p in corpus:
        all_words.extend(tokenize(p))
    vocab = sorted(set(all_words))
    return {
        "phrases": corpus,
        "stats": {
            "total_phrases": len(corpus),
            "total_words": len(all_words),
            "vocab_size": len(vocab),
            "vocab": vocab,
        }
    }

@app.post("/api/corpus/add")
async def add_phrase(body: PhraseIn):
    """Agrega una frase al corpus y lo persiste."""
    phrase = body.phrase.strip()
    if not phrase:
        raise HTTPException(400, "La frase no puede estar vacía.")
    if len(tokenize(phrase)) < 3:
        raise HTTPException(400, "La frase debe tener al menos 3 palabras.")
    if len(phrase) > 500:
        raise HTTPException(400, "La frase es demasiado larga (máx. 500 caracteres).")

    corpus = await get_corpus()
    if phrase in corpus:
        raise HTTPException(409, "Esta frase ya existe en el corpus.")

    corpus.append(phrase)
    await save_corpus(corpus)
    return {"ok": True, "total_phrases": len(corpus)}

@app.delete("/api/corpus/{index}")
async def delete_phrase(index: int):
    """Elimina una frase del corpus por índice."""
    corpus = await get_corpus()
    if index < 0 or index >= len(corpus):
        raise HTTPException(404, "Índice fuera de rango.")
    removed = corpus.pop(index)
    await save_corpus(corpus)
    return {"ok": True, "removed": removed}

@app.delete("/api/corpus")
async def reset_corpus():
    """Limpia todo el corpus."""
    await save_corpus([])
    return {"ok": True}

@app.get("/api/model/tokens")
async def get_tokens(phrase: str):
    """Tokeniza una frase y devuelve la lista de tokens con sus IDs."""
    corpus = await get_corpus()
    all_words = []
    for p in corpus:
        all_words.extend(tokenize(p))
    vocab = sorted(set(all_words))
    vocab_index = {w: i for i, w in enumerate(vocab)}

    tokens = tokenize(phrase)
    return {
        "tokens": [
            {"word": t, "id": vocab_index.get(t, -1)}
            for t in tokens
        ],
        "vocab_size": len(vocab),
    }

@app.get("/api/model/probabilities")
async def get_probabilities(word: Optional[str] = None):
    """
    Devuelve la tabla de probabilidades condicionales.
    Si se pasa `word`, filtra solo las entradas de esa palabra.
    """
    corpus = await get_corpus()
    if not corpus:
        raise HTTPException(400, "El corpus está vacío. Agrega frases primero.")

    markov = build_model(corpus)
    probs  = compute_probs(markov)

    if word:
        word = word.lower()
        if word not in probs:
            raise HTTPException(404, f"'{word}' no está en el vocabulario.")
        return {"word": word, "successors": probs[word]}

    return {"model": probs}

@app.post("/api/model/generate")
async def generate_text(body: GenerateIn):
    """
    Genera texto usando la cadena de Markov.
    Devuelve el texto generado y el log de cada decisión (para mostrar en el taller).
    """
    corpus = await get_corpus()
    if not corpus:
        raise HTTPException(400, "El corpus está vacío.")

    seed = body.seed.lower().strip()
    length = max(3, min(body.length, 30))

    markov = build_model(corpus)

    if seed not in markov:
        raise HTTPException(
            404,
            f"'{seed}' no está en el vocabulario o no tiene sucesores. "
            f"Palabras disponibles: {sorted(markov.keys())[:10]}"
        )

    current = seed
    words   = [current]
    steps   = []

    for _ in range(length - 1):
        nexts = markov.get(current)
        if not nexts:
            break
        total   = sum(nexts.values())
        chosen  = weighted_choice(nexts)
        prob    = round(nexts[chosen] / total, 4)
        steps.append({
            "from":   current,
            "to":     chosen,
            "count":  nexts[chosen],
            "total":  total,
            "prob":   prob,
            "prob_pct": f"{prob*100:.1f}%",
            "fraction": f"{nexts[chosen]}/{total}",
        })
        words.append(chosen)
        current = chosen

    return {
        "seed":  seed,
        "text":  " ".join(words),
        "words": words,
        "steps": steps,
    }

@app.get("/api/model/vocabulary")
async def get_vocabulary():
    """Devuelve vocabulario completo con índices."""
    corpus = await get_corpus()
    all_words = []
    for p in corpus:
        all_words.extend(tokenize(p))
    vocab = sorted(set(all_words))
    return {
        "vocab": [{"word": w, "id": i} for i, w in enumerate(vocab)],
        "size": len(vocab),
    }

@app.get("/api/health")
async def health():
    return {"status": "ok", "kv_configured": bool(KV_URL)}
