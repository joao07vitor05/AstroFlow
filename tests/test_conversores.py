# Testes das funções de conversão. Não usam banco nem internet.
from datetime import date, datetime

import pytest

from astroflow.asteroides.transform.silver_cad import para_cd
from astroflow.asteroides.transform.silver_neows import para_data_hora_neows
from astroflow.asteroides.transform.silver_sentry_detalhe import para_darc
from astroflow.asteroides.transform.silver_sentry_resumo import separar_range
from astroflow.comum.conversores import (
    para_data,
    para_datahora,
    para_float,
    para_int,
)


# ---------- para_float ----------
def test_para_float_converte_texto():
    assert para_float("1.5") == 1.5


def test_para_float_nulos_viram_none():
    # 'NaN' em TEXTO é o caso do v_inf da Sentry
    for valor in (None, "", "  ", "NaN"):
        assert para_float(valor) is None


def test_para_float_lixo_levanta_erro():
    # lixo tem que dar erro, nunca virar nulo em silêncio
    with pytest.raises(ValueError):
        para_float("abc")


# ---------- para_int ----------
def test_para_int_converte_texto():
    assert para_int("7") == 7


def test_para_int_zero_continua_zero_e_nulo_continua_nulo():
    # regra do ts_max: 0 é valor real, None nunca vira 0
    assert para_int("0") == 0
    assert para_int(None) is None


# ---------- datas ----------
def test_para_data_corta_fracao_de_dia():
    assert para_data("2020-10-3.80160") == date(2020, 10, 3)  # last_obs do resumo
    assert para_data("2108-05-24.69") == date(2108, 5, 24)  # date do modo V


def test_para_data_nulo():
    assert para_data(None) is None
    assert para_data("") is None


def test_para_datahora():
    assert para_datahora("2016-04-01 12:00:00") == datetime(2016, 4, 1, 12, 0, 0)
    assert para_datahora(None) is None


def test_para_cd_do_cad():
    # mês abreviado em inglês (testa também o idioma do sistema)
    assert para_cd("2026-Nov-18 12:34") == datetime(2026, 11, 18, 12, 34)


def test_para_data_hora_neows():
    assert para_data_hora_neows("1900-Dec-27 01:30") == datetime(1900, 12, 27, 1, 30)


# ---------- limpezas específicas ----------
def test_para_darc():
    assert para_darc("469.18 days") == 469.18
    assert para_darc(None) is None


def test_separar_range():
    assert separar_range("2064-2118") == (2064, 2118)
    assert separar_range("2064") == (2064, 2064)  # ano único: min = max
    assert separar_range(None) == (None, None)
