# Pipeline do domínio asteroides: só declara os passos (nome, módulo, função).
# Cada passo vira uma tarefa do Airflow depois. A ordem da lista é a ordem de execução.
from astroflow.comum.passos import executar_etapa

_EXT = "astroflow.asteroides.extract"
_SIL = "astroflow.asteroides.transform"
_GOL = "astroflow.asteroides.gold"

EXTRACAO = [
    ("extract_jplsentry", f"{_EXT}.extract_jplsentry", "main"),  # modos S, V, R e O -> bronze.sentry_raw
    ("extract_jplcad", f"{_EXT}.extract_jplcad", "main"),  # -> bronze.cad_raw
    ("extract_neows", f"{_EXT}.extract_NeoWs", "main"),  # feed + lookup -> bronze.neows_*
]

SILVER = [
    ("criar_silver", f"{_SIL}.criar_silver", "main"),  # cria as tabelas se não existirem
    # asteroide primeiro: todas as outras referenciam silver.asteroide(des)
    ("silver_asteroide", f"{_SIL}.silver_asteroide", "carregar_silver_asteroide"),
    ("silver_sentry_resumo", f"{_SIL}.silver_sentry_resumo", "carregar_silver_sentry_resumo"),
    ("silver_sentry_detalhe", f"{_SIL}.silver_sentry_detalhe", "carregar_silver_sentry_detalhe"),
    ("silver_sentry_removido", f"{_SIL}.silver_sentry_removido", "carregar_silver_sentry_removido"),
    (
        "silver_sentry_impacto_virtual",
        f"{_SIL}.silver_sentry_impacto_virtual",
        "carregar_silver_sentry_impacto_virtual",
    ),
    ("silver_cad", f"{_SIL}.silver_cad", "carregar_silver_cad"),
    # neows: carrega asteroide -> orbita -> aproximacao (nessa ordem, por causa das FKs)
    ("silver_neows", f"{_SIL}.silver_neows", "main"),
]

GOLD = [
    ("criar_gold", f"{_GOL}.criar_gold", "main"),  # schema gold, dimensão e fatos
    # dimensão primeiro: as fatos precisam da asteroide_sk
    ("gold_dim_asteroide", f"{_GOL}.gold_dim_asteroide", "main"),
    ("gold_fact_aprox_cad", f"{_GOL}.gold_fact_aprox_cad", "main"),
    ("gold_fact_aprox_neows", f"{_GOL}.gold_fact_aprox_neows", "main"),
    ("gold_fact_impacto_virtual", f"{_GOL}.gold_fact_impacto_virtual", "main"),
]

# A ordem do dicionário é a ordem do "tudo".
ETAPAS = {"extracao": EXTRACAO, "silver": SILVER, "gold": GOLD}


def executar(etapa: str = "tudo") -> None:
    executar_etapa(etapa, ETAPAS)