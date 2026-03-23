import os
import json
import re
import email
import email.utils
import boto3
from string import Template
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

# ---------------------------------------------------------------------------
# LLM config — loaded from llm_config.json at cold start
# ---------------------------------------------------------------------------

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llm_config.json')) as _f:
    LLM_CONFIG = json.load(_f)

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------

s3            = boto3.client('s3',              region_name='us-west-2')
dynamodb      = boto3.resource('dynamodb',      region_name='us-west-2')
bedrock       = boto3.client('bedrock-runtime', region_name='us-west-2')
ses           = boto3.client('ses',             region_name='us-west-2')
lambda_client = boto3.client('lambda',          region_name='us-west-2')

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    record     = event['Records'][0]
    message_id = record['ses']['mail']['messageId']
    tenant_id  = os.environ['TENANT_ID']

    # Read and parse raw email from S3
    raw = s3.get_object(
        Bucket=os.environ['SES_INBOUND_BUCKET'],
        Key=f'{tenant_id}/{message_id}'
    )['Body'].read()
    msg = email.message_from_bytes(raw)

    # Sender auth
    _, from_addr = email.utils.parseaddr(msg.get('From', ''))
    whitelist = [a.strip().lower() for a in os.environ['SENDER_WHITELIST'].split(',')]
    if from_addr.lower() not in whitelist:
        print(f'Rejected sender: {from_addr}')
        return

    subject = msg.get('Subject', '') or ''
    body    = _extract_body(msg)

    # Guard: empty body — nothing to process
    if not body.strip():
        _send_email(
            'Website update failed',
            'Your email arrived but the body was empty — nothing to process.\n\n'
            'Please include your update in the email body and try again.'
        )
        return

    table = dynamodb.Table(os.environ['DDB_TABLE'])

    # Read all current state from DDB
    config = {item['sk']: item for item in table.query(
        KeyConditionExpression=Key('pk').eq('config')
    ).get('Items', [])}

    all_posts = table.query(
        KeyConditionExpression=Key('pk').eq('post'),
        ScanIndexForward=False
    ).get('Items', [])

    posts_list = '\n'.join(
        f"  - sk={p['sk']} | {p.get('title_en', '(no title)')} | {p.get('date', '')} | {p.get('text_en', '')[:150]}"
        for p in all_posts
    ) or '  (no posts yet)'

    # Build prompt — Template uses $variable syntax; curly braces are inert
    prompt = Template(LLM_CONFIG['unified_prompt']).safe_substitute(
        subject    = subject,
        body       = body,
        about_en   = config.get('about',   {}).get('text_en', ''),
        about_ko   = config.get('about',   {}).get('text_ko', ''),
        contact_en = config.get('contact', {}).get('text_en', ''),
        contact_ko = config.get('contact', {}).get('text_ko', ''),
        intro_en   = config.get('intro',   {}).get('text_en', ''),
        intro_ko   = config.get('intro',   {}).get('text_ko', ''),
        posts_list = posts_list,
    )

    try:
        result = _parse_json_response(_call_bedrock(prompt))
    except Exception as e:
        print(f'Bedrock/parse error: {e}')
        _send_email(
            'Website update failed',
            f'Webmaster could not process your request.\n\n'
            f'Error: {e}\n\n'
            f'--- Your original email ---\n'
            f'Subject: {subject}\n\n'
            f'{body}'
        )
        return

    action = result.get('action', 'error')
    print(f'Action classified: {action}')

    if action == 'new_post':
        _handle_new_post(result, msg, tenant_id, table)
    elif action == 'static_update':
        _handle_static_update(result, table)
    elif action == 'remove':
        _handle_remove(result, table, all_posts)
    elif action == 'remove_all':
        _handle_remove_all(all_posts, table)
    else:
        _handle_error(result, subject, body)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_body(msg):
    """Prefer text/plain; fall back to tag-stripped text/html."""
    plain = None
    html  = None
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            continue
        ct = part.get_content_type()
        if ct == 'text/plain' and plain is None:
            plain = part.get_payload(decode=True).decode('utf-8', errors='replace')
        elif ct == 'text/html' and html is None:
            raw_html = part.get_payload(decode=True).decode('utf-8', errors='replace')
            html = re.sub(r'<[^>]+>', ' ', raw_html).strip()
    return plain or html or ''


def _call_bedrock(prompt):
    response = bedrock.invoke_model(
        modelId=os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-haiku-4-5-20251001-v1:0'),
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': LLM_CONFIG['max_tokens'],
            'messages': [{'role': 'user', 'content': prompt}],
        })
    )
    return json.loads(response['body'].read())['content'][0]['text']


def _parse_json_response(raw):
    """Extract JSON from model response, tolerating markdown code fences."""
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    return json.loads(match.group()) if match else json.loads(raw)


def _invoke_publisher():
    lambda_client.invoke(
        FunctionName=os.environ['PUBLISHER_FUNCTION'],
        InvocationType='Event',  # async — fire and forget
    )


def _send_email(subject, body_text):
    ses.send_email(
        Source=os.environ['SES_FROM_ADDRESS'],
        Destination={'ToAddresses': [os.environ['CONFIRM_EMAIL_TO']]},
        Message={
            'Subject': {'Data': subject},
            'Body':    {'Text': {'Data': body_text}},
        }
    )

# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _handle_new_post(result, msg, tenant_id, table):
    asset_bucket = os.environ['ASSET_BUCKET']

    # Image attachment (first image/* wins)
    image_key = ''
    for part in msg.walk():
        if part.get_content_maintype() == 'image' and part.get_filename():
            ts        = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            image_key = f'{tenant_id}/{ts}_{part.get_filename()}'
            s3.put_object(
                Bucket=asset_bucket,
                Key=image_key,
                Body=part.get_payload(decode=True),
                ContentType=part.get_content_type(),
            )
            break

    now = datetime.now(timezone.utc)
    table.put_item(Item={
        'pk':        'post',
        'sk':        now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'title_en':  result.get('title_en', ''),
        'title_ko':  result.get('title_ko', ''),
        'text_en':   result.get('text_en', ''),
        'text_ko':   result.get('text_ko', ''),
        'date':      now.strftime('%B %d, %Y'),
        'image_key': image_key,
    })

    _invoke_publisher()
    _send_email(
        subject='Website updated',
        body_text=f"New post: {result.get('title_en', '(no title)')}\n\n{result.get('text_en', '')[:200]}",
    )


def _handle_static_update(result, table):
    section = result.get('section', '')
    if section not in ('about', 'contact', 'intro'):
        _send_email(
            'Website update failed',
            f'Webmaster could not determine which section to update (got: "{section}").\n\n'
            f'Valid sections are: about, contact, intro.\n'
            f'Please try again with a clearer description of what you want to change.'
        )
        return

    table.put_item(Item={
        'pk':      'config',
        'sk':      section,
        'text_en': result.get('text_en', ''),
        'text_ko': result.get('text_ko', ''),
    })

    _invoke_publisher()
    _send_email(
        subject='Website updated',
        body_text='\n'.join([
            f'{section.capitalize()} section updated.',
            '',
            'New content:',
            result.get('text_en', ''),
            '',
            'Previous content (save this if you need to revert):',
            result.get('previous_en', '') or '(none)',
        ]),
    )


def _handle_remove(result, table, all_posts):
    sk    = result.get('sk', '').strip()
    title = result.get('title_en', '').strip()
    if not sk and not title:
        _send_email(
            'Website update failed',
            'Webmaster could not identify which post to remove.\n\n'
            'Please try again with a more specific description, or use the exact title.\n\n'
            + _format_post_list(all_posts)
        )
        return

    # Match by sk first (precise), then title exact, then title case-insensitive
    post = next((p for p in all_posts if p.get('sk') == sk), None) if sk else None
    if not post:
        post = next((p for p in all_posts if p.get('title_en', '') == title), None)
    if not post:
        post = next((p for p in all_posts if p.get('title_en', '').lower() == title.lower()), None)

    if not post:
        _send_email(
            'Website update failed',
            'Webmaster could not find a post matching that description.\n\n'
            + _format_post_list(all_posts)
        )
        return

    table.delete_item(Key={'pk': 'post', 'sk': post['sk']})
    _invoke_publisher()
    _send_email(
        subject='Website updated',
        body_text='\n'.join([
            f"Post removed: {post.get('title_en', '(no title)')}",
            f"Date: {post.get('date', '')}",
            '',
            '--- Full removed text (English) ---',
            post.get('text_en', ''),
            '',
            '--- Full removed text (Korean) ---',
            post.get('text_ko', ''),
            '',
            'To re-add with changes, email tyl_update@scottgross.works',
        ]),
    )


def _handle_remove_all(all_posts, table):
    if not all_posts:
        _send_email('Website update failed', 'There are no posts to remove.')
        return

    for post in all_posts:
        table.delete_item(Key={'pk': 'post', 'sk': post['sk']})

    _invoke_publisher()
    count = len(all_posts)
    _send_email(
        subject='Website updated',
        body_text=f'Removed {count} post{"s" if count != 1 else ""}.',
    )


def _handle_error(result, subject, body):
    _send_email(
        subject='Website update failed',
        body_text='\n'.join([
            "Webmaster couldn't figure out what you wanted to do.",
            '',
            f"What the AI concluded: {result.get('message', 'Unknown error')}",
            '',
            '--- Your original email ---',
            f'Subject: {subject}',
            '',
            body,
        ]),
    )


def _format_post_list(all_posts):
    if not all_posts:
        return 'Your site currently has no posts.'
    lines = ['Your current posts:']
    for p in all_posts:
        lines.append(f"  - {p.get('title_en', '(no title)')} | {p.get('date', '')}")
    return '\n'.join(lines)
