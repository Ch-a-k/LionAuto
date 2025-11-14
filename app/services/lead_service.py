from app.schemas import CreateLeadSchema
from app.core.config import settings

from fastapi import HTTPException
import aiosmtplib
import asyncio
import re
import httpx
from loguru import logger

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from tortoise.expressions import Q
from app.models import Lead
from app.schemas import CreateLeadSchema, LeadSchema

async def lead_generation(
    body: CreateLeadSchema,
    local: Optional[str]
):
    pipeline_id = settings.tornados_id_amocrm[local] if local else settings.tornados_id_amocrm["ua"]
    result = {
        "name": "З сайту factum-auto.com",
        "tags_to_add": [{
                "name": "Website"
            }],
        "pipeline_id": pipeline_id,
        "responsible_user_id": settings.tornados_contact_amocrm[local] if local in settings.tornados_contact_amocrm else 2254705,  # manager id (inside profile)
        "_embedded": {
            "contacts": [
                {
                    "responsible_user_id": settings.tornados_contact_amocrm[local] if local in settings.tornados_contact_amocrm else 2254705,
                    "first_name": body.name,
                    "custom_fields_values": [

                    ]
                }
            ]
        },
        "custom_fields_values": [
        ]
    }

    contacts_custom_fields_values: list = result['_embedded']['contacts'][0]['custom_fields_values']
    if body.phone:
        _phone = re.sub(r'[^\d+]', '', body.phone)
        _phone_body ={
            "field_code": "PHONE",
            "values": [
                {
                    "enum_code": "WORK",
                    "value": _phone
                }
            ]
        }
        contacts_custom_fields_values.append(_phone_body)

    if body.email:
        _email_body = {
            "field_code": "EMAIL",
            "values": [
                {
                    "enum_code": "WORK",
                    "value": body.email
                }
            ]
        }
        contacts_custom_fields_values.append(_email_body)
    
    if body.client_id:
        _client_id_body = {
            "field_id": 571759,
            "values": [
                {
                    "value": body.client_id
                }
            ]
        }
        result['custom_fields_values'].append(_client_id_body)

    # add custom fields
    for field_name, field_value in body.model_dump().items():
        field_id = settings.field_values_const_amocrm.get(field_name)
        if not field_id:
            continue
        r = {
            "field_id": field_id,
            "values": [
                {
                    "value": field_value
                }
            ]
        }
        result['custom_fields_values'].append(r)

    # add custom fields
    contacts_custom_fields_values: list = result['custom_fields_values']
    for field_name, field_value in body.model_dump().items():
        field_id = settings.custom_field_value_const_amocrm.get(field_name)
        if not field_id:
            continue

        r = {
            "field_id": field_id,
            "values": [
                {
                    "value": field_value,
                }
            ]
        }
        result['custom_fields_values'].append(r)


    data = [result]
    # x = json.dumps(data)
    _url = f"https://{settings.amocrm_api_base_subdomain}.amocrm.ru/api/v4/leads/complex"
    # create async tasks

    # Gmail SMTP server address: smtp.gmail.com
    # Gmail SMTP username: contact@factum-auto.com
    # Gmail SMTP password: 46EcwJ9b4bqgLG
    # Gmail SMTP port (TLS): 587
    # Gmail SMTP port (SSL): 465
    # Gmail SMTP TLS/SSL required: Yes

    _headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {settings.amocrm_api_access_token}',
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(_url, json=data, headers=_headers)
    
    
    recipients = [
        'nazarfapikulyk@gmail.com',
        'artemenko36nastya@gmail.com',
        'aleksey.factum@gmail.com',
        'kachuryura391@gmail.com',
        'ooleksiivna08@gmail.com',
        'devteam@factum-auto.com',
        'solnishkoffanother@gmail.com'
    ]
    subject = "З сайту factum-auto.com"
    email_body = await generate_email_body(body)
    asyncio.create_task(send_email(recipients, subject, email_body))
    # await send_email(recipients, subject, email_body)


    if response.status_code < 200 or response.status_code > 204:
        errors = {
            301: 'Moved permanently.',
            400: 'Wrong structure of the array of transmitted data, or invalid identifiers of custom fields.',
            401: 'Not Authorized. There is no account information on the server. You need to make a request to another server on the transmitted IP.',
            403: 'The account is blocked, for repeatedly exceeding the number of requests per second.',
            404: 'Not found.',
            500: 'Internal server error.',
            502: 'Bad gateway.',
            503: 'Service unavailable.'
        }
        error_message = errors.get(response.status_code, 'Undefined error')
        token = settings.tg_bot_token
        chat_id = settings.misha_id  # Replace with your actual chat_id
        message = email_body
        response = await send_telegram_message(token, chat_id, message)
        error_message = errors.get(response.status_code, 'Undefined error')
        raise HTTPException(status_code=response.status_code, detail=f"Error {response.status_code}. {error_message}")

    return response.json()


async def send_telegram_message(token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload)
        return response.json()
    

async def send_single_email(recipient, subject, body):
    try:
        # Формирование письма
        msg = MIMEMultipart()
        msg['From'] = settings.gmail_user
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Отправка письма
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_server,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.gmail_user,
            password=settings.gmail_password,
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке email {recipient}: {e}")


async def send_email(recipient_list, subject, body):
    tasks = [send_single_email(recipient, subject, body) for recipient in recipient_list]
    await asyncio.gather(*tasks)


async def generate_email_body(data: CreateLeadSchema) -> str:
    fields = [
        ("Оставил номер", f"{data.phone}"),
        ("Имя", data.name),
        ("Класс кузова", data.body_class),
        ("Год", data.year),
        ("Бюджет", data.budget),
        ("Email", data.email),
        ("Комментарий", data.comment),
        ("Источник UTM", data.utm_source),
        ("Канал UTM", data.utm_medium),
        ("Кампания UTM", data.utm_campaign),
        ("Термин UTM", data.utm_term),
        ("Контент UTM", data.utm_content),
        ("Client ID", data.client_id),
    ]

    body_lines = [f"{label}: {value}" for label, value in fields if value is not None]
    return "\n".join(body_lines)


async def create_new_lead(lead_data: CreateLeadSchema) -> LeadSchema:
    """
    Создание нового лида
    """
    lead = await Lead.create(**lead_data.dict(exclude_unset=True))
    return LeadSchema(**lead.__dict__)  # или lead.to_dict() если используешь .to_dict()


async def get_leads(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
) -> List[LeadSchema]:
    """
    Получение списка лидов с пагинацией и поиском
    """
    query = Lead.all()

    if search:
        query = query.filter(
            Q(phone__icontains=search) |
            Q(name__icontains=search) |
            Q(email__icontains=search)
        )

    leads = await query.offset(skip).limit(limit)
    return [LeadSchema.model_validate(lead) for lead in leads]


async def get_lead(lead_id: int) -> LeadSchema:
    lead = await Lead.get_or_none(id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Преобразуем ORM объект в dict вручную
    lead_dict = lead.__dict__
    lead_dict.pop("_saved_in_db", None)  # убрать внутренние флаги Tortoise, если есть
    
    return LeadSchema(**lead_dict)


async def update_lead(lead_id: int, lead_data: CreateLeadSchema) -> LeadSchema:
    """
    Обновление данных лида
    """
    lead = await Lead.get_or_none(id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    for field, value in lead_data.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await lead.save()
    
    # Преобразуем ORM объект в dict вручную
    lead_dict = lead.__dict__
    lead_dict.pop("_saved_in_db", None)  # убрать внутренние флаги Tortoise, если есть

    return LeadSchema(**lead_dict)


async def delete_lead(lead_id: int) -> None:
    """
    Удаление лида
    """
    lead = await Lead.get_or_none(id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await lead.delete()