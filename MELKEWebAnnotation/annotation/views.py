from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import DocumentInfo, SentenceInfo, Entity, Relation
import re
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import pysolr

def index(request):
    return render(request, 'index.html')

def search_documents(request):
    query = request.GET.get('query')
    search_type = request.GET.get('search_type')
    solr = pysolr.Solr('http://localhost:8980/solr/pkde4j/', timeout=10)
    # Do a health check.
    solr.ping()

    if search_type == 'pmid':
        request.session['pmid'] = query
        results = solr.search(q='pmid:{}'.format(query))
        doc_list = vis_annotation(query, results.docs)
        request.session['doc_list'] = doc_list

        # 'COMPOUND', 'GENE', 'BIOLOGICAL_PROCESS', 'PHENOTYPE', 'ORGAN', 'CELL', 'TISSUE', 'MOLECULAR_FUNCTION'
        if doc_list != None:
            return render(request, 'annotation.html', {
                'result': True,
                'doc_list': json.dumps(doc_list),
                'GENE': True,
                'COMPOUND': True,
                'PHENOTYPE': True,
                'BIOLOGICAL_PROCESS': True,
                'MOLECULAR_FUNCTION': True,
                'TISSUE': True,
                'ORGAN': True,
                'CELL': True,
                'HERB': True,
            })
        else:
            return render(request, 'annotation.html', {
                'result': False,
            })

    elif search_type == 'keyword':
        qs = solr.search(q='sentence:{}'.format(query), rows=100).docs
        documents = []
        pmid_list = list(set([q['pmid'][0] for q in qs]))

        for pmid in pmid_list:
            documents.extend(DocumentInfo.objects.filter(pm_id=pmid))

        p = Paginator(documents, 5)
        page_numbers_range = 5
        max_index = p.num_pages

        page = request.GET.get('page')
        current_page = int(page) if page else 1

        start_index = int((current_page - 1) / page_numbers_range) * page_numbers_range
        end_index = start_index + page_numbers_range

        if end_index >= max_index:
            end_index = max_index

        page_range = p.page_range[start_index:end_index]
        prev_index = start_index if (start_index - 1) > 1 else 1
        next_index = end_index + 1 if (end_index + 1) < max_index else max_index

        try:
            list_ = p.page(current_page)

        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            list_ = p.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            list_ = p.page(p.num_pages)

        return render(request, 'search.html', {
            'page_range': page_range,
            'prev_index': prev_index,
            'next_index': next_index,
            'doc_list': list_,
            'query': query,
        })


def vis_annotation(pmid, results_dict):
    docs = results_dict
    if len(docs) > 0:
        sentences = [sent['sentence'][0] for sent in docs]
        sentences = [re.sub('(rsquo;)|(rdquo;)|(&)|(\?)', '', sent).replace('\(\(', '\(').replace('\)\)', '\)').strip()
                     for sent in sentences]
        sentences = [re.sub('[\s]+', ' ', sent) for sent in sentences]
        # sentences = [re.sub('[^A-Za-z0-9-.,\(\)\'\"]', '', sent).replace('\(\(', '\(').replace('\)\)', '\)').strip() for sent in sentences]
        abstract = "\n".join(sentences)
        
        denotations = []
        relation_list = []
        for sent_info in docs:
            entities = Entity.objects.filter(sent=sent_info['sent_id'][0]).order_by('sent_id', 'span_begin')
            
            for e in entities:
                sent_id = int(str(e.sent_id).split(str(pmid))[-1])
                words = sentences[sent_id].split(' ')

                if sent_id == 0:
                    sent_start = 0
                    if e.span_begin == 0:
                        start = sent_start
                    else:
                        start = sent_start + len(' '.join(words[:e.span_begin])) + 1

                    end = sent_start + len(' '.join(words[:e.span_end + 1]))

                else:
                    sent_start = len(' '.join([sentences[sent_id] for sent_id in range(sent_id)])) + 1

                    if e.span_begin == 0:
                        start = sent_start
                    else:
                        start = sent_start + len(' '.join(words[:e.span_begin])) + 1

                    end = sent_start + len(' '.join(words[:e.span_end + 1]))

                for idx in range(start, end + 1):
                    if re.search('[\[\]\{\}\(\)\"\'.,:;]', abstract[idx]):
                        start += 1
                    else:
                        break
                for idx in range(end - 1, start, -1):
                    if re.search('[\[\]\{\}\(\)\"\'.,:;]', abstract[idx]):
                        end -= 1
                    else:
                        break

                span = dict()
                span['begin'] = start
                span['end'] = end

                denotations.append({'id': e.entity_id, 'span': span, 'obj': e.entity_type})

            relations = Relation.objects.filter(sent=sent_info['sent_id'][0]).order_by('sent_id')

            for idx, r in enumerate(relations):
                relation_list.append({'id': r.relation_id, 'subj': r.entity1_id, 'pred': r.relation_type,
                                      'obj': re.sub('[\n\r]', '', r.entity2_id)})

        qs = {'text': abstract.replace('\n', ' '), 'denotations': denotations, 'relations': relation_list}
        return qs

    else:
        return None

def filter_entities(request):
    entity_type = request.GET.getlist('entityType')
    entity_bool = dict()

    for e in ['GENE', 'COMPOUND', 'PHENOTYPE', 'BIOLOGICAL_PROCESS', 'MOLECULAR_FUNCTION', 'TISSUE', 'ORGAN', 'CELL',
              'HERB']:
        if e in entity_type:
            entity_bool[e] = True
        else:
            entity_bool[e] = False
    
    pmid = request.session.get('pmid')
    abstract = request.session.get('doc_list')['text']
    denotations = request.session.get('doc_list')['denotations']
    relations = request.session.get('doc_list')['relations']

    entity_list = []
    entity_id_list = []
    relation_list = []
    for entity in denotations:
        if entity['obj'] in entity_type:
            entity_list.append(entity)
            entity_id_list.append(entity['id'])
    for relation in relations:
        if (relation['subj'] in entity_id_list) and (relation['obj'] in entity_id_list):
            relation_list.append(relation)

    doc_list = {'text': abstract, 'denotations': entity_list, 'relations': relation_list}

    return render(request, 'annotation.html', {
        'result': True,
        'doc_list': json.dumps(doc_list),
        'GENE': entity_bool['GENE'],
        'COMPOUND': entity_bool['COMPOUND'],
        'PHENOTYPE': entity_bool['PHENOTYPE'],
        'BIOLOGICAL_PROCESS': entity_bool['BIOLOGICAL_PROCESS'],
        'MOLECULAR_FUNCTION': entity_bool['MOLECULAR_FUNCTION'],
        'TISSUE': entity_bool['TISSUE'],
        'ORGAN': entity_bool['ORGAN'],
        'CELL': entity_bool['CELL'],
        'HERB': entity_bool['HERB'],
    })