import boto3

table = boto3.resource('dynamodb', region_name='us-west-2').Table('webmaster-tyl')

# --- Config sections ---

table.put_item(Item={
    'pk': 'config', 'sk': 'intro',
    'text_en': 'Classical piano for concerts, events, and private occasions.',
    'text_ko': '콘서트, 행사 및 개인 행사를 위한 클래식 피아노.',
})
print('seeded config:intro')

table.put_item(Item={
    'pk': 'config', 'sk': 'about',
    'text_en': 'Welcome to my page. I am a professional pianist based in New York.',
    'text_ko': '제 페이지에 오신 것을 환영합니다. 저는 뉴욕에서 활동하는 전문 피아니스트입니다.',
})
print('seeded config:about')

table.put_item(Item={
    'pk': 'config', 'sk': 'contact',
    'text_en': 'Email: tyl@example.com | Phone: (555) 123-4567',
    'text_ko': '이메일: tyl@example.com | 전화: (555) 123-4567',
})
print('seeded config:contact')

# --- Blog posts ---

table.put_item(Item={
    'pk': 'post',
    'sk': '2026-03-20T12:00:00Z',
    'title_en': 'Spring Concert Season Begins',
    'title_ko': '봄 콘서트 시즌이 시작됩니다',
    'text_en': 'Excited to announce the start of the spring concert season. Looking forward to sharing new repertoire with audiences.',
    'text_ko': '봄 콘서트 시즌의 시작을 알리게 되어 기쁩니다. 새로운 레퍼토리를 관객들과 함께 나누기를 기대합니다.',
    'date': 'March 20, 2026',
    'image_key': '',
})
print('seeded post:2026-03-20')

table.put_item(Item={
    'pk': 'post',
    'sk': '2026-03-21T12:00:00Z',
    'title_en': 'Practice Notes: Chopin Ballade No. 1',
    'title_ko': '연습 노트: 쇼팽 발라드 1번',
    'text_en': 'Spent the afternoon working through the development section of Chopin\'s first Ballade. The transition into the coda never gets easier.',
    'text_ko': '오후 내내 쇼팽 발라드 1번의 전개부를 연습했습니다. 코다로 넘어가는 부분은 언제나 어렵게 느껴집니다.',
    'date': 'March 21, 2026',
    'image_key': '',
})
print('seeded post:2026-03-21')

table.put_item(Item={
    'pk': 'post',
    'sk': '2026-03-22T12:00:00Z',
    'title_en': 'Welcome to My New Website',
    'title_ko': '새 웹사이트에 오신 것을 환영합니다',
    'text_en': 'I am excited to share my music and upcoming performances with you through this page.',
    'text_ko': '이 페이지를 통해 저의 음악과 다가오는 공연을 여러분과 나눌 수 있어 기쁩니다.',
    'date': 'March 22, 2026',
    'image_key': '',
})
print('seeded post:2026-03-22')

print('\nDone. 3 config sections + 3 posts written to webmaster-tyl.')
