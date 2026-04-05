#!/usr/bin/env python3
"""
BoardMD — Direct Wikimedia image search with OAuth
Filtro USMLE: só busca imagens para categorias clinicamente relevantes
"""
import json, re, hashlib, time, requests
from requests_oauthlib import OAuth1
from supabase import create_client

SUPA_URL       = 'https://hwdcgbcnphkmxaasties.supabase.co'
SUPA_KEY       = 'SUPABASE_KEY_REMOVED'
BUCKET         = 'boardmd-images'
STORAGE_PUBLIC = f'{SUPA_URL}/storage/v1/object/public/{BUCKET}'
PROGRESS_FILE  = 'progress_direct_images.json'
LOG_FILE       = 'images_direct_log.json'
MIN_SCORE      = 8
WIKI_DELAY     = 1.0

# OAuth credentials
CONSUMER_TOKEN  = '35690e34d342aa90093ead8177dd5b69'
CONSUMER_SECRET = 'eadea8d4eb548a8939711f2c42681be1847da42f'
ACCESS_TOKEN    = '8a738b010ccf9f1f28fbc3188c8b5ed2'
ACCESS_SECRET   = '05e0981fb1160f298bf6622cc2ffaef317eb3551'

oauth = OAuth1(CONSUMER_TOKEN, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_SECRET)

ALLOWED_LICENSES = {
    'cc0', 'public domain', 'cc by', 'cc by 2.0', 'cc by 3.0', 'cc by 4.0',
    'cc by-sa', 'cc by-sa 2.0', 'cc by-sa 3.0', 'cc by-sa 4.0',
    'pd', 'public domain dedication'
}

# ── FILTRO USMLE ─────────────────────────────────────────────────────────────
# Sufixos de medicamentos — pular sempre
DRUG_SUFFIXES = (
    'mab','nib','zole','olol','pril','artan','statin','mycin','cillin',
    'cycline','floxacin','sartan','dipine','vir','navir','lukast','tidine',
    'prazole','oxacin','tropin','sterone','amine','epam','azepam','barbital',
    'caine','dronate','gliptin','gliflozin','glutide','tide','kinase',
    'ximab','zumab','lizumab','tinib','rafenib','ciclib'
)

# Palavras que indicam conteúdo não visual / abstrato — pular
ABSTRACT_WORDS = {
    'pathway','mechanism','inhibition','inhibitor','activation','signaling',
    'mutation','deletion','insertion','polymorphism','genotype','phenotype',
    'receptor','ligand','enzyme','protein','gene','mrna','rna','dna',
    'synthesis','metabolism','catabolism','anabolism','transcription',
    'translation','replication','phosphorylation','acetylation',
    'acid','ion','channel','pump','transporter','gradient','potential',
    'deficiency','excess','level','ratio','index','score','scale',
    'therapy','treatment','management','approach','strategy','regimen',
    'stage','grade','class','type','classification','criteria','definition',
    'test','assay','measurement','value','normal','abnormal','elevated','low',
    'increase','decrease','elevation','reduction','change','shift',
    'effect','side effect','adverse','toxicity','overdose','dose',
    'interaction','contraindication','indication','mechanism of action',
}

# Palavras que indicam imagem NÃO médica — pular
BAD_VISUAL = {
    'plant','leaf','flower','food','landscape','flag','logo','cartoon',
    'animal','bird','insect','fish','tree','fruit','vegetable','mineral',
    'map','chart','diagram','graph','table','formula','equation','structure',
    'molecule','chemical','compound','element','atom',
}

# Categorias que TÊM valor visual para USMLE — buscar sempre
VISUAL_KEYWORDS = {
    # Dermatologia
    'rash','eruption','lesion','macule','papule','pustule','vesicle','bulla',
    'plaque','nodule','ulcer','erythema','purpura','petechiae','ecchymosis',
    'urticaria','eczema','psoriasis','melanoma','carcinoma','sarcoma',
    'acne','rosacea','vitiligo','alopecia','tinea','candidiasis','herpes',
    'shingles','warts','molluscum','impetigo','cellulitis','abscess',
    # Histologia / Patologia
    'histology','biopsy','slide','microscopy','stain','hematoxylin','eosin',
    'granuloma','necrosis','fibrosis','inflammation','infiltrate','inclusion',
    'reed-sternberg','psammoma','lewy body','mallory','russell body',
    'giant cell','foam cell','signet ring','koilocyte','aschoff',
    # Radiologia / Imagem
    'x-ray','xray','radiograph','ct scan','mri','ultrasound','echo',
    'chest x','abdominal','fracture','consolidation','effusion','mass',
    'opacity','atelectasis','pneumothorax','cardiomegaly','widening',
    # Oftalmologia
    'fundus','retina','papilledema','cherry red','cotton wool','drusen',
    'cataract','glaucoma','cornea','iris','pupil','kayser-fleischer',
    'band keratopathy','rubeosis',
    # Microrganismos
    'bacteria','fungus','parasite','protozoa','helminth','virus','gram',
    'acid-fast','spore','hyphae','pseudohyphae','trophozoite','cyst',
    'trypanosoma','plasmodium','leishmania','giardia','entamoeba',
    'cryptococcus','aspergillus','candida','pneumocystis',
    # Síndromes com fenótipo físico
    'down syndrome','marfan','turner','klinefelter','noonan','williams',
    'beckwith','digeorge','fragile x','prader-willi','angelman',
    # Achados físicos clássicos
    'moon facies','buffalo hump','caput medusae','spider angioma',
    'palmar erythema','dupuytren','heberden','bouchard','osler',
    'janeway','splinter hemorrhage','koilonychia','leukonychia',
    'clubbing','cyanosis','jaundice','icterus','goiter',
    # Estruturas anatômicas
    'heart','lung','liver','kidney','brain','spleen','thyroid','adrenal',
    'pancreas','bowel','colon','stomach','esophagus','aorta','artery','vein',
    # ECG / Ondas
    'ekg','ecg','electrocardiogram','st elevation','st depression',
    'delta wave','q wave','bundle branch','atrial fibrillation','flutter',
}

def should_skip_answer(answer):
    """Retorna True se a resposta não vale buscar imagem."""
    a = answer.lower().strip()
    
    # Muito curto ou muito longo
    if len(a) < 4 or len(a.split()) > 8:
        return True
    
    # É um número ou dosagem
    if re.match(r'^[\d\s\.\,\%\+\-\/]+$', a):
        return True
    
    # Termina com sufixo de medicamento
    for suffix in DRUG_SUFFIXES:
        if a.endswith(suffix) or a.endswith(suffix + 's'):
            return True
    
    # Contém palavra abstrata
    words = set(re.sub(r'[^a-z\s]', ' ', a).split())
    if words & ABSTRACT_WORDS:
        return True
    
    # Contém palavra não visual
    if words & BAD_VISUAL:
        return True
    
    return False

def has_visual_value(answer):
    """Retorna True se a resposta provavelmente tem valor visual para USMLE."""
    a = answer.lower()
    
    # Verifica se contém alguma keyword visual
    for kw in VISUAL_KEYWORDS:
        if kw in a:
            return True
    
    # Doenças com sufixos típicos que têm imagem
    disease_patterns = [
        r'\b\w+itis\b',      # inflamações
        r'\b\w+osis\b',      # condições
        r'\b\w+oma\b',       # tumores
        r'\b\w+emia\b',      # condições sanguíneas
        r'\b\w+pathy\b',     # patologias
        r'\b\w+trophy\b',    # atrofia/hipertrofia
        r'\b\w+plasia\b',    # displasias
        r'syndrome\b',
        r'disease\b',
        r'fracture\b',
        r'infection\b',
        r'tumor\b',
        r'cancer\b',
        r'carcinoma\b',
        r'lymphoma\b',
        r'leukemia\b',
    ]
    
    for pattern in disease_patterns:
        if re.search(pattern, a):
            return True
    
    return False

sb = create_client(SUPA_URL, SUPA_KEY)
try:
    sb.storage.from_(BUCKET).list()
    print("Supabase Storage OK!")
except Exception as e:
    print(f"Storage ERRO: {e}"); exit(1)

def normalize(s):
    return re.sub(r'[^a-z0-9]', ' ', s.lower()).strip()

def score_match(answer, img_title):
    a = normalize(answer)
    t = normalize(img_title)
    score = 0
    if a == t: score += 10
    elif t.startswith(a): score += 8
    elif a.startswith(t) and len(t) > 5: score += 7
    else:
        a_words = [w for w in a.split() if len(w) > 3]
        t_words = set(t.split())
        if a_words and all(w in t_words for w in a_words):
            score += 6
        else:
            matched = sum(1 for w in a_words if w in t_words)
            if a_words:
                ratio = matched / len(a_words)
                if ratio >= 0.8: score += 4
                elif ratio >= 0.6: score += 2
    if len(t.split()) <= 4: score += 1
    t_words = set(t.split())
    if t_words & BAD_VISUAL: score -= 5
    return score

def search_wikimedia(answer):
    time.sleep(WIKI_DELAY)
    try:
        r = requests.get('https://commons.wikimedia.org/w/api.php',
            params={
                'action': 'query',
                'generator': 'search',
                'gsrnamespace': 6,
                'gsrsearch': answer,
                'gsrlimit': 10,
                'prop': 'imageinfo',
                'iiprop': 'url|mime|extmetadata',
                'format': 'json'
            },
            timeout=15,
            headers={'User-Agent': 'BoardMD/1.0 (boardmd.app; wboim@hotmail.com)'}
        )
        if r.status_code == 429:
            print(f"  429 — aguardando 30s...")
            time.sleep(30)
            return None, None, None

        pages = r.json().get('query', {}).get('pages', {})
        best_score = 0
        best_url   = None
        best_meta  = None
        best_title = None

        for page in pages.values():
            if 'imageinfo' not in page: continue
            info = page['imageinfo'][0]
            mime = info.get('mime', '')
            if not mime.startswith('image/'): continue

            title = page.get('title', '').replace('File:', '').rsplit('.', 1)[0]
            sc    = score_match(answer, title)
            if sc < MIN_SCORE: continue

            meta = info.get('extmetadata', {})
            lic  = meta.get('LicenseShortName', {}).get('value', '').lower()
            lic2 = meta.get('License', {}).get('value', '').lower()
            combined = lic + ' ' + lic2
            is_free = any(al in combined for al in ALLOWED_LICENSES)
            if not is_free: continue

            if sc > best_score:
                best_score = sc
                best_url   = info['url']
                best_meta  = meta
                best_title = title

        return best_url, best_meta, best_title

    except Exception as e:
        print(f"  wiki err: {e}")
        return None, None, None

def download_img(url):
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20,
                headers={'User-Agent': 'BoardMD/1.0 (boardmd.app; wboim@hotmail.com)'})
            if r.status_code == 200 and len(r.content) > 3000:
                return r.content
            if r.status_code == 429:
                print(f"  img 429 — aguardando 30s...")
                time.sleep(30)
                continue
            print(f"  dl err: status={r.status_code} size={len(r.content)}")
            break
        except Exception as e:
            print(f"  dl exc: {e}")
            break
    return None

def upload_supabase(img_bytes, fname):
    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else 'jpg'
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
try:    p = json.load(open(PROGRESS_FILE))
except: p = {'done': [], 'stats': {'matched': 0, 'dl': 0, 'fail': 0, 'nomatch': 0, 'skipped': 0}}
if 'skipped' not in p['stats']: p['stats']['skipped'] = 0
done = set(p['done']); st = p['stats']
try:    log = json.load(open(LOG_FILE))
except: log = []

print("Carregando cards sem imagem...")
all_cards = []
offset = 0
while True:
    batch = (sb.table('cards')
               .select('id,c,deck')
               .is_('img', 'null')
               .range(offset, offset + 999)
               .execute())
    all_cards.extend(batch.data)
    if len(batch.data) < 1000: break
    offset += 1000
print(f"Cards sem imagem: {len(all_cards)} | Ja processados: {len(done)}\n")

SAVE_EVERY = 50
counter    = 0

for card in all_cards:
    cid    = card['id']
    if cid in done: continue

    answer = (card.get('c') or '').strip()
    deck   = (card.get('deck') or '')

    # ── FILTRO USMLE ──
    if should_skip_answer(answer):
        p['done'].append(cid); st['skipped'] += 1; counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    if not has_visual_value(answer):
        p['done'].append(cid); st['skipped'] += 1; counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    url, meta, title = search_wikimedia(answer)

    if not url:
        p['done'].append(cid); st['nomatch'] += 1; counter += 1
        if counter % SAVE_EVERY == 0:
            json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    st['matched'] += 1
    img_bytes = download_img(url)
    if not img_bytes:
        p['done'].append(cid); st['fail'] += 1; counter += 1
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    ext      = url.split('.')[-1].lower().split('?')[0]
    if ext not in ['jpg','jpeg','png','gif','webp']: ext = 'jpg'
    hname    = hashlib.md5(img_bytes).hexdigest()[:12] + '.' + ext
    supa_url = upload_supabase(img_bytes, hname)

    if not supa_url:
        p['done'].append(cid); st['fail'] += 1; counter += 1
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        continue

    lic    = meta.get('LicenseShortName', {}).get('value', 'CC BY-SA') if meta else 'CC BY-SA'
    author = meta.get('Artist', {}).get('value', '') if meta else ''
    author = re.sub(r'<[^>]+>', '', author)[:60]

    try:
        sb.table('cards').update({'img': {
            'url':     supa_url,
            'alt':     answer[:80],
            'credit':  f'Wikimedia Commons — {title[:60]}',
            'license': lic,
            'author':  author,
            'source':  'Wikimedia/Direct'
        }}).eq('id', cid).execute()
        st['dl'] += 1
        log.append({'card_id': cid, 'deck': deck, 'answer': answer,
                    'img_title': title, 'url': supa_url, 'license': lic})
        print(f"  OK [{st['dl']}] {answer[:45]} → {title[:40]}")
    except Exception as e:
        print(f"  supa err: {e}")

    p['done'].append(cid); counter += 1
    if counter % SAVE_EVERY == 0:
        json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
        json.dump(log, open(LOG_FILE, 'w'), ensure_ascii=True)
        pct = len(p['done']) / len(all_cards) * 100
        print(f"  [{pct:.1f}%] dl:{st['dl']} matched:{st['matched']} skipped:{st['skipped']} fail:{st['fail']} nomatch:{st['nomatch']}")

json.dump(p, open(PROGRESS_FILE, 'w'), ensure_ascii=True)
json.dump(log, open(LOG_FILE, 'w'), ensure_ascii=True)
print(f"\nCONCLUIDO: matched:{st['matched']} dl:{st['dl']} skipped:{st['skipped']} fail:{st['fail']} nomatch:{st['nomatch']}")
