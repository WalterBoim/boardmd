import json, re, time, hashlib, requests
from supabase import create_client

SUPA_URL       = 'https://hwdcgbcnphkmxaasties.supabase.co'
SUPA_KEY       = 'sb_secret_8JKUqdUWu6EIDetxG8G3vA_BdqmPq0X'
BUCKET         = 'boardmd-images'
STORAGE_PUBLIC = f'{SUPA_URL}/storage/v1/object/public/{BUCKET}'
PROGRESS_FILE  = 'progress_anking_images.json'
MIN_SCORE      = 3

sb = create_client(SUPA_URL, SUPA_KEY)

# Teste conexao Storage
try:
    sb.storage.from_(BUCKET).list()
    print("Supabase Storage OK!")
except Exception as e:
    print(f"Storage ERRO: {e}"); exit(1)

# Carrega mapa AnKing
with open('anking_images.json') as f:
    anking_raw = json.load(f)

anking_images = {}
for fname, ctx in anking_raw.items():
    key = re.sub(r'\.[a-z]+$', '', fname.replace('_', ' ').lower().strip())
    anking_images[key] = {'file': fname, 'ctx': ctx}
print(f"AnKing: {len(anking_images)} imagens")

img_index = {}
for img_key in anking_images:
    for word in re.findall(r'[a-z]{4,}', img_key):
        img_index.setdefault(word, []).append(img_key)

MEDICAL = {'histopathology','pathology','histology','anatomy','syndrome','disease',
    'carcinoma','tumor','cancer','cell','tissue','nerve','bone','muscle','artery',
    'vein','heart','liver','kidney','brain','lung','skin','blood','stain',
    'inflammation','necrosis','fibrosis','edema','abscess','ulcer','fracture',
    'lesion','biopsy','thyroid','adrenal','pancreas','spleen','lymph','marrow',
    'colon','intestine','stomach','bronchus','aorta','coronary','cerebral',
    'spinal','renal','hepatic','ovary','uterus','prostate','testis'}

BAD = {'bird','animal','plant','flower','food','landscape','flag','logo','cartoon','physeo'}

def score(answer, img_key, ctx):
    sc = 0
    awords = re.findall(r'[a-z]{4,}', answer.lower())
    itext  = (img_key + ' ' + ctx).lower()
    for w in awords:
        if len(w) > 4 and w in itext: sc += 3
        elif w in itext: sc += 1
    iwords = set(re.findall(r'[a-z]{4,}', img_key))
    sc += len(iwords & MEDICAL) * 0.5
    sc -= len(iwords & BAD) * 5
    return sc

def get_wiki_url(filename):
    fname = filename.replace(' ', '_')
    try:
        r = requests.get('https://commons.wikimedia.org/w/api.php',
            params={'action':'query','titles':f'File:{fname}','prop':'imageinfo',
                    'iiprop':'url|mime|extmetadata','format':'json'},
            timeout=10, headers={'User-Agent':'BoardMD/1.0 (boardmd.app)'})
        for page in r.json().get('query', {}).get('pages', {}).values():
            if 'imageinfo' in page:
                info = page['imageinfo'][0]
                if info.get('mime', '').startswith('image/'):
                    return info['url'], info.get('extmetadata', {})
    except Exception as e:
        print(f"  wiki err: {e}")
    return None, None

def download_img(url):
    try:
        r = requests.get(url, timeout=20, headers={'User-Agent':'BoardMD/1.0 (boardmd.app)'})
        if r.status_code == 200 and len(r.content) > 3000:
            return r.content
        print(f"  dl err: status={r.status_code} size={len(r.content)}")
    except Exception as e:
        print(f"  dl exc: {e}")
    return None

def upload_supabase(img_bytes, fname):
    ext = fname.rsplit('.', 1)[-1].lower()
    ct  = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png',
           'gif':'image/gif','webp':'image/webp'}.get(ext, 'image/jpeg')
    path = f'imgs/{fname}'
    try:
        sb.storage.from_(BUCKET).upload(
            path, img_bytes,
            file_options={'content-type': ct, 'upsert': 'true'}
        )
        return f'{STORAGE_PUBLIC}/{path}'
    except Exception as e:
        print(f"  storage err: {e}")
        return None

# Progresso
try:
    p = json.load(open(PROGRESS_FILE))
except:
    p = {'done': [], 'stats': {'matched': 0, 'dl': 0, 'fail': 0, 'nomatch': 0}}

done = set(p['done'])
st   = p['stats']

# Carrega cards
print("Carregando cards...")
all_cards = []
offset = 0
while True:
    batch = sb.table('cards').select('id,c').range(offset, offset + 999).execute()
    all_cards.extend(batch.data)
    if len(batch.data) < 1000: break
    offset += 1000
print(f"Total: {len(all_cards)} | Feitos: {len(done)}")

# Teste pipeline
print("\nTestando pipeline...")
test = list(anking_images.values())[5]
turl, _ = get_wiki_url(test['file'])
print(f"  Arquivo: {test['file']}")
print(f"  URL Wikimedia: {turl}")
if turl:
    tb = download_img(turl)
    print(f"  Bytes: {len(tb) if tb else 0}")
    if tb:
        tr = upload_supabase(tb, 'test_ok.jpg')
        print(f"  Supabase Storage: {tr}")
print()

# Loop principal
SAVE_EVERY = 100
counter    = 0

for card in all_cards:
    cid    = card['id']
    if cid in done: continue

    answer = (card.get('c') or '').strip()
    if not answer or len(answer) < 3:
        p['done'].append(cid); st['nomatch'] += 1
        counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    awords     = set(re.findall(r'[a-z]{4,}', answer.lower()))
    candidates = set()
    for w in awords:
        if w in img_index: candidates.update(img_index[w])

    if not candidates:
        p['done'].append(cid); st['nomatch'] += 1
        counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    best_sc, best_img = 0, None
    for ik in candidates:
        s = score(answer, ik, anking_images[ik]['ctx'])
        if s > best_sc: best_sc = s; best_img = ik

    if best_sc < MIN_SCORE or not best_img:
        p['done'].append(cid); st['nomatch'] += 1
        counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    st['matched'] += 1
    idata      = anking_images[best_img]
    url, meta  = get_wiki_url(idata['file'])
    time.sleep(2.5)  # rate limit Wikimedia

    if not url:
        p['done'].append(cid); st['fail'] += 1
        counter += 1
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    img_bytes = download_img(url)
    if not img_bytes:
        p['done'].append(cid); st['fail'] += 1
        counter += 1
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    ext = url.split('.')[-1].lower().split('?')[0]
    if ext not in ['jpg','jpeg','png','gif','webp']: ext = 'jpg'
    hname    = hashlib.md5(img_bytes).hexdigest()[:12] + '.' + ext
    supa_url = upload_supabase(img_bytes, hname)

    if not supa_url:
        p['done'].append(cid); st['fail'] += 1
        counter += 1
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    lic    = meta.get('LicenseShortName', {}).get('value', 'CC BY-SA 3.0') if meta else 'CC BY-SA 3.0'
    credit = re.sub(r'\.[a-z]+$', '', idata['file'].replace('_', ' '))[:60]
    try:
        sb.table('cards').update({'img': {
            'url':     supa_url,
            'alt':     answer[:80],
            'credit':  f'Wikimedia Commons - {credit}',
            'license': lic,
            'source':  'AnKing/Wikimedia'
        }}).eq('id', cid).execute()
        st['dl'] += 1
        print(f"  OK [{st['dl']}] {answer[:40]}")
    except Exception as e:
        print(f"  supa err: {e}")

    p['done'].append(cid)
    counter += 1
    if counter % SAVE_EVERY == 0:
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        pct = len(p['done']) / len(all_cards) * 100
        print(f"[{pct:.1f}%] dl:{st['dl']} matched:{st['matched']} fail:{st['fail']} nomatch:{st['nomatch']}")

json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
print(f"\nCONCLUIDO: matched:{st['matched']} dl:{st['dl']} fail:{st['fail']} nomatch:{st['nomatch']}")
