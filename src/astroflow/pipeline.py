# Orquestrador principal: escolhe o domínio e chama o pipeline dele.
# Não tem lógica de negócio nem lista de passos (cada domínio tem o seu pipeline.py).
#
# Uso:
#   python -m astroflow.pipeline                                  # asteroides, tudo
#   python -m astroflow.pipeline --etapa silver                   # asteroides, só silver
#   python -m astroflow.pipeline --dominio asteroides --etapa gold
import argparse
import importlib
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# domínio -> módulo do pipeline dele (DONKI e APOD entram aqui depois)
DOMINIOS = {
    "asteroides": "astroflow.asteroides.pipeline",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline AstroFlow")
    parser.add_argument("--dominio", choices=list(DOMINIOS), default="asteroides")
    parser.add_argument(
        "--etapa",
        choices=["extracao", "silver", "gold", "tudo"],
        default="tudo",
        help="qual parte rodar (padrão: tudo)",
    )
    args = parser.parse_args()

    dominio = importlib.import_module(DOMINIOS[args.dominio])
    dominio.executar(args.etapa)


if __name__ == "__main__":
    main()