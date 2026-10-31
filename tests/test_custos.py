"""Testa a lógica de custos contra os números validados no dashboard do Power BI."""
import pytest

from api.custos import CostData, NomeInvalido, normalizar, status_do_desvio

TOLERANCIA = 1.5  # R$, por causa de arredondamentos de exibição no Power BI


@pytest.fixture(scope="module")
def dados():
    return CostData()


def test_duplicatas_removidas(dados):
    assert dados.lancamentos_brutos == 1949
    assert len(dados.lancamentos) == 1934


def test_data_e_mes_de_corte(dados):
    assert dados.data_corte.strftime("%Y-%m-%d") == "2026-09-30"
    assert dados.mes_corte.strftime("%Y-%m-%d") == "2026-09-01"


def test_totais_batem_com_o_power_bi(dados):
    r = dados.resumo()
    assert r["orcado_ate_corte"] == pytest.approx(63_228_077, abs=TOLERANCIA)
    assert r["custo_real"] == pytest.approx(70_056_076, abs=TOLERANCIA)
    assert r["desvio_pct"] == 10.8
    assert r["projecao_custo_final"] == pytest.approx(76_364_663, abs=TOLERANCIA)
    assert r["estouro_projetado"] == pytest.approx(6_864_663, abs=TOLERANCIA)
    assert r["orcamento_final"] == pytest.approx(69_500_000, abs=TOLERANCIA)


def test_totais_por_projeto(dados):
    atl = dados.resumo("Atlântico")
    assert atl["orcado_ate_corte"] == pytest.approx(38_813_510, abs=TOLERANCIA)
    assert atl["custo_real"] == pytest.approx(43_491_264, abs=TOLERANCIA)
    assert atl["desvio_pct"] == 12.1
    assert atl["projecao_custo_final"] == pytest.approx(46_463_262, abs=TOLERANCIA)
    assert atl["estouro_projetado"] == pytest.approx(4_463_262, abs=TOLERANCIA)

    pac = dados.resumo("Pacífico")
    assert pac["orcado_ate_corte"] == pytest.approx(24_414_567, abs=TOLERANCIA)
    assert pac["custo_real"] == pytest.approx(26_564_813, abs=TOLERANCIA)
    assert pac["desvio_pct"] == 8.8
    assert pac["projecao_custo_final"] == pytest.approx(29_901_401, abs=TOLERANCIA)


def test_projecao_total_e_a_soma_dos_pacotes(dados):
    linhas = dados.pacotes_do_projeto()
    soma = sum(linha["projecao_custo_final"] for linha in linhas)
    assert dados.resumo()["projecao_custo_final"] == pytest.approx(soma, abs=1.0)


def test_pacotes_do_atlantico(dados):
    linhas = {l["pacote"]: l for l in dados.pacotes_do_projeto("Atlântico")}
    assert len(linhas) == 8
    fab = linhas["Fabricação"]
    assert fab["orcado_ate_corte"] == pytest.approx(9_240_000, abs=TOLERANCIA)
    assert fab["custo_real"] == pytest.approx(12_344_059, abs=TOLERANCIA)
    assert fab["desvio_pct"] == pytest.approx(33.6, abs=0.05)
    assert fab["status"] == "Crítico"
    assert linhas["Engenharia"]["status"] == "Crítico"
    assert linhas["Gerenciamento"]["status"] == "Dentro do orçamento"
    assert linhas["Instalação"]["status"] == "Atenção"


def test_pior_pacote_vem_primeiro(dados):
    linhas = dados.pacotes_do_projeto("Atlântico")
    assert linhas[0]["pacote"] == "Fabricação"


def test_pacote_encerrado_nao_projeta_estouro_extra(dados):
    # Fabricação (Atlântico) já consumiu todo o orçamento previsto: projeção = custo real.
    fab = next(l for l in dados.pacotes_do_projeto("Atlântico") if l["pacote"] == "Fabricação")
    assert fab["projecao_custo_final"] == pytest.approx(fab["custo_real"], abs=1.0)


def test_nomes_sem_acento_e_maiusculas(dados):
    assert dados.resumo("atlantico")["projeto"] == "Atlântico"
    assert dados.detalhe_pacote("FABRICACAO", "Atlantico")["pacote"] == "Fabricação"


def test_nome_invalido_lista_os_nomes_certos(dados):
    with pytest.raises(NomeInvalido) as erro:
        dados.resumo("Índico")
    assert "Atlântico" in str(erro.value) and "Pacífico" in str(erro.value)
    with pytest.raises(NomeInvalido):
        dados.detalhe_pacote("Marketing")


def test_detalhe_do_pacote(dados):
    d = dados.detalhe_pacote("Fabricação", "Atlântico")
    assert d["status"] == "Crítico"
    assert d["custo_por_categoria"][0]["valor_brl"] >= d["custo_por_categoria"][-1]["valor_brl"]
    assert sum(c["percentual"] for c in d["custo_por_categoria"]) == pytest.approx(100, abs=0.5)
    assert len(d["maiores_lancamentos"]) == 5
    assert len(d["meses_com_maior_estouro"]) == 3
    assert d["evolucao_mensal"][0]["mes"] < d["evolucao_mensal"][-1]["mes"]
    assert all(m["desvio"] <= d["meses_com_maior_estouro"][0]["desvio"] + 0.01 for m in d["evolucao_mensal"])


def test_glosados_ficam_fora_do_custo_real(dados):
    todos = dados.lancamentos
    sem_glosado = todos[todos["status_aprovacao"] != "Glosado"]["valor_brl"].sum()
    assert dados.resumo()["custo_real"] == pytest.approx(sem_glosado, abs=1.0)
    glosados = dados.lancamentos_filtrados(status="glosado", limite=200)
    assert glosados and all(l["status_aprovacao"] == "Glosado" for l in glosados)


def test_lancamentos_sem_categoria(dados):
    r = dados.sem_categoria()
    assert r["total"] == int(dados.lancamentos["categoria_custo"].isna().sum())
    assert r["total"] == len(r["lancamentos"]) <= 100
    assert "Material" in r["categorias_validas"]
    assert all(l["descricao"] for l in r["lancamentos"])


def test_aditivos(dados):
    todos = dados.aditivos_filtrados()
    assert len(todos) == 24
    aprovados = dados.aditivos_filtrados(status="aprovado")
    assert all(a["status"] == "Aprovado" for a in aprovados)


def test_status_do_desvio_nos_limites():
    assert status_do_desvio(15.01) == "Crítico"
    assert status_do_desvio(15.0) == "Atenção"
    assert status_do_desvio(5.01) == "Atenção"
    assert status_do_desvio(5.0) == "Dentro do orçamento"
    assert status_do_desvio(-20) == "Dentro do orçamento"
    assert status_do_desvio(None) == "Dentro do orçamento"


def test_normalizar():
    assert normalizar("  Fabricação ") == "fabricacao"
