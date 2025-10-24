from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import (
    UserAuctionAccountCreate,
    UserAuctionAccountUpdate,
    UserAuctionAccountResponse
)
from app.models.user_auction import UserAuctionAccount
from app.core.security.encryption import validate_username, encrypt
from app.api.dependencies import get_current_user
from app.tasks.account_validation import validate_auction_account

router = APIRouter()


@router.post("/", response_model=UserAuctionAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_auction_account(
    account_in: UserAuctionAccountCreate,
    current_user = Depends(get_current_user)
):
    """
    Создаёт новый аккаунт пользователя для определённого аукциона (например, Copart, IAAI).

    Проверяет корректность имени пользователя в зависимости от типа аукциона,
    шифрует логин и пароль, сохраняет запись в базе данных и
    запускает асинхронную задачу для валидации учётных данных.

    Args:
        account_in (UserAuctionAccountCreate): Данные нового аккаунта (auction_type, username, password).
        current_user: Текущий пользователь, полученный из зависимости get_current_user.

    Returns:
        UserAuctionAccountResponse: Созданный аукционный аккаунт (в зашифрованном виде).

    Raises:
        HTTPException: 
            - 400 — если формат имени пользователя не соответствует требованиям для данного аукциона.
    """
    if not validate_username(account_in.auction_type.value, account_in.username):
        raise HTTPException(status_code=400, detail="Invalid username format for auction type")

    encrypted_username = encrypt(account_in.username)
    encrypted_password = encrypt(account_in.password)

    account = await UserAuctionAccount.create(
        user=current_user,
        auction_type=account_in.auction_type,
        encrypted_username=encrypted_username,
        encrypted_password=encrypted_password
    )

    # Асинхронная проверка валидности аккаунта через Celery
    validate_auction_account.delay(account.id)
    return account


@router.put("/{account_id}", response_model=UserAuctionAccountResponse)
async def update_auction_account(
    account_id: int,
    account_in: UserAuctionAccountUpdate,
    current_user = Depends(get_current_user)
):
    """
    Обновляет существующий аукционный аккаунт пользователя.

    Может изменять логин и/или пароль. Новые данные шифруются,
    и после обновления снова запускается проверка через Celery.

    Args:
        account_id (int): Идентификатор аккаунта.
        account_in (UserAuctionAccountUpdate): Новые данные (username, password).
        current_user: Текущий пользователь, полученный из зависимости get_current_user.

    Returns:
        UserAuctionAccountResponse: Обновлённый аукционный аккаунт.

    Raises:
        HTTPException: 
            - 404 — если аккаунт не найден для данного пользователя.
            - 400 — если имя пользователя некорректно для выбранного типа аукциона.
            - 400 — если пароль короче 8 символов.
    """
    account = await UserAuctionAccount.get_or_none(id=account_id, user=current_user)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account_in.username:
        if not validate_username(account.auction_type.value, account_in.username):
            raise HTTPException(status_code=400, detail="Invalid username format for auction type")
        account.encrypted_username = encrypt(account_in.username)

    if account_in.password:
        if len(account_in.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        account.encrypted_password = encrypt(account_in.password)

    await account.save()

    # Повторная валидация аккаунта после изменения
    validate_auction_account.delay(account.id)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auction_account(
    account_id: int,
    current_user = Depends(get_current_user)
):
    """
    Удаляет аукционный аккаунт пользователя.

    Args:
        account_id (int): Идентификатор аккаунта для удаления.
        current_user: Текущий пользователь, полученный из зависимости get_current_user.

    Raises:
        HTTPException: 
            - 404 — если аккаунт не найден для данного пользователя.
    """
    account = await UserAuctionAccount.get_or_none(id=account_id, user=current_user)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await account.delete()
    return
