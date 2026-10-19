"""Parâmetros da regra de suitability.

Ficam separados do código do motor para que possam ser ajustados
sem alterar a lógica de cálculo.
"""

from decimal import Decimal

# Regra do enunciado: alerta quando o risco projetado ultrapassar
# 10% acima do score máximo do cliente.
FATOR_ALERTA = Decimal("1.10")

# O enunciado NÃO define a partir de quando a ordem é rejeitada.
# Premissa adotada: rejeitar acima de 30% do score máximo, seguindo a
# mesma lógica percentual da regra de alerta. Esse valor é coerente com
# os exemplos do enunciado (2.78 em Alerta e 3.5 Rejeitado, para score 2.5).
FATOR_REJEICAO = Decimal("1.30")

# Identifica qual versão da regra gerou cada decisão (rastreabilidade).
VERSAO_REGRA = "1.0.0"

# Precisão usada para exibir os valores na saída (2 casas, como no enunciado).
CASAS_DECIMAIS = Decimal("0.01")
