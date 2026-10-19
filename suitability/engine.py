"""Lógica central do Motor de Validação de Suitability de Carteira.

Todas as funções deste módulo são puras: recebem dados e devolvem um
resultado, sem ler arquivos, sem acessar banco e sem imprimir nada.
Isso permite que o mesmo motor seja chamado por uma CLI, por uma API
ou por um job de monitoramento, e que seja testado de forma isolada.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from suitability.config import (
    CASAS_DECIMAIS,
    FATOR_ALERTA,
    FATOR_REJEICAO,
    VERSAO_REGRA,
)

APROVADO = "Aprovado"
ALERTA = "Alerta"
REJEITADO = "Rejeitado"


class EntradaInvalidaError(ValueError):
    """Erro lançado quando os dados de entrada não permitem uma decisão."""


# ---------------------------------------------------------------------------
# 1. Validação e normalização das entradas
# ---------------------------------------------------------------------------

def _para_decimal(valor, campo: str) -> Decimal:
    """Converte um número para Decimal, rejeitando valores inválidos.

    A conversão passa por str() para que um float como 1.2 vire
    Decimal("1.2"), e não Decimal(1.1999999999999999555910790149937...).
    """
    # bool é subclasse de int em Python (True == 1), então é barrado à parte.
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise EntradaInvalidaError(f"'{campo}' deve ser numérico, recebido: {valor!r}")
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise EntradaInvalidaError(f"'{campo}' deve ser numérico, recebido: {valor!r}")
    if not numero.is_finite():
        raise EntradaInvalidaError(f"'{campo}' deve ser um número finito, recebido: {valor!r}")
    return numero


def _obter_campo(dados: dict, campo: str, origem: str):
    if not isinstance(dados, dict):
        raise EntradaInvalidaError(f"{origem} deve ser um objeto, recebido: {dados!r}")
    if campo not in dados:
        raise EntradaInvalidaError(f"Campo obrigatório ausente em {origem}: '{campo}'")
    return dados[campo]


def _normalizar_perfil(perfil: dict) -> dict:
    score = _para_decimal(
        _obter_campo(perfil, "score_max_risco", "perfil"), "perfil.score_max_risco"
    )
    if score <= 0:
        raise EntradaInvalidaError("'perfil.score_max_risco' deve ser maior que zero")
    return {"perfil": perfil.get("perfil"), "score_max_risco": score}


def _normalizar_ativo(item: dict, campo_valor: str, origem: str) -> dict:
    risco = _para_decimal(_obter_campo(item, "risco", origem), f"{origem}.risco")
    valor = _para_decimal(_obter_campo(item, campo_valor, origem), f"{origem}.{campo_valor}")
    if risco < 0:
        raise EntradaInvalidaError(f"'{origem}.risco' não pode ser negativo")
    if valor <= 0:
        raise EntradaInvalidaError(f"'{origem}.{campo_valor}' deve ser maior que zero")
    return {"ativo": item.get("ativo"), "risco": risco, campo_valor: valor}


def _normalizar_carteira(carteira: list) -> list:
    if not isinstance(carteira, list):
        raise EntradaInvalidaError(f"carteira deve ser uma lista, recebido: {carteira!r}")
    return [
        _normalizar_ativo(item, "valor_investido", f"carteira[{i}]")
        for i, item in enumerate(carteira)
    ]


# ---------------------------------------------------------------------------
# 2. Cálculos
# ---------------------------------------------------------------------------

def calcular_risco(carteira: list) -> Decimal | None:
    """Risco da carteira: média do risco ponderada pelo valor investido.

        R = Σ(risco_i × valor_investido_i) / Σ(valor_investido_i)

    Retorna None para carteira vazia, pois a divisão seria por zero.
    """
    if not carteira:
        return None
    soma_ponderada = sum(
        (ativo["risco"] * ativo["valor_investido"] for ativo in carteira), Decimal("0")
    )
    soma_valores = sum((ativo["valor_investido"] for ativo in carteira), Decimal("0"))
    return soma_ponderada / soma_valores


def projetar_risco(carteira: list, ordem: dict) -> Decimal:
    """Risco da carteira caso a nova ordem de compra seja executada.

    A ordem é tratada como mais um ativo da carteira, e a mesma
    fórmula de calcular_risco() é reaproveitada.
    """
    ordem_como_ativo = {
        "ativo": ordem.get("ativo"),
        "risco": ordem["risco"],
        "valor_investido": ordem["valor_ordem"],
    }
    return calcular_risco(carteira + [ordem_como_ativo])


def calcular_limites(score_max_risco: Decimal) -> tuple[Decimal, Decimal]:
    """Retorna (limite_alerta, limite_rejeicao) para o score do cliente."""
    return score_max_risco * FATOR_ALERTA, score_max_risco * FATOR_REJEICAO


def classificar(
    risco_projetado: Decimal, limite_alerta: Decimal, limite_rejeicao: Decimal
) -> str:
    """Define o status da ordem.

    O limite de rejeição é verificado primeiro: se o alerta fosse testado
    antes, um risco muito alto cairia em "Alerta" em vez de "Rejeitado".
    As comparações usam ">" porque a regra fala em "ultrapassar" o limite:
    um risco exatamente igual ao limite ainda está dentro dele.
    """
    if risco_projetado > limite_rejeicao:
        return REJEITADO
    if risco_projetado > limite_alerta:
        return ALERTA
    return APROVADO


# ---------------------------------------------------------------------------
# 3. Montagem da saída
# ---------------------------------------------------------------------------

def _arredondar(valor: Decimal | None) -> Decimal | None:
    if valor is None:
        return None
    return valor.quantize(CASAS_DECIMAIS, rounding=ROUND_HALF_UP)


def _montar_mensagem(status: str, limite_alerta: Decimal) -> str:
    if status == APROVADO:
        return "Ordem executada. Carteira em conformidade."
    if status == ALERTA:
        return (
            "Atenção: O risco da carteira ultrapassará o limite de "
            f"{_arredondar(limite_alerta)}. É necessário termo de ciência."
        )
    return "Risco excessivo. A operação viola a política de Suitability."


def validar(perfil: dict, carteira: list, ordem: dict, agora: datetime | None = None) -> dict:
    """Ponto de entrada do motor: valida uma nova ordem de compra.

    Retorna um dicionário com os campos exigidos pelo enunciado
    (status, risco_projetado, mensagem) e um bloco "detalhes" com os
    dados usados na decisão, para fins de auditoria.

    Lança EntradaInvalidaError se as entradas forem inválidas.
    O parâmetro "agora" existe para que os testes possam fixar o horário.
    """
    perfil_ok = _normalizar_perfil(perfil)
    carteira_ok = _normalizar_carteira(carteira)
    ordem_ok = _normalizar_ativo(ordem, "valor_ordem", "ordem")

    risco_atual = calcular_risco(carteira_ok)
    risco_projetado = projetar_risco(carteira_ok, ordem_ok)
    limite_alerta, limite_rejeicao = calcular_limites(perfil_ok["score_max_risco"])
    status = classificar(risco_projetado, limite_alerta, limite_rejeicao)

    momento = agora or datetime.now(timezone.utc)

    return {
        "status": status,
        "risco_projetado": _arredondar(risco_projetado),
        "mensagem": _montar_mensagem(status, limite_alerta),
        "detalhes": {
            "perfil": perfil_ok["perfil"],
            "score_max_risco": perfil_ok["score_max_risco"],
            "risco_atual": _arredondar(risco_atual),
            "limite_alerta": _arredondar(limite_alerta),
            "limite_rejeicao": _arredondar(limite_rejeicao),
            "ativo_ordem": ordem_ok["ativo"],
            "valor_ordem": ordem_ok["valor_ordem"],
            "versao_regra": VERSAO_REGRA,
            "avaliado_em": momento.isoformat(),
        },
    }
