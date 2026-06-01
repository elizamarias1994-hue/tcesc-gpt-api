from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx, re
from bs4 import BeautifulSoup

app = FastAPI(
    title="API Intermediária TCE/SC para GPT",
    version="0.1.0",
    description="Localiza documentos públicos do TCE/SC por processo, prejulgado, decisão, resolução e termo de busca."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TCE_BASE = "https://www.tcesc.tc.br"
CONSULTA_BASE = "https://consulta.tce.sc.gov.br"
SERVICOS_BASE = "https://servicos.tcesc.tc.br"

class SearchResult(BaseModel):
    status: str
    tipo: str | None = None
    identificador: str | None = None
    titulo: str | None = None
    url: str | None = None
    fonte: str | None = None
    observacao: str | None = None

class SearchResponse(BaseModel):
    consulta: str
    resultados: list[SearchResult]
    pendencias: list[str] = Field(default_factory=list)

def normalize_process_number(s: str) -> str:
    return re.sub(r"\D", "", s or "")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tcesc/municipios")
async def municipios():
    url = f"{SERVICOS_BASE}/endpoints-portal-transparencia/municipios.php"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

@app.get("/tcesc/unidades-gestoras")
async def unidades_gestoras():
    url = f"{SERVICOS_BASE}/endpoints-portal-transparencia/unidades-gestoras.php"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

@app.get("/tcesc/prejulgado/{numero}", response_model=SearchResult)
async def prejulgado(numero: int):
    # Padrão público observado para PDFs de prejulgados:
    # https://consulta.tce.sc.gov.br/RelatoriosDecisao/ConsultaPrejulgado/{processo}_{prejulgado}.pdf
    # Como o código do processo nem sempre é inferível, a API retorna busca orientada.
    return SearchResult(
        status="depende_consulta",
        tipo="prejulgado",
        identificador=str(numero),
        fonte="TCE/SC - Pesquisa de Prejulgados",
        url="https://virtual.tce.sc.gov.br/pwa/#/prejulgados",
        observacao="O número do prejulgado não basta para montar o PDF direto em todos os casos. Consultar a pesquisa oficial de prejulgados."
    )

@app.get("/tcesc/processo/{numero}", response_model=SearchResponse)
async def processo(numero: str):
    n = normalize_process_number(numero)
    if len(n) < 8:
        raise HTTPException(400, "Número de processo inválido ou insuficiente.")
    resultados = [
        SearchResult(
            status="consulta_manual",
            tipo="processo",
            identificador=numero,
            fonte="Consulta de processos do TCE/SC",
            url="https://servicos.tcesc.tc.br/processo",
            observacao="Use o número do processo na consulta oficial. Esta API evita inventar URLs quando o endpoint não estiver documentado."
        ),
        SearchResult(
            status="busca_auxiliar",
            tipo="busca_web_restrita",
            identificador=numero,
            fonte="Busca restrita ao domínio oficial",
            url=f"https://www.google.com/search?q=site%3Atce.sc.gov.br+OR+site%3Aconsulta.tce.sc.gov.br+%22{numero}%22",
            observacao="Fallback para localizar PDFs de votos, decisões e relatórios já indexados."
        )
    ]
    return SearchResponse(
        consulta=numero,
        resultados=resultados,
        pendencias=["Mapear endpoint público específico de consulta processual, caso o TCE/SC disponibilize documentação oficial."]
    )

@app.get("/tcesc/localizar", response_model=SearchResponse)
async def localizar(q: str = Query(..., description="Termo, número de processo, decisão, resolução ou prejulgado")):
    resultados = []
    pendencias = []
    # Identifica padrões básicos
    processos = re.findall(r"\b(?:CON|PNO|REP|DEN|TCE|RLA|REC|LCC|PAP)?\s*@?\s*\d{2}/\d{7,8}\b", q, flags=re.I)
    prejulgados = re.findall(r"prejulgado\s*(?:n[ºo.]*)?\s*(\d{1,5})", q, flags=re.I)
    decisoes = re.findall(r"decis[aã]o\s*(?:n[ºo.]*)?\s*(\d{1,5}/\d{4})", q, flags=re.I)
    resolucoes = re.findall(r"resolu[cç][aã]o\s*(?:n[ºo.]*)?\s*(?:TC[- ]*)?(\d{1,5}/\d{4})", q, flags=re.I)

    for p in processos:
        resultados.append(SearchResult(
            status="consulta_manual",
            tipo="processo",
            identificador=p.strip(),
            fonte="Consulta de processos do TCE/SC",
            url="https://servicos.tcesc.tc.br/processo",
            observacao="Consultar oficialmente pelo número do processo."
        ))

    for pr in prejulgados:
        resultados.append(SearchResult(
            status="depende_consulta",
            tipo="prejulgado",
            identificador=pr,
            fonte="Pesquisa de Prejulgados do TCE/SC",
            url="https://virtual.tce.sc.gov.br/pwa/#/prejulgados",
            observacao="Validar redação atual no cadastro oficial de prejulgados."
        ))

    for d in decisoes:
        resultados.append(SearchResult(
            status="referencia_extraida",
            tipo="decisao",
            identificador=d,
            fonte="TCE/SC",
            url=None,
            observacao="Número de decisão extraído; localizar pelo processo ou DOTC-e."
        ))

    for r in resolucoes:
        resultados.append(SearchResult(
            status="referencia_extraida",
            tipo="resolucao",
            identificador=r,
            fonte="Legislação TCE/SC",
            url="https://leis.org",
            observacao="Conferir em legislação oficial do TCE/SC."
        ))

    if not resultados:
        pendencias.append("Nenhum identificador estruturado foi extraído; refinar a consulta com número do processo, decisão, resolução ou prejulgado.")
        resultados.append(SearchResult(
            status="busca_auxiliar",
            tipo="busca_web_restrita",
            identificador=q,
            fonte="Busca restrita ao TCE/SC",
            url=f"https://www.google.com/search?q=site%3Atcesc.tc.br+OR+site%3Aconsulta.tce.sc.gov.br+%22{q}%22",
            observacao="Fallback para pesquisa textual em fontes oficiais indexadas."
        ))

    return SearchResponse(consulta=q, resultados=resultados, pendencias=pendencias)