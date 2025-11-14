from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.testing.config import db_url

from db.fixtures.fixtures_base import auctions, ports, usa_states, manheim_usa_locations, iaai_usa_locations, copart_usa_locations, canada_locations
from db.fixtures.fixtures_portprice_b2b import manh_prices, iaai_price, copart_price, canada_prices
from db.fixtures.fixtures_aucfees_b2b import auction_fee_types,fee_ranges_manheim_canada, fee_ranges_impact_canada, fee_ranges_copart_canada, fee_ranges_iaai_usa, fee_ranges_manheim_usa, fee_ranges_copart_usa
from db.fixtures.fixtures_frieights_b2b import freight_costs, map_fuels, port_cervices,map_vechile, expeditory_mults
from db.fixtures.fixtures_pension_b2b import pens_fees, pens_const
from db.fixtures.fixtures_excise_b2b import ukr_transfer, excices1,excices2,sublot_prices, port_add_1, port_additional_charges, adjustments

from app.core.config import settings

# TOCHANGE

# fix for linux path
db_url = settings.database_url
db_url = 'postgresql' + db_url[db_url.find('://'):]


engine = create_engine(db_url + "?options=-csearch_path=calculator")  # DB URL in new schema
Session = sessionmaker(bind=engine)
session = Session()

for auc in auctions:
    session.add(auc)
session.commit()

for state in usa_states:
    session.add(state)
session.commit()

for state in iaai_usa_locations:
    session.add(state)
session.commit()

for state in copart_usa_locations:
    session.add(state)
session.commit()

for state in manheim_usa_locations:
    session.add(state)
session.commit()

for state in canada_locations:
    session.add(state)
session.commit()

for entry in ports:
    session.add(entry)

for auc in iaai_price:
    session.add(auc)
session.commit()

for auc in manh_prices:
    session.add(auc)
session.commit()

for auc in copart_price:
    session.add(auc)
session.commit()

for auc in canada_prices:
    session.add(auc)
session.commit()


for a in auction_fee_types:
    session.add(a)
session.commit()


for a in fee_ranges_manheim_canada:
    session.add(a)
session.commit()


for a in fee_ranges_impact_canada:
    session.add(a)
session.commit()

for a in fee_ranges_copart_canada:
    session.add(a)
session.commit()

for a in fee_ranges_iaai_usa:
    session.add(a)
session.commit()

for a in fee_ranges_copart_usa:
    session.add(a)
session.commit()

for a in fee_ranges_manheim_usa:
    session.add(a)
session.commit()

for a in freight_costs:
    session.add(a)
session.commit()

for a in map_fuels:
    session.add(a)
session.commit()

for a in map_vechile:
    session.add(a)
session.commit()

for a in expeditory_mults:
    session.add(a)
session.commit()

for a in port_cervices:
    session.add(a)
session.commit()

for a in pens_const:
    session.add(a)
session.commit()

for a in pens_fees:
    session.add(a)
session.commit()

for a in ukr_transfer:
    session.add(a)
session.commit()
for a in sublot_prices:
    session.add(a)
session.commit()
for a in excices1:
    session.add(a)
session.commit()
for a in excices2:
    session.add(a)
session.commit()

for a in port_add_1:
    session.add(a)
session.commit()
for a in port_additional_charges:
    session.add(a)
session.commit()
for a in adjustments:
    session.add(a)
session.commit()

session.close()