-- Zona curada: tabla Iceberg deduplicada (la extracción más reciente gana)
-- Reemplazar <DATA_BUCKET> por el nombre real del bucket.

CREATE DATABASE IF NOT EXISTS clima_curated;

-- Carga inicial
CREATE TABLE clima_curated.weather_daily_iceberg
WITH (
  table_type = 'ICEBERG',
  location = 's3://<DATA_BUCKET>/curated/weather_daily_iceberg/',
  is_external = false,
  format = 'PARQUET'
) AS
SELECT ciudad, fecha, temp_max, temp_min, precipitacion
FROM (
  SELECT ciudad, CAST(fecha AS date) AS fecha, temp_max, temp_min, precipitacion,
         ROW_NUMBER() OVER (PARTITION BY ciudad, fecha ORDER BY ingest_date DESC) AS rn
  FROM clima_raw.daily
)
WHERE rn = 1;

-- Actualización diaria (la ejecuta la Lambda clima-lab-curate)
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
  VALUES (s.ciudad, s.fecha, s.temp_max, s.temp_min, s.precipitacion);

-- Mantenimiento periódico (por ejemplo, semanal)
OPTIMIZE clima_curated.weather_daily_iceberg REWRITE DATA USING BIN_PACK;
VACUUM clima_curated.weather_daily_iceberg;
