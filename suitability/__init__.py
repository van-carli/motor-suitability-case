"""Motor de Validação de Suitability de Carteira (Case I, Genial Investimentos)."""

from suitability.engine import (
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

__all__ = [
    "ALERTA",
    "APROVADO",
    "REJEITADO",
    "EntradaInvalidaError",
    "calcular_limites",
    "calcular_risco",
    "classificar",
    "projetar_risco",
    "validar",
]
