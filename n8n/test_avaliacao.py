"""Testa o script que mede a acurácia da classificação com IA."""
import pandas as pd
import pytest

from n8n.avaliar_classificacao import GABARITO_PADRAO, avaliar, ler_csv, relatorio

GAB = pd.DataFrame({
    "lancamento_id": ["A", "B", "C", "D"],
    "descricao": ["horas", "chapas", "taxas", "diarias"],
    "categoria_real": ["Mão de obra", "Material", "Outros", "Viagens"],
})


def ia(linhas):
    return pd.DataFrame(linhas, columns=["lancamento_id", "categoria_sugerida", "decisao"])


def test_tudo_certo_e_automatico():
    r = avaliar(ia([("A", "Mão de obra", "Aplicar automaticamente"), ("B", "Material", "Aplicar automaticamente"),
                    ("C", "Outros", "Aplicar automaticamente"), ("D", "Viagens", "Aplicar automaticamente")]), GAB)
    assert r["acuracia"] == r["acuracia_automatica"] == r["cobertura_automatica"] == 100.0
    assert r["erros_sem_revisao"] == 0 and len(r["erros"]) == 0


def test_erro_automatico_e_revisao_desnecessaria():
    r = avaliar(ia([("A", "Mão de obra", "Aplicar automaticamente"),
                    ("B", "Serviços", "Aplicar automaticamente"),     # erro que passaria sem revisão
                    ("C", "Outros", "Revisão manual"),               # acerto mandado para revisão
                    ("D", "Equipamentos", "Revisão manual")]), GAB)   # erro, mas foi para revisão
    assert r["acertos"] == 2 and r["acuracia"] == 50.0
    assert r["automaticos"] == 2 and r["acuracia_automatica"] == 50.0
    assert r["erros_sem_revisao"] == 1
    assert r["revisao_manual"] == 2 and r["revisoes_desnecessarias"] == 1


def test_lancamento_que_a_ia_nao_devolveu_conta_como_erro_e_revisao():
    r = avaliar(ia([("A", "Mão de obra", "Aplicar automaticamente")]), GAB)
    assert r["total"] == 4 and r["acertos"] == 1
    assert r["revisao_manual"] == 3 and r["sem_categoria_da_ia"] == 3


def test_ids_repetidos_e_fora_do_gabarito():
    r = avaliar(ia([("A", "Mão de obra", "Aplicar automaticamente"), ("A", "Outros", "Aplicar automaticamente"),
                    ("Z", "Outros", "Aplicar automaticamente")]), GAB)
    assert r["acertos"] == 1            # vale a primeira resposta de A
    assert r["ids_fora_do_gabarito"] == 1


def test_colunas_obrigatorias():
    with pytest.raises(ValueError):
        avaliar(pd.DataFrame({"lancamento_id": ["A"]}), GAB)


def test_ler_csv_com_ponto_e_virgula_ou_virgula(tmp_path):
    (tmp_path / "a.csv").write_text("lancamento_id;categoria_sugerida\nA;Mão de obra\n", encoding="utf-8-sig")
    (tmp_path / "b.csv").write_text("lancamento_id,categoria_sugerida\nA,Mão de obra\n", encoding="utf-8")
    assert ler_csv(tmp_path / "a.csv").loc[0, "categoria_sugerida"] == "Mão de obra"
    assert ler_csv(tmp_path / "b.csv").loc[0, "categoria_sugerida"] == "Mão de obra"


def test_gabarito_real_tem_os_58_lancamentos_e_categorias_validas():
    g = ler_csv(GABARITO_PADRAO)
    assert len(g) == 58 and g["lancamento_id"].is_unique
    assert set(g["categoria_real"]) <= {"Mão de obra", "Material", "Serviços", "Equipamentos", "Viagens", "Outros"}


def test_relatorio_menciona_o_numero_principal():
    texto = relatorio(avaliar(ia([("A", "Mão de obra", "Aplicar automaticamente")]), GAB))
    assert "Acerto entre os automáticos" in texto and "Matriz de confusão" in texto
