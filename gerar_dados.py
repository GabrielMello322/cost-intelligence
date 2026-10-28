"""
Cost Intelligence - gerador de dados FICTÍCIOS de controle de custos.

Simula dois projetos de engenharia (Atlântico e Pacífico) com orçamento mensal,
lançamentos de custo (notas fiscais), fornecedores e aditivos contratuais.
Todos os nomes, valores e fornecedores são inventados. Nenhum dado real.

Uso: python gerar_dados.py
Saída: arquivos CSV na pasta ./dados (separador ';' e decimal ',', padrão pt-BR)
"""
import os
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
DATA_CORTE = pd.Timestamp("2026-09-30")  # custos reais existem até este mês
OUT = "dados"
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- dimensões
projetos = pd.DataFrame([
    {"projeto_id": "PRJ01", "projeto": "Atlântico", "inicio": "2025-01-01", "duracao_meses": 24, "orcamento_total_brl": 42_000_000},
    {"projeto_id": "PRJ02", "projeto": "Pacífico",  "inicio": "2025-07-01", "duracao_meses": 18, "orcamento_total_brl": 27_500_000},
])

# (id, nome, % do orçamento, início relativo, fim relativo, multiplicador médio de estouro)
pacotes_cfg = [
    ("PAC01", "Engenharia",          0.12, 0.00, 0.50, 1.12),
    ("PAC02", "Gerenciamento",       0.10, 0.00, 1.00, 1.03),
    ("PAC03", "Suprimentos",         0.18, 0.10, 0.60, 1.06),
    ("PAC04", "Fabricação",          0.22, 0.20, 0.75, 1.15),
    ("PAC05", "Logística",           0.08, 0.35, 0.85, 1.08),
    ("PAC06", "Instalação",          0.20, 0.55, 0.95, 1.10),
    ("PAC07", "Comissionamento",     0.06, 0.80, 1.00, 1.00),
    ("PAC08", "Qualidade e HSE",     0.04, 0.00, 1.00, 0.97),
]
pacotes = pd.DataFrame(pacotes_cfg, columns=["pacote_id", "pacote", "peso", "ini", "fim", "mult"])

fornecedores_por_pacote = {
    "PAC01": ["Alfa Engenharia Consultiva", "Núcleo Projetos Técnicos", "Vetor Simulações Estruturais", "Prisma Engenharia"],
    "PAC02": ["Gestão Integrada Ltda", "Horizonte Consultoria em Projetos", "Pilar Planejamento"],
    "PAC03": ["Comercial Aço Forte", "Distribuidora Ômega Industrial", "Cabos e Conexões Brasil", "Válvulas Meridional", "Suprimentos Delta"],
    "PAC04": ["Metalúrgica Norte-Sul", "Caldeiraria Atlas", "Estruturas Marítimas Boreal", "Soldagem Premium", "Usinagem Rocha & Filhos"],
    "PAC05": ["TransMar Logística", "Rota Segura Transportes", "Porto Express Agenciamento", "Cargas Pesadas Itaúna"],
    "PAC06": ["Operações Offshore Tritão", "Mergulho Técnico Abissal", "Içamentos Colossus", "Embarcações Netuno"],
    "PAC07": ["Teste & Partida Serviços", "Comissiona Engenharia", "Instrumentação Sigma"],
    "PAC08": ["Segura Inspeções", "Laudos Técnicos Veritas", "Treinamentos HSE Brasil"],
}
forn_rows, k = [], 1
for pid, nomes in fornecedores_por_pacote.items():
    for n in nomes:
        forn_rows.append({"fornecedor_id": f"FOR{k:03d}", "fornecedor": n, "pacote_principal_id": pid})
        k += 1
fornecedores = pd.DataFrame(forn_rows)

# ---------------------------------------------------------------- orçamento mensal
orc_rows, plano = [], {}
for _, p in projetos.iterrows():
    ini = pd.Timestamp(p["inicio"])
    meses = pd.date_range(ini, periods=p["duracao_meses"], freq="MS")
    n = len(meses)
    for _, pk in pacotes.iterrows():
        s, e = int(round(pk["ini"] * n)), max(int(round(pk["fim"] * n)), int(round(pk["ini"] * n)) + 2)
        e = min(e, n)
        t = np.arange(n)
        w = np.zeros(n)
        janela = (t >= s) & (t < e)
        if pk["pacote_id"] in ("PAC02", "PAC08"):
            w[janela] = 1.0
        else:
            w[janela] = np.sin(np.pi * (t[janela] - s + 0.5) / (e - s))
        w = w / w.sum()
        total_pacote = p["orcamento_total_brl"] * pk["peso"]
        for m, val in zip(meses, w * total_pacote):
            orc_rows.append({"projeto_id": p["projeto_id"], "pacote_id": pk["pacote_id"],
                             "mes": m.date().isoformat(), "valor_orcado_brl": round(val, 2)})
        plano[(p["projeto_id"], pk["pacote_id"])] = (meses, w * total_pacote)
orcamento = pd.DataFrame(orc_rows)

# ---------------------------------------------------------------- lançamentos (notas fiscais)
categorias_por_pacote = {
    "PAC01": (["Mão de obra", "Serviços", "Outros"], [0.7, 0.25, 0.05]),
    "PAC02": (["Mão de obra", "Serviços", "Viagens", "Outros"], [0.6, 0.2, 0.1, 0.1]),
    "PAC03": (["Material", "Serviços", "Outros"], [0.8, 0.12, 0.08]),
    "PAC04": (["Material", "Mão de obra", "Serviços", "Equipamentos"], [0.45, 0.3, 0.15, 0.1]),
    "PAC05": (["Serviços", "Equipamentos", "Outros"], [0.7, 0.2, 0.1]),
    "PAC06": (["Equipamentos", "Mão de obra", "Serviços", "Viagens"], [0.4, 0.3, 0.2, 0.1]),
    "PAC07": (["Serviços", "Mão de obra", "Equipamentos"], [0.5, 0.35, 0.15]),
    "PAC08": (["Serviços", "Mão de obra", "Outros"], [0.5, 0.3, 0.2]),
}
modelos_desc = {
    "Mão de obra": ["Horas técnicas equipe - medição {n}", "Alocação de equipe {mes}", "HH especialistas referente a {mes}", "Mobilização de pessoal campo medição {n}"],
    "Material": ["Chapas de aço estrutural lote {n}", "Cabos e conectores NF {nf}", "Fornecimento de tubulação e conexões lote {n}", "Material de consumo para fabricação NF {nf}"],
    "Serviços": ["Serviço de inspeção e ensaios NF {nf}", "Consultoria especializada medição {n}", "Serviços de soldagem e tratamento NF {nf}", "Assessoria técnica ref. {mes}"],
    "Equipamentos": ["Locação de guindaste período {n}", "Locação de equipamento de içamento NF {nf}", "Equipamentos de teste e medição NF {nf}"],
    "Viagens": ["Passagens e hospedagem equipe campo", "Deslocamento de equipe técnica {mes}", "Diárias e transporte terrestre NF {nf}"],
    "Outros": ["Despesas diversas conforme NF {nf}", "Ajuste administrativo ref. {mes}", "Taxas e licenças NF {nf}"],
}

# choques realistas de custo (projeto, pacote, mês relativo inicial, mês relativo final, acréscimo)
choques = {
    ("PRJ01", "PAC04"): (8, 11, 0.28),   # alta do preço do aço
    ("PRJ01", "PAC01"): (6, 14, 0.15),   # mudanças de escopo na engenharia
    ("PRJ02", "PAC06"): (9, 12, 0.22),   # atrasos por condições de mar
    ("PRJ02", "PAC05"): (4, 7, 0.18),    # congestionamento portuário
}

lanc_rows, nf_seq = [], 4000
for _, p in projetos.iterrows():
    for _, pk in pacotes.iterrows():
        meses, orc_mensal = plano[(p["projeto_id"], pk["pacote_id"])]
        cats, probs = categorias_por_pacote[pk["pacote_id"]]
        forn_ids = fornecedores.loc[fornecedores.pacote_principal_id == pk["pacote_id"], "fornecedor_id"].tolist()
        for i, (m, orc) in enumerate(zip(meses, orc_mensal)):
            if orc <= 0 or m > DATA_CORTE:
                continue
            fator = pk["mult"] + 0.004 * i * (1 if pk["pacote_id"] in ("PAC01", "PAC04") else 0)
            ch = choques.get((p["projeto_id"], pk["pacote_id"]))
            if ch and ch[0] <= i <= ch[1]:
                fator += ch[2]
            real = orc * fator * rng.lognormal(0, 0.07)
            n_lanc = int(rng.poisson(8)) + 3
            partes = rng.dirichlet(np.ones(n_lanc)) * real
            dias_mes = m.days_in_month
            for valor in partes:
                nf_seq += int(rng.integers(1, 9))
                cat = rng.choice(cats, p=probs)
                desc = rng.choice(modelos_desc[cat]).format(
                    n=int(rng.integers(1, 12)), nf=nf_seq, mes=m.strftime("%m/%Y"))
                r = rng.random()
                status = "Aprovado" if r < 0.90 else ("Pendente" if r < 0.97 else "Glosado")
                lanc_rows.append({
                    "projeto_id": p["projeto_id"], "pacote_id": pk["pacote_id"],
                    "fornecedor_id": rng.choice(forn_ids),
                    "data_lancamento": (m + pd.Timedelta(days=int(rng.integers(0, dias_mes)))).date().isoformat(),
                    "nf_numero": nf_seq, "descricao": desc, "categoria_custo": cat,
                    "valor_brl": round(float(valor), 2), "status_aprovacao": status,
                })

lancamentos = pd.DataFrame(lanc_rows)

# sujeira intencional (para treinar tratamento de dados e classificação com IA)
idx_sem_cat = lancamentos.sample(frac=0.03, random_state=1).index
lancamentos.loc[idx_sem_cat, "categoria_custo"] = np.nan                    # ~3% sem categoria
duplicadas = lancamentos.sample(frac=0.008, random_state=2).copy()          # ~0,8% NFs duplicadas
lancamentos = pd.concat([lancamentos, duplicadas], ignore_index=True)
lancamentos = lancamentos.sort_values(["data_lancamento", "projeto_id"]).reset_index(drop=True)
lancamentos.insert(0, "lancamento_id", [f"LAN{i:05d}" for i in range(1, len(lancamentos) + 1)])

# ---------------------------------------------------------------- aditivos contratuais
adit_modelos = [
    ("PAC01", "Revisão de escopo de projeto básico solicitada pelo cliente"),
    ("PAC04", "Reajuste de preço de aço estrutural conforme índice"),
    ("PAC06", "Extensão de campanha offshore por janela meteorológica"),
    ("PAC05", "Armazenagem adicional por atraso de embarque"),
    ("PAC03", "Substituição de fornecedor de válvulas especiais"),
    ("PAC07", "Testes adicionais exigidos pela certificadora"),
]
adit_rows = []
for i in range(1, 25):
    p = projetos.iloc[int(rng.integers(0, 2))]
    pac, desc = adit_modelos[int(rng.integers(0, len(adit_modelos)))]
    ini = pd.Timestamp(p["inicio"])
    data = ini + pd.Timedelta(days=int(rng.integers(30, 600)))
    if data > DATA_CORTE:
        data = DATA_CORTE - pd.Timedelta(days=int(rng.integers(1, 60)))
    adit_rows.append({
        "aditivo_id": f"ADT{i:03d}", "projeto_id": p["projeto_id"], "pacote_id": pac,
        "data": data.date().isoformat(), "descricao": desc,
        "valor_brl": round(float(rng.uniform(150_000, 1_800_000)), 2),
        "status": rng.choice(["Aprovado", "Em análise", "Rejeitado"], p=[0.55, 0.3, 0.15]),
    })
aditivos = pd.DataFrame(adit_rows).sort_values("data").reset_index(drop=True)

# ---------------------------------------------------------------- calendário
cal = pd.DataFrame({"data": pd.date_range("2025-01-01", "2026-12-31", freq="D")})
cal["ano"] = cal.data.dt.year
cal["mes_num"] = cal.data.dt.month
cal["ano_mes"] = cal.data.dt.strftime("%Y-%m")
cal["trimestre"] = "T" + cal.data.dt.quarter.astype(str)
cal["data"] = cal.data.dt.date.astype(str)

# ---------------------------------------------------------------- salvar
def salvar(df, nome):
    df.to_csv(os.path.join(OUT, nome), sep=";", decimal=",", index=False, encoding="utf-8-sig")

salvar(projetos, "dim_projetos.csv")
salvar(pacotes[["pacote_id", "pacote"]], "dim_pacotes.csv")
salvar(fornecedores, "dim_fornecedores.csv")
salvar(cal, "dim_calendario.csv")
salvar(orcamento, "fato_orcamento.csv")
salvar(lancamentos, "fato_lancamentos.csv")
salvar(aditivos, "fato_aditivos.csv")

# ---------------------------------------------------------------- resumo
print("Linhas:", {"orcamento": len(orcamento), "lancamentos": len(lancamentos), "aditivos": len(aditivos)})
orc_ate_corte = orcamento[pd.to_datetime(orcamento.mes) <= DATA_CORTE].groupby(["projeto_id", "pacote_id"]).valor_orcado_brl.sum()
real = lancamentos.groupby(["projeto_id", "pacote_id"]).valor_brl.sum()
resumo = pd.concat([orc_ate_corte, real], axis=1)
resumo["desvio_%"] = ((resumo.valor_brl / resumo.valor_orcado_brl - 1) * 100).round(1)
print(resumo.round(0))
