"""Testes do motor de suitability.

Rodar com:  python -m pytest -v
"""

from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from suitability import (
    ALERTA,
    APROVADO,
    REJEITADO,
    EntradaInvalidaError,
    calcular_limites,
    calcular_risco,
    classificar,
    projetar_risco,
    validar,
)

# Dados do enunciado
PERFIL_MODERADO = {"perfil": "Moderado", "score_max_risco": 2.5}
CARTEIRA = [
    {"ativo": "CDB XPTO", "risco": 1.2, "valor_investido": 50000},
    {"ativo": "Ação ABC", "risco": 4.0, "valor_investido": 10000},
]
ORDEM_FII = {"ativo": "FII YYY", "risco": 3.5, "valor_ordem": 5000}

# Mesma carteira, já em Decimal, para testar as funções de cálculo diretamente
CARTEIRA_DEC = [
    {"ativo": "CDB XPTO", "risco": D("1.2"), "valor_investido": D("50000")},
    {"ativo": "Ação ABC", "risco": D("4.0"), "valor_investido": D("10000")},
]


# ---------------------------------------------------------------------------
# calcular_risco
# ---------------------------------------------------------------------------

def test_risco_atual_da_carteira_do_enunciado():
    # (1.2 × 50000 + 4.0 × 10000) / 60000 = 100000 / 60000
    assert calcular_risco(CARTEIRA_DEC) == D("100000") / D("60000")


def test_risco_de_carteira_vazia_e_none():
    assert calcular_risco([]) is None


def test_risco_de_carteira_com_um_ativo_e_o_proprio_risco():
    carteira = [{"ativo": "X", "risco": D("3.3"), "valor_investido": D("1000")}]
    assert calcular_risco(carteira) == D("3.3")


# ---------------------------------------------------------------------------
# projetar_risco
# ---------------------------------------------------------------------------

def test_risco_projetado_com_a_ordem_do_enunciado():
    ordem = {"ativo": "FII YYY", "risco": D("3.5"), "valor_ordem": D("5000")}
    # (100000 + 3.5 × 5000) / 65000 = 117500 / 65000
    assert projetar_risco(CARTEIRA_DEC, ordem) == D("117500") / D("65000")


def test_risco_projetado_com_carteira_vazia_e_o_risco_da_ordem():
    ordem = {"ativo": "CDB", "risco": D("1.2"), "valor_ordem": D("10000")}
    assert projetar_risco([], ordem) == D("1.2")


def test_projetar_nao_altera_a_carteira_original():
    carteira = list(CARTEIRA_DEC)
    projetar_risco(carteira, {"ativo": "Y", "risco": D("2"), "valor_ordem": D("1")})
    assert carteira == CARTEIRA_DEC


# ---------------------------------------------------------------------------
# calcular_limites e classificar
# ---------------------------------------------------------------------------

def test_limites_para_score_moderado():
    assert calcular_limites(D("2.5")) == (D("2.75"), D("3.25"))


@pytest.mark.parametrize(
    "risco_projetado, esperado",
    [
        (D("2.10"), APROVADO),
        (D("2.50"), APROVADO),    # igual ao score: dentro da tolerância
        (D("2.75"), APROVADO),    # exatamente no limite: não "ultrapassa"
        (D("2.7501"), ALERTA),    # logo acima do limite de alerta
        (D("2.78"), ALERTA),      # exemplo do enunciado
        (D("3.25"), ALERTA),      # exatamente no limite de rejeição
        (D("3.2501"), REJEITADO), # logo acima do limite de rejeição
        (D("3.50"), REJEITADO),   # exemplo do enunciado
    ],
)
def test_classificacao_nas_fronteiras(risco_projetado, esperado):
    assert classificar(risco_projetado, D("2.75"), D("3.25")) == esperado


# ---------------------------------------------------------------------------
# validar (fluxo completo)
# ---------------------------------------------------------------------------

def test_validar_caso_aprovado_do_enunciado():
    r = validar(PERFIL_MODERADO, CARTEIRA, ORDEM_FII)
    assert r["status"] == APROVADO
    assert r["risco_projetado"] == D("1.81")
    assert r["mensagem"] == "Ordem executada. Carteira em conformidade."


def test_validar_caso_alerta():
    ordem = {"ativo": "Ação ABC", "risco": 4.0, "valor_ordem": 60000}
    r = validar(PERFIL_MODERADO, CARTEIRA, ordem)
    assert r["status"] == ALERTA
    assert r["risco_projetado"] == D("2.83")
    assert "2.75" in r["mensagem"]
    assert "termo de ciência" in r["mensagem"]


def test_validar_caso_rejeitado():
    ordem = {"ativo": "Ação ABC", "risco": 4.0, "valor_ordem": 150000}
    r = validar(PERFIL_MODERADO, CARTEIRA, ordem)
    assert r["status"] == REJEITADO
    assert r["risco_projetado"] == D("3.33")
    assert r["mensagem"] == "Risco excessivo. A operação viola a política de Suitability."


def test_validar_cliente_sem_carteira():
    ordem = {"ativo": "CDB XPTO", "risco": 1.2, "valor_ordem": 10000}
    r = validar(PERFIL_MODERADO, [], ordem)
    assert r["status"] == APROVADO
    assert r["detalhes"]["risco_atual"] is None


def test_saida_contem_campos_exigidos_e_dados_de_auditoria():
    momento = datetime(2027, 1, 4, 10, 0, tzinfo=timezone.utc)
    r = validar(PERFIL_MODERADO, CARTEIRA, ORDEM_FII, agora=momento)
    assert {"status", "risco_projetado", "mensagem"} <= r.keys()
    d = r["detalhes"]
    assert d["risco_atual"] == D("1.67")
    assert d["limite_alerta"] == D("2.75")
    assert d["limite_rejeicao"] == D("3.25")
    assert d["versao_regra"] == "1.0.0"
    assert d["avaliado_em"] == "2027-01-04T10:00:00+00:00"


def test_limites_acompanham_o_perfil_do_cliente():
    conservador = {"perfil": "Conservador", "score_max_risco": 1.5}
    r = validar(conservador, CARTEIRA, ORDEM_FII)
    # risco projetado 1.81 > 1.65 (alerta) e <= 1.95 (rejeição)
    assert r["status"] == ALERTA
    assert "1.65" in r["mensagem"]


def test_decimal_evita_alerta_falso_por_erro_de_float():
    # Risco projetado exato: (4.5 × 10000 + 2.7 × 350000) / 360000 = 2.75,
    # exatamente no limite de alerta, portanto Aprovado.
    # Com float, a mesma conta dá 2.7500000000000004 e dispararia um alerta indevido.
    assert (4.5 * 10000 + 2.7 * 350000) / 360000 > 2.5 * 1.1  # o problema existe em float
    carteira = [{"ativo": "A", "risco": 4.5, "valor_investido": 10000}]
    ordem = {"ativo": "B", "risco": 2.7, "valor_ordem": 350000}
    r = validar(PERFIL_MODERADO, carteira, ordem)
    assert r["status"] == APROVADO


# ---------------------------------------------------------------------------
# Entradas inválidas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "perfil, carteira, ordem",
    [
        ({}, CARTEIRA, ORDEM_FII),                                          # score ausente
        ({"score_max_risco": 0}, CARTEIRA, ORDEM_FII),                      # score zero
        ({"score_max_risco": "abc"}, CARTEIRA, ORDEM_FII),                  # score não numérico
        ({"score_max_risco": True}, CARTEIRA, ORDEM_FII),                   # bool não é número
        (PERFIL_MODERADO, "não é lista", ORDEM_FII),                        # carteira inválida
        (PERFIL_MODERADO, [{"ativo": "X", "risco": 1}], ORDEM_FII),         # valor ausente
        (PERFIL_MODERADO, [{"ativo": "X", "risco": -1, "valor_investido": 10}], ORDEM_FII),
        (PERFIL_MODERADO, CARTEIRA, {"ativo": "Y", "risco": 2, "valor_ordem": 0}),
        (PERFIL_MODERADO, CARTEIRA, {"ativo": "Y", "risco": 2, "valor_ordem": -500}),
        (PERFIL_MODERADO, CARTEIRA, {"ativo": "Y", "risco": float("nan"), "valor_ordem": 10}),
        (PERFIL_MODERADO, CARTEIRA, None),                                  # ordem ausente
    ],
)
def test_entradas_invalidas_lancam_erro(perfil, carteira, ordem):
    with pytest.raises(EntradaInvalidaError):
        validar(perfil, carteira, ordem)
