from ..models import (FreightCosts, MapFuelToFreightType, MapVehicleToFreightType, PortDeliveryServices,
                      ExpeditoryMult)

# ports = [
# Port(name='NEWARK, NJ', country='USA', is_export=True,commentary='b2c'),
# Port(name='SAVANNAH, GA', country='USA', is_export=True,commentary='b2c'),
# Port(name='HOUSTON, TX', country='USA', is_export=True,commentary='b2c'),
# Port(name='MIAMI, FL', country='USA', is_export=True,commentary='b2c'),
# Port(name='CA', country='USA', is_export=True,commentary='b2c'),
# Port(name='Montreal', country='Canada', is_export=True,commentary='b2c'),
# Port(name='Seattle', country='USA', is_export=True,commentary='b2c'),
#
# Port(name='Klaipeda', country='Lithuania', is_export=False,commentary='b2c'),
# Port(name='Bremerhaven', country='Germany', is_export=False,commentary='b2c'),
# ]

# additional costs is just +175$
freight_costs = [
FreightCosts(country_from='USA', port_from="NEWARK, NJ",port_to="Bremerhaven",cost=600, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="SAVANNAH, GA",port_to="Bremerhaven",cost=625, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="HOUSTON, TX",port_to="Bremerhaven",cost=775, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="MIAMI, FL",port_to="Bremerhaven",cost=725, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="CA",port_to="Bremerhaven",cost=1200, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='Canada', port_from="Montreal",port_to="Bremerhaven",cost=950, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='Canada', port_from="Seattle",port_to="Bremerhaven",cost=1950, currency='USD', freight_type='base',commentary='b2c'),

FreightCosts(country_from='USA', port_from="NEWARK, NJ",port_to="Klaipeda",cost=740, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="SAVANNAH, GA",port_to="Klaipeda",cost=790, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='USA', port_from="HOUSTON, TX",port_to="Klaipeda",cost=940, currency='USD', freight_type='base',commentary='b2c'),

FreightCosts(country_from='USA', port_from="CA",port_to="Klaipeda",cost=1270, currency='USD', freight_type='base',commentary='b2c'),
FreightCosts(country_from='Canada', port_from="Montreal",port_to="Klaipeda",cost=950, currency='USD', freight_type='base',commentary='b2c'),
]

map_fuels = [
MapFuelToFreightType(fuel_type="Бензин",freight_type="Базовый",commentary='b2c'),
MapFuelToFreightType(fuel_type="Дизель",freight_type="Базовый",commentary='b2c'),
MapFuelToFreightType(fuel_type="Гибрид",freight_type="Дополнительный",commentary='b2c'),
MapFuelToFreightType(fuel_type="Электро",freight_type="Дополнительный",commentary='b2c'),
]

map_vechile = [
MapVehicleToFreightType(vehicle_type="SEDAN",coefficient=1,commentary='b2c'),
MapVehicleToFreightType(vehicle_type="SUV",coefficient=1.1,commentary='b2c'),
MapVehicleToFreightType(vehicle_type="long SUV/pick-up",coefficient=2,commentary='b2c'),
MapVehicleToFreightType(vehicle_type="long SUV",coefficient=2,commentary='b2c'),
MapVehicleToFreightType(vehicle_type="pick-up",coefficient=2,commentary='b2c'),
MapVehicleToFreightType(vehicle_type="Мотоцикл",coefficient=0.5,commentary='b2c'),
]

port_cervices = [
PortDeliveryServices(vehicle_type="SEDAN",coefficient=1,commentary='b2c'),
PortDeliveryServices(vehicle_type="SUV",coefficient=1.1,commentary='b2c'),
PortDeliveryServices(vehicle_type="long SUV/pick-up",coefficient=2,commentary='b2c'),
PortDeliveryServices(vehicle_type="long SUV",coefficient=2,commentary='b2c'),
PortDeliveryServices(vehicle_type="pick-up",coefficient=2,commentary='b2c'),
PortDeliveryServices(vehicle_type="Мотоцикл",coefficient=1,commentary='b2c'),
]

expeditory_mults = [
ExpeditoryMult(vehicle_type="SEDAN", multiplier=1,commentary='b2c'),
ExpeditoryMult(vehicle_type="SUV", multiplier=1.1,commentary='b2c'),
ExpeditoryMult(vehicle_type="long SUV/pick-up", multiplier=2,commentary='b2c'),
ExpeditoryMult(vehicle_type="Мотоцикл", multiplier=1,commentary='b2c'),
ExpeditoryMult(vehicle_type="long SUV", multiplier=2,commentary='b2c'),
ExpeditoryMult(vehicle_type="pick-up", multiplier=2,commentary='b2c'),
]