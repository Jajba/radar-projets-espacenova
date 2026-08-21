import re
from dataclasses import dataclass
from hashlib import sha256

TRANSACTION = [
    'cession','céder','ceder','aliénation','alienation','acquéreur','acquereur','vente immobilière','vente immobiliere',
    'promesse de vente','compromis','cession immobilière','cession immobiliere','cession à la société','cession a la societe',
    'acquisition foncière','acquisition fonciere','réservation foncière','reservation fonciere','prix de cession'
]
LAND = [
    'terrain','parcelle','lot','emprise','foncier économique','foncier economique','parcelle cadastrée','parcelle cadastree',
    'section cadastrale','prix au m²','prix au m2','za ','zac','zae','zone d’activités','zone d\'activités','zone d activites',
    'zone industrielle','zone artisanale','zone commerciale','parc d’activités','parc d activites'
]
PROJECT = [
    'implantation','construction','extension','agrandissement','bâtiment industriel','batiment industriel','atelier','entrepôt','entrepot',
    'plateforme logistique','locaux d’activité','locaux d activite','unité de production','unite de production','nouveau site',
    'cabinet médical','cabinet medical','maison de santé','maison de sante','centre de santé','centre de sante','pôle de santé','pole de sante',
    'résidence senior','residence senior','bureaux','commerce'
]
ENTITY = [' sas ',' sarl ',' sci ',' société ',' societe ',' entreprise ',' groupe ',' acquéreur ',' acquereur ',' bénéficiaire ',' beneficiaire ']
REJECT = [
    'vente de véhicule','vente de vehicule','cession de véhicule','cession de vehicule','matériel informatique','materiel informatique',
    'logiciel','mobilier réformé','mobilier reforme','ferraillage','cession gratuite de matériel','cession gratuite de materiel'
]

def norm(s):
    s = (s or '').lower().replace('\xa0',' ')
    return re.sub(r'\s+', ' ', s)

def hits(text, terms):
    t=norm(text)
    return [x for x in terms if x in t]

def excerpt(text, positions, radius=700):
    if not text: return ''
    if not positions: return text[:1400]
    p=min(positions)
    return re.sub(r'\s+', ' ', text[max(0,p-radius):p+radius]).strip()

@dataclass
class Candidate:
    score: str
    confidence: float
    convergence: float
    signal_type: str
    facts: str
    deductions: str
    unknowns: str
    evidence: str
    company_sci: str='Non indiqué'
    project: str='Non indiqué'

COMPANY_PATTERNS = [
    re.compile(r'(?:au profit de|à la société|a la societe|acquéreur\s*:?|acquereur\s*:?)\s+(?:la\s+)?((?:SCI|SASU?|SARL|SA)\s+[A-Z0-9À-ÖØ-Ý&\-\. \'’]{2,80})', re.I),
    re.compile(r'((?:SCI|SASU?|SARL|SA)\s+[A-Z0-9À-ÖØ-Ý&\-\. \'’]{2,80})', re.I),
]

def find_company(text):
    for pat in COMPANY_PATTERNS:
        m=pat.search(text or '')
        if m:
            return re.sub(r'\s+',' ',m.group(1)).strip(' .,:;')[:120]
    return 'Non indiqué'

def evaluate(text):
    t=norm(text)
    if len(t)<80: return None
    rej=hits(t, REJECT)
    tx=hits(t, TRANSACTION)
    la=hits(t, LAND)
    pr=hits(t, PROJECT)
    en=hits(' '+t+' ', ENTITY)
    # A land/project signal requires at least two semantic families. Strong transaction+land is enough.
    points = len(set(tx))*3 + len(set(la))*2 + len(set(pr))*3 + min(2,len(set(en)))
    if rej and not (la and pr):
        return None
    strong = bool(tx and la and pr)
    medium = bool((tx and la) or (la and pr))
    if not medium:
        return None
    score = 'A' if strong or points >= 12 else ('B' if points >= 7 else 'C')
    confidence = min(99, 55 + min(points,20)*2 + (8 if strong else 0))
    convergence = min(100, 20*bool(tx) + 25*bool(la) + 30*bool(pr) + 10*bool(en) + min(points,15))
    poss=[]
    for term in set(tx+la+pr):
        p=t.find(term)
        if p>=0: poss.append(p)
    ev=excerpt(text, poss)
    company=find_company(ev)
    facts = 'Source contient : ' + ', '.join((tx[:3]+la[:3]+pr[:3])[:8])
    deductions = 'Signal compatible avec une opération foncière / immobilière à qualifier commercialement.'
    unknowns = 'Entreprise, surfaces, prix et calendrier : Non indiqué sauf si explicitement présents dans l’extrait.'
    signal = ' + '.join([x for x,ok in [('transaction',bool(tx)),('foncier',bool(la)),('projet',bool(pr))] if ok])
    return Candidate(score, confidence, convergence, signal, facts, deductions, unknowns, ev, company_sci=company)

def lead_code(source_id, url, evidence):
    return 'LEAD-' + sha256(f'{source_id}|{url}|{evidence[:500]}'.encode('utf-8','ignore')).hexdigest()[:16].upper()
