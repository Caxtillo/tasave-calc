"""
Verifica que el BCV ya haya publicado la tasa del dia siguiente.

El BCV actualiza la "Fecha Valor" en la tarde/noche (aprox. 5-8 PM VET), asi
que despues de las 9 PM VET la tasa debe corresponder al siguiente dia habil.
Si no cambio, el workflow falla y GitHub manda correo de aviso.

Uso:  python verify_rate.py
      VERIFY_NOW=2026-11-10T21:30:00-04:00 python verify_rate.py   (pruebas)
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

VET = timezone(timedelta(hours=-4))
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rates.json")
# Hora (VET) a partir de la cual exigimos que la tasa ya sea la del dia siguiente.
CHECK_HOUR = 21

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def sin_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def parse_fecha_efectiva(texto):
    """'Miercoles, 11 Noviembre 2026' -> date(2026, 11, 11)"""
    match = re.search(r"(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})", texto or "")
    if not match:
        return None
    dia, mes, anio = match.groups()
    mes_num = MESES.get(sin_acentos(mes).lower())
    if not mes_num:
        return None
    return datetime(int(anio), mes_num, int(dia)).date()


def siguiente_dia_habil(fecha):
    nxt = fecha + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def now_vet():
    override = os.environ.get("VERIFY_NOW")
    if override:
        return datetime.fromisoformat(override).astimezone(VET)
    return datetime.now(VET)


def main():
    ahora = now_vet()
    print(f"Hora VET: {ahora:%Y-%m-%d %H:%M}")

    if ahora.weekday() >= 5:
        print("Fin de semana: el BCV no publica tasa nueva, no se verifica.")
        return 0
    if ahora.hour < CHECK_HOUR:
        print(f"Antes de las {CHECK_HOUR}:00 VET: aun no se exige la tasa del dia siguiente.")
        return 0

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    efectiva = parse_fecha_efectiva(data.get("effective_date", ""))
    esperada = siguiente_dia_habil(ahora.date())

    if efectiva is None:
        print(f"ERROR: no se pudo interpretar effective_date={data.get('effective_date')!r}")
        return 1

    print(f"Fecha Valor en rates.json: {efectiva} | esperada: {esperada}")
    if efectiva < esperada:
        print(
            "ERROR: el BCV todavia no publico la tasa del dia siguiente "
            f"(sigue en {efectiva}). Revisar https://www.bcv.org.ve/"
        )
        return 1

    print("OK: la tasa ya esta actualizada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
