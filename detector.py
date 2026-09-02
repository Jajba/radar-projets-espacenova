import re
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TRANSACTION = [
    'cession', 'céder', 'ceder', 'aliénation', 'alienation', 'acquéreur', 'acquereur',
    'vente immobilière', 'vente immobiliere', 'promesse de vente', 'compromis',
    'cession immobilière', 'cession immobiliere', 'cession à la société',
    'cession a la societe', 'acquisition foncière', 'acquisition fonciere',
    'réservation foncière', 'reservation fonciere', 'prix de cession'
]

LAND = [
    'terrain', 'parcelle', 'lot', 'emprise', 'foncier économique', 'foncier economique',
    'parcelle cadastrée', 'parcelle cadastree', 'section cadastrale', 'prix au m²',
    'prix au m2', ' za ', 'zac', 'zae', 'zone d’activités', "zone d'activités",
    'zone d activites', 'zone industrielle', 'zone artisanale', 'zone commerciale',
    'parc d’activités', 'parc d activites'
]

PROJECT = [
    'implantation', 'construction', 'extension', 'agrandissement',
    'bâtiment industriel', 'batiment industriel', 'atelier', 'entrepôt', 'entrepot',
    'plateforme logistique', 'locaux d’activité', 'locaux d activite',
    'unité de production', 'unite de production', 'nouveau site',
    'cabinet médical', 'cabinet medical', 'maison de santé', 'maison de sante',
    'centre de santé', 'centre de sante', 'pôle de santé', 'pole de sante',
    'résidence senior', 'residence senior', 'bureaux', 'commerce'
]

ENTITY = [
    ' sas ', ' sasu ', ' sarl ', ' sci ', ' société ', ' societe ',
    ' entreprise ', ' groupe ', ' acquéreur ', ' acquereur ',
    ' bénéficiaire ', ' beneficiaire '
]

REJECT = [
    'vente de véhicule', 'vente de vehicule', 'cession de véhicule',
    'cession de vehicule', 'matériel informatique', 'materiel informatique',
    'logiciel', 'mobilier réformé', 'mobilier reforme', 'ferraillage',
    'cession gratuite de matériel', 'cession gratuite de materiel'
]

STRONG_ACTION = [
    'approuve la cession', 'décide de céder', 'decide de ceder',
    'autorise la cession', 'autorise la vente', 'cession au profit de',
    'cession à la société', 'cession a la societe', 'promesse de vente',
    'acquisition foncière', 'acquisition fonciere', 'permis de construire',
    'implantation de', 'construction de', 'extension de'
]

ADMIN_NOISE = [
    'membres présents', 'membres presents', 'membres absents',
    'procuration', 'secrétaire de séance', 'secretaire de seance',
    'appel nominal', 'quorum'
]


def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\xa0', ' ')).strip()


def norm(s):
    return clean(s).lower()


def hits(text, terms):
    t = norm(text)
    return list(dict.fromkeys(x for x in terms if x in t))


def make_windows(text, lines_per_window=7, step=4):
    """Analyse des zones locales du document au lieu de mélanger tout le PDF."""
    lines = [clean(x) for x in (text or '').splitlines() if len(clean(x)) >= 15]

    if len(lines) >= 3:
        windows = []
        for i in range(0, len(lines), step):
            block = clean(' '.join(lines[i:i + lines_per_window]))
            if len(block) >= 120:
                windows.append(block)
        return windows

    # Fallback pour les pages HTML / PDF avec peu de retours ligne.
    raw = clean(text)
    if not raw:
        return []

    size = 2600
    overlap = 500
    out = []
    start = 0
    while start < len(raw):
        block = raw[start:start + size]
        if len(block) >= 120:
            out.append(block)
        start += size - overlap
    return out


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
    company_sci: str = 'Non indiqué'
    project: str = 'Non indiqué'


COMPANY_PATTERNS = [
    re.compile(
        r'(?:au profit de|à la société|a la societe|acquéreur\s*:|acquereur\s*:|'
        r'bénéficiaire\s*:|beneficiaire\s*:)\s+(?:la\s+)?'
        r'((?:SCI|SASU?|SARL|SA)\s+[A-Za-zÀ-ÿ0-9&\'’.\- ]{2,70})',
        re.I
    ),
    re.compile(
        r'\b((?:SCI|SASU?|SARL|SA)\s+[A-Za-zÀ-ÿ0-9&\'’.\-]{2,45}'
        r'(?:\s+[A-Za-zÀ-ÿ0-9&\'’.\-]{2,25}){0,4})\b',
        re.I
    ),
]

SURFACE_RE = re.compile(
    r'\b(\d{1,3}(?:[ .]\d{3})*(?:[,.]\d+)?)\s*(m²|m2|ha|hectares?)\b',
    re.I
)

AMOUNT_RE = re.compile(
    r'\b(\d{1,3}(?:[ .]\d{3})*(?:[,.]\d+)?)\s*(€|euros?)\b',
    re.I
)

PARCEL_RE = re.compile(
    r'\b(?:parcelle|section cadastrale|section)\s+'
    r'([A-Z]{1,3}\s*[-]?\s*\d{1,6})\b',
    re.I
)


def find_company(text):
    for pat in COMPANY_PATTERNS:
        m = pat.search(text or '')
        if m:
            value = clean(m.group(1)).strip(' .,:;')
            # évite d'absorber une phrase entière
            value = re.split(
                r'\s+(?:pour|sur|située|situee|sise|dont|représentée|representee)\s+',
                value,
                maxsplit=1,
                flags=re.I
            )[0]
            return value[:120]
    return 'Non indiqué'


def first_surface(text):
    m = SURFACE_RE.search(text or '')
    return clean(' '.join(m.groups())) if m else None


def first_amount(text):
    m = AMOUNT_RE.search(text or '')
    return clean(' '.join(m.groups())) if m else None


def first_parcel(text):
    m = PARCEL_RE.search(text or '')
    return clean(m.group(1)) if m else None


def build_project(project_hits, company, surface, amount):
    if not project_hits:
        return 'Non indiqué'

    parts = [project_hits[0].capitalize()]
    if company != 'Non indiqué':
        parts.append(company)
    if surface:
        parts.append(surface)
    if amount:
        parts.append(amount)

    return ' — '.join(parts)[:250]


def evaluate_window(window):
    tx = hits(window, TRANSACTION)
    la = hits(window, LAND)
    pr = hits(window, PROJECT)
    en = hits(' ' + norm(window) + ' ', ENTITY)
    rej = hits(window, REJECT)
    actions = hits(window, STRONG_ACTION)
    noise = hits(window, ADMIN_NOISE)

    if rej and not (la and pr):
        return None

    # Il faut au moins deux familles sémantiques dans LA MÊME ZONE du document.
    families = sum([bool(tx), bool(la), bool(pr)])
    if families < 2:
        return None

    # On cible en priorité les signaux fonciers / immobiliers.
    if not ((tx and la) or (la and pr) or (tx and pr)):
        return None

    company = find_company(window)
    surface = first_surface(window)
    amount = first_amount(window)
    parcel = first_parcel(window)

    concrete_details = sum([
        company != 'Non indiqué',
        bool(surface),
        bool(amount),
        bool(parcel)
    ])

    # Les listes d'élus / PV administratifs ne doivent pas devenir des A
    # uniquement parce que plusieurs mots-clés apparaissent dans le document.
    if len(noise) >= 2 and not actions and concrete_details == 0:
        return None

    term_variety = len(set(tx)) + len(set(la)) + len(set(pr))
    points = (
        families * 3
        + min(term_variety, 6)
        + min(len(actions), 2) * 4
        + concrete_details * 4
        + min(len(en), 2)
    )

    # A = opportunité réellement documentée, pas simple convergence de mots-clés.
    score_a = (
        families == 3
        and concrete_details >= 1
        and (bool(actions) or concrete_details >= 2)
        and points >= 18
    )

    score_b = (
        families >= 2
        and (bool(actions) or concrete_details >= 1)
        and points >= 11
    )

    score = 'A' if score_a else ('B' if score_b else 'C')

    confidence = min(
        99,
        48
        + families * 7
        + min(term_variety, 5) * 2
        + min(len(actions), 2) * 5
        + concrete_details * 5
    )

    convergence = min(
        100,
        families * 20
        + min(term_variety, 5) * 3
        + min(len(actions), 2) * 7
        + concrete_details * 6
    )

    facts_parts = []
    if company != 'Non indiqué':
        facts_parts.append(f'Entreprise : {company}')
    if surface:
        facts_parts.append(f'Surface : {surface}')
    if amount:
        facts_parts.append(f'Montant : {amount}')
    if parcel:
        facts_parts.append(f'Parcelle : {parcel}')

    semantic = []
    if tx:
        semantic.append('transaction=' + ', '.join(tx[:2]))
    if la:
        semantic.append('foncier=' + ', '.join(la[:2]))
    if pr:
        semantic.append('projet=' + ', '.join(pr[:2]))

    if semantic:
        facts_parts.append('Signaux : ' + ' | '.join(semantic))

    facts = ' ; '.join(facts_parts) if facts_parts else 'Signal immobilier/foncier à qualifier.'

    missing = []
    if company == 'Non indiqué':
        missing.append('entreprise')
    if not surface:
        missing.append('surface')
    if not amount:
        missing.append('montant')
    if not parcel:
        missing.append('parcelle')

    unknowns = (
        'À compléter : ' + ', '.join(missing)
        if missing
        else 'Principales données structurantes détectées dans la source.'
    )

    signal = ' + '.join([
        name for name, ok in [
            ('transaction', bool(tx)),
            ('foncier', bool(la)),
            ('projet', bool(pr))
        ] if ok
    ])

    project = build_project(pr, company, surface, amount)

    deductions = (
        'Opportunité potentiellement exploitable commercialement. '
        'La source doit confirmer le porteur, le calendrier et le besoin immobilier.'
        if score in ('A', 'B')
        else
        'Signal faible ou incomplet : conserver en veille, sans action commerciale immédiate.'
    )

    return Candidate(
        score=score,
        confidence=confidence,
        convergence=convergence,
        signal_type=signal,
        facts=facts,
        deductions=deductions,
        unknowns=unknowns,
        evidence=clean(window)[:2200],
        company_sci=company,
        project=project
    )


def evaluate(text):
    """
    Analyse locale du document.
    On retient seulement la meilleure opportunité du document.
    """
    if len(norm(text)) < 80:
        return None

    candidates = []

    for window in make_windows(text):
        cand = evaluate_window(window)
        if cand:
            candidates.append(cand)

    if not candidates:
        return None

    rank = {'A': 3, 'B': 2, 'C': 1}

    candidates.sort(
        key=lambda c: (
            rank.get(c.score, 0),
            c.confidence,
            c.convergence,
            c.company_sci != 'Non indiqué',
            c.project != 'Non indiqué'
        ),
        reverse=True
    )

    return candidates[0]


def canonical_url(url):
    """
    Supprime uniquement les paramètres de tracking.
    Évite de créer plusieurs leads pour le même document avec des URL marketing différentes.
    """
    try:
        parts = urlsplit(url or '')
        query = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith('utm_')
            and k.lower() not in ('fbclid', 'gclid')
        ]
        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip('/'),
            urlencode(query),
            ''
        ))
    except Exception:
        return url or ''


def lead_code(source_id, url, evidence):
    """
    Un document canonique = un lead maximum.
    L'extrait de texte n'entre plus dans l'identifiant.
    """
    stable_url = canonical_url(url)
    raw = f'{source_id}|{stable_url}'
    return 'LEAD-' + sha256(
        raw.encode('utf-8', 'ignore')
    ).hexdigest()[:16].upper()
