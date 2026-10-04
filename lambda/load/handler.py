import json
import os
import ssl
import urllib.parse

import boto3
import pg8000.native

s3 = boto3.client("s3")
sm = boto3.client("secretsmanager")

SQL_UPSERT = """
INSERT INTO clima.weather_daily (ciudad, fecha, temp_max, temp_min, precipitacion)
VALUES (:ciudad, CAST(:fecha AS date), :temp_max, :temp_min, :precipitacion)
ON CONFLICT (ciudad, fecha) DO UPDATE SET
  temp_max      = EXCLUDED.temp_max,
  temp_min      = EXCLUDED.temp_min,
  precipitacion = EXCLUDED.precipitacion,
  ingested_at   = now()
"""


def conectar():
    cred = json.loads(sm.get_secret_value(SecretId=os.environ["SECRET_ID"])["SecretString"])
    ctx = ssl.create_default_context(cafile="global-bundle.pem")
    return pg8000.native.Connection(
        user=cred["username"], password=cred["password"],
        host=os.environ["DB_HOST"], database="clima", ssl_context=ctx,
    )


def handler(event, context):
    con = conectar()
    resumen = {}
    try:
        for rec in event["Records"]:
            bucket = rec["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(rec["s3"]["object"]["key"])
            cuerpo = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
            filas = [json.loads(linea) for linea in cuerpo.splitlines() if linea.strip()]

            con.run("START TRANSACTION")
            for r in filas:
                con.run(SQL_UPSERT, ciudad=r["ciudad"], fecha=r["fecha"],
                        temp_max=r["temp_max"], temp_min=r["temp_min"],
                        precipitacion=r["precipitacion"])
            con.run("COMMIT")
            resumen[key] = len(filas)
    finally:
        con.close()
    print(json.dumps(resumen))
    return resumen