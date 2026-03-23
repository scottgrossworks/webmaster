import os
import json
import boto3

ses = boto3.client('ses', region_name='us-west-2')

CORS_HEADERS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
}


def lambda_handler(event, context):
    # OPTIONS preflight
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS' \
            or event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': ''}

    try:
        body = json.loads(event.get('body') or '{}')
    except Exception:
        return _resp(400, 'Invalid request.')

    # Honeypot
    if body.get('honeypot'):
        return _resp(200, 'OK')

    name    = (body.get('name')    or '').strip()
    email   = (body.get('email')   or '').strip()
    message = (body.get('message') or '').strip()

    if not name or not email or not message:
        return _resp(400, 'Name, email, and message are required.')

    to_addr   = os.environ['CONFIRM_EMAIL_TO']
    from_addr = os.environ['SES_FROM_ADDRESS']

    ses.send_email(
        Source=from_addr,
        Destination={'ToAddresses': [to_addr]},
        ReplyToAddresses=[email],
        Message={
            'Subject': {'Data': f'Message from {name} via your website'},
            'Body':    {'Text': {'Data': f'From: {name} <{email}>\n\n{message}'}},
        },
    )

    return _resp(200, 'Message sent.')


def _resp(status, msg):
    return {
        'statusCode': status,
        'headers':    CORS_HEADERS,
        'body':       json.dumps({'message': msg}),
    }
