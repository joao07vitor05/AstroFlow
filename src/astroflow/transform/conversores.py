# Funções de conversão de tipo, compartilhadas entre as cargas silver.
from datetime import datetime


def para_float(valor):
    """Texto -> float. None, '' e 'NaN' (texto) viram None."""
    if valor is None or str(valor).strip() in ("", "NaN"):
        return None
    return float(valor)  # se vier lixo, dá erro (melhor do que criar nulo calado)


def para_int(valor):
    """Texto/número -> int. None e '' viram None."""
    if valor is None or str(valor).strip() == "":
        return None
    return int(valor)


def para_data(valor):
    """'2020-10-3.80160' -> date(2020, 10, 3): corta a fração de dia."""
    if valor is None or str(valor).strip() == "":
        return None
    return datetime.strptime(valor.split(".")[0], "%Y-%m-%d").date()


def para_datahora(valor):
    """'2025-01-21 07:27:44' -> datetime."""
    if valor is None or str(valor).strip() == "":
        return None
    return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")