from fastapi import APIRouter
import httpx

router = APIRouter()

@router.get("/{vin}")
async def get_nhts_data(vin: str):
    """
    Получает и декодирует информацию о транспортном средстве с помощью API NHTSA на основе переданного VIN-кода.

    Аргументы:
        vin (str): Идентификационный номер транспортного средства (VIN) для декодирования.

    Возвращает:
        dict: Словарь, содержащий:
            - "lot_mark_image" (str): Зарезервированное поле для изображения (пока пустое).
            - "data" (list): Список словарей с данными о транспортном средстве, где:
                - "variable" (str): Название параметра.
                - "value" (str | None): Значение параметра, если оно доступно.
            - "error" (str, опционально): Сообщение об ошибке в случае возникновения исключения.

    Исключения:
        Exception: В случае ошибки при запросе к API или обработке данных.
    """
    try:
        result_list = []
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinExtended/{vin}?format=json"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            data = data.get("Results", None)
            if data:
                for values in data:
                    if values.get('Variable', None) is not None and values.get('Value', None) is not None:
                        result_list.append({"variable":values.get('Variable', None), "value":values.get('Value', None)})
        return {
            "lot_mark_image":"",
            "data":result_list
        }
    except Exception as e:
        return {"error":f"{e}"}
