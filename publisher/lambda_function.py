import os
import boto3
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from boto3.dynamodb.conditions import Key

HERE = os.path.dirname(os.path.abspath(__file__))

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
s3 = boto3.client('s3', region_name='us-west-2')


def lambda_handler(event, context):
    table_name  = os.environ['DDB_TABLE']
    site_bucket = os.environ['SITE_BUCKET']
    asset_bucket = os.environ['ASSET_BUCKET']
    posts_per_page = int(os.environ.get('POSTS_PER_PAGE', '3'))
    site_title  = os.environ['SITE_TITLE']

    table = dynamodb.Table(table_name)

    # --- Read config sections (about, contact, intro) ---
    config_sections = {}
    try:
        resp = table.query(KeyConditionExpression=Key('pk').eq('config'))
        for item in resp.get('Items', []):
            config_sections[item['sk']] = item
    except Exception:
        pass  # empty DDB — render with blanks

    # --- Read blog posts (newest first) ---
    posts_list = []
    try:
        resp = table.query(
            KeyConditionExpression=Key('pk').eq('post'),
            ScanIndexForward=False,
            Limit=posts_per_page
        )
        for item in resp.get('Items', []):
            image_key = item.get('image_key', '')
            image_url = (
                f'https://{asset_bucket}.s3.us-west-2.amazonaws.com/{image_key}'
                if image_key else None
            )
            posts_list.append({
                'title_en':  item.get('title_en', ''),
                'title_ko':  item.get('title_ko', ''),
                'date':      item.get('date', ''),
                'text_en':   item.get('text_en', ''),
                'text_ko':   item.get('text_ko', ''),
                'image_url': image_url,
            })
    except Exception:
        pass  # empty DDB — render with no posts

    # --- Render template ---
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, 'templates')))
    template = env.get_template('index.html')
    context = {
        'site_title':     site_title,
        'current_year':   datetime.now().year,
        'about_text_en':  config_sections.get('about',   {}).get('text_en', ''),
        'about_text_ko':  config_sections.get('about',   {}).get('text_ko', ''),
        'contact_text_en':config_sections.get('contact', {}).get('text_en', ''),
        'contact_text_ko':config_sections.get('contact', {}).get('text_ko', ''),
        'intro_text_en':  config_sections.get('intro',   {}).get('text_en', ''),
        'intro_text_ko':  config_sections.get('intro',   {}).get('text_ko', ''),
        'posts':          posts_list,
    }
    html = template.render(**context)

    # --- Write index.html to S3 ---
    s3.put_object(
        Bucket=site_bucket,
        Key='index.html',
        Body=html.encode('utf-8'),
        ContentType='text/html'
    )

    # --- Write static assets to S3 ---
    static_dir = os.path.join(HERE, 'static')
    for filename, content_type in [('style.css', 'text/css'), ('site.js', 'application/javascript')]:
        filepath = os.path.join(static_dir, filename)
        with open(filepath, 'rb') as f:
            s3.put_object(
                Bucket=site_bucket,
                Key=f'static/{filename}',
                Body=f.read(),
                ContentType=content_type
            )

    return {'statusCode': 200}
