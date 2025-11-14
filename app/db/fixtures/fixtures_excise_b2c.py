from ..models import (ExciseTaxCar, ExciseTaxElectrocarBike, UkraineTransfer, SublotPrice,
                      PortAdditionalChargesConst, PortAdditionalCharges, Adjustments)

ukr_transfer = [
UkraineTransfer(id=1, value=300, unit='USD',vehicle_type="SEDAN", commentary='b2c'),
UkraineTransfer(id=2, value=300, unit='USD',vehicle_type="SUV", commentary='b2c'),
UkraineTransfer(id=3, value=600, unit='USD',vehicle_type="long SUV/pick-up", commentary='b2c'),
UkraineTransfer(id=4, value=300, unit='USD',vehicle_type="Мотоцикл", commentary='b2c'),
UkraineTransfer(id=5, value=600, unit='USD',vehicle_type="long SUV", commentary='b2c'),
UkraineTransfer(id=6, value=600, unit='USD',vehicle_type="pick-up", commentary='b2c'),
]

sublot_prices = [
    SublotPrice(id=1, auction_name='IAAI - USA', value=100, unit='USD', commentary='b2c'),
    SublotPrice(id=2, auction_name='Copart - USA', value=50, unit='USD', commentary='b2c'),
]

excices1 = [
    ExciseTaxElectrocarBike(fuel_type='Электро', volume_from=0, volume_to=-1,cost_per_unit=1,unit='кВт⋅ч', currency='EUR', commentary='b2c'),
    ExciseTaxElectrocarBike(fuel_type='Мотоцикл', volume_from=0, volume_to=500,cost_per_unit=0.062,unit='см3', currency='EUR', commentary='b2c'),
    ExciseTaxElectrocarBike(fuel_type='Мотоцикл', volume_from=500, volume_to=800,cost_per_unit=0.443,unit='см3', currency='EUR', commentary='b2c'),
    ExciseTaxElectrocarBike(fuel_type='Мотоцикл', volume_from=800, volume_to=-1,cost_per_unit=0.447,unit='см3', currency='EUR', commentary='b2c'),
]

excices2 = [
    ExciseTaxCar(unit='см3', fuel_type="Бензин", volume_from=0,volume_to=3000, cost=50, currency='EUR', commentary='b2c'),
    ExciseTaxCar(unit='см3', fuel_type="Бензин", volume_from=3000,volume_to=-1, cost=100,currency='EUR', commentary='b2c'),
    ExciseTaxCar(unit='см3', fuel_type="Дизель", volume_from=0,volume_to=3500, cost=75, currency='EUR', commentary='b2c'),
    ExciseTaxCar(unit='см3', fuel_type="Дизель", volume_from=3500,volume_to=0, cost=150,currency='EUR', commentary='b2c'),
    ExciseTaxCar(unit='см3', fuel_type="Гибрид", volume_from=0,volume_to=3000,  cost=50,currency='EUR', commentary='b2c'),
    ExciseTaxCar(unit='см3', fuel_type="Гибрид", volume_from=3000,volume_to=-1, cost=100,currency='EUR', commentary='b2c'),
]

port_add_1 = [
    PortAdditionalChargesConst(country_from='USA', fee_name='Услуги "Factum Авто Украина"', fee_value=0,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='USA', fee_name='Расходы на Экспорт', fee_value=75,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='USA', fee_name='Сбор за Хранение', fee_value=50,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='USA', fee_name='Сертификация', fee_value=110,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='USA', fee_name='Стоянка в порту', fee_value=50,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='USA', fee_name='Страхование', fee_value=1.5,fee_unit='%%%', commentary='b2c'),

    PortAdditionalChargesConst(country_from='Canada', fee_name='Услуги "Factum Авто Украина"', fee_value=0,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='Canada', fee_name='Расходы на Экспорт', fee_value=150,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='Canada', fee_name='Сбор за Хранение', fee_value=50,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='Canada', fee_name='Сертификация', fee_value=110,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='Canada', fee_name='Стоянка в порту', fee_value=50,fee_unit='USD', commentary='b2c'),
    PortAdditionalChargesConst(country_from='Canada', fee_name='Страхование', fee_value=1.5,fee_unit='%%%', commentary='b2c'),
]

port_additional_charges = [
PortAdditionalCharges(port_to='Klaipeda', country_from='USA', fee_name='Экспедиторские услуги', fee_value=325, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='USA', fee_name='Брокерские услуги', fee_value=125, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='USA', fee_name='Доставка до Украины', fee_value=600, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='USA', fee_name='Доставка до Украины (Высокий тариф)', fee_value=600, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='Canada', fee_name='Экспедиторские услуги', fee_value=325, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='Canada', fee_name='Брокерские услуги', fee_value=125, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='Canada', fee_name='Доставка до Украины', fee_value=600, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Klaipeda', country_from='Canada', fee_name='Доставка до Украины (Высокий тариф)', fee_value=600, fee_unit='USD', commentary='b2c'),

PortAdditionalCharges(port_to='Bremerhaven', country_from='USA', fee_name="Экспедиторские услуги", fee_value=575, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='USA', fee_name="Брокерские услуги", fee_value=100, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='USA', fee_name="Доставка до Украины", fee_value=775, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='USA', fee_name="Доставка до Украины (Высокий тариф)", fee_value=980, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='Canada', fee_name="Экспедиторские услуги", fee_value=565, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='Canada', fee_name="Брокерские услуги", fee_value=100, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='Canada', fee_name="Доставка до Украины", fee_value=880, fee_unit='USD', commentary='b2c'),
PortAdditionalCharges(port_to='Bremerhaven', country_from='Canada', fee_name="Доставка до Украины (Высокий тариф)", fee_value=980, fee_unit='USD', commentary='b2c'),
]

adjustments = [
    Adjustments(country_from='USA', service_name='Услуги "Factum Авто Украина"', value=600, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Брокерские услуги', value=100, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Экспедиторские услуги', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Расходы на Экспорт', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Доставка до порту відправлення в США', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Морське транспортування в Європу', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Сертификация', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Стоянка в порту', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Доставка до Украины (Высокий тариф)', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='USA', service_name='Сборы аукциона', value=0, unit='USD', commentary='b2c'),

    Adjustments(country_from='Canada', service_name='Услуги "Factum Авто Украина"', value=600, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Брокерские услуги', value=100, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Экспедиторские услуги', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Расходы на Экспорт', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Доставка до порту відправлення в США', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Морське транспортування в Європу', value=50, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Сертификация', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Стоянка в порту', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Доставка до Украины (Высокий тариф)', value=0, unit='USD', commentary='b2c'),
    Adjustments(country_from='Canada', service_name='Сборы аукциона', value=0, unit='USD', commentary='b2c'),
]
