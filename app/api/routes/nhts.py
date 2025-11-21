from fastapi import APIRouter
import httpx

router = APIRouter()

@router.get("/{vin}")
async def get_nhts_data(vin: str):
    """
    Декодер VIN с использованием API NHTSA.
    Возвращает только полезные данные (без пустых значений и Not Applicable).
    """
    try:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinExtended/{vin}?format=json"

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)

            if response.status_code != 200:
                return {"error": f"NHTSA API returned {response.status_code}"}

            payload = response.json()
            rows = payload.get("Results", [])

            result_list = []

            for row in rows:
                variable = row.get("Variable")
                value = row.get("Value")

                # пропускаем пустые, None, мусор
                if not variable or not value:
                    continue

                # игнорируем "Not Applicable"
                if str(value).strip().lower() == "not applicable":
                    continue

                result_list.append({
                    "variable": variable,
                    "value": value
                })

        return {
            "lot_mark_image": "",
            "data": result_list
        }

    except Exception as e:
        return {"error": f"{e}"}

