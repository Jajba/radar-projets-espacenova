import argparse, hashlib, io, re, sys
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import fitz
import pandas as pd
from sqlalchemy import select, update, insert, and_
from sqlalchemy.exc import IntegrityError
from config import MASTER_XLSX, REQUEST_TIMEOUT, MAX_DOC_BYTES, USER_AGENT, MAX_LINKS_PER_SOURCE, MIN_TEXT_CHARS
from db import engine, init_db, sources, documents, leads, errors, runs, utcnow
from detector import evaluate, lead_code

LINK_HINTS = ['deliber','délibér','conseil','proces','procès','pv','decision','décision','actes','crac','rapport','seance','séance','compte-rendu','compte rendu']

class RadarCrawler:
    def __init__(self, dry_run=False):
        self.dry_run=dry_run
        self.session=requests.Session()
        self.session.headers.update({'User-Agent':USER_AGENT,'Accept-Language':'fr-FR,fr;q=0.9'})

    def bootstrap_sources(self):
        with engine.begin() as conn:
            count=conn.execute(select(sources.c.id).limit(1)).first()
            if count: return
        df=pd.read_excel(MASTER_XLSX, sheet_name='Sources')
        rows=[]
        for _,r in df.iterrows():
            url=str(r.get('URL_source_principale') or '').strip()
            if not url or url.lower()=='nan': continue
            code=str(r.get('ID_source') or f'SRC-{len(rows)+1:03d}')
            active=str(r.get('Actif','Oui')).strip().lower() not in ('non','false','0')
            rows.append(dict(source_code=code,name=str(r.get('Nom_source') or code),structure_type=str(r.get('Type_structure') or ''),department=str(r.get('Departement') or ''),url=url,alt_url=str(r.get('URL_alternative') or ''),page_type=str(r.get('Type_page') or ''),prep_status=str(r.get('Statut_preparation') or ''),audit_priority=str(r.get('Priorite_audit') or ''),active=active,notes=str(r.get('Notes') or ''),radar_family=str(r.get('Famille_radar') or 'Foncier public')))
        if not self.dry_run:
            with engine.begin() as conn: conn.execute(insert(sources), rows)

    def fetch(self,url):
        r=self.session.get(url,timeout=REQUEST_TIMEOUT,allow_redirects=True)
        r.raise_for_status()
        if len(r.content)>MAX_DOC_BYTES: raise ValueError('Document trop volumineux')
        return r

    def discover(self, base_url, response):
        ctype=response.headers.get('content-type','').lower()
        if 'pdf' in ctype or base_url.lower().split('?')[0].endswith('.pdf'):
            return [(response.url, 'PDF direct')]
        soup=BeautifulSoup(response.text,'html.parser')
        out=[]; seen=set()
        for a in soup.find_all('a',href=True):
            href=urljoin(response.url,a['href'].strip())
            text=' '.join(a.stripped_strings)
            blob=(href+' '+text).lower()
            is_pdf='.pdf' in urlparse(href).path.lower()
            relevant=is_pdf or any(k in blob for k in LINK_HINTS)
            if relevant and href.startswith(('http://','https://')) and href not in seen:
                seen.add(href); out.append((href,text[:250] or href.rsplit('/',1)[-1]))
            if len(out)>=MAX_LINKS_PER_SOURCE: break
        # Always analyze source HTML itself too: some sites publish decisions inline.
        out.insert(0,(response.url,'Page source'))
        return out

    def extract_text(self, url, response=None):
        r=response or self.fetch(url)
        ctype=r.headers.get('content-type','').lower()
        if 'pdf' in ctype or r.url.lower().split('?')[0].endswith('.pdf'):
            doc=fitz.open(stream=r.content,filetype='pdf')
            text='\n'.join(page.get_text('text') for page in doc)
            return text,'application/pdf',hashlib.sha256(r.content).hexdigest()
        soup=BeautifulSoup(r.text,'html.parser')
        for tag in soup(['script','style','nav','footer']): tag.decompose()
        text='\n'.join(s.strip() for s in soup.stripped_strings if s.strip())
        return text,ctype or 'text/html',hashlib.sha256(r.content).hexdigest()

    def upsert_document(self, source_id, url, title, hsh, ctype, text_chars, ocr_required, status='PROCESSED', error=None):
        now=utcnow()
        with engine.begin() as conn:
            row=conn.execute(select(documents).where(and_(documents.c.source_id==source_id,documents.c.url==url))).mappings().first()
            if row:
                changed = bool(hsh and hsh != row['content_hash'])
                if not self.dry_run:
                    conn.execute(update(documents).where(documents.c.id==row['id']).values(last_seen_at=now,content_hash=hsh or row['content_hash'],content_type=ctype,status=status,text_chars=text_chars,ocr_required=ocr_required,error=error,processed_at=now if changed or not row['processed_at'] else row['processed_at']))
                return row['id'], changed
            if self.dry_run: return None, True
            res=conn.execute(insert(documents).values(source_id=source_id,url=url,title=title,content_hash=hsh,content_type=ctype,first_seen_at=now,last_seen_at=now,processed_at=now,status=status,text_chars=text_chars,ocr_required=ocr_required,error=error))
            return res.inserted_primary_key[0], True

    def add_lead(self, source, document_id, url, cand):
        code=lead_code(source['id'],url,cand.evidence)
        if self.dry_run: return True
        with engine.begin() as conn:
            if conn.execute(select(leads.c.id).where(leads.c.lead_code==code)).first(): return False
            conn.execute(insert(leads).values(lead_code=code,source_id=source['id'],document_id=document_id,detected_at=utcnow(),company_sci=cand.company_sci,end_user='Non indiqué',territory=source['name'],commune='Non indiqué',zone_site='Non indiqué',signal_family=source.get('radar_family') or 'Foncier public',signal_type=cand.signal_type,project=cand.project,commercial_score=cand.score,convergence_score=cand.convergence,confidence_pct=cand.confidence,facts=cand.facts,deductions=cand.deductions,unknowns=cand.unknowns,recommended_action='Vérifier la délibération puis qualifier le porteur de projet et contacter si pertinent.',evidence_excerpt=cand.evidence,source_url=url,status='Nouveau'))
        return True

    def log_error(self, source_id, url, typ, detail):
        if self.dry_run: return
        with engine.begin() as conn:
            conn.execute(insert(errors).values(source_id=source_id,occurred_at=utcnow(),url=url,error_type=typ,detail=str(detail)[:4000]))

    def scan_source(self, source):
        stats={'ok':False,'docs_new':0,'leads_new':0}
        try:
            first=self.fetch(source['url'])
            links=self.discover(source['url'],first)
            # newest-looking links often appear first on institutional pages; process bounded list
            for url,title in links:
                try:
                    resp=first if url==first.url else self.fetch(url)
                    text,ctype,hsh=self.extract_text(url,resp)
                    ocr=('pdf' in ctype and len(text.strip())<MIN_TEXT_CHARS)
                    status='OCR_REQUIRED' if ocr else 'PROCESSED'
                    doc_id,is_new=self.upsert_document(source['id'],url,title,hsh,ctype,len(text),ocr,status=status)
                    if is_new: stats['docs_new']+=1
                    if ocr: continue
                    cand=evaluate(text)
                    if cand and is_new:
                        if self.add_lead(source,doc_id,url,cand): stats['leads_new']+=1
                except Exception as e:
                    self.log_error(source['id'],url,type(e).__name__,e)
            stats['ok']=True
            if not self.dry_run:
                with engine.begin() as conn:
                    conn.execute(update(sources).where(sources.c.id==source['id']).values(last_checked_at=utcnow(),last_ok_at=utcnow(),consecutive_errors=0))
        except Exception as e:
            self.log_error(source['id'],source['url'],type(e).__name__,e)
            if not self.dry_run:
                with engine.begin() as conn:
                    conn.execute(update(sources).where(sources.c.id==source['id']).values(last_checked_at=utcnow(),consecutive_errors=(source.get('consecutive_errors') or 0)+1))
        return stats

    def run(self, limit=None):
        init_db(); self.bootstrap_sources(); start=utcnow()
        with engine.begin() as conn:
            q=select(sources).where(sources.c.active==True).order_by(sources.c.audit_priority, sources.c.id)
            if limit: q=q.limit(limit)
            srcs=list(conn.execute(q).mappings())
            run_id=None
            if not self.dry_run:
                run_id=conn.execute(insert(runs).values(started_at=start,sources_total=len(srcs))).inserted_primary_key[0]
        total={'sources_total':len(srcs),'sources_ok':0,'sources_error':0,'documents_new':0,'leads_new':0}
        for i,s in enumerate(srcs,1):
            print(f'[{i}/{len(srcs)}] {s["name"]}')
            st=self.scan_source(s)
            total['sources_ok']+=int(st['ok']); total['sources_error']+=int(not st['ok']); total['documents_new']+=st['docs_new']; total['leads_new']+=st['leads_new']
        if not self.dry_run and run_id:
            with engine.begin() as conn:
                conn.execute(update(runs).where(runs.c.id==run_id).values(finished_at=utcnow(),**total))
        print(total)
        return total

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run-once', action='store_true', help='Lance un scan complet une fois')
    p.add_argument('--dry-run', action='store_true', help='Teste sans écrire en base')
    p.add_argument('--limit', type=int, default=None, help='Limite le nombre de sources pour un test')
    args=p.parse_args()
    RadarCrawler(dry_run=args.dry_run).run(limit=args.limit)
