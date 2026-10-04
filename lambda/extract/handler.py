import datetime
import json
import os
import urllib.request

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
CIUDADES = {"san_jose": (9.93, -84.08), "montreal": (45.50, -73.57)}
URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=auto&past_days=7"
)


def handler(event, context):
    hoy = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    resumen = {}
    for ciudad, (lat, lon) in CIUDADES.items():
        with urllib.request.urlopen(URL.format(lat=lat, lon=lon), timeout=20) as r:
            d = json.load(r)["daily"]
        filas = [
            json.dumps({
                "ciudad": ciudad,
                "fecha": dia,
                "temp_max": d["temperature_2m_max"][i],
                "temp_min": d["temperature_2m_min"][i],
                "precipitacion": d["precipitation_sum"][i],
            })
            for i, dia in enumerate(d["time"])
        ]
        key = f"raw/open_meteo/daily/ingest_date={hoy}/{ciudad}.json1"
        s3.put_object(Bucket=BUCKET, Key=key, Body="\n".join(filas) + "\n")
        resumen[ciudad] = len(filas)
    return {"ingest_date": hoy, "filas": resumen}