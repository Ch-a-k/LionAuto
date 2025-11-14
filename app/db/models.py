from typing import List, Optional

from sqlalchemy import Boolean, Column, Double, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, String, \
    Table, Text, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import decimal


metadata = MetaData(schema="calculator")
class Base(DeclarativeBase):
    metadata = metadata


class Adjustments(Base):
    __tablename__ = 'adjustments'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='adjustments_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_from: Mapped[Optional[str]] = mapped_column(String(100))
    service_name: Mapped[Optional[str]] = mapped_column(String(255))
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String(3))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class Auctions(Base):
    __tablename__ = 'auctions'
    __table_args__ = (
        PrimaryKeyConstraint('auction_name', name='auctions_pkey'),
    )

    auction_name: Mapped[str] = mapped_column(String, primary_key=True)
    country: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auction_fee_type: Mapped[List['AuctionFeeType']] = relationship('AuctionFeeType', back_populates='auctions')
    auction_yards: Mapped[List['AuctionYards']] = relationship('AuctionYards', back_populates='auctions')
    map_auction_to_tax_list: Mapped[List['MapAuctionToTaxList']] = relationship('MapAuctionToTaxList', back_populates='auctions')
    port_charges: Mapped[List['PortCharges']] = relationship('PortCharges', back_populates='auctions')
    sublot_price: Mapped[List['SublotPrice']] = relationship('SublotPrice', back_populates='auctions')


class ExciseTaxCar(Base):
    __tablename__ = 'excise_tax_car'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='excise_tax_car_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fuel_type: Mapped[Optional[str]] = mapped_column(String)
    volume_from: Mapped[Optional[float]] = mapped_column(Double(53))
    volume_to: Mapped[Optional[float]] = mapped_column(Double(53))
    cost: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class ExciseTaxElectrocarBike(Base):
    __tablename__ = 'excise_tax_electrocar_bike'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='excise_tax_electrocar_bike_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fuel_type: Mapped[Optional[str]] = mapped_column(String)
    volume_from: Mapped[Optional[float]] = mapped_column(Double(53))
    volume_to: Mapped[Optional[float]] = mapped_column(Double(53))
    cost_per_unit: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 3))
    unit: Mapped[Optional[str]] = mapped_column(String)
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class ExpeditoryMult(Base):
    __tablename__ = 'expeditory_mult'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='expeditory_mult_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_type: Mapped[str] = mapped_column(Text)
    multiplier: Mapped[decimal.Decimal] = mapped_column(Numeric(4, 2))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class FreightForwardingServices(Base):
    __tablename__ = 'freight_forwarding_services'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='freight_forwarding_services_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_type: Mapped[Optional[str]] = mapped_column(String)
    country: Mapped[Optional[str]] = mapped_column(String)
    coefficient: Mapped[Optional[float]] = mapped_column(Double(53))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class MapFuelToFreightType(Base):
    __tablename__ = 'map_fuel_to_freight_type'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='map_fuel_to_freight_type_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fuel_type: Mapped[Optional[str]] = mapped_column(String)
    freight_type: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class MapVehicleToFreightType(Base):
    __tablename__ = 'map_vehicle_to_freight_type'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='map_vehicle_to_freight_type_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String)
    coefficient: Mapped[Optional[float]] = mapped_column(Double(53))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class PensionFundConst(Base):
    __tablename__ = 'pension_fund_const'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='pension_fund_const_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class PensionFundFee(Base):
    __tablename__ = 'pension_fund_fee'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='pension_fund_fee_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_from: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    price_to: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    fee_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    vehicle_type: Mapped[Optional[str]] = mapped_column(String)
    unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class Port(Base):
    __tablename__ = 'port'
    __table_args__ = (
        PrimaryKeyConstraint('name', name='port_pkey'),
    )

    name: Mapped[str] = mapped_column(String, primary_key=True)
    country: Mapped[Optional[str]] = mapped_column(String)
    is_export: Mapped[Optional[bool]] = mapped_column(Boolean)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    freight_costs: Mapped[List['FreightCosts']] = relationship('FreightCosts', foreign_keys='[FreightCosts.port_from]', back_populates='port')
    freight_costs_: Mapped[List['FreightCosts']] = relationship('FreightCosts', foreign_keys='[FreightCosts.port_to]', back_populates='port_')
    port_additional_charges: Mapped[List['PortAdditionalCharges']] = relationship('PortAdditionalCharges', back_populates='port')
    port_charges: Mapped[List['PortCharges']] = relationship('PortCharges', back_populates='port')


class PortAdditionalChargesConst(Base):
    __tablename__ = 'port_additional_charges_const'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='port_additional_charges_const_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_from: Mapped[Optional[str]] = mapped_column(String)
    fee_name: Mapped[Optional[str]] = mapped_column(String)
    fee_value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    fee_unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class PortDeliveryServices(Base):
    __tablename__ = 'port_delivery_services'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='port_delivery_services_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String)
    coefficient: Mapped[Optional[float]] = mapped_column(Double(53))
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class UkraineTransfer(Base):
    __tablename__ = 'ukraine_transfer'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='ukraine_transfer_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String)
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)


class UsaStatesDictionary(Base):
    __tablename__ = 'usa_states_dictionary'
    __table_args__ = (
        PrimaryKeyConstraint('state', name='usa_states_dictionary_pkey'),
    )

    state: Mapped[str] = mapped_column(String, primary_key=True)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auction_site_dictionary: Mapped[List['AuctionSiteDictionary']] = relationship('AuctionSiteDictionary', back_populates='usa_states_dictionary')


class AuctionFeeType(Base):
    __tablename__ = 'auction_fee_type'
    __table_args__ = (
        ForeignKeyConstraint(['auction_name'], ['auctions.auction_name'], name='auction_fee_type_auction_name_fkey'),
        PrimaryKeyConstraint('id', name='auction_fee_type_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_name: Mapped[Optional[str]] = mapped_column(String)
    tax_name: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auctions: Mapped[Optional['Auctions']] = relationship('Auctions', back_populates='auction_fee_type')
    auction_fee_range: Mapped[List['AuctionFeeRange']] = relationship('AuctionFeeRange', back_populates='fee_type')


class AuctionSiteDictionary(Base):
    __tablename__ = 'auction_site_dictionary'
    __table_args__ = (
        ForeignKeyConstraint(['state'], ['usa_states_dictionary.state'], name='auction_site_dictionary_state_fkey'),
        PrimaryKeyConstraint('id', name='auction_site_dictionary_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_name: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    usa_states_dictionary: Mapped[Optional['UsaStatesDictionary']] = relationship('UsaStatesDictionary', back_populates='auction_site_dictionary')


class AuctionYards(Base):
    __tablename__ = 'auction_yards'
    __table_args__ = (
        ForeignKeyConstraint(['auction'], ['auctions.auction_name'], name='auction_yards_auction_fkey'),
        PrimaryKeyConstraint('id', name='auction_yards_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction: Mapped[Optional[str]] = mapped_column(String)
    auction_yard: Mapped[Optional[str]] = mapped_column(String)
    location_state: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auctions: Mapped[Optional['Auctions']] = relationship('Auctions', back_populates='auction_yards')


t_fee_exceptions_by_state = Table(
    'fee_exceptions_by_state', Base.metadata,
    Column('state', String),
    Column('value', Numeric(10, 2)),
    Column('unit', String),
    Column('commentary', Text),
    ForeignKeyConstraint(['state'], ['usa_states_dictionary.state'], name='fee_exceptions_by_state_state_fkey')
)


class FreightCosts(Base):
    __tablename__ = 'freight_costs'
    __table_args__ = (
        ForeignKeyConstraint(['port_from'], ['port.name'], name='freight_costs_port_from_fkey'),
        ForeignKeyConstraint(['port_to'], ['port.name'], name='freight_costs_port_to_fkey'),
        PrimaryKeyConstraint('id', name='freight_costs_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_from: Mapped[Optional[str]] = mapped_column(String)
    country_to: Mapped[Optional[str]] = mapped_column(String)
    port_from: Mapped[Optional[str]] = mapped_column(String)
    port_to: Mapped[Optional[str]] = mapped_column(String)
    cost: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    freight_type: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    port: Mapped[Optional['Port']] = relationship('Port', foreign_keys=[port_from], back_populates='freight_costs')
    port_: Mapped[Optional['Port']] = relationship('Port', foreign_keys=[port_to], back_populates='freight_costs_')


class MapAuctionToTaxList(Base):
    __tablename__ = 'map_auction_to_tax_list'
    __table_args__ = (
        ForeignKeyConstraint(['auction'], ['auctions.auction_name'], name='map_auction_to_tax_list_auction_fkey'),
        PrimaryKeyConstraint('id', name='map_auction_to_tax_list_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction: Mapped[Optional[str]] = mapped_column(String)
    tax_name: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auctions: Mapped[Optional['Auctions']] = relationship('Auctions', back_populates='map_auction_to_tax_list')


class PortAdditionalCharges(Base):
    __tablename__ = 'port_additional_charges'
    __table_args__ = (
        ForeignKeyConstraint(['port_to'], ['port.name'], name='port_additional_charges_port_to_fkey'),
        PrimaryKeyConstraint('id', name='port_additional_charges_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_from: Mapped[Optional[str]] = mapped_column(String)
    port_to: Mapped[Optional[str]] = mapped_column(String)
    fee_name: Mapped[Optional[str]] = mapped_column(String)
    fee_value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    fee_unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    port: Mapped[Optional['Port']] = relationship('Port', back_populates='port_additional_charges')


class PortCharges(Base):
    __tablename__ = 'port_charges'
    __table_args__ = (
        ForeignKeyConstraint(['auction'], ['auctions.auction_name'], name='port_charges_auction_fkey'),
        ForeignKeyConstraint(['port_to'], ['port.name'], name='port_charges_port_to_fkey'),
        PrimaryKeyConstraint('id', name='port_charges_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction: Mapped[Optional[str]] = mapped_column(String)
    port_to: Mapped[Optional[str]] = mapped_column(String)
    price: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    transport_type: Mapped[Optional[str]] = mapped_column(String)
    auction_yard: Mapped[Optional[str]] = mapped_column(String(255))
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auctions: Mapped[Optional['Auctions']] = relationship('Auctions', back_populates='port_charges')
    port: Mapped[Optional['Port']] = relationship('Port', back_populates='port_charges')


class SublotPrice(Base):
    __tablename__ = 'sublot_price'
    __table_args__ = (
        ForeignKeyConstraint(['auction_name'], ['auctions.auction_name'], name='sublot_price_auction_name_fkey'),
        PrimaryKeyConstraint('id', name='sublot_price_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_name: Mapped[Optional[str]] = mapped_column(String)
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    auctions: Mapped[Optional['Auctions']] = relationship('Auctions', back_populates='sublot_price')


class AuctionFeeRange(Base):
    __tablename__ = 'auction_fee_range'
    __table_args__ = (
        ForeignKeyConstraint(['fee_type_id'], ['auction_fee_type.id'], name='auction_fee_range_fee_type_id_fkey'),
        PrimaryKeyConstraint('id', name='auction_fee_range_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fee_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    price_from: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    price_to: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    fee_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text)

    fee_type: Mapped[Optional['AuctionFeeType']] = relationship('AuctionFeeType', back_populates='auction_fee_range')
