# Funções compartilhadas por todos os domínios para rodar os passos da pipeline.
import importlib
import logging
import time

log = logging.getLogger("astroflow")


def rodar_passo(nome: str, modulo: str, funcao: str) -> None:
    """Importa o módulo, roda a função, mede o tempo e, se falhar, registra e relança."""
    inicio = time.time()
    log.info("INICIO  %s", nome)
    try:
        # o import acontece AQUI, só quando o passo roda (não quando a lista é lida)
        fn = getattr(importlib.import_module(modulo), funcao)
        fn()
    except Exception:
        log.exception("FALHOU  %s", nome)
        raise  # para tudo: os passos seguintes dependem deste
    log.info("OK      %s (%.1fs)", nome, time.time() - inicio)


def executar_etapa(etapa: str, etapas: dict) -> None:
    """Roda uma etapa ("extracao", "silver", "gold") ou todas ("tudo"), na ordem do dicionário."""
    nomes = list(etapas) if etapa == "tudo" else [etapa]
    inicio = time.time()
    for nome_etapa in nomes:
        for nome, modulo, funcao in etapas[nome_etapa]:
            rodar_passo(nome, modulo, funcao)
    log.info("Pipeline concluída em %.1fs", time.time() - inicio)