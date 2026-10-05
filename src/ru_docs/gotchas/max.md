# МАКС Bot API

## Токен только в заголовке Authorization, не в query
Передача `access_token` в query-параметрах больше не поддерживается: `Authorization: <access_token>`
(без слова Bearer). Старые примеры и SDK с `?access_token=` перестали работать.
Источник: https://dev.max.ru/docs-api/methods/POST/messages
Проверено: 2026-10-04

## Вебхук только HTTPS с доверенным сертификатом
С 25 мая 2026 вебхуки по HTTP и с самоподписанными сертификатами не принимаются. Подписка -
`POST /subscriptions`. Пока активна подписка на вебхук, Long Polling (`GET /updates`) не работает.
Источник: https://dev.max.ru/docs-api/methods/POST/subscriptions
Проверено: 2026-10-04

## Long Polling - только для разработки
`GET /updates` ограничен по скорости и сроку хранения событий; документация прямо говорит, что для
production он не подходит - используйте вебхук.
Источник: https://dev.max.ru/docs/chatbots/bots-coding/prepare
Проверено: 2026-10-04

## Не больше 30 запросов в секунду на platform-api2.max.ru
Лимит 30 rps на бота. Массовую рассылку растягивайте очередью с паузами, обрабатывайте 429.
Источник: https://dev.max.ru/docs-api/use-cases/event-notifications
Проверено: 2026-10-04

## Вложение после загрузки ещё не готово: attachment.not.ready
Файл после `POST /uploads` сервер обрабатывает асинхронно (большие - дольше). Сообщение с ним сразу
после загрузки может вернуть `{"code": "attachment.not.ready"}` - повторяйте отправку с паузой.
Источник: https://dev.max.ru/docs-api/methods/POST/uploads
Проверено: 2026-10-04
