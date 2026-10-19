# Motor de Validação de Suitability de Carteira

Solução do case técnico do Programa de Estágio de Férias 2027 da Genial Investimentos (Tecnologia). O repositório contém o motor que valida se uma nova compra mantém a carteira do cliente adequada ao seu perfil de risco, e a documentação com as respostas às questões do case.

## O problema

Instituições como a Genial precisam garantir que os investimentos de cada cliente sejam adequados ao seu perfil de risco, uma obrigação prevista na Resolução CVM 30. Esse processo é chamado de suitability.

Avaliar cada ativo isoladamente não é suficiente. Uma compra pequena de um ativo arriscado pode não mudar muito a carteira, enquanto uma compra grande do mesmo ativo pode tirá-la do perfil do cliente. Por isso, o que precisa ser avaliado é o risco da carteira como um todo, e isso deve acontecer antes de cada nova compra.

## O que o motor faz

Antes de uma compra ser executada, o motor responde a uma pergunta: se esta ordem for executada, a carteira continua adequada ao perfil do cliente? Para isso, ele segue quatro passos:

1. Calcula o **risco atual** da carteira, que é a média do risco dos ativos ponderada pelo valor investido em cada um.
2. Calcula o **risco projetado**, que é o risco que a carteira teria se a compra acontecesse.
3. Calcula os **limites** do cliente a partir do score máximo de risco do seu perfil.
4. **Classifica** a ordem e devolve a decisão junto com os valores que a justificam.

A ordem recebe um de três status. Os limites são proporcionais ao score do cliente; abaixo, o exemplo para o perfil Moderado (score 2,5):

| Status | Quando ocorre | Limite para score 2,5 | O que significa |
|---|---|---|---|
| Aprovado | Risco projetado até 110% do score | até 2,75 | A compra pode ser executada |
| Alerta | Acima de 110% e até 130% do score | acima de 2,75 até 3,25 | A compra só segue se o cliente assinar um termo de ciência |
| Rejeitado | Acima de 130% do score | acima de 3,25 | A compra é bloqueada |

O limite de alerta (110%) vem do enunciado. O limite de rejeição (130%) não foi definido no enunciado e é uma premissa desta solução, explicada no [relatório do Case I](docs/case-report.md#premissas-adotadas). Os dois valores ficam em `suitability/config.py` e podem ser alterados sem mexer na lógica do motor.

![Fluxo do motor de suitability](./docs/img/fluxo-motor-suitability.svg)

### Exemplo

Entrada (`examples/aprovado.json`, com os dados do enunciado):

```json
{
  "perfil": {"perfil": "Moderado", "score_max_risco": 2.5},
  "carteira": [
    {"ativo": "CDB XPTO", "risco": 1.2, "valor_investido": 50000},
    {"ativo": "Ação ABC", "risco": 4.0, "valor_investido": 10000}
  ],
  "ordem": {"ativo": "FII YYY", "risco": 3.5, "valor_ordem": 5000}
}
```

Saída:

```json
{
  "status": "Aprovado",
  "risco_projetado": 1.81,
  "mensagem": "Ordem executada. Carteira em conformidade.",
  "detalhes": {
    "perfil": "Moderado",
    "score_max_risco": 2.5,
    "risco_atual": 1.67,
    "limite_alerta": 2.75,
    "limite_rejeicao": 3.25,
    "ativo_ordem": "FII YYY",
    "valor_ordem": 5000.0,
    "versao_regra": "1.0.0",
    "avaliado_em": "2026-10-19T20:19:03.633492+00:00"
  }
}
```

Os campos `status`, `risco_projetado` e `mensagem` são os pedidos no enunciado. O bloco `detalhes` registra os dados usados na decisão e a versão da regra aplicada, para que a decisão possa ser verificada depois em uma auditoria.

## Como executar

Requisito: **Python 3.10 ou superior**.

```bash
# 1. Criar e ativar um ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux ou macOS

# 2. Instalar a dependência de testes
pip install -r requirements.txt

# 3. Validar uma ordem a partir de um arquivo JSON
python main.py examples/aprovado.json

# 4. Rodar os testes
python -m pytest -v
```

A pasta `examples/` tem um arquivo de entrada para cada situação. Os arquivos contêm apenas os dados de entrada (perfil, carteira e ordem); o resultado é calculado pelo motor a cada execução. Para testar outros valores, basta criar um arquivo JSON no mesmo formato e passá-lo ao `main.py`.

| Arquivo | Situação | Resultado |
|---|---|---|
| `aprovado.json` | Dados do enunciado | Aprovado (risco 1,81) |
| `alerta.json` | Compra de R$ 60.000 em Ação ABC | Alerta (risco 2,83) |
| `rejeitado.json` | Compra de R$ 150.000 em Ação ABC | Rejeitado (risco 3,33) |
| `carteira_vazia.json` | Cliente sem nenhum ativo | Aprovado (risco 1,20) |
| `entrada_invalida.json` | Valor da ordem negativo | Erro de validação |

## Estrutura do repositório

```
.
├── suitability/
│   ├── engine.py          # lógica do motor: validação das entradas, cálculos e decisão
│   └── config.py          # parâmetros da regra (fatores de alerta e rejeição, versão)
├── main.py                # execução pelo terminal: lê o JSON, chama o motor e mostra o resultado
├── tests/test_engine.py   # testes automatizados
├── examples/              # arquivos de entrada para cada situação
└── docs/
    ├── case-report.md     # relatório do Case I
    ├── case-2-infra.md    # respostas do Case II
    └── img/               # fluxograma do motor (.drawio editável e .svg)
```

O motor foi escrito como um conjunto de funções que apenas recebem dados e devolvem uma decisão, sem ler arquivos, acessar banco de dados ou depender de rede. A leitura do arquivo e a exibição do resultado ficam no `main.py`. Com essa separação, a mesma lógica pode ser usada pelo terminal, por uma API ou por um processo automático, e pode ser testada de forma isolada.

## Testes

São 33 testes, que verificam:

- os cálculos do risco atual e do risco projetado com os dados do enunciado;
- a classificação exatamente nos limites e logo acima deles (por exemplo, 2,75 é Aprovado e 2,7501 é Alerta);
- os três status de ponta a ponta, incluindo o cliente sem carteira;
- a rejeição de entradas inválidas, como valores negativos, campos ausentes e textos no lugar de números;
- a precisão numérica: o motor usa o tipo `Decimal` porque, com `float`, um risco exatamente igual ao limite pode ser calculado como 2,7500000000000004 e gerar um alerta indevido. Um dos testes reproduz esse caso.

## Documentação

- **[docs/case-report.md](docs/case-report.md): relatório do Case I.** Apresenta a solução, as premissas adotadas nos pontos que o enunciado deixou em aberto e as respostas às duas perguntas do case: o que a Genial precisa prever, do ponto de vista tecnológico e de compliance, quando o cliente aceita o termo de ciência após um alerta; e como usar o motor para monitorar o desenquadramento passivo, incluindo os canais de comunicação com o cliente.
- **[docs/case-2-infra.md](docs/case-2-infra.md): respostas do Case II.** Trata dos cinco cenários de infraestrutura: crescimento de demanda, indisponibilidade do servidor, lentidão, monitoramento e mudança em produção, com a justificativa de cada abordagem.
- **[docs/img](docs/img): fluxograma do motor**, com o caminho completo da validação e o que acontece depois de cada status.
