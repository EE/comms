# Comms API

Base URL: `/api/`

Authentication: pass a Knox token in the `Authorization` header:

    Authorization: Token <your-token>

---

## Outbound messages

All outbound endpoints live under `/api/outbound-messages/`.

### Send an email

    POST /api/outbound-messages/

The `from_email` address must match the authenticated user's email.

#### Request body (JSON)

| Field          | Type    | Required | Notes                                                      |
|----------------|---------|----------|------------------------------------------------------------|
| from_email     | string  | yes      | Must equal your account email. `"Name <email>"` is allowed |
| to             | string  | yes      | Comma-separated addresses (max 50 total with cc/bcc)       |
| subject        | string  | no       | Max 2 000 characters                                       |
| html_body      | string  | *        | * At least one of html_body / text_body is required        |
| text_body      | string  | *        |                                                            |
| cc             | string  | no       | Comma-separated                                            |
| bcc            | string  | no       | Comma-separated                                            |
| reply_to       | string  | no       |                                                            |
| tag            | string  | no       | Max 1 000 characters                                       |
| track_opens    | boolean | no       | Default false                                              |
| track_links    | string  | no       | None, HtmlAndText, HtmlOnly, TextOnly. Default None        |
| message_stream | string  | no       | Default "outbound"                                         |
| metadata       | object  | no       | Arbitrary string key/value pairs                           |

#### Example request

```json
{
  "from_email": "you@yourdomain.com",
  "to": "recipient@example.com",
  "subject": "Hello",
  "text_body": "Hi there."
}
```

#### Success response (200)

```json
{
  "ErrorCode": 0,
  "Message": "OK",
  "MessageID": "b7bc2f4a-e38e-4336-af7d-e6c392c2f817",
  "SubmittedAt": "2026-01-01T00:00:00Z",
  "To": "recipient@example.com"
}
```

Errors from the mail provider are forwarded as-is (e.g. 422 for an inactive
recipient).

### List sent messages

    GET /api/outbound-messages/

Search and list previously sent outbound messages. Results are automatically
scoped to emails sent by the authenticated user.

#### Query parameters

| Parameter     | Required | Notes                                                |
|---------------|----------|------------------------------------------------------|
| count         | no       | Messages per page, max 500. Default 20               |
| offset        | no       | Number of messages to skip. Default 0                |
| recipient     | no       | Filter by recipient email                            |
| tag           | no       | Filter by tag                                        |
| status        | no       | `queued` or `sent`                                   |
| fromdate      | no       | Inclusive start date, e.g. `2026-01-01`              |
| todate        | no       | Inclusive end date                                    |
| subject       | no       | Filter by subject                                    |
| messagestream | no       | Message stream ID. Default "outbound"                |

#### Example response (200)

```json
{
  "TotalCount": 1,
  "Messages": [
    {
      "MessageID": "0ac29aee-e1cd-480d-b08d-4f48548ff48d",
      "From": "sender@example.com",
      "To": [{"Email": "recipient@example.com", "Name": null}],
      "Subject": "Hello",
      "Status": "Sent",
      "ReceivedAt": "2026-01-01T00:00:00Z",
      "MessageStream": "outbound"
    }
  ]
}
```

### Get message details

    GET /api/outbound-messages/{MessageID}/

Returns full details for a single sent message, including body, headers, and
delivery events. Only messages sent by the authenticated user are accessible.

#### Example response (200)

```json
{
  "MessageID": "07311c54-0687-4ab9-b034-b54b5bad88ba",
  "From": "sender@example.com",
  "To": [{"Email": "recipient@example.com", "Name": null}],
  "Subject": "Hello",
  "TextBody": "Hi there.",
  "HtmlBody": "",
  "Status": "Sent",
  "ReceivedAt": "2026-01-01T00:00:00Z",
  "MessageStream": "outbound",
  "MessageEvents": [
    {
      "Recipient": "recipient@example.com",
      "Type": "Delivered",
      "ReceivedAt": "2026-01-01T00:00:05Z",
      "Details": {}
    }
  ]
}
```

---

## Inbox (received emails)

### List emails

    GET /api/inbound-emails/

Paginated list of emails routed to the authenticated user.

### Retrieve a single email

    GET /api/inbound-emails/{id}/

### Delete an email

    DELETE /api/inbound-emails/{id}/

### Response fields

| Field          | Type   |
|----------------|--------|
| id             | uuid   |
| message_id     | string |
| from_email     | string |
| from_name      | string |
| to             | string |
| cc             | string |
| bcc            | string |
| subject        | string |
| text_body      | string |
| html_body      | string |
| stripped_reply  | string |
| tag            | string |
| mailbox_hash   | string |
| date           | string |
| created_at     | string |
