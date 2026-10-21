"""Tempo em minutos desde 00:00 de domingo, 17/10/2049."""
from datetime import datetime, timedelta

DIA = 1440
T0 = 1080
JANELA_PUBLICA = (T0, T0 + 28 * DIA)
PONTA = (18 * 60, 21 * 60)

EPOCA = datetime(2049, 10, 17)
_DIAS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def minutos(dt: datetime) -> int:
    return int((dt - EPOCA).total_seconds() // 60)


def dia_semana(t) -> int:
    """Seg=0 ... Dom=6."""
    return (6 + int(t // DIA)) % 7


def aberta(agencia, t) -> bool:
    """Aberta em t? `agencia.horario[dia]` é None (fechado) ou (ini, fim) em minutos do dia."""
    j = agencia.horario[dia_semana(t)]
    if j is None:
        return False
    minuto = t - (t // DIA) * DIA
    return j[0] <= minuto < j[1]


def eh_ponta(t) -> bool:
    """Seg-sex, 18:00 <= hora < 21:00."""
    dia, m = divmod(int(t), DIA)
    return (6 + dia) % 7 < 5 and PONTA[0] <= m < PONTA[1]


def texto(t) -> str:
    """Ex.: 'Seg 18/10 07:30'."""
    d = EPOCA + timedelta(minutes=int(t))
    return f"{_DIAS[d.weekday()]} {d:%d/%m %H:%M}"
