# Marketplace: 1 модель + фото (API)

Ця документація описує **отримання/редагування однієї моделі** та **роботу з фото моделі**.

## Базові речі

- **Публічні ендпоінти**: `/marketplace/*` (в `app/main.py` підключені без `Depends(get_current_user)`).
- **Адмін ендпоінти**: `/admin/marketplace/*` (вимагають авторизації `Bearer`).
- **Позначення**:
  - `{{API_BASE_URL}}` — наприклад `https://api.example.com`
  - `{{TOKEN}}` — access token (JWT)

---

## 1) Отримати одну модель (detail)

**GET** `/marketplace/car-models/{model_id}`

### Query параметри
- `lang` (string, default `"en"`, формат: `^[a-z]{2}$`) — мова для підстановки перекладів (fallback на `en`)

### Приклад

```bash
curl "{{API_BASE_URL}}/marketplace/car-models/123?lang=uk"
```

### Відповідь (200 OK) — приклад

```json
{
  "id": 123,
  "brand_id": 1,
  "brand_name": "Toyota",
  "model_name": "Camry",
  "year": 2023,
  "length_mm": 4885,
  "width_mm": 1840,
  "height_mm": 1445,
  "wheelbase_mm": 2825,
  "slogan": "Надійність щодня",
  "engine": "2.5L Гібрид",
  "fuel_type": "Гібрид",
  "drive_type": "Передній",
  "transmission": "CVT",
  "suspension": null,
  "interior": null,
  "body_colors": "Чорний, Білий",
  "interior_colors": "Бежевий",
  "image_objects": [
    { "id": 77, "url": "car_models/123/9d3a7c1c0b1a4d5fa2b3c4d5e6f7a8b9.jpg" },
    { "id": 78, "url": "car_models/123/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d.webp" }
  ]
}
```

### Помилки
- `404`: `"Model not found"`

---

## 2) Редагувати одну модель (update)

**PUT** `/admin/marketplace/car-models/{model_id}`

> Важливий нюанс реалізації: під час оновлення бекенд **видаляє всі старі** `ModelAttribute` та `ModelColor` для моделі і **створює заново** з того, що прийшло в body. Тому UI має відправляти **повний стан** атрибутів/кольорів, а не “patch”.

### Headers
- `Authorization: Bearer {{TOKEN}}`
- `Content-Type: application/json`

### Body (CarModelCreate) — приклад

```json
{
  "brand_id": 1,
  "model_name": "Camry",
  "year": 2023,
  "length_mm": 4885,
  "width_mm": 1840,
  "height_mm": 1445,
  "wheelbase_mm": 2825,
  "attributes": [
    { "attribute_type_code": "slogan", "language_code": "en", "value": "Reliability every day" },
    { "attribute_type_code": "slogan", "language_code": "uk", "value": "Надійність щодня" },
    { "attribute_type_code": "engine", "language_code": "en", "value": "2.5L Hybrid" },
    { "attribute_type_code": "engine", "language_code": "uk", "value": "2.5L Гібрид" }
  ],
  "colors": [
    { "color_type_code": "body", "language_code": "en", "color_name": "Black" },
    { "color_type_code": "body", "language_code": "uk", "color_name": "Чорний" },
    { "color_type_code": "interior", "language_code": "en", "color_name": "Beige" },
    { "color_type_code": "interior", "language_code": "uk", "color_name": "Бежевий" }
  ]
}
```

### Приклад (curl)

```bash
curl -X PUT "{{API_BASE_URL}}/admin/marketplace/car-models/123" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": 1,
    "model_name": "Camry",
    "year": 2023,
    "length_mm": 4885,
    "width_mm": 1840,
    "height_mm": 1445,
    "wheelbase_mm": 2825,
    "attributes": [
      { "attribute_type_code": "slogan", "language_code": "en", "value": "Reliability every day" },
      { "attribute_type_code": "slogan", "language_code": "uk", "value": "Надійність щодня" }
    ],
    "colors": []
  }'
```

### Відповідь (200 OK)

```json
{ "status": "updated" }
```

### Як отримати актуальні дані після update
Викликайте detail:
- `GET /marketplace/car-models/{model_id}?lang=uk`

### Типові помилки (400)
- `"Model not found"` — якщо `model_id` не існує
- `"Brand not found"` — якщо `brand_id` невалідний
- `"Unsupported language codes: ..."` — якщо `language_code` не існує в таблиці мов
- `"Unknown attribute type: ..."` / `"Unknown color type: ..."` — якщо типів не існує

---

## 3) Фото моделі

### 3.1 Завантажити фото до моделі

**POST** `/admin/marketplace/car-models/{model_id}/images`

**Content-Type**: `multipart/form-data`

**Поле форми**:
- `files` — список файлів (можна кілька)

**Обмеження (бекенд)**:
- Дозволені розширення: `.jpg`, `.jpeg`, `.png`, `.webp`
- Максимум: **10 MB на файл**
- Файли зберігаються на диску в `settings.media_root` (за замовчуванням `/var/www/media`) в підпапці:
  - `car_models/{model_id}/{uuid}.{ext}`

**Приклад (curl, 2 файли)**:

```bash
curl -X POST "{{API_BASE_URL}}/admin/marketplace/car-models/123/images" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -F "files=@/path/to/front.jpg" \
  -F "files=@/path/to/side.webp"
```

**Відповідь (201 Created)**:

```json
{
  "uploaded_count": 2,
  "image_paths": [
    "car_models/123/9d3a7c1c0b1a4d5fa2b3c4d5e6f7a8b9.jpg",
    "car_models/123/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d.webp"
  ]
}
```

**Де взяти `id` зображення?**
- Після upload зробіть `GET /marketplace/car-models/{model_id}` — там буде `image_objects: [{id, url}]`.

> Примітка про URL: зараз бекенд повертає `url` як **відносний шлях** (`car_models/...`). Публічний base для медіа має надаватись інфраструктурою (наприклад Nginx), тож у фронтенді зазвичай роблять:
> - `finalUrl = {{MEDIA_PUBLIC_BASE_URL}} + "/" + image.url`

**Помилки**:
- `400`:
  - `"Model not found"`
  - `"Invalid file extension: ..."`
  - `"File too large: ... (max 10 MB)"`

---

### 3.2 Видалити фото (за id зображення)

**DELETE** `/marketplace/car-model-images`

**Body**:

```json
{ "image_ids": [77, 78] }
```

**Приклад (curl)**:

```bash
curl -X DELETE "{{API_BASE_URL}}/marketplace/car-model-images" \
  -H "Content-Type: application/json" \
  -d '{ "image_ids": [77] }'
```

**Відповідь (200 OK)**:

```json
{ "deleted_count": 1 }
```

**Що реально відбувається при delete**
- Видаляється файл з диску (`/var/www/media/<image_path>`) якщо існує
- Видаляється запис `car_model_images`

> Security note: цей delete-ендпоінт зараз знаходиться в публічному роутері `/marketplace` (без авторизації). Якщо це небажано — краще перенести його в `/admin/marketplace` і захистити.

---

## Рекомендований UI flow для адмінки (1 модель)

- **Сторінка деталі/редагування**
  - Завантажити дані: `GET /marketplace/car-models/{id}?lang={{uiLang}}`
  - Редагування (текст/атрибути/кольори): `PUT /admin/marketplace/car-models/{id}`
  - Фото:
    - Завантажити: `POST /admin/marketplace/car-models/{id}/images`
    - Перечитати detail, щоб отримати `image_objects` з `id`
    - Видаляти вибрані фото: `DELETE /marketplace/car-model-images` з масивом `image_ids`

