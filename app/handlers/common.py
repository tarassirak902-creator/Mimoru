from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards.home import HOME_HINT, home_menu
from app.services.access import is_service_owner
from app.services.ui import panel_header

router = Router(name=__name__)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    await message.answer(
        panel_header("Главное меню", "Добро пожаловать в Mimoru.\n\n" + HOME_HINT),
        reply_markup=home_menu(is_service_owner(message.from_user.id)),
    )


@router.message(Command("help"))
async def help_command(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    await message.answer(
        panel_header("Как пользоваться Mimoru", "Большинство настроек доступны кнопками — команды запоминать не нужно.")
        + "\n\nПервый запуск\n"
        "1. Добавьте Mimoru администратором в Telegram-группу.\n"
        "2. Напишите в группе «подключить».\n"
        "3. Вернитесь сюда и нажмите «🏠 Управлять моими группами».\n\n"
        "Быстрая модерация\n"
        "Ответьте на сообщение участника: пред, мут 2ч или бан. "
        "Причину Mimoru предложит выбрать кнопкой.\n\n"
        "Отмена ввода\n"
        "Когда бот попросит прислать текст, рядом появится кнопка «✖️ Отменить ввод».",
        reply_markup=home_menu(is_service_owner(message.from_user.id)),
    )
