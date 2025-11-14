from ..models import PensionFundFee, PensionFundConst

pens_const = [
    PensionFundConst(id=1, name='АКТУАЛЬНЫЙ ПРОЖИТОЧНЫЙ МИНИМУМ', value=3028, commentary='b2c')
]

pens_fees = [
PensionFundFee(price_from=0, price_to=499620,           fee_amount=3, unit='%%%', commentary='b2c'),
PensionFundFee(price_from=499620, price_to=878120,      fee_amount=4, unit='%%%', commentary='b2c'),
PensionFundFee(price_from=878120, price_to=-1,   fee_amount=5, unit='%%%', commentary='b2c'),
PensionFundFee(price_from=0, price_to=499620,           fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2c'),
PensionFundFee(price_from=499620, price_to=878120,      fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2c'),
PensionFundFee(price_from=878120, price_to=-1,   fee_amount=0, unit='%%%', vehicle_type='Электро', commentary='b2c'),
]