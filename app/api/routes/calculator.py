from fastapi import APIRouter, Query

from app.schemas import TransLiteral
from app.calculator.utils import (countries_list, auctions_list, auctions_yard_list, prepare_costs, port_from,
                                  adjustmens,
                                  mapping_fuel_tofreight_type, mapping_vehicle_to_freight_type,
                                  mapping_port_delivery_coefficients, freight_costs_const)
router = APIRouter()

@router.get("/countries_from")
def get_countries(
    language: TransLiteral = Query("en"),
):
    return {'countries': countries_list()}

@router.get("/auctions")
def get_auctions(
        country: str,
        language: TransLiteral = Query("en")):
    res =  auctions_list(country)
    return res

@router.get("/auction_yards")
def get_auction_yards(
        auction: str,
        language: TransLiteral = Query("en")):
    result =  auctions_yard_list(auction)
    return result

@router.get("/port_from")
def get_port_from(
        auction_yard: str,
        language: TransLiteral = Query("en")):

    return {}

### test from this point
@router.get("/port_to")
def get_port_to(
        auction_yard: str,
        auction: str,
        language: TransLiteral = Query("en")
):
    return port_from(auction_yard, auction)

@router.get("/calculations")
def get_inner_calculations(
        auction_name: str,
        car_price: str,
        language: TransLiteral = Query("en"),
):
    result =  prepare_costs(auction_name, car_price)
    return result

@router.get("/adjustmens")
def get_adjustmens(
        country: str,
        language: TransLiteral = Query("en"),
):
    result =  adjustmens(country)
    return result

@router.get("/get_fuel_coefficients")
def get_fuel_coefficients(
        language: TransLiteral = Query("en"),
):
    return mapping_fuel_tofreight_type()



@router.get("/get_vehicle_coefficients")
def get_vehicle_coefficients(
        language: TransLiteral = Query("en"),
):
    return mapping_vehicle_to_freight_type()


@router.get("/get_port_coefficients")
def get_port_coefficients(
        language: TransLiteral = Query("en"),
):
    return mapping_port_delivery_coefficients()


@router.get("/get_freight_costs")
def get_port_coefficients(
        language: TransLiteral = Query("en"),
):
    return freight_costs_const()
