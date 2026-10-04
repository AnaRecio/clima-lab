-- PostgreSQL (RDS): esquema, tabla y usuarios con mínimo privilegio
-- Las contraseñas se generan con:
--   aws secretsmanager get-random-password --password-length 32 --exclude-punctuation
-- y se guardan en los secretos clima-lab/pipeline-writer y clima-lab/reporting-reader.
-- Nunca escribir las contraseñas reales en este archivo.

CREATE SCHEMA clima;

CREATE TABLE clima.weather_daily (
  ciudad        text          NOT NULL,
  fecha         date          NOT NULL,
  temp_max      numeric(5,2),
  temp_min      numeric(5,2),
  precipitacion numeric(6,2),
  ingested_at   timestamptz   NOT NULL DEFAULT now(),
  PRIMARY KEY (ciudad, fecha)
);

-- Usuario del pipeline: solo lee y escribe en su tabla (sin DELETE)
CREATE ROLE pipeline_writer LOGIN PASSWORD '<PW_WRITER>';
GRANT USAGE ON SCHEMA clima TO pipeline_writer;
GRANT SELECT, INSERT, UPDATE ON clima.weather_daily TO pipeline_writer;

-- Usuario de reportes: solo lectura en todo el esquema
CREATE ROLE reporting_reader LOGIN PASSWORD '<PW_READER>';
GRANT USAGE ON SCHEMA clima TO reporting_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA clima TO reporting_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA clima GRANT SELECT ON TABLES TO reporting_reader;
