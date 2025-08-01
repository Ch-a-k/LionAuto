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

    validate_auction_account.delay(account.id)
    return account

@router.put("/{account_id}", response_model=UserAuctionAccountResponse)
async def update_auction_account(
    account_id: int,
    account_in: UserAuctionAccountUpdate,
    current_user = Depends(get_current_user)
):
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
    validate_auction_account.delay(account.id)
    return account

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auction_account(
    account_id: int,
    current_user = Depends(get_current_user)
):
    account = await UserAuctionAccount.get_or_none(id=account_id, user=current_user)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await account.delete()
    return
