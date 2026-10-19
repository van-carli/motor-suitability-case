"""Interface de linha de comando do motor de suitability.

Uso:
    python main.py examples/aprovado.json

O arquivo de entrada deve conter as chaves "perfil", "carteira" e "ordem".
Esta camada só faz entrada e saída: lê o JSON, chama o motor e imprime
o resultado. Toda a regra de negócio está em suitability/engine.py.
"""

import argparse
import json
import sys
from decimal import Decimal

from suitability import EntradaInvalidaError, validar


def _decimal_para_json(valor):
    """json.dumps não sabe serializar Decimal; aqui ele vira número."""
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(f"Tipo não serializável: {type(valor).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida uma ordem de compra (suitability).")
    parser.add_argument("arquivo", help="caminho do JSON com perfil, carteira e ordem")
    args = parser.parse_args()

    try:
        with open(args.arquivo, encoding="utf-8") as f:
            # parse_float=Decimal: números com casas decimais já chegam como Decimal,
            # sem passar por float.
            dados = json.load(f, parse_float=Decimal)
    except (OSError, json.JSONDecodeError) as erro:
        print(json.dumps({"status": "Erro", "mensagem": f"Falha ao ler entrada: {erro}"},
                         ensure_ascii=False, indent=2))
        return 1

    try:
        if not isinstance(dados, dict):
            raise EntradaInvalidaError("O arquivo deve conter um objeto JSON")
        for chave in ("perfil", "carteira", "ordem"):
            if chave not in dados:
                raise EntradaInvalidaError(f"Chave obrigatória ausente no arquivo: '{chave}'")
        resultado = validar(dados["perfil"], dados["carteira"], dados["ordem"])
    except EntradaInvalidaError as erro:
        print(json.dumps({"status": "Erro", "mensagem": str(erro)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=_decimal_para_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
