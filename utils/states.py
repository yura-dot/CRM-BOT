from aiogram.fsm.state import State, StatesGroup

class RegisterStates(StatesGroup):
    first_name = State()
    last_name = State()
    email = State()
    phone = State()
    password_note = State()
    accept_terms = State()

class AddProductStates(StatesGroup):
    name = State()
    sku = State()
    photo = State()
    description = State()
    ingredients = State()
    volume = State()
    client_price = State()
    purchase_price = State()
    stock_qty = State()
    brand = State()
    category = State()
    comment = State()

class AddCompanyStates(StatesGroup):
    name = State()
    city = State()
    iban = State()
    display_name = State()
    edrpou = State()
    legal_address = State()
    director = State()
    phone = State()

class AddBrandStates(StatesGroup):
    name = State()

class AddCategoryStates(StatesGroup):
    name = State()

class FopSettingsStates(StatesGroup):
    fop_name = State()
    iban = State()
    edrpou = State()
    bank_name = State()
    legal_address = State()
    phone = State()

class InvoiceStates(StatesGroup):
    due_date = State()
    notes = State()

class EditProfileStates(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    np_city = State()
    np_branch = State()
    np_recipient = State()

class EditProductStates(StatesGroup):
    field = State()
    value = State()

class StockUpdateStates(StatesGroup):
    qty = State()

# Стейти для вибору доставки під час оформлення замовлення
class DeliveryStates(StatesGroup):
    choose_type = State()       # вибір типу доставки
    nova_poshta_city = State()  # місто НП
    nova_poshta_branch = State()# відділення НП
    nova_poshta_recipient = State() # отримувач НП
    taxi_address = State()      # адреса таксі
    taxi_datetime = State()     # дата/час таксі
