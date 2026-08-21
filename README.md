# Radar Projets EspaceNova — V1

Application métier de veille et qualification de signaux fonciers/immobiliers.

## Ce que fait cette V1
- importe les sources du classeur maître ;
- visite les pages sources ;
- découvre les PDF et liens de délibérations/décisions/PV/CRAC ;
- mémorise les documents déjà vus ;
- extrait le texte HTML/PDF ;
- marque les scans illisibles `OCR_REQUIRED` ;
- détecte les combinaisons transaction + foncier + projet ;
- élimine plusieurs faux positifs évidents ;
- crée des leads A/B/C avec preuve source obligatoire ;
- journalise les erreurs et le taux de couverture ;
- fournit un dashboard Streamlit.

## Lancer localement
```bash
python -m venv .venv
# Windows : .venv\\Scripts\\activate
# macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
python crawler.py --run-once --limit 10
streamlit run app.py
```

## Test sans modifier la base
```bash
python crawler.py --dry-run --limit 5
```

## Production
- `DATABASE_URL` absent : SQLite local.
- `DATABASE_URL` PostgreSQL : base partagée en production.
- même image Docker pour l'interface et le job de scan.
- UI : commande Docker par défaut.
- Job quotidien : `python crawler.py --run-once`.

## Limite volontaire V1
La V1 est déterministe pour éviter les hallucinations. L'enrichissement IA multi-sources (croisement Sitadel, aides, santé, foncières, presse, etc.) se branche au-dessus de cette base après validation du taux de détection du collecteur.
