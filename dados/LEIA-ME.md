# Cost Intelligence – Base de dados fictícia

Todos os dados são **inventados** (projetos, fornecedores, valores). Gerados por `gerar_dados.py` (seed fixa, reprodutível).
Formato dos CSVs: separador `;`, decimal `,`, UTF-8 (padrão pt-BR). Custos reais existem até 30/09/2026.

## Tabelas
| Arquivo | Descrição | Chave |
|---|---|---|
| dim_projetos | 2 projetos fictícios (Atlântico e Pacífico) | projeto_id |
| dim_pacotes | 8 pacotes de trabalho (Engenharia, Fabricação, Instalação...) | pacote_id |
| dim_fornecedores | 31 fornecedores fictícios | fornecedor_id |
| dim_calendario | Datas de 2025 a 2026 | data |
| fato_orcamento | Orçamento mensal por projeto e pacote, até o fim do projeto | projeto_id + pacote_id + mes |
| fato_lancamentos | Notas fiscais / lançamentos de custo reais | lancamento_id |
| fato_aditivos | Aditivos contratuais (valor, status) | aditivo_id |

## Relacionamentos (modelo estrela)
fato_orcamento, fato_lancamentos e fato_aditivos se ligam a dim_projetos (projeto_id) e dim_pacotes (pacote_id).
fato_lancamentos também se liga a dim_fornecedores (fornecedor_id). Datas ligam em dim_calendario.

## Problemas de qualidade INTENCIONAIS (para tratamento de dados e IA)
- ~3% dos lançamentos estão sem `categoria_custo` (a descrição em texto livre permite classificar com IA).
- ~0,8% das notas fiscais estão duplicadas (mesmo nf_numero e valor).
- `status_aprovacao` inclui Pendente e Glosado, que devem ser tratados na análise.
