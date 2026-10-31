"""Regras de custo do Cost Intelligence.

Espelha as medidas DAX do dashboard no Power BI, para que a API, o agente e o
dashboard mostrem sempre os mesmos números:

- Custo Real: soma dos lançamentos, sem os Glosados e sem notas duplicadas.
- Orçado até o Corte: orçamento até o mês da última data com custo registrado.
- Projeção do custo final: calculada pacote a pacote
  (custo real + orçamento restante x desvio acumulado do pacote) e depois somada.
- Status: Crítico (desvio > 15%), Atenção (> 5%) ou Dentro do orçamento.

Os dados são fictícios e ficam na pasta `dados/` (CSV com ';' e decimal ',').
"""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PASTA_PADRAO = Path(os.environ.get("COST_DATA_DIR", Path(__file__).resolve().parent.parent / "dados"))
CHAVE = ["projeto_id", "pacote_id"]
STATUS_VALIDOS = ["Aprovado", "Pendente", "Glosado"]


class NomeInvalido(ValueError):
    """Projeto, pacote ou status que não existe na base."""


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar nomes ('Atlântico' == 'atlantico')."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def status_do_desvio(desvio_pct: Optional[float]) -> str:
    """Mesma regra da medida 'Status do Pacote' do Power BI."""
    if desvio_pct is None or pd.isna(desvio_pct):
        return "Dentro do orçamento"
    if desvio_pct > 15:
        return "Crítico"
    if desvio_pct > 5:
        return "Atenção"
    return "Dentro do orçamento"


def _registros(df: pd.DataFrame) -> list:
    """DataFrame -> lista de dicts em tipos simples (datas como texto, NaN como None)."""
    saida = df.copy()
    for coluna in saida.columns:
        if pd.api.types.is_datetime64_any_dtype(saida[coluna]):
            saida[coluna] = saida[coluna].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_float_dtype(saida[coluna]):
            saida[coluna] = saida[coluna].round(2)
    saida = saida.astype(object).where(saida.notna(), None)
    return saida.to_dict(orient="records")


def _numero(valor) -> float:
    return round(float(valor), 2)


class CostData:
    """Carrega os CSVs e responde às perguntas de custo."""

    def __init__(self, pasta: Optional[os.PathLike] = None):
        self.pasta = Path(pasta) if pasta else PASTA_PADRAO

        def ler(nome: str, **kwargs) -> pd.DataFrame:
            return pd.read_csv(self.pasta / nome, sep=";", decimal=",", encoding="utf-8-sig", **kwargs)

        self.projetos = ler("dim_projetos.csv")
        self.pacotes = ler("dim_pacotes.csv")
        fornecedores = ler("dim_fornecedores.csv")[["fornecedor_id", "fornecedor"]]
        self.orcamento = ler("fato_orcamento.csv", parse_dates=["mes"])

        lancamentos = ler("fato_lancamentos.csv", parse_dates=["data_lancamento"])
        self.lancamentos_brutos = len(lancamentos)
        # Notas duplicadas têm lancamento_id diferente; por isso ele fica fora da comparação.
        colunas = [c for c in lancamentos.columns if c != "lancamento_id"]
        lancamentos = lancamentos.drop_duplicates(subset=colunas).reset_index(drop=True)
        self.lancamentos = (
            lancamentos.merge(self.projetos[["projeto_id", "projeto"]], on="projeto_id", how="left")
            .merge(self.pacotes[["pacote_id", "pacote"]], on="pacote_id", how="left")
            .merge(fornecedores, on="fornecedor_id", how="left")
        )

        aditivos = ler("fato_aditivos.csv", parse_dates=["data"])
        self.aditivos = aditivos.merge(self.projetos[["projeto_id", "projeto"]], on="projeto_id", how="left").merge(
            self.pacotes[["pacote_id", "pacote"]], on="pacote_id", how="left"
        )

        self.data_corte = self.lancamentos["data_lancamento"].max()
        self.mes_corte = self.data_corte.replace(day=1)

    # ------------------------------------------------------------------ nomes
    @property
    def nomes_projetos(self) -> list:
        return self.projetos["projeto"].tolist()

    @property
    def nomes_pacotes(self) -> list:
        return self.pacotes["pacote"].tolist()

    def _ids_projeto(self, projeto: Optional[str]) -> list:
        if not projeto:
            return self.projetos["projeto_id"].tolist()
        achado = self.projetos[self.projetos["projeto"].map(normalizar) == normalizar(projeto)]
        if achado.empty:
            raise NomeInvalido(f"Projeto '{projeto}' não existe. Projetos válidos: {', '.join(self.nomes_projetos)}.")
        return achado["projeto_id"].tolist()

    def _id_pacote(self, pacote: Optional[str]) -> Optional[str]:
        if not pacote:
            return None
        achado = self.pacotes[self.pacotes["pacote"].map(normalizar) == normalizar(pacote)]
        if achado.empty:
            raise NomeInvalido(f"Pacote '{pacote}' não existe. Pacotes válidos: {', '.join(self.nomes_pacotes)}.")
        return achado["pacote_id"].iloc[0]

    def _nome_projeto(self, projeto: Optional[str]) -> str:
        if not projeto:
            return "Todos os projetos"
        ids = self._ids_projeto(projeto)
        return self.projetos.loc[self.projetos["projeto_id"] == ids[0], "projeto"].iloc[0]

    # --------------------------------------------------------------- métricas
    def tabela_pacotes(self, projeto: Optional[str] = None, pacote: Optional[str] = None) -> pd.DataFrame:
        """Uma linha por projeto e pacote, com as mesmas medidas do dashboard."""
        ids_projeto = self._ids_projeto(projeto)
        id_pacote = self._id_pacote(pacote)

        orc = self.orcamento[self.orcamento["projeto_id"].isin(ids_projeto)]
        lanc = self.lancamentos[
            self.lancamentos["projeto_id"].isin(ids_projeto) & (self.lancamentos["status_aprovacao"] != "Glosado")
        ]
        if id_pacote:
            orc = orc[orc["pacote_id"] == id_pacote]
            lanc = lanc[lanc["pacote_id"] == id_pacote]

        orcado_corte = orc[orc["mes"] <= self.mes_corte].groupby(CHAVE)["valor_orcado_brl"].sum()
        orcamento_final = orc.groupby(CHAVE)["valor_orcado_brl"].sum()
        custo_real = lanc.groupby(CHAVE)["valor_brl"].sum()

        t = pd.concat(
            [
                orcado_corte.rename("orcado_ate_corte"),
                custo_real.rename("custo_real"),
                orcamento_final.rename("orcamento_final"),
            ],
            axis=1,
        ).fillna(0.0)
        t = t.reset_index()

        t["desvio"] = t["custo_real"] - t["orcado_ate_corte"]
        t["desvio_pct"] = np.where(t["orcado_ate_corte"] != 0, t["desvio"] / t["orcado_ate_corte"] * 100, np.nan)
        fator = np.where(t["orcado_ate_corte"] != 0, t["custo_real"] / t["orcado_ate_corte"].replace(0, np.nan), 1.0)
        fator = np.nan_to_num(fator, nan=1.0)
        restante = t["orcamento_final"] - t["orcado_ate_corte"]
        t["projecao_custo_final"] = t["custo_real"] + restante * fator
        t["estouro_projetado"] = t["projecao_custo_final"] - t["orcamento_final"]
        t["status"] = t["desvio_pct"].map(status_do_desvio)

        t = t.merge(self.projetos[["projeto_id", "projeto"]], on="projeto_id").merge(
            self.pacotes[["pacote_id", "pacote"]], on="pacote_id"
        )
        colunas = [
            "projeto",
            "pacote",
            "orcado_ate_corte",
            "custo_real",
            "desvio",
            "desvio_pct",
            "orcamento_final",
            "projecao_custo_final",
            "estouro_projetado",
            "status",
        ]
        return t[colunas].sort_values("desvio_pct", ascending=False, na_position="last").reset_index(drop=True)

    @staticmethod
    def _somar(t: pd.DataFrame) -> dict:
        """Totais de uma tabela de pacotes (a projeção é a soma pacote a pacote)."""
        orcado = t["orcado_ate_corte"].sum()
        real = t["custo_real"].sum()
        final = t["orcamento_final"].sum()
        projecao = t["projecao_custo_final"].sum()
        desvio = real - orcado
        desvio_pct = desvio / orcado * 100 if orcado else None
        return {
            "orcado_ate_corte": _numero(orcado),
            "custo_real": _numero(real),
            "desvio": _numero(desvio),
            "desvio_pct": None if desvio_pct is None else round(float(desvio_pct), 1),
            "orcamento_final": _numero(final),
            "projecao_custo_final": _numero(projecao),
            "estouro_projetado": _numero(projecao - final),
            "status": status_do_desvio(desvio_pct),
        }

    # ------------------------------------------------------------- consultas
    def resumo(self, projeto: Optional[str] = None) -> dict:
        t = self.tabela_pacotes(projeto)
        ids = self._ids_projeto(projeto)
        lanc = self.lancamentos[self.lancamentos["projeto_id"].isin(ids)]
        adit = self.aditivos[self.aditivos["projeto_id"].isin(ids)]
        resultado = {
            "projeto": self._nome_projeto(projeto),
            "data_corte": self.data_corte.strftime("%Y-%m-%d"),
            **self._somar(t),
            "pacotes_criticos": t.loc[t["status"] == "Crítico", "pacote"].tolist() if projeto else None,
            "lancamentos": int(len(lanc)),
            "lancamentos_sem_categoria": int(lanc["categoria_custo"].isna().sum()),
            "aditivos_aprovados_brl": _numero(adit.loc[adit["status"] == "Aprovado", "valor_brl"].sum()),
        }
        if not projeto:
            resultado["por_projeto"] = [
                {"projeto": nome, **self._somar(t[t["projeto"] == nome])} for nome in self.nomes_projetos
            ]
            resultado.pop("pacotes_criticos")
        return resultado

    def pacotes_do_projeto(self, projeto: Optional[str] = None) -> list:
        return _registros(self.tabela_pacotes(projeto))

    def detalhe_pacote(self, pacote: str, projeto: Optional[str] = None) -> dict:
        """Tudo que ajuda a explicar o desvio de um pacote."""
        id_pacote = self._id_pacote(pacote)
        ids = self._ids_projeto(projeto)
        t = self.tabela_pacotes(projeto, pacote)
        nome_pacote = self.pacotes.loc[self.pacotes["pacote_id"] == id_pacote, "pacote"].iloc[0]

        lanc = self.lancamentos[
            self.lancamentos["projeto_id"].isin(ids)
            & (self.lancamentos["pacote_id"] == id_pacote)
            & (self.lancamentos["status_aprovacao"] != "Glosado")
        ].copy()
        total = lanc["valor_brl"].sum()

        por_categoria = (
            lanc.assign(categoria=lanc["categoria_custo"].fillna("Sem categoria"))
            .groupby("categoria")["valor_brl"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        por_categoria["percentual"] = por_categoria["valor_brl"] / total * 100 if total else 0.0

        orc = self.orcamento[
            self.orcamento["projeto_id"].isin(ids)
            & (self.orcamento["pacote_id"] == id_pacote)
            & (self.orcamento["mes"] <= self.mes_corte)
        ]
        orcado_mes = orc.groupby("mes")["valor_orcado_brl"].sum().rename("orcado")
        lanc["mes"] = lanc["data_lancamento"].dt.to_period("M").dt.to_timestamp()
        real_mes = lanc.groupby("mes")["valor_brl"].sum().rename("real")
        por_mes = pd.concat([orcado_mes, real_mes], axis=1).fillna(0.0).sort_index()
        por_mes["desvio"] = por_mes["real"] - por_mes["orcado"]
        por_mes = por_mes.reset_index()
        piores_meses = por_mes.sort_values("desvio", ascending=False).head(3)
        por_mes["mes"] = por_mes["mes"].dt.strftime("%Y-%m")
        piores_meses = piores_meses.assign(mes=piores_meses["mes"].dt.strftime("%Y-%m"))

        maiores = lanc.sort_values("valor_brl", ascending=False).head(5)[
            ["lancamento_id", "data_lancamento", "fornecedor", "descricao", "categoria_custo", "valor_brl", "status_aprovacao"]
        ]
        fornecedores = (
            lanc.groupby("fornecedor")["valor_brl"].sum().sort_values(ascending=False).head(3).reset_index()
        )

        adit = self.aditivos[self.aditivos["projeto_id"].isin(ids) & (self.aditivos["pacote_id"] == id_pacote)]
        aditivos = adit.sort_values("data")[["aditivo_id", "projeto", "data", "descricao", "valor_brl", "status"]]

        return {
            "pacote": nome_pacote,
            "projeto": self._nome_projeto(projeto),
            "data_corte": self.data_corte.strftime("%Y-%m-%d"),
            **self._somar(t),
            "custo_por_categoria": _registros(por_categoria),
            "meses_com_maior_estouro": _registros(piores_meses),
            "evolucao_mensal": _registros(por_mes),
            "maiores_lancamentos": _registros(maiores),
            "principais_fornecedores": _registros(fornecedores),
            "aditivos": _registros(aditivos),
            "aditivos_aprovados_brl": _numero(adit.loc[adit["status"] == "Aprovado", "valor_brl"].sum()),
        }

    def lancamentos_filtrados(
        self,
        projeto: Optional[str] = None,
        pacote: Optional[str] = None,
        status: Optional[str] = None,
        limite: int = 20,
    ) -> list:
        ids = self._ids_projeto(projeto)
        id_pacote = self._id_pacote(pacote)
        df = self.lancamentos[self.lancamentos["projeto_id"].isin(ids)]
        if id_pacote:
            df = df[df["pacote_id"] == id_pacote]
        if status:
            valido = [s for s in STATUS_VALIDOS if normalizar(s) == normalizar(status)]
            if not valido:
                raise NomeInvalido(f"Status '{status}' não existe. Status válidos: {', '.join(STATUS_VALIDOS)}.")
            df = df[df["status_aprovacao"] == valido[0]]
        colunas = [
            "lancamento_id",
            "data_lancamento",
            "projeto",
            "pacote",
            "fornecedor",
            "descricao",
            "categoria_custo",
            "valor_brl",
            "status_aprovacao",
        ]
        return _registros(df.sort_values("valor_brl", ascending=False).head(limite)[colunas])

    def sem_categoria(self, limite: int = 100) -> dict:
        """Lançamentos sem categoria: a entrada do workflow de classificação com IA."""
        df = self.lancamentos[self.lancamentos["categoria_custo"].isna()]
        colunas = ["lancamento_id", "projeto", "pacote", "fornecedor", "descricao", "valor_brl", "status_aprovacao"]
        return {
            "total": int(len(df)),
            "categorias_validas": ["Mão de obra", "Material", "Serviços", "Equipamentos", "Viagens", "Outros"],
            "lancamentos": _registros(df.sort_values("lancamento_id").head(limite)[colunas]),
        }

    def aditivos_filtrados(
        self, projeto: Optional[str] = None, pacote: Optional[str] = None, status: Optional[str] = None
    ) -> list:
        ids = self._ids_projeto(projeto)
        id_pacote = self._id_pacote(pacote)
        df = self.aditivos[self.aditivos["projeto_id"].isin(ids)]
        if id_pacote:
            df = df[df["pacote_id"] == id_pacote]
        if status:
            df = df[df["status"].map(normalizar) == normalizar(status)]
        colunas = ["aditivo_id", "projeto", "pacote", "data", "descricao", "valor_brl", "status"]
        return _registros(df.sort_values("data")[colunas])
