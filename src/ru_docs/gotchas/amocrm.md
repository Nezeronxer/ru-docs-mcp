# amoCRM API v4

## refresh_token обменивается один раз: новую пару сохраняйте сразу, иначе нужна повторная авторизация
`POST /oauth2/access_token` с `grant_type=refresh_token` возвращает новую пару access/refresh, старый refresh после
этого недействителен. Не сохранили новый (или 3 месяца не было обменов) - доступ придётся запрашивать у пользователя
заново. `access_token` в примере ответа живёт `expires_in: 86400` (сутки). `redirect_uri` в запросе должен точно
совпадать с указанным в настройках интеграции.
Источник: https://www.amocrm.ru/developers/content/oauth/step-by-step
Проверено: 2026-10-05

## Лимит 7 запросов/с на интеграцию и 50/с на аккаунт: превышение - 429, затем блокировка с 403
При превышении приходит HTTP `429`; при многократных нарушениях аккаунт блокируется и на любой запрос API
отвечает `403`. После окончания подписки запись блокируется сразу, чтение закрывается через 30 дней, ответ `402`.
Запросы шлите на поддомен аккаунта (`https://company.amocrm.ru`), а не на общий домен `www.amocrm.ru`.
Источник: https://www.amocrm.ru/developers/content/api/recommendations
Проверено: 2026-10-05

## Размеры пачек: читать до 250 (потолок 500), писать до 250, но рекомендуют 50; на 504 уменьшайте пачку
Большинство методов возвращает не более 250 сущностей, максимум для сделок/контактов/компаний/покупателей - 500.
Создавать и менять можно до 250 за запрос, для стабильности рекомендуют не более 50. На `504` уменьшите число
сущностей в запросе и повторите. На `401` проверьте срок access token, обновите его по refresh token и повторите.
Источник: https://www.amocrm.ru/developers/content/api/recommendations
Проверено: 2026-10-05

## Значения кастомных полей - в custom_fields_values: поле по field_id или field_code, формат зависит от типа
Элемент массива: `field_id` или `field_code` плюс `values` (`[{"value": ...}]`). Для `date`, `date_time`, `birthday`
`value` - Unix Timestamp или RFC-3339. Для `select`, `multiselect`, `radiobutton` можно передать значение, символьный
код или ID значения. Для `multitext` (Телефон, Email) нужны `value` и `enum_id` или `enum_code` (телефон: `WORK`,
`MOB`, `HOME` и др.; email: `WORK`, `PRIV`, `OTHER`).
Источник: https://www.amocrm.ru/developers/content/crm_platform/custom-fields
Проверено: 2026-10-05

## Вебхуки amoCRM приходят как x-www-form-urlencoded, а не JSON, и при удалении несут только id
Тело - POST-переменная вида `{entity: {action: {"0": {поля сущности}}}}` для создания и изменения и
`{entity: {action: "id"}}` для удаления. В примере все значения (`id`, `price`, даты в `custom_fields`) - строки.
Работать с вебхуками через API можно с расширенного или профессионального тарифа.
Источник: https://www.amocrm.ru/developers/content/crm_platform/webhooks-format
Проверено: 2026-10-05

## Подпись хука отключения интеграции: HMAC-SHA256 от "client_uuid|account_id", разделитель "|"
Хук приходит GET-запросом; в примере проверки читаются `client_uuid`, `signature`, `account_id`. В тексте подпись
названа «конкатенацией», но в коде строка собирается как `sprintf('%s|%s', $clientId, $hookAccountId)`, ключ -
`client_secret` интеграции. Сначала сверьте `client_uuid` со своим ID интеграции, затем подпись через `hash_equals`.
Источник: https://www.amocrm.ru/developers/content/oauth/step-by-step
Проверено: 2026-10-05
