# Fase 1: Crear y proteger los buckets de S3

## 1. Definir nombres únicos para los buckets

Los nombres de los buckets deben ser únicos en todo AWS. Para evitar conflictos, usa el ID de tu cuenta como sufijo.

```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export DATA_BUCKET="clima-lab-datalake-${ACCOUNT_ID}"
export RESULTS_BUCKET="clima-lab-athena-results-${ACCOUNT_ID}"
```

## 2. Crear los buckets

```bash
aws s3api create-bucket \
  --bucket "$DATA_BUCKET" \
  --region us-east-1

aws s3api create-bucket \
  --bucket "$RESULTS_BUCKET" \
  --region us-east-1
```

Cada comando responde con un `Location` indicando la ubicación del bucket.

## 3. Bloquear el acceso público

Aunque los buckets nuevos vienen bloqueados por defecto, es recomendable dejar esta configuración explícita.

```bash
aws s3api put-public-access-block \
  --bucket "$DATA_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-public-access-block \
  --bucket "$RESULTS_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 4. Activar versionado en el bucket de datos

El versionado protege contra sobrescrituras y borrados accidentales.

```bash
aws s3api put-bucket-versioning \
  --bucket "$DATA_BUCKET" \
  --versioning-configuration Status=Enabled
```

## 5. Configurar reglas de ciclo de vida para controlar costos

### Bucket de datos

Las versiones antiguas se eliminan después de 30 días para evitar que el versionado acumule costo.

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$DATA_BUCKET" \
  --lifecycle-configuration '{"Rules":[{"ID":"limpiar-versiones-viejas","Status":"Enabled","Filter":{"Prefix":""},"NoncurrentVersionExpiration":{"NoncurrentDays":30}}]}'
```

### Bucket de resultados de Athena

Todo el contenido se elimina después de 7 días.

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$RESULTS_BUCKET" \
  --lifecycle-configuration '{"Rules":[{"ID":"expirar-resultados","Status":"Enabled","Filter":{"Prefix":""},"Expiration":{"Days":7}}]}'
```

## 6. Verificar la configuración

```bash
aws s3 ls
aws s3api get-bucket-encryption --bucket "$DATA_BUCKET"
aws s3api get-bucket-versioning --bucket "$DATA_BUCKET"
aws s3api get-public-access-block --bucket "$DATA_BUCKET"
```

> Esta validación confirma que los buckets se crearon correctamente y que las políticas de seguridad están aplicadas.