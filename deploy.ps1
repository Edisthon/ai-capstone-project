Compress-Archive -Path index.html, styles.css, script.js, data.json -DestinationPath ecosip_deploy.zip -Force
Write-Host "Deployment package ecosip_deploy.zip created successfully!"
