from ..models import PensionFundFee, PensionFundConst

pens_const = [
    PensionFundConst(id=1, name='АКТУАЛЬНЫЙ ПРОЖИТОЧНЫЙ МИНИМУМ', value=2481, commentary='b2b')
]

pens_fees = [
PensionFundFee(price_from=0, price_to=409365,           fee_amount=3, unit='%%%', commentary='b2b'),
PensionFundFee(price_from=409365, price_to=719490,      fee_amount=4, unit='%%%', commentary='b2b'),
PensionFundFee(price_from=719490, price_to=-1,      fee_amount=5, unit='%%%', commentary='b2b'),
PensionFundFee(price_from=0, price_to=409365,          fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2b'),
PensionFundFee(price_from=409365, price_to=719490,      fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2b'),
PensionFundFee(price_from=719490, price_to=-1,      fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2b'),
]