"""Testa os endpoints HTTP. Exige fastapi e httpx (pip install -r api/requirements-dev.txt)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

cliente = TestClient(app)


def test_saude():
    r = cliente.get("/saude")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "ok"
    assert "Atlântico" in corpo["projetos"]
    assert "Fabricação" in corpo["pacotes"]


def test_resumo_total_e_por_projeto():
    total = cliente.get("/resumo").json()
    assert total["projeto"] == "Todos os projetos"
    assert total["projecao_custo_final"] == pytest.approx(76_364_663, abs=1.5)
    assert len(total["por_projeto"]) == 2

    atl = cliente.get("/resumo", params={"projeto": "Atlântico"}).json()
    assert atl["desvio_pct"] == 12.1
    assert "Fabricação" in atl["pacotes_criticos"]


def test_pacotes_ordenados_por_desvio():
    linhas = cliente.get("/pacotes", params={"projeto": "atlantico"}).json()
    assert linhas[0]["pacote"] == "Fabricação"
    assert linhas[0]["status"] == "Crítico"


def test_detalhe_do_pacote_com_acento_na_url():
    r = cliente.get("/pacotes/Fabricação", params={"projeto": "Atlântico"})
    assert r.status_code == 200
    assert r.json()["pacote"] == "Fabricação"
    assert cliente.get("/pacotes/fabricacao").status_code == 200


def test_nome_invalido_devolve_404_com_ajuda():
    r = cliente.get("/resumo", params={"projeto": "Índico"})
    assert r.status_code == 404
    assert "Atlântico" in r.json()["detail"]


def test_lancamentos_e_limite():
    linhas = cliente.get("/lancamentos", params={"pacote": "Fabricação", "limite": 5}).json()
    assert len(linhas) == 5
    assert linhas[0]["valor_brl"] >= linhas[-1]["valor_brl"]
    assert cliente.get("/lancamentos", params={"limite": 0}).status_code == 422


def test_sem_categoria_e_aditivos():
    sem = cliente.get("/lancamentos/sem-categoria").json()
    assert sem["total"] > 0 and sem["lancamentos"][0]["descricao"]
    assert len(cliente.get("/aditivos").json()) == 24
