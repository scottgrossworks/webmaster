@echo off
REM Build and Deploy Script for Contact Lambda
REM Region: us-west-2
REM Function: webmaster-tyl-contact

SET AWS_REGION=us-west-2
SET FUNCTION_NAME=webmaster-tyl-contact
SET BUILD_DIR=build
SET ZIP_FILE=contact.zip

echo ========================================
echo Building Contact Lambda (ZIP)
echo ========================================

REM Step 1: Clean build directory
echo [1/3] Cleaning build directory...
if exist %BUILD_DIR% rmdir /s /q %BUILD_DIR%
mkdir %BUILD_DIR%

REM Step 2: Copy Lambda code
echo [2/3] Copying Lambda function code...
copy lambda_function.py %BUILD_DIR%\

REM Step 3: Create zip file
echo [3/3] Creating deployment package...
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
