-- Zona raw: tabla sobre JSON Lines con partition projection (sin crawler)
-- Antes: aws glue create-database --database-input '{"Name":"clima_raw"}'
-- Reemplazar <DATA_BUCKET> por el nombre real del bucket.

CREATE EXTERNAL TABLE clima_raw.daily (
  ciudad        string,
  fecha         string,
  temp_max      double,
  temp_min      double,
  precipitacion double
)
PARTITIONED BY (ingest_date string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://<DATA_BUCKET>/raw/open_meteo/daily/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.ingest_date.type' = 'date',
  'projection.ingest_date.format' = 'yyyy-MM-dd',
  'projection.ingest_date.range' = '2026-10-01,NOW',
  'projection.ingest_date.interval' = '1',
  'projection.ingest_date.interval.unit' = 'DAYS',
  'storage.location.template' = 's3://<DATA_BUCKET>/raw/open_meteo/daily/ingest_date=${ingest_date}/'
);
