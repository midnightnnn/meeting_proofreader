# Powershell script for deployment (User is on Windows)
# Usage: ./deploy.ps1 [PROJECT_ID]

param (
    [string]$ProjectId = "YOUR_PROJECT_ID_HERE"
)

$ImageName = "gcr.io/$ProjectId/meeting-proofreader"
$Region = "asia-northeast3"

Write-Host "1. Building Docker Image..."
docker build -t $ImageName .

Write-Host "2. Pushing to Container Registry..."
docker push $ImageName

Write-Host "3. Deploying to Cloud Run..."
gcloud run deploy meeting-proofreader `
    --image $ImageName `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --port 8080

Write-Host "Done!"
