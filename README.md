# Tender Email Updates API

A FastAPI service for collecting email subscriptions to tender updates. It stores subscription addresses in PostgreSQL and runs independently from the tender scraper and AI services.

## Start locally with Docker Compose

1. Copy `.env.example` to `.env`, set a strong `POSTGRES_PASSWORD`, and configure the SMTP settings for your email provider.
2. Start the service:

   ```powershell
   docker compose up --build -d
   ```

3. Open `http://localhost:8004` for the signup page or `http://localhost:8004/docs` for the interactive API documentation.

## API

`POST /email-updates/subscriptions` accepts JSON such as:

```json
{"email": "person@example.com"}
```

The endpoint validates and normalizes the email address, creates a pending subscription, and sends a confirmation link. The address becomes active only after the user opens the link and clicks **Confirm subscription**. After activation, the API sends a second email confirming the subscription. Confirmation links expire after 24 hours. Repeated requests for an active address do not create duplicates.

`POST /email-updates/confirm` accepts the confirmation token. `GET /health` reports service status.

Set `APP_BASE_URL` to the public URL of this service so confirmation links work for recipients. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_USE_TLS` with credentials from your mail provider. Without SMTP configuration, signup returns an error instead of pretending an email was sent. An unsubscribe flow is not included yet.
