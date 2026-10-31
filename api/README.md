# API de custos

Responde perguntas sobre os custos dos projetos com **as mesmas regras do dashboard no Power BI**. É a camada que o agente de IA e o app usam para consultar os dados.

## Como rodar

Na pasta principal do repositório (a que contém `dados/`, `api/` e `tests/`):

```bash
pip install -r api/requirements-dev.txt
python -m pytest
python -m uvicorn api.main:app --reload
```

Depois abra <http://127.0.0.1:8000/docs>: a documentação é interativa e permite testar cada endpoint pelo navegador.

## Endpoints

| Endpoint | O que responde |
|---|---|
| `GET /saude` | Se a API está no ar, a data de corte e os nomes válidos de projetos e pacotes |
| `GET /resumo?projeto=` | Orçado até o corte, custo real, desvio, projeção do custo final e estouro projetado |
| `GET /pacotes?projeto=` | Desvio de cada pacote, do pior para o melhor, com status Crítico, Atenção ou Dentro do orçamento |
| `GET /pacotes/{pacote}?projeto=` | Tudo para explicar o desvio: custo por categoria, meses com maior estouro, maiores lançamentos, fornecedores e aditivos |
| `GET /lancamentos?projeto=&pacote=&status=&limite=` | Lançamentos (notas fiscais), do maior valor para o menor |
| `GET /lancamentos/sem-categoria` | Lançamentos sem categoria, com a descrição e as categorias válidas (entrada da classificação com IA) |
| `GET /aditivos?projeto=&pacote=&status=` | Aditivos contratuais |

Os nomes aceitam maiúsculas e minúsculas e não exigem acento: `atlantico` e `fabricacao` funcionam. Um nome inexistente devolve erro 404 com a lista dos nomes válidos, o que ajuda um agente de IA a corrigir a própria chamada.

Exemplo: `GET /pacotes/Fabricação?projeto=Atlântico`

## Regras de negócio (iguais às medidas DAX)

- **Custo real:** soma dos lançamentos sem os **Glosados**; os **Pendentes** entram. Notas duplicadas são removidas (1.949 linhas viram 1.934).
- **Orçado até o corte:** orçamento até o mês da última data com custo registrado (set/2026).
- **Desvio:** custo real menos orçado até o corte. **Status:** Crítico acima de 15%, Atenção acima de 5%.
- **Projeção do custo final:** calculada pacote a pacote (custo real + orçamento restante x desvio acumulado do pacote) e somada. O total sempre fecha com a soma dos pacotes.

## Testes

`tests/test_custos.py` confere a lógica contra os números validados no Power BI (por exemplo, projeção total de R$ 76.364.663 e Fabricação do Atlântico em +33,6%). `tests/test_api.py` testa os endpoints HTTP.

Para apontar para outra pasta de dados, defina a variável de ambiente `COST_DATA_DIR`.
