"""API do Cost Intelligence.

Responde perguntas sobre custos de projetos com as mesmas regras do dashboard no
Power BI. Foi pensada para ser usada por automações (n8n), agentes de IA e apps.

Para rodar, na pasta principal do repositório:
    python -m uvicorn api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs
"""
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from .custos import CostData, NomeInvalido

app = FastAPI(
    title="Cost Intelligence API",
    description=(
        "Consulta de custos de projetos de engenharia (dados fictícios): orçado vs. custo real, "
        "desvios, projeção do custo final, lançamentos e aditivos. Os nomes de projeto e pacote "
        "aceitam maiúsculas/minúsculas e não exigem acento (ex.: 'atlantico', 'fabricacao')."
    ),
    version="0.1.0",
)

dados = CostData()


def _responder(funcao, *args, **kwargs):
    """Executa uma consulta e transforma nome inválido em erro 404 com a lista de nomes certos."""
    try:
        return funcao(*args, **kwargs)
    except NomeInvalido as erro:
        raise HTTPException(status_code=404, detail=str(erro))


@app.get("/saude", summary="Verifica se a API está no ar e lista os nomes válidos")
def saude():
    return {
        "status": "ok",
        "data_corte": dados.data_corte.strftime("%Y-%m-%d"),
        "projetos": dados.nomes_projetos,
        "pacotes": dados.nomes_pacotes,
    }


@app.get("/resumo", summary="Totais de custo de um projeto, ou dos dois juntos")
def resumo(projeto: Optional[str] = Query(None, description="Nome do projeto. Vazio = todos.")):
    """Orçado até o corte, custo real, desvio, projeção do custo final e estouro projetado."""
    return _responder(dados.resumo, projeto)


@app.get("/pacotes", summary="Desvio de cada pacote de trabalho, do pior para o melhor")
def pacotes(projeto: Optional[str] = Query(None, description="Nome do projeto. Vazio = todos.")):
    """Uma linha por projeto e pacote, com status Crítico, Atenção ou Dentro do orçamento."""
    return _responder(dados.pacotes_do_projeto, projeto)


@app.get("/pacotes/{pacote}", summary="Detalhe de um pacote para explicar o desvio")
def pacote_detalhe(
    pacote: str,
    projeto: Optional[str] = Query(None, description="Nome do projeto. Vazio = todos."),
):
    """Custo por categoria, meses com maior estouro, maiores lançamentos, fornecedores e aditivos."""
    return _responder(dados.detalhe_pacote, pacote, projeto)


@app.get("/lancamentos", summary="Lançamentos de custo (notas fiscais), do maior valor para o menor")
def lancamentos(
    projeto: Optional[str] = Query(None, description="Nome do projeto."),
    pacote: Optional[str] = Query(None, description="Nome do pacote."),
    status: Optional[str] = Query(None, description="Aprovado, Pendente ou Glosado."),
    limite: int = Query(20, ge=1, le=200, description="Quantidade máxima de linhas."),
):
    return _responder(dados.lancamentos_filtrados, projeto, pacote, status, limite)


@app.get("/lancamentos/sem-categoria", summary="Lançamentos sem categoria de custo (para classificar com IA)")
def lancamentos_sem_categoria(limite: int = Query(100, ge=1, le=500)):
    """Entrada do workflow de classificação: traz a descrição de cada lançamento e as categorias válidas."""
    return dados.sem_categoria(limite)


@app.get("/aditivos", summary="Aditivos contratuais")
def aditivos(
    projeto: Optional[str] = Query(None, description="Nome do projeto."),
    pacote: Optional[str] = Query(None, description="Nome do pacote."),
    status: Optional[str] = Query(None, description="Aprovado, Em análise ou Rejeitado."),
):
    return _responder(dados.aditivos_filtrados, projeto, pacote, status)
