import time
import requests
from datetime import datetime
from utils.db.deps import session_maker_sync
from app.parser.models import ParserFile
from app.lot.models import Lot
from typing import List

class GoogleSheetMonitor:
    def __init__(self, api_key, spreadsheet_id, sheet_name, start_row, end_row):
        """
        Инициализация монитора.
        """
        self.api_key = api_key
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.start_row = start_row
        self.end_row = end_row
        self.base_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"

    def get_data(self, range_name):
        """
        Получение данных из указанного диапазона Google Sheets.
        """
        url = f"{self.base_url}/values/{range_name}?key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("values", [])
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []

    def monitor_sheet(self):
        """
        Основной метод, который проверяет диапазон ячеек и увеличивает его.
        """
        self.end_row += 1
        while True:
            # Определение текущего диапазона
            range_name = f"{self.sheet_name}!A{self.start_row}:I{self.end_row}"
            print(f"Checking range: {range_name}")
            
            # Получение данных
            data = self.get_data(range_name)
            if data:
                for _, row in enumerate(data):
                    try:
                            # Проверяем, если есть дата в первой колонке
                        sale_date_str = row[0]
                        sale_date = datetime.strptime(sale_date_str, "%d.%m.%Y")
                        current_date = datetime.now()
                        print(f'[DEBUG] row with vin: {row[3]}, date: {row[0]}')
                        # Проверка на заданное условие
                        if sale_date < current_date:
                            if any("IAAI" in str(cell) for cell in row):
                                with session_maker_sync() as db:
                                    vin = row[3].strip()
                                    vin = vin.replace(' ','')
                                    lots: List[Lot] = db.query(Lot).filter(Lot.vin == vin).all()
                                    if lots:
                                        for lot in lots:
                                            lot.is_historical = True  # Update field
                                            lot.sale_datetime = sale_date
                                            if any("usd" in str(cell) for cell in row) or any("usd" in str(cell) for cell in row):
                                                # Преобразование строки в число с плавающей точкой
                                                value = row[4].replace('usd', '').strip()  # Удалить "usd" и пробелы

                                                # Заменить неразрывные пробелы и запятую на точку
                                                value = value.replace('\xa0', '').replace(',', '.')

                                                # Преобразовать в float
                                                try:
                                                    value = value.replace(' ','').replace('.00','')
                                                    numeric_value = int(value)
                                                    lot.bid = numeric_value
                                                    print(numeric_value)
                                                except ValueError as e:
                                                    print(f"Ошибка при преобразовании в число: {e}")
                                            db.commit() 
                                            print(f'[SUCCESS] Change lot with vin: {lot.vin}')
                            self.end_row += 1
                    except Exception as e:
                        print(e)
                        continue
            # Ждём 5 минут перед следующей проверкой
            time.sleep(5)
            self.start_row+=1

# Настройка параметров
API_KEY = "AIzaSyC9E-I9GHn9CLO_IhYLT0s_98WIoRoRGEQ"
SPREADSHEET_ID = "1u2A3ekCq8_03GvzweXATUvqDzssuka_1wwmp5UdaMhY"
SHEET_NAME = "Список покупок"
START_ROW = 1500
END_ROW = 2000

# Создаём экземпляр монитора
monitor = GoogleSheetMonitor(API_KEY, SPREADSHEET_ID, SHEET_NAME, START_ROW, END_ROW)

# Запускаем мониторинг
monitor.monitor_sheet()