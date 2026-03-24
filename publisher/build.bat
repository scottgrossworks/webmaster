@echo off
REM Build and Deploy Script for Publisher Lambda
REM Region: us-west-2
REM Function: webmaster-tyl-publisher

SET AWS_REGION=us-west-2
SET FUNCTION_NAME=webmaster-tyl-publisher
SET BUILD_DIR=build
SET ZIP_FILE=publisher.zip

echo ========================================
echo Building Publisher Lambda (ZIP)
echo ========================================

REM Step 1: Clean build directory
echo [1/4] Cleaning build directory...
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

REM Step 2: Install dependencies to build directory
echo [2/4] Installing Python dependencies for Linux (Lambda runtime)...
pip install -r requirements.txt --target %BUILD_DIR% --upgrade --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Dependency installation failed!
    exit /b %ERRORLEVEL%
)

REM Step 3: Copy Lambda code, templates, and static assets
echo [3/4] Copying Lambda function code, templates, and static assets...
copy lambda_function.py %BUILD_DIR%\
xcopy /E /I templates %BUILD_DIR%\templates
xcopy /E /I static %BUILD_DIR%\static

REM Step 3b: Inject contact API URL from config.json
echo [3b/4] Injecting contact API URL...
powershell -command "$cfg = Get-Content ..\config.json | ConvertFrom-Json; (Get-Content %BUILD_DIR%\templates\index.html) -replace '%%%%CONTACT_API_URL%%%%', $cfg.contact_api_url | Set-Content %BUILD_DIR%\templates\index.html"

REM Step 4: Create zip file
echo [4/4] Creating deployment package...
cd %BUILD_DIR%
powershell -command "Compress-Archive -Path * -DestinationPath ..\%ZIP_FILE% -Force"
cd ..

echo ========================================
echo Build Complete
echo ========================================
echo Package: %ZIP_FILE%
echo Size:
dir %ZIP_FILE% | find "%ZIP_FILE%"

echo.
echo ========================================
echo Deploying to Lambda...
echo ========================================

aws lambda update-function-code --function-name %FUNCTION_NAME% --zip-file fileb://%ZIP_FILE% --region %AWS_REGION%
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Lambda function '%FUNCTION_NAME%' does not exist!
    echo Create it first in AWS Console, then re-run this script.
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================
echo Deployment Successful
echo ========================================
echo Function: %FUNCTION_NAME%
echo Region: %AWS_REGION%
echo ========================================

echo.
echo ========================================
echo Invoking publisher to refresh S3 site...
echo ========================================
aws lambda invoke --function-name %FUNCTION_NAME% --region %AWS_REGION% NUL
echo Site updated.
