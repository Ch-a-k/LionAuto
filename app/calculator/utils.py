from decimal import Decimal, ROUND_HALF_UP

from app.db.models import (AuctionFeeType, AuctionFeeRange, Auctions, PortCharges, Adjustments, MapFuelToFreightType,
                       MapVehicleToFreightType, PortDeliveryServices, FreightCosts)
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from contextlib import contextmanager, asynccontextmanager

from app.core.config import settings

# db_url = settings.database_url
db_url = 'postgresql://' + settings.postgres_user + ':' + str(settings.postgres_password) + '@' + 'host.docker.internal:' \
         + str(settings.postgres_port) + '/' + settings.postgres_db

engine = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)


@contextmanager
def get_session(): # creates access to db
    session = Session()
    try:
        yield session
    finally:
        session.close()

# Doesn't work - killed 4 hours, refuse to kill more

# ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:123321@localhost:5432/postgres"
# async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)
#
# AsyncSessionLocal = sessionmaker(bind=async_engine,class_=AsyncSession,expire_on_commit=False,)

# @asynccontextmanager
# def get_session():
#     with AsyncSessionLocal() as session:
#         yield session


def get_fee_types(auction_name):
    with (get_session() as session):
        fee_types = session.query(AuctionFeeType.tax_name, AuctionFeeType.id)\
        .filter(AuctionFeeType.auction_name == auction_name)
        res = {}
        for f in fee_types:
            res[f[0]] = f[1]
    return res # dict

def get_fee_amounts(auction_name, car_price):
    #returns dict with name(tax) : [price, value]
    fee_list = get_fee_types(auction_name)
    # print(fee_list)
    with (get_session() as session):
        res = {}
        for fee_name, fee_val in fee_list.items():
            q = session.query(AuctionFeeRange)\
            .filter(AuctionFeeRange.fee_type_id == fee_val,
                    AuctionFeeRange.price_from <= car_price,
                    or_(
                        AuctionFeeRange.price_to > car_price,
                        AuctionFeeRange.price_to == -1
                    ))

            for a in q:
                # print(a.fee_amount, a.unit, a.fee_type_id)
                res[a.fee_type_id] = [a.fee_amount, a.unit]
    ress = {}
    # print (res)
    for ind, val in fee_list.items():
        try:
            ress[ind] = res[val]
        except:
            pass

    if auction_name == "IAAI - USA":
        ress['Environmental fee'] = [Decimal('15.00'), 'USD']
        ress['Service fee'] = [Decimal('95.00'), 'USD']

    return ress

def prepare_costs(auction_name, car_price):
    # main function for calculation of all auc fee values.
    # does the same job as 'Bнутренний Рассчет', only for auction fees
    fee_amts = get_fee_amounts(auction_name, car_price)
    results = {}
    for fee_name, fee_value in fee_amts.items():
        if fee_value[1] == '%%%': # якщо відсотки - треба конвертувати в USD
            calc = car_price * 0.01 * float(fee_value[0])
            decimal_value = Decimal(str(calc)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            results[fee_name] = [decimal_value, 'USD']
        else:
            results[fee_name] = fee_value

    return results

def excice_calculation(fuel_type, volume, car_type):
    if car_type in []:
        pass

def countries_list():
    return ['USA', 'Canada']

def auctions_list(country_name):
    with (get_session() as session):
        q = session.query(Auctions.auction_name) \
        .filter(Auctions.country == country_name)
    return [row[0] for row in q.all()]

def auctions_yard_list(auction_name):
    with (get_session() as session):
        q = session.query(PortCharges.auction_yard) \
            .filter(PortCharges.auction == auction_name) \
            .distinct()
    return [row[0] for row in q.all()]
#
# print(auctions_yard_list('IAAI - USA'))
def port_from(auction_yard, auction):
    with (get_session() as session):
        q = session.query(PortCharges.port_to)\
                .filter(PortCharges.auction_yard == auction_yard,
                        PortCharges.auction == auction,
                        PortCharges.price > 0)
    return [row[0] for row in q.all()]


def adjustmens(country):
    with (get_session() as session):
        q = session.query(Adjustments.service_name,Adjustments.value, Adjustments.unit)\
            .filter(Adjustments.country_from == country)
    res = [list(r) for r in q]
    res2 = []
    for r in res: # convert Decimal to str
        res2.append({'name': r[0],
        'value': str(r[1]),
        'currency': r[2]})
    return res2


def mapping_fuel_tofreight_type():
    with (get_session() as session):
        q = session.query(MapFuelToFreightType)
    res = []
    for r in q:
        res.append({
            'id': r.id,
            'fuel_type': r.fuel_type,
            'freight_type': r.freight_type,
            'commentary': r.commentary
        })

    return res
# print(auctions_yard_list(auction_name="IAAI - USA"))
# print(port_from(auction_yard="BALTIMORE MD 21226", auction="IAAI - USA"))


def mapping_vehicle_to_freight_type():
    with (get_session() as session):
        q = session.query(MapVehicleToFreightType)
    res = []
    for r in q:
        res.append({
            'id': r.id,
            'vehicle_type': r.vehicle_type,
            'coefficient': r.coefficient,
            'commentary': r.commentary
        })

    return res

def mapping_port_delivery_coefficients():
    with (get_session() as session):
        q = session.query(PortDeliveryServices)
    res = []
    for r in q:
        res.append({
            'id': r.id,
            'vehicle_type': r.vehicle_type,
            'coefficient': r.coefficient,
            'commentary': r.commentary
        })

    return res

def freight_costs_const():
    with (get_session() as session):
        q = session.query(FreightCosts)
    res = []
    for r in q:
        res.append({
            'id': r.id,
            'country_from': r.country_from,
            'port_from': r.port_from,
            'port_to': r.port_to,
            'cost': str(r.cost),
            'currency': r.currency,
            'freight_type': r.freight_type,
            'commentary': r.commentary,
        })

    return res

