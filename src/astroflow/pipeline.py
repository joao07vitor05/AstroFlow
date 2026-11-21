# Orquestrador: roda a extração (APIs -> bronze) e a transformação (bronze -> silver).
# Não tem lógica de negócio: só chama as funções dos módulos, na ordem certa.
# Cada passo é independente, então cada um vira uma tarefa do Airflow depois.
#
# Uso:
#   python -m astroflow.pipeline                    # tudo
#   python -m astroflow.pipeline --etapa extracao   # só APIs -> bronze
#   python -m astroflow.pipeline --etapa silver     # só bronze -> silver
import argparse
import logging
import time

from astroflow.extract import extract_jplcad, extract_jplsentry, extract_NeoWs
from astroflow.transform import (
    criar_silver,
    silver_asteroide,
    silver_cad,
    silver_neows,
    silver_sentry_detalhe,
    silver_sentry_impacto_virtual,
    silver_sentry_removido,
    silver_sentry_resumo,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("astroflow")

# Cada passo: (nome, função sem parâmetros). A ordem da lista é a ordem de execução.
EXTRACAO = [
    ("extract_jplsentry", extract_jplsentry.main),  # modos S, V, R e O -> bronze.sentry_raw
    ("extract_jplcad", extract_jplcad.main),  # -> bronze.cad_raw
    ("extract_neows", extract_NeoWs.main),  # feed + lookup -> bronze.neows_*
]

SILVER = [
    ("criar_silver", criar_silver.main),  # cria as tabelas se não existirem (as bronze já existem)
    # asteroide primeiro: todas as outras referenciam silver.asteroide(des)
    ("silver_asteroide", silver_asteroide.carregar_silver_asteroide),
    ("silver_sentry_resumo", silver_sentry_resumo.carregar_silver_sentry_resumo),
    ("silver_sentry_detalhe", silver_sentry_detalhe.carregar_silver_sentry_detalhe),
    ("silver_sentry_removido", silver_sentry_removido.carregar_silver_sentry_removido),
    (
        "silver_sentry_impacto_virtual",
        silver_sentry_impacto_virtual.carregar_silver_sentry_impacto_virtual,
    ),
    ("silver_cad", silver_cad.carregar_silver_cad),
    # neows: carrega asteroide -> orbita -> aproximacao (nessa ordem, por causa das FKs)
    ("silver_neows", silver_neows.main),
]


def rodar_passo(nome, funcao) -> None:
    """Roda um passo, mede o tempo e, se falhar, registra e interrompe a pipeline."""
    inicio = time.time()
    log.info("INICIO  %s", nome)
    try:
        funcao()
    except Exception:
        log.exception("FALHOU  %s", nome)
        raise  # para tudo: os passos seguintes dependem deste
    log.info("OK      %s (%.1fs)", nome, time.time() - inicio)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline AstroFlow")
    parser.add_argument(
        "--etapa",
        choices=["extracao", "silver", "tudo"],
        default="tudo",
        help="qual parte rodar (padrão: tudo)",
    )
    args = parser.parse_args()

    passos = []
    if args.etapa in ("extracao", "tudo"):
        passos += EXTRACAO
    if args.etapa in ("silver", "tudo"):
        passos += SILVER

    inicio = time.time()
    for nome, funcao in passos:
        rodar_passo(nome, funcao)
    log.info("Pipeline concluída em %.1fs", time.time() - inicio)


if __name__ == "__main__":
    main()
