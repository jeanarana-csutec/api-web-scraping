import os
import uuid
import requests
import boto3

IGP_API_URL = os.environ.get(
    "IGP_API_URL",
    "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/2026",  # CONFIRMAR en DevTools
)
TABLE_NAME = "TablaSismosIGP"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def lambda_handler(event, context):
    resp = requests.get(IGP_API_URL, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return {"statusCode": resp.status_code, "body": "Error al acceder al IGP"}

    data = resp.json()
    if not data:
        return {"statusCode": 404, "body": "No se encontraron sismos"}

    # Más recientes primero y nos quedamos con los 10 últimos
    data.sort(key=lambda s: f"{s.get('fecha_local','')} {s.get('hora_local','')}", reverse=True)
    sismos = []
    for i, s in enumerate(data[:10], start=1):
        sismos.append({
            "id": str(uuid.uuid4()),
            "numero": i,
            "reporte": str(s.get("reporte", "")),
            "referencia": str(s.get("referencia", "")),
            "fecha_hora_local": f"{s.get('fecha_local','')} {s.get('hora_local','')}",
            "magnitud": str(s.get("magnitud", "")),
            "profundidad": str(s.get("profundidad", "")),
            "latitud": str(s.get("latitud", "")),
            "longitud": str(s.get("longitud", "")),
        })

    table = boto3.resource("dynamodb").Table(TABLE_NAME)

    # Limpiar tabla antes de insertar (con paginación)
    items = []
    scan = table.scan()
    items.extend(scan["Items"])
    while "LastEvaluatedKey" in scan:
        scan = table.scan(ExclusiveStartKey=scan["LastEvaluatedKey"])
        items.extend(scan["Items"])
    with table.batch_writer() as batch:
        for it in items:
            batch.delete_item(Key={"id": it["id"]})

    with table.batch_writer() as batch:
        for s in sismos:
            batch.put_item(Item=s)

    return {"statusCode": 200, "body": sismos}
