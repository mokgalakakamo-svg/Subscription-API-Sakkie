# Tender Subscription API

A FastAPI service for customer registration/login, subscription plan listing, and subscription lifecycle management. It uses PostgreSQL and runs independently from the tender scraper and AI services.

## Start locally with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set unique strong values for `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`.
3. Start the service:

   ```powershell
   docker compose up --build -d
   ```

4. Open `http://localhost:8001/docs`.

The API creates its subscription tables and seeds Free, Professional, and Business plans at startup. Paid plan activation is disabled unless `BILLING_MODE=mock`; mock confirmation is for development only and does not process payments. Connect a payment provider and verify signed webhooks before enabling paid subscriptions in production.

See the API contract in the original Tender Scrapping Database project for route details, or use the interactive OpenAPI docs at `/docs`.
