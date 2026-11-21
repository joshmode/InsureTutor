from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.services.brochures import OWNER_COOKIE


def pdf(text='Insurance benefits. Administrative charge is US$12 monthly.', *, encrypted=False, pages=1):
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page()
        if text: page.insert_text((50, 60), text)
    options = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='reader') if encrypted else {}
    content = document.tobytes(**options)
    document.close()
    return content


@pytest.fixture
def client(tmp_path, monkeypatch):
    knowledge = tmp_path / 'knowledge'; knowledge.mkdir()
    (knowledge / 'default.pdf').write_bytes(pdf('Default insurance policy. Administrative charge is US$99 monthly.'))
    for key,value in {'KNOWLEDGE_BASE_DIR':str(knowledge),'DOCUMENTS':'default.pdf','DATA_DIR':str(tmp_path/'data'),
                      'ENABLE_EMBEDDINGS':'false','EMBEDDING_ENABLED':'false','LLM_API_KEY':''}.items():
        monkeypatch.setenv(key,value)
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def upload(client, content=None, name='Alpha.pdf'):
    return client.post('/api/brochures', content=content if content is not None else pdf(),
                       headers={'Content-Type':'application/pdf','X-File-Name':name})


def test_private_upload_chat_sources_and_reset_do_not_change_default(client):
    response = upload(client); assert response.status_code == 201, response.text
    document = response.json(); identifier=document['id']
    assert document['filename']=='Alpha.pdf' and document['pages']==1 and document['chunks']>0
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    answer=client.post('/api/chat',json={'message':'What is the administrative charge?','brochure_id':identifier}).json()
    assert answer['kind']=='answer' and answer['model_generated'] is False
    assert 'US$12' in answer['message'] and 'US$99' not in answer['message']
    assert all(c['document']=='Alpha.pdf' for c in answer['citations'])
    source=client.get('/source-document',params={'brochure_id':identifier,'document':'Alpha.pdf'})
    assert source.status_code==200 and source.content.startswith(b'%PDF-')
    chunk=answer['citations'][0]
    assert client.get('/api/chunks/'+chunk['id'],params={'brochure_id':identifier}).json()['excerpt']==chunk['excerpt']
    assert client.get('/source-document',params={'brochure_id':identifier,'document':'wrong.pdf'}).status_code==404
    assert client.get('/api/chunks/'+chunk['id']).status_code==404
    default=client.post('/api/chat',json={'message':'What is the administrative charge?'}).json()
    assert 'US$99' in default['message'] and 'US$12' not in default['message']
    assert client.delete('/api/brochures/'+identifier).status_code==204
    assert client.post('/api/chat',json={'message':'What is the administrative charge?','brochure_id':identifier}).status_code==404


def test_owner_isolation_and_separate_indices_survive_cache_reload(client):
    alpha=upload(client).json(); owner_a=client.cookies.get(OWNER_COOKIE)
    client.cookies.clear()
    beta=upload(client,pdf('Insurance benefits. Administrative charge is US$34 monthly.'),'Beta.pdf').json()
    assert beta['id']!=alpha['id']
    assert client.get('/source-document',params={'brochure_id':alpha['id']}).status_code==404
    assert client.delete('/api/brochures/'+alpha['id']).status_code==404
    assert client.get('/api/chunks/anything',params={'brochure_id':alpha['id']}).status_code==404
    assert client.post('/api/chat',json={'message':'What is the administrative charge?','brochure_id':alpha['id']}).status_code==404
    store=app.state.runtime.brochures
    assert store.contexts[alpha['id']].retriever.embedding_backend is store.contexts[beta['id']].retriever.embedding_backend
    store.contexts.clear()
    client.cookies.clear();client.cookies.set(OWNER_COOKIE,owner_a)
    answer=client.post('/api/chat',json={'message':'What is the administrative charge?','brochure_id':alpha['id']}).json()
    assert 'US$12' in answer['message'] and 'US$34' not in answer['message']


@pytest.mark.parametrize('content',[b'%PDF-invalid',pdf('',pages=1),pdf(encrypted=True),pdf('',pages=101)])
def test_bad_encrypted_scanned_or_overlong_pdf_is_rejected_without_changing_default(client,content):
    result=upload(client,content)
    assert result.status_code==422, result.text
    assert client.get('/api/health').json()['chunks']>0
    assert not list(app.state.runtime.brochures.root.glob('*/metadata.json'))


def test_upload_limits_and_filename_validation(client):
    assert upload(client,b'%PDF-'+b'x'*(8*1024*1024)).status_code==413
    assert upload(client,name='../unsafe.pdf').status_code==422
    assert client.post('/api/brochures',content=b'not PDF',headers={'Content-Type':'text/plain'}).status_code==415


def test_upload_expiry_and_capacity(client,monkeypatch):
    store=app.state.runtime.brochures
    store.settings.max_private_brochures=1
    document=upload(client).json()
    assert upload(client).status_code==429
    import backend.app.services.brochures as module
    expiry=document['expires_at']
    monkeypatch.setattr(module.time,'time',lambda:expiry+1)
    assert client.get('/source-document',params={'brochure_id':document['id']}).status_code==404
    assert not (store.root/document['id']).exists()


def test_parser_timeout_cleans_reservation_and_receives_no_provider_secret(client,monkeypatch):
    import subprocess
    import backend.app.services.brochures as module
    def timeout(*args,**kwargs):
        assert 'LLM_API_KEY' not in kwargs['env']
        raise subprocess.TimeoutExpired(args[0],25)
    monkeypatch.setattr(module.subprocess,'run',timeout)
    assert upload(client).status_code==422
    assert not [p for p in app.state.runtime.brochures.root.iterdir() if p.is_dir()]


def test_generic_brochure_does_not_inherit_flexi_rates(client):
    from backend.app.chat.prompts import build_messages
    response=upload(client).json()
    context=app.state.runtime.brochures.contexts[response['id']]
    hits=context.retriever.search('administrative charge').hits
    system=build_messages('en','What are the charges?',hits,[])[0]['content']
    assert 'FLEXI' not in system and '0.25%' not in system and '2.75%' not in system


@pytest.mark.parametrize(('question','language'), [('费用是什么？','zh-Hans'),('費用是什麼？','zh-Hant')])
def test_chinese_fee_question_can_retrieve_english_upload(client,question,language):
    document=upload(client).json()
    answer=client.post('/api/chat',json={'message':question,'language':language,'brochure_id':document['id']}).json()
    assert answer['kind']=='answer' and answer['citations']
    assert 'US$12' in answer['message']


def test_each_upload_regenerates_vectors_without_loading_another_model(client):
    import numpy as np
    class Backend:
        available=True
        def __init__(self): self.inputs=[]
        def embed_documents(self,texts):
            self.inputs.append(texts)
            return np.array([[1.,0.] for _ in texts])
        def embed_query(self,text): return np.array([1.,0.])
    backend=Backend(); store=app.state.runtime.brochures;store.backend=backend
    first=upload(client).json()
    second=upload(client,pdf('Insurance benefits. Administrative charge is US$34 monthly.'),'Beta.pdf').json()
    assert len(backend.inputs)==2
    assert 'US$12' in ' '.join(backend.inputs[0]) and 'US$34' in ' '.join(backend.inputs[1])
    assert store.contexts[first['id']].retriever.embedding_backend is backend
    assert store.contexts[second['id']].retriever.embedding_backend is backend


def test_other_products_may_have_different_guarantees_and_included_benefits():
    from backend.app.guardrails.grounding import inspect_draft
    from backend.app.ingestion.chunker import Chunk
    from backend.app.retrieval.hybrid import RetrievalHit
    source=Chunk('different','Other.pdf',1,'Benefits','The 4% rate is guaranteed annually. Critical Illness Benefit is automatically included in the basic plan.')
    hits=[RetrievalHit(source,1,1,0)]
    assert inspect_draft('The 4% rate is guaranteed annually. [S1]',hits)
    assert inspect_draft('Critical Illness Benefit is automatically included in the basic plan. [S1]',hits)


def test_misspelled_document_context_cannot_silently_use_default(client):
    document=upload(client).json()
    result=client.post('/api/chat',json={'message':'What are the fees?','brochureId':document['id']})
    assert result.status_code==422


def test_canceled_upload_deletes_eventual_thread_result():
    import asyncio,threading
    from types import SimpleNamespace
    from starlette.requests import Request
    from starlette.responses import Response
    from backend.app.api.routes import upload_brochure
    entered=threading.Event();release=threading.Event();deleted=threading.Event()
    class Store:
        def create(self,*args):
            entered.set();assert release.wait(2)
            return SimpleNamespace(info=SimpleNamespace(id='a'*32))
        def delete(self,identifier,owner):
            assert identifier=='a'*32 and owner=='b'*64
            deleted.set()
    async def run():
        async def receive():return {'type':'http.request','body':b'%PDF-test','more_body':False}
        request=Request({'type':'http','method':'POST','scheme':'http','path':'/api/brochures',
                         'headers':[(b'content-type',b'application/pdf'),(b'cookie',(OWNER_COOKIE+'='+'b'*64).encode())],
                         'app':SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(brochures=Store())))},receive)
        task=asyncio.create_task(upload_brochure(request,Response()))
        for _ in range(200):
            if entered.is_set():break
            await asyncio.sleep(.005)
        assert entered.is_set();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        release.set()
        for _ in range(200):
            if deleted.is_set():break
            await asyncio.sleep(.005)
        assert deleted.is_set()
    asyncio.run(run())


def test_native_parsers_are_serialized_across_store_instances(client,monkeypatch):
    import concurrent.futures,threading,time
    from backend.app.services.brochures import BrochureStore
    import backend.app.services.brochures as module
    first=app.state.runtime.brochures
    second=BrochureStore(first.settings,first.llm,first.backend,first.retrieval_lock)
    original=module.subprocess.run;lock=threading.Lock();active=0
    def tracked(*args,**kwargs):
        nonlocal active
        with lock:
            active+=1;assert active==1
        try:
            time.sleep(.02)
            return original(*args,**kwargs)
        finally:
            with lock:active-=1
    monkeypatch.setattr(module.subprocess,'run',tracked)
    content=pdf()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(store.create,content,'Fixture.pdf','c'*64) for store in [first,second]]
        results=[future.result(timeout=10) for future in futures]
    assert len({result.info.id for result in results})==2
