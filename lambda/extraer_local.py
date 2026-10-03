import json
import os
import urllib.request

CIUDADES = {"san-jose": (9.93, -84.08), "montreal": (45.50, -73.57)}

URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=auto&past_days=7"
)

os.makedirs("data", exist_ok=True)

for ciudad, (lat, lon) in CIUDADES.items():
    with urllib.request.urlopen(URL.format(lat=lat, lon=lon), timeout=20) as r:
        d = json.load(r)["daily"]
        ruta = f"data/{ciudad}.json"
        with open(ruta, "w") as f:
            for i, dia in enumerate(d["time"]):
                f.write(
                    json.dumps(
                        {
                            "ciudad": ciudad,
                            "fecha": dia,
                            "temp_max": d["temperature_2m_max"][i],
                            "temp_min": d["temperature_2m_min"][i],
                            "precipitacion": d["precipitation_sum"][i],
                        }
                    )
                    + "\n"
                )
        print(f"{ruta}: {len(d['time'])} registros")