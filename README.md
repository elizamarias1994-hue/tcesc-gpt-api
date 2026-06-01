# API Intermediária TCE/SC para GPT

API FastAPI para servir como Action de um GPT jurídico de pesquisa documental no TCE/SC.

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /health`
- `GET /tcesc/municipios`
- `GET /tcesc/unidades-gestoras`
- `GET /tcesc/processo/{numero}`
- `GET /tcesc/prejulgado/{numero}`
- `GET /tcesc/localizar?q=CON 25/00125020 Decisão 492/2026`

## Uso como GPT Action

Publique esta API em Render, Railway, Fly.io ou Cloud Run.
Depois importe o arquivo `openapi.yaml` no construtor do GPT.