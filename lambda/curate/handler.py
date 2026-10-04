import os
import time

import boto3

athena = boto3.client("athena")

SQL_MERGE = """
MERGE INTO clima_curated.weather_daily_iceberg t
USING (
  SELECT ciudad, CAST(fecha AS date) AS fecha, temp_max, temp_min, precipitacion
  FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ciudad, fecha ORDER BY ingest_date DESC) AS rn
    FROM clima_raw.daily
  )
  WHERE rn = 1
) s
ON t.ciudad = s.ciudad AND t.fecha = s.fecha
WHEN MATCHED THEN UPDATE SET
  temp_max = s.temp_max, temp_min = s.temp_min, precipitacion = s.precipitacion
WHEN NOT MATCHED THEN INSERT (ciudad, fecha, temp_max, temp_min, precipitacion)
  VALUES (s.ciudad, s.fecha, s.temp_max, s.temp_min, s.precipitacion)
"""


def handler(event, context):
    qid = athena.start_query_execution(
        QueryString=SQL_MERGE, WorkGroup=os.environ["WORKGROUP"]
    )["QueryExecutionId"]

    while True:
        q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        estado = q["Status"]["State"]
        if estado in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(3)

    if estado != "SUCCEEDED":
        raise RuntimeError(f"MERGE terminó en {estado}: {q['Status'].get('StateChangeReason')}")

    stats = q.get("Statistics", {})
    resultado = {
        "query_id": qid,
        "estado": estado,
        "bytes_escaneados": stats.get("DataScannedInBytes"),
        "segundos": round(stats.get("TotalExecutionTimeInMillis", 0) / 1000, 1),
    }
    print(resultado)
    return resultado