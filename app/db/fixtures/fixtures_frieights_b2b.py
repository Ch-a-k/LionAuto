from ..models import (FreightCosts, MapFuelToFreightType, MapVehicleToFreightType, PortDeliveryServices,
                      ExpeditoryMult)

# ports = [
# Port(name='NEWARK, NJ', country='USA', is_export=True,commentary='b2b'),
# Port(name='SAVANNAH, GA', country='USA', is_export=True,commentary='b2b'),
# Port(name='HOUSTON, TX', country='USA', is_export=True,commentary='b2b'),
# Port(name='MIAMI, FL', country='USA', is_export=True,commentary='b2b'),
# Port(name='CA', country='USA', is_export=True,commentary='b2b'),
# Port(name='Montreal', country='Canada', is_export=True,commentary='b2b'),
# Port(name='Seattle', country='USA', is_export=True,commentary='b2b'),
#
# Port(name='Klaipeda', country='Lithuania', is_export=False,commentary='b2b'),
# Port(name='Bremerhaven', country='Germany', is_export=False,commentary='b2b'),
# ]

# additional costs is just +100$
freight_costs = [
FreightCosts(country_from='USA', port_from="NEWARK, NJ",port_to="Bremerhaven",cost=500, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="SAVANNAH, GA",port_to="Bremerhaven",cost=525, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="HOUSTON, TX",port_to="Bremerhaven",cost=675, currency='USD', freight_type='base',commentary='b2b'),

FreightCosts(country_from='USA', port_from="CA",port_to="Bremerhaven",cost=1100, currency='USD', freight_type='base',commentary='b2b'),


FreightCosts(country_from='USA', port_from="NEWARK, NJ",port_to="Klaipeda",cost=600, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="SAVANNAH, GA",port_to="Klaipeda",cost=650, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="HOUSTON, TX",port_to="Klaipeda",cost=775, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="MIAMI, FL",port_to="Klaipeda",cost=930, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="CA",port_to="Klaipeda",cost=1075, currency='USD', freight_type='base',commentary='b2b'),
FreightCosts(country_from='USA', port_from="Seattle",port_to="Klaipeda",cost=1950, currency='USD', freight_type='base',commentary='b2b'),

FreightCosts(country_from='Canada', port_from="Montreal",port_to="Klaipeda",cost=1175, currency='USD', freight_type='base',commentary='b2b'),
]

map_fuels = [
MapFuelToFreightType(fuel_type="Бензин",freight_type="Базовый",commentary='b2b'),
MapFuelToFreightType(fuel_type="Дизель",freight_type="Базовый",commentary='b2b'),
MapFuelToFreightType(fuel_type="Гибрид",freight_type="Дополнительный",commentary='b2b'),
MapFuelToFreightType(fuel_type="Электро",freight_type="Дополнительный",commentary='b2b'),
]

map_vechile = [
MapVehicleToFreightType(vehicle_type="SEDAN",coefficient=1,commentary='b2b'),
MapVehicleToFreightType(vehicle_type="SUV",coefficient=1,commentary='b2b'),
MapVehicleToFreightType(vehicle_type="long SUV/pick-up",coefficient=2,commentary='b2b'),
MapVehicleToFreightType(vehicle_type="long SUV",coefficient=2,commentary='b2b'),
MapVehicleToFreightType(vehicle_type="pick-up",coefficient=2,commentary='b2b'),
MapVehicleToFreightType(vehicle_type="Мотоцикл",coefficient=0.5,commentary='b2b'),
]

port_cervices = [
PortDeliveryServices(vehicle_type="SEDAN",coefficient=1,commentary='b2b'),
PortDeliveryServices(vehicle_type="SUV",coefficient=1,commentary='b2b'),
PortDeliveryServices(vehicle_type="long SUV/pick-up",coefficient=1.5,commentary='b2b'),
PortDeliveryServices(vehicle_type="long SUV",coefficient=1.5,commentary='b2b'),
PortDeliveryServices(vehicle_type="pick-up",coefficient=1.5,commentary='b2b'),
PortDeliveryServices(vehicle_type="Мотоцикл",coefficient=1,commentary='b2b'),
]

expeditory_mults = [
ExpeditoryMult(vehicle_type="SEDAN", multiplier=1,commentary='b2b'),
ExpeditoryMult(vehicle_type="SUV", multiplier=1,commentary='b2b'),
ExpeditoryMult(vehicle_type="long SUV/pick-up", multiplier=2,commentary='b2b'),
ExpeditoryMult(vehicle_type="Мотоцикл", multiplier=1,commentary='b2b'),
ExpeditoryMult(vehicle_type="long SUV", multiplier=2,commentary='b2b'),
ExpeditoryMult(vehicle_type="pick-up", multiplier=2,commentary='b2b'),
]