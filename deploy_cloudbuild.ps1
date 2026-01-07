# Powershell script for deployment using Cloud Build (No local Docker needed)
# Usage: ./deploy_cloudbuild.ps1 [PROJECT_ID]

param (
    [string]$ProjectId = "rising-parser-464807-f6"
)

$ServiceName = "meeting-proofreader"
$Region = "asia-northeast3"

Write-Host "1. Submitting build to Cloud Build..."
# This uploads the source and builds the image in the cloud
gcloud builds submit --tag gcr.io/$ProjectId/$ServiceName .

Write-Host "2. Deploying to Cloud Run..."
gcloud run deploy $ServiceName `
    --image gcr.io/$ProjectId/$ServiceName `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --port 8080 `
    --set-secrets="OPENAI_API_KEY=gpt_key:latest" `
    --set-env-vars="APP_PASSWORD=wkrrkfka" `
    --timeout=3600




Write-Host "Done!"
