# clima-lab

Pipeline de datos de punta a punta en AWS con reportes en Microsoft Fabric.

Extrae datos diarios de clima desde una API pública, los guarda en un data lake en S3,
los cataloga y consulta con Athena, los carga en PostgreSQL y los publica en Power BI
a través de un OneLake shortcut, todo de forma automática y con permisos mínimos
para cada componente.

## Arquitectura

~~~
                    EventBridge Scheduler (6:00 y 6:15)
                         |                    |
                         v                    v
API Open-Meteo --> Lambda extract       Lambda curate
                         |                    | MERGE (Athena)
                         v                    v
                  S3 raw/ (JSON Lines)   S3 curated/ (Iceberg)
                    |            |                |
         evento S3  |            | Athena         | OneLake shortcut
                    v            v                v
             Lambda load    Glue Data Catalog   Fabric lakehouse
             (en la VPC)    + partition          (Iceberg -> Delta)
                    |         projection              |
                    v                                 v
         RDS PostgreSQL (upsert)              Power BI (Direct Lake)
~~~

## Flujo diario

1. **6:00, extracción.** EventBridge Scheduler invoca `clima-lab-extract`, que consulta la API de Open-Meteo y guarda un archivo JSON Lines por ciudad en `raw/open_meteo/daily/ingest_date=AAAA-MM-DD/`.
2. **Carga en PostgreSQL.** Cada archivo nuevo dispara `clima-lab-load` mediante una notificación de S3. La Lambda corre dentro de la VPC, lee la contraseña de Secrets Manager por un VPC endpoint y hace upsert en RDS PostgreSQL por SSL.
3. **6:15, curación.** EventBridge Scheduler invoca `clima-lab-curate`, que ejecuta en Athena un `MERGE` hacia una tabla Iceberg deduplicada en `curated/`.
4. **Reportes.** Fabric lee la tabla Iceberg mediante un OneLake shortcut, que la expone como tabla Delta, y Power BI la consume con Direct Lake.

## Componentes

| Componente | Servicio | Función |
|---|---|---|
| Zona raw | S3 | Datos tal como llegan de la API; nunca se modifican |
| Zona curada | S3 + Apache Iceberg | Datos deduplicados, actualizados con `MERGE` |
| Catálogo | Glue Data Catalog | Tablas `clima_raw.daily` y `clima_curated.weather_daily_iceberg` |
| Consultas | Athena | Workgroup con límite de 1 GB por consulta |
| Extracción | Lambda (Python 3.12) | `lambda/extract/handler.py` |
| Carga | Lambda en VPC + RDS PostgreSQL 18 | `lambda/load/handler.py`, upsert por `(ciudad, fecha)` |
| Curación | Lambda + Athena | `lambda/curate/handler.py`, `MERGE` diario |
| Orquestación | EventBridge Scheduler + notificaciones de S3 | Horarios diarios y disparo por eventos |
| Secretos | Secrets Manager | Contraseñas de los usuarios de PostgreSQL |
| Red | VPC, security groups, VPC endpoints | Acceso privado de la Lambda a RDS, S3 y Secrets Manager |
| Reportes | Microsoft Fabric + Power BI | OneLake shortcut y modelo Direct Lake |

## Estructura del repositorio

~~~
clima-lab/
├── README.md
├── env.sh                      # Variables de sesión (source env.sh después de aws login)
├── .gitignore
├── docs/                       # Notas de configuración
├── iam/                        # Políticas de confianza de los roles
│   ├── glue-trust.json
│   ├── lambda-trust.json
│   └── scheduler-trust.json
├── lambda/
│   ├── extraer_local.py        # Extracción local para pruebas
│   ├── extract/handler.py      # API -> S3 raw
│   ├── load/handler.py         # S3 raw -> PostgreSQL (upsert)
│   └── curate/handler.py       # MERGE de Athena -> Iceberg
└── sql/
    ├── 01_raw_daily.sql        # Tabla raw con partition projection
    ├── 02_curated.sql          # Tabla Iceberg, MERGE y mantenimiento
    └── 03_postgres_setup.sql   # Esquema, tabla y usuarios de PostgreSQL
~~~

## Modelo de datos

Columnas en todas las capas: `ciudad`, `fecha`, `temp_max`, `temp_min`, `precipitacion`.

- **Raw:** una fila por ciudad, fecha y extracción. Cada extracción trae 7 días pasados y 7 de pronóstico, así que las fechas se repiten entre extracciones.
- **Curada y PostgreSQL:** una fila por `(ciudad, fecha)`. Cuando una fecha aparece en varias extracciones, gana la más reciente.

## Decisiones de diseño

- **Raw inmutable.** Cualquier día se puede reprocesar sin volver a llamar a la API.
- **Partition projection en lugar de crawler.** Athena calcula las particiones por fecha: sin costo por ejecución y sin pasos extra cada día.
- **Cargas idempotentes.** Upsert en PostgreSQL y `MERGE` en Iceberg por `(ciudad, fecha)`: reprocesar un archivo nunca duplica datos.
- **Carga atómica por archivo.** Cada archivo se carga en una transacción: entran todas sus filas o ninguna.
- **Iceberg en lugar de Delta.** Athena escribe y actualiza Iceberg con SQL; Delta requeriría Spark. Fabric virtualiza Iceberg como Delta, así que no se copian datos.
- **Shortcut en lugar de Mirroring.** Para datos en S3, el shortcut los lee en su lugar; Mirroring está pensado para replicar bases de datos.
- **Dos Lambdas separadas para extraer y cargar.** La de extracción necesita internet y la de carga necesita la red privada de RDS. Separarlas evita un NAT gateway.

## Seguridad

Mínimo privilegio en IAM: cada componente tiene su propia identidad con acceso solo a sus recursos.

| Identidad | Permisos |
|---|---|
| `clima-lab-extract-role` | Logs; `s3:PutObject` solo en `raw/open_meteo/*` |
| `clima-lab-load-role` | Logs y VPC; `s3:GetObject` en `raw/open_meteo/*`; `GetSecretValue` solo del secreto del pipeline |
| `clima-lab-curate-role` | Logs; Athena en su workgroup; lectura del catálogo y `UpdateTable`; lectura de `raw/`; escritura en la tabla Iceberg y en los resultados de Athena |
| `clima-lab-scheduler-role` | `lambda:InvokeFunction` solo sobre extract y curate |
| `clima-lab-glue-role` | Servicio de Glue; lectura y escritura solo en el bucket de datos |
| Usuario `clima-lab-fabric-reader` | `ListBucket` y `GetObject` solo sobre `curated/` |

Además:

- **Mínimo privilegio en PostgreSQL.** `pipeline_writer` puede leer, insertar y actualizar su tabla, sin `DELETE`. `reporting_reader` solo lee.
- **Sin secretos en el código.** Contraseñas generadas aleatoriamente, guardadas en Secrets Manager y leídas en tiempo de ejecución.
- **Red privada.** RDS solo acepta conexiones desde la IP de administración y desde el security group de la Lambda. La Lambda llega a S3 y Secrets Manager por VPC endpoints, sin internet.
- **Cifrado.** S3 con SSE-S3, RDS con almacenamiento cifrado y conexiones por TLS verificadas con el certificado de RDS.
- **Repositorio.** `git-secrets` bloquea commits con claves de AWS; el número de cuenta se calcula en `env.sh` y nunca se escribe en los archivos.
- **Credenciales temporales.** La CLI usa `aws login` en lugar de access keys permanentes.

## Cómo reproducirlo

Requisitos: cuenta de AWS, AWS CLI v2, Python 3.12 y un workspace de Microsoft Fabric.

1. **Acceso:** usuario IAM con MFA y `aws login --profile clima-lab`; luego `source env.sh`.
2. **Almacenamiento:** buckets de datos y de resultados con bloqueo público, versionado y reglas de ciclo de vida.
3. **Catálogo:** bases de datos `clima_raw` y `clima_curated`; ejecutar `sql/01_raw_daily.sql` en Athena.
4. **Extracción:** rol y Lambda `clima-lab-extract`; programación diaria con EventBridge Scheduler.
5. **PostgreSQL:** instancia RDS, secretos en Secrets Manager y `sql/03_postgres_setup.sql`.
6. **Red:** security groups y VPC endpoints de S3 (gateway) y Secrets Manager (interface).
7. **Carga:** rol y Lambda `clima-lab-load` dentro de la VPC, con `pg8000` y el certificado de RDS en el paquete; notificación de S3 sobre `raw/`.
8. **Curación:** carga inicial con `sql/02_curated.sql`; rol, Lambda `clima-lab-curate` y su programación diaria.
9. **Fabric:** usuario IAM de solo lectura; shortcut de Amazon S3 en la sección Tables del lakehouse apuntando a la carpeta de la tabla Iceberg; modelo semántico Direct Lake.

## Costos

Los servicios que cobran por hora aunque no se usen son RDS, el VPC endpoint de interface y las direcciones IPv4 públicas. Durante el desarrollo, RDS se puede detener con `aws rds stop-db-instance`; la extracción sigue guardando en `raw/` y esos archivos se recargan después. El resto (S3, Athena, Lambda, Scheduler) cuesta centavos con este volumen.

## Lecciones aprendidas

- Cuando una columna sale vacía en Athena sin error, casi siempre es porque la clave del JSON no coincide con el nombre de la columna. Los nombres se definen al inicio y se usan iguales en todas las capas.
- Un CTAS no puede escribir fuera del bucket de resultados si el workgroup impone su configuración; y nunca conviene dejar datos permanentes en un bucket con borrado automático.
- Una Lambda dentro de una VPC no tiene internet: necesita VPC endpoints para llegar a los servicios de AWS.
- En Fabric, un shortcut a una tabla va en Tables y apunta a la carpeta de la tabla; en Files, solo son archivos.
- `Account ... is denied access` es una restricción de la cuenta y se resuelve con AWS Support; `not authorized to perform` es un permiso de IAM que falta.

## Próximos pasos

- Encadenar extracción, carga y curación con Step Functions en lugar de horarios separados.
- Mantenimiento semanal automático de Iceberg (`OPTIMIZE` y `VACUUM`).
- Alertas cuando una Lambda falla (CloudWatch Alarms + SNS).
- Infraestructura como código (CloudFormation o Terraform).
- RDS sin acceso público, con conexión por SSM.

## Tecnologías

AWS (S3, Glue Data Catalog, Athena, Lambda, EventBridge Scheduler, RDS PostgreSQL, Secrets Manager, VPC, IAM), Apache Iceberg, Python, SQL, Microsoft Fabric, Power BI.

## Autora

Ana Recio
