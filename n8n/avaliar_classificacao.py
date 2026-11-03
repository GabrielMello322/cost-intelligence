"""Avalia a classificação feita pela IA no n8n contra o gabarito.

Uso (na pasta principal do repositório):
    python n8n/avaliar_classificacao.py caminho/do/classificacao_ia.csv

O gabarito (n8n/gabarito_categorias.csv) guarda a categoria verdadeira dos lançamentos
que ficaram sem categoria nos dados fictícios. Ele existe só para medir a IA e nunca é
enviado a ela.
"""
import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).resolve().parent
GABARITO_PADRAO = PASTA / "gabarito_categorias.csv"


def ler_csv(caminho) -> pd.DataFrame:
    """Lê CSV em UTF-8, com ';' ou ',' como separador (o n8n e o Excel usam os dois)."""
    with open(caminho, encoding="utf-8-sig") as arquivo:
        primeira = arquivo.readline()
    separador = ";" if primeira.count(";") >= primeira.count(",") else ","
    return pd.read_csv(caminho, sep=separador, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def avaliar(classificacao: pd.DataFrame, gabarito: pd.DataFrame) -> dict:
    """Compara a categoria sugerida pela IA com a categoria verdadeira."""
    faltando = {"lancamento_id", "categoria_sugerida", "decisao"} - set(classificacao.columns)
    if faltando:
        raise ValueError(f"O CSV da IA precisa ter as colunas: {', '.join(sorted(faltando))}")

    ia = classificacao.drop_duplicates("lancamento_id", keep="first")
    base = gabarito.merge(ia, on="lancamento_id", how="left", suffixes=("", "_ia"))
    base["categoria_sugerida"] = base["categoria_sugerida"].fillna("")
    base["decisao"] = base["decisao"].fillna("Revisão manual")
    base["acertou"] = base["categoria_sugerida"] == base["categoria_real"]

    automatico = base[base["decisao"] == "Aplicar automaticamente"]
    revisao = base[base["decisao"] != "Aplicar automaticamente"]
    erros = base[~base["acertou"]]
    # erros que passariam direto para o sistema, sem ninguém revisar
    erros_sem_revisao = automatico[~automatico["acertou"]]

    por_tipo = None
    if "tipo" in base.columns:
        por_tipo = base.groupby("tipo")["acertou"].agg(acertos="sum", total="count")
        por_tipo["erros_sem_revisao"] = automatico[~automatico["acertou"]].groupby("tipo").size()
        por_tipo = por_tipo.fillna(0).astype(int)

    return {
        "por_tipo": por_tipo,
        "total": len(base),
        "acertos": int(base["acertou"].sum()),
        "acuracia": _pct(base["acertou"].sum(), len(base)),
        "automaticos": len(automatico),
        "cobertura_automatica": _pct(len(automatico), len(base)),
        "acuracia_automatica": _pct(automatico["acertou"].sum(), len(automatico)),
        "erros_sem_revisao": len(erros_sem_revisao),
        "revisao_manual": len(revisao),
        "revisoes_desnecessarias": int(revisao["acertou"].sum()),
        "sem_categoria_da_ia": int((base["categoria_sugerida"] == "").sum()),
        "ids_fora_do_gabarito": int((~ia["lancamento_id"].isin(gabarito["lancamento_id"])).sum()),
        "erros": erros,
        "matriz": pd.crosstab(base["categoria_real"], base["categoria_sugerida"].replace("", "(vazio)"),
                              rownames=["verdadeira"], colnames=["IA sugeriu"]),
    }


def _pct(parte, total) -> float:
    return round(100 * float(parte) / total, 1) if total else 0.0


def relatorio(r: dict) -> str:
    linhas = [
        "AVALIAÇÃO DA CLASSIFICAÇÃO COM IA",
        "=" * 34,
        f"Lançamentos avaliados:        {r['total']}",
        f"Acertos:                      {r['acertos']} ({r['acuracia']}%)",
        "",
        "Fluxo com revisão humana:",
        f"  Aplicados automaticamente:  {r['automaticos']} ({r['cobertura_automatica']}% do total)",
        f"  Acerto entre os automáticos: {r['acuracia_automatica']}%  <- o número que mais importa",
        f"  Erros que passariam sem revisão: {r['erros_sem_revisao']}",
        f"  Enviados para revisão manual: {r['revisao_manual']} "
        f"(destes, {r['revisoes_desnecessarias']} a IA tinha acertado)",
    ]
    if r["sem_categoria_da_ia"]:
        linhas.append(f"  Sem categoria devolvida pela IA: {r['sem_categoria_da_ia']}")
    if r["ids_fora_do_gabarito"]:
        linhas.append(f"  Ids do CSV que não existem no gabarito: {r['ids_fora_do_gabarito']}")
    if r["por_tipo"] is not None:
        linhas += ["", "Por tipo de caso (acertos / total, erros sem revisão):"]
        for tipo, l in r["por_tipo"].iterrows():
            linhas.append(f"  {tipo:<10} {l['acertos']}/{l['total']}   erros sem revisão: {l['erros_sem_revisao']}")
    linhas += ["", "Matriz de confusão (linhas = verdadeira, colunas = IA):", r["matriz"].to_string()]
    if len(r["erros"]):
        linhas += ["", "Erros:"]
        for _, e in r["erros"].iterrows():
            linhas.append(f"  {e['lancamento_id']}  verdadeira={e['categoria_real']}  IA={e['categoria_sugerida'] or '(vazio)'}"
                          f"  [{e['decisao']}]  {e['descricao']}")
    linhas += ["", "Atenção: os dados são sintéticos e as descrições seguem modelos repetidos; "
                   "em notas fiscais reais a acurácia tende a ser menor."]
    return "\n".join(linhas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classificacao", help="CSV gerado pelo fluxo do n8n (classificacao_ia.csv)")
    ap.add_argument("--gabarito", default=str(GABARITO_PADRAO), help="CSV com a categoria verdadeira")
    args = ap.parse_args(argv)
    print(relatorio(avaliar(ler_csv(args.classificacao), ler_csv(args.gabarito))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
