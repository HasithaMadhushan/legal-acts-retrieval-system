# AWS Setup Guide

This guide is planning documentation for a future AWS deployment of the academic MVP. It does not require application code changes and does not wire the app to S3 or RDS yet.

## 1. Deployment Shape

Recommended AWS layout:

- Frontend: AWS Amplify hosting for the Next.js app.
- Backend: AWS App Runner running the FastAPI container from ECR.
- Database: Amazon RDS PostgreSQL, `db.t3.micro` for academic demo scale.
- Upload storage later: S3 bucket `legal-acts-uploads`.
- Domain: Route 53 hosted zone and ACM certificate.
- API routing: prefer same-domain `/api` routing when possible; otherwise use `api.your-domain.com`.

Keep the legal disclaimer visible in the UI and exports. Do not add legal advice, legal opinions, legal conclusions, or authoritative legal interpretation.

## 2. IAM User or Role

Create least-privilege IAM access for deployment:

1. Create an IAM user or IAM Identity Center permission set for deployment.
2. Grant scoped access for:
   - ECR push/pull for project repositories.
   - App Runner service management.
   - Amplify app management.
   - RDS read/manage access as needed.
   - S3 access to the uploads and backups buckets only.
   - Route 53 and ACM only if managing DNS/certificates manually.
3. Enable MFA for console access.
4. Do not store AWS access keys in the repository.

## 3. RDS PostgreSQL

Create a PostgreSQL database:

1. Engine: PostgreSQL 16 if available.
2. Instance class: `db.t3.micro` for demo.
3. Storage: start small, enable autoscaling only if needed.
4. Public access: disabled where possible.
5. Security group: allow inbound only from App Runner VPC connector or trusted deployment network.
6. Database name: `legal_acts`.
7. User: create an application DB user with a strong password.
8. Backups: enable automated backups for at least 7 days.

Use a production `DATABASE_URL` like:

```text
postgresql+psycopg://APP_USER:APP_PASSWORD:RDS_PORT/legal_acts
```

Store the real value in App Runner environment variables or AWS Secrets Manager, never in Git.

## 4. S3 Upload Bucket

Create bucket:

```text
legal-acts-uploads
```

Recommended settings:

- Block all public access.
- Enable versioning.
- Enable server-side encryption with SSE-S3 or SSE-KMS.
- Add lifecycle policy:
  - transition old noncurrent versions to cheaper storage;
  - expire incomplete multipart uploads;
  - retain current uploads for the academic project lifetime.
- Add CORS only if the frontend uploads directly to S3 later. For the current MVP, backend upload remains the planned path.

Do not integrate this bucket into application code until a later storage phase is approved.

## 5. ECR Image Repositories

Create two ECR repositories:

- `legal-acts-backend`
- `legal-acts-frontend` if not using Amplify build from Git.

Manual image push outline:

```powershell
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t legal-acts-backend ./backend
docker tag legal-acts-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/legal-acts-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/legal-acts-backend:latest
```

Repeat for frontend only if using container hosting for frontend.

## 6. Backend with App Runner

1. Create App Runner service from ECR image `legal-acts-backend`.
2. Port: `8000`.
3. Health check path: `/health`.
4. Set environment variables from `env.production.example`.
5. Use RDS PostgreSQL `DATABASE_URL`.
6. Use a strong `SECRET_KEY`.
7. Configure VPC connector if RDS is private.
8. Configure logs in CloudWatch.

For production-like operation, later update the backend container command to use Gunicorn with Uvicorn workers. The current MVP Uvicorn command is acceptable for academic demo validation.

## 7. Frontend with Amplify

Preferred:

1. Connect Amplify to the Git repository.
2. Set app root to `frontend`.
3. Build command: `npm run build`.
4. Start/hosting handled by Amplify for Next.js.
5. Set `NEXT_PUBLIC_API_BASE_URL` to the deployed API base URL.

Alternative:

- Build static/frontend assets and serve through S3 + CloudFront only if the app can be deployed in that mode. The current Next.js app uses App Router and dynamic pages, so Amplify is simpler.

## 8. Route 53, ACM, and API Routing

Simpler URL choices:

- Frontend: `https://your-domain.com`
- API: `https://api.your-domain.com/api/v1`

Same-domain `/api` is operationally cleaner for CORS, but with Amplify + App Runner it may require CloudFront routing rules. Use `api.your-domain.com` first if same-domain routing takes too long.

Steps:

1. Create or use a Route 53 hosted zone.
2. Request ACM certificate for:
   - `your-domain.com`
   - `www.your-domain.com`
   - `api.your-domain.com`
3. Validate certificate using DNS.
4. Point frontend domain to Amplify.
5. Point API domain to App Runner custom domain.
6. Set backend `CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com`.

## 9. Backup Strategy

Database:

- Enable RDS automated backups.
- Add manual `pg_dump` before demos and releases.
- Store encrypted dump files in a private S3 backup bucket.

Uploads:

- If still using local/App Runner ephemeral storage, do not rely on it for long-term uploads.
- Before AWS storage integration, keep uploads in the database-backed demo environment or move to persistent storage.
- After S3 integration, rely on S3 versioning plus lifecycle rules.

Example backup command from a secure machine:

```powershell
pg_dump $env:DATABASE_URL | gzip > legal_acts_backup.sql.gz
aws s3 cp legal_acts_backup.sql.gz s3://legal-acts-backups/database/
```

## 10. Security Checklist

- Use a strong production `SECRET_KEY`.
- Never commit `.env` or AWS credentials.
- Restrict RDS network access.
- Keep S3 buckets private.
- Enable HTTPS-only public access.
- Set production CORS origins exactly.
- Keep uploads private unless explicitly serving files.
- Validate PDF extension, MIME type, size, and content signature.
- Keep demo users dummy only.
- Do not collect unnecessary personal data.
- Keep legal disclaimer visible.
- Do not implement legal advice or authoritative interpretation features.

## 11. Manual Deployment Checklist

1. Run backend tests and frontend build locally.
2. Build and push backend image to ECR.
3. Deploy/update App Runner backend.
4. Confirm `/health` works.
5. Deploy frontend through Amplify.
6. Confirm login with demo users.
7. Upload a public/sample PDF as Admin.
8. Confirm processing, search, verification, and disclaimers.
9. Run `pg_dump` backup before final demo.
