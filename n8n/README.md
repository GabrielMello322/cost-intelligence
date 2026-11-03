# Fase 2: classificação de lançamentos com IA (n8n + Gemini)

Automação que pega os lançamentos de custo **sem categoria**, pede a uma IA (Gemini) uma categoria para cada um e **só aplica sozinho o que tem confiança alta**. O resto vai para revisão humana. É a Fase 2 do projeto [Cost Intelligence](../README.md); a entrada vem da [API de custos](../api/README.md).

> Todos os dados são fictícios.

## Como funciona

```
Gatilho manual
   -> Buscar lançamentos sem categoria     (GET na API de custos: 58 lançamentos)
   -> Montar pedido para o Gemini          (instruções + categorias válidas + lançamentos)
   -> Classificar com Gemini               (categoria, confiança e justificativa por lançamento)
   -> Validar respostas da IA              (confere tudo e decide: aplicar ou revisar)
   -> Convert to File                      (classificacao_ia.csv)
```

Cada nó de código tem comentários explicando o que faz. Os fluxos exportados estão na pasta:

| Arquivo | O que é |
|---|---|
| `workflow_classificar_lancamentos.json` | Fluxo principal: lê os lançamentos da API |
| `workflow_teste_dificil.json` | Mesmo fluxo, mas lê 30 casos difíceis escritos à mão em vez da API |
| `gabarito_categorias.csv` | Categoria verdadeira dos 58 lançamentos (só para medir a IA; nunca é enviada a ela) |
| `gabarito_dificil.csv` | Categoria verdadeira dos 30 casos difíceis |
| `classificacao_ia.csv`, `classificacao_dificil.csv` | Saídas reais das duas execuções |
| `avaliar_classificacao.py` | Compara a saída da IA com o gabarito e imprime o relatório |

## Decisões de projeto

- **Saída estruturada:** o Gemini é obrigado a responder em JSON com um esquema fixo, e a categoria só pode ser uma das seis válidas.
- **Não confiar na IA:** mesmo com o esquema, o nó de validação confere se todo id existe, aparece uma vez só e tem categoria e confiança válidas. Qualquer problema vai para revisão manual.
- **IA com revisão humana:** confiança de 0,8 ou mais é aplicada automaticamente; abaixo disso, vai para `Revisão manual`. O limiar de 0,8 foi definido de antemão, não ajustado nos resultados.
- **Defesa contra prompt injection:** as descrições são tratadas como dado, e não como instrução. O esquema limita o que a IA pode devolver e a validação confere o resultado. Dois casos do teste difícil tentam enganar a IA.
- **Segredos fora do código:** a chave da API fica na área *Credentials* do n8n. Os fluxos exportados guardam só o nome da credencial.
- **Um pedido só:** os 58 lançamentos cabem em um único pedido (cerca de 8 mil tokens no total).

## Resultados

Modelo: `gemini-3.5-flash-lite`.

| | Lançamentos | Acertos | Aplicados automaticamente | Acerto entre os automáticos | Erros sem revisão |
|---|---|---|---|---|---|
| Base do projeto | 58 | 58 (100%) | 57 | 100% | 0 |
| Teste difícil | 30 | 28 (93,3%) | 27 | 96,3% | 1 |

**Teste difícil, por tipo de caso:** claros 12/12, de fronteira 11/12, vagos 2/3, abreviado 1/1, tentativas de injeção 2/2.

**Análise dos erros do teste difícil:**
- `TST025`, "Frete aéreo urgente de peça sobressalente": a IA classificou como *Viagens* com confiança alta, e o lançamento seria aplicado sem revisão. Pela definição, Viagens é transporte de **equipe**, e frete de peça é *Serviços*. A mesma IA acertou o frete rodoviário (`TST012`), então é uma inconsistência.
- `TST023`, nota única com mobilização, passagens e locação: a IA errou, mas a confiança ficou baixa e o lançamento foi corretamente para revisão manual.

## Limitações

- **Os 100% da base são otimistas.** Os dados são sintéticos e as descrições seguem poucos modelos repetidos, e as definições do prompt foram escritas olhando para eles. Em notas fiscais reais a acurácia tende a ser menor.
- **O teste difícil é pequeno** (30 casos, escritos por mim). Os rótulos dos casos de fronteira são julgamentos meus. O resultado mostra **comportamento**, e não uma acurácia estatisticamente precisa.
- **O prompt ainda não foi ajustado** com base nos erros. Se for, esse conjunto deixa de ser um teste limpo e será preciso criar casos novos.
- O fluxo gera um CSV com as sugestões e **não grava de volta** em nenhum sistema.
- Na camada gratuita da API do Gemini, os dados enviados podem ser usados pelo Google para melhorar seus produtos. Aqui os dados são fictícios; com dados reais, usar um plano pago ou ambiente corporativo.

## Como rodar

1. Ligue a API, na pasta principal do repositório:
   `python -m uvicorn api.main:app --reload`
2. Ligue o n8n (precisa de Node.js 20.19 a 24): `npx n8n`, e abra <http://localhost:5678>.
3. Crie uma chave em <https://aistudio.google.com/apikey> e, no n8n, uma credencial **Header Auth** chamada `Gemini API Key`, com **Name** `x-goog-api-key` e **Value** igual à chave.
4. Importe os fluxos pelo menu de três pontinhos, em **Import > From file**, e escolha a credencial no nó *Classificar com Gemini*.
5. Execute o fluxo, baixe o CSV do nó *Convert to File* e meça:
   `python n8n/avaliar_classificacao.py n8n/classificacao_ia.csv`
   Para o teste difícil:
   `python n8n/avaliar_classificacao.py n8n/classificacao_dificil.csv --gabarito n8n/gabarito_dificil.csv`

Os testes do script de avaliação rodam com `python -m pytest n8n`.

## Próximos passos

- Ajustar o prompt com base na análise de erros, medir de novo com casos novos e registrar o antes e o depois.
- Alertas: avisar (Telegram ou e-mail) quando um pacote passar de 15% de desvio.
