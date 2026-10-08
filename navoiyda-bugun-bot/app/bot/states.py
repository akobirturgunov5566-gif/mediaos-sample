from aiogram.fsm.state import State, StatesGroup


class NewListing(StatesGroup):
    phone = State()
    subtype = State()
    category = State()
    title = State()
    salary = State()
    price = State()
    location = State()
    description = State()
    photo = State()


class Contact(StatesGroup):
    text = State()


class RejectReason(StatesGroup):
    text = State()
