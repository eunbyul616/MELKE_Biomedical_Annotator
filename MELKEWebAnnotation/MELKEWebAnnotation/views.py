from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json
import glob
import pandas as pd
import os
import pymysql
from .search_change import wordCound, senNum, wordNum
import re
from annotation.models import DocumentInfo, SentenceInfo, Entity, Relation
from .settings import DATABASES_HOST, DATABASES_NAME, DATABASES_USER, DATABASES_PASSWORD

class SessionDataframe:
    def __init__(self, df):
        self.data = df

@login_required
def modify_data(request):
    file_list = [file.replace('\\', '/').split('/')[-1] for file in glob.glob('MELKEWebAnnotation/files/*.json')]

    return render(request, 'upload_file.html', {
        'file_list': file_list,
    })

@login_required
def select_file(request):
    selected_file = request.GET.get('selected_file')
    pmid = request.GET.get('pm_id').strip()
    request.session['pmid'] = pmid

    with open(os.path.join('MELKEWebAnnotation/files/', selected_file), "r") as f:
        json_data = json.load(f)

    try:
        conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
        curs = conn.cursor()

        sql = "select * from relation order by relation_id"
        curs.execute(sql)
        data = curs.fetchall()
        relation_id = int(data[-1][1]) + 1

    except Exception as e:
        relation_id = 1

    conn.close()

    sen = []
    senCharLen = []
    entity_id_dict = {}

    entity_df = pd.DataFrame(
        columns=['sent_id', 'entity_id', 'entity_name', 'entity_type', 'span_begin', 'span_end', 'modify_type'])
    relation_df = pd.DataFrame(
        columns=['sent_id', 'relation_id', 'relation_type', 'entity1_id', 'entity2_id', 'modify_type'])

    p1 = re.compile('(T[0-9]+)|(R[0-9]+)')

    text = json_data['text'].split('\n')
    sentences = [s.sentence for s in SentenceInfo.objects.filter(pm_id=pmid).order_by('sent_id')]
    sentences = [re.sub('(rsquo;)|(rdquo;)|(&)|(\?)', '', sent).replace('\(\(', '\(').replace('\)\)', '\)').strip() for
                 sent in sentences]

    conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
    curs = conn.cursor()
    sql = "select * from sentence_info right join entity ON sentence_info.sent_id = entity.sent_id " \
          "where sentence_info.pm_id='{}'".format(pmid)
    curs.execute(sql)
    entities = curs.fetchall()

    json_entity_id = [d['id'] for d in json_data['denotations']]
    for entity in entities:
        if entity[3] not in json_entity_id:
            entity_df = entity_df.append(pd.DataFrame(
                [[entity[0], entity[3], entity[4], entity[5], entity[6], entity[7], 'delete']],
                columns=['sent_id', 'entity_id', 'entity_name', 'entity_type', 'span_begin', 'span_end', 'modify_type']),
                ignore_index=True)

    sql = "select * from sentence_info right join relation ON sentence_info.sent_id = relation.sent_id " \
          "where sentence_info.pm_id='{}';".format(pmid)

    curs.execute(sql)
    relations = curs.fetchall()
    conn.close()

    json_relation_id = [d['id'] for d in json_data['relations']]

    for relation in relations:
        if str(relation[4]) not in json_relation_id:
            relation_df = relation_df.append(
                pd.DataFrame([[relation[0], relation[4], relation[5], relation[6], relation[7], 'delete']],
                             columns=['sent_id', 'relation_id', 'relation_type', 'entity1_id',
                                      'entity2_id', 'modify_type']),
                ignore_index=True)

    for i in range(len(text)):
        temp = wordCound(text[i])
        sen.append(temp[0])
        senCharLen.append(temp[1])

    for i in range(len(json_data['denotations'])):
        if p1.match(json_data['denotations'][i]['id']):
            begin = int(json_data['denotations'][i]['span']['begin'])
            end = int(json_data['denotations'][i]['span']['end'])

            word = json_data['text'][begin:end]
            num, b, e = senNum(sen, senCharLen, begin, end)
            wnum = wordNum(sen[num], num, b, e, word)

            try:
                conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
                curs = conn.cursor()
                sql = "select * from entity where sent_id = {};".format(int(pmid + str(num+1)))
                curs.execute(sql)
                data = curs.fetchall()
                entity_id = pmid + '_' + str(num) + '_' + 'T'+str(len(data))

            except Exception as e:
                entity_id = pmid + '_' + str(num) + '_' + 'T0'

            conn.close()

            entity_id_dict[json_data['denotations'][i]['id']] = entity_id

            entity_df = entity_df.append(pd.DataFrame(
                [[pmid + str(num), str(entity_id), word, json_data['denotations'][i]['obj'], wnum[0], wnum[1], 'add']],
                columns=['sent_id', 'entity_id', 'entity_name', 'entity_type', 'span_begin', 'span_end', 'modify_type']),
                                         ignore_index=True)
        else:
            conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
            curs = conn.cursor()
            sql = "select * from entity where entity_id = '" + json_data['denotations'][i]['id'] + "';"
            curs.execute(sql)
            data = curs.fetchall()
            conn.close()

            try:
                if json_data['denotations'][i]['obj'] != data[0][2]:
                    entity_df = entity_df.append(pd.DataFrame(
                        [[data[0][5], data[0][0], data[0][1], json_data['denotations'][i]['obj'], data[0][3], data[0][4], 'add']],
                        columns=['sent_id', 'entity_id', 'entity_name', 'entity_type', 'span_begin', 'span_end', 'modify_type']),
                        ignore_index=True)
            except Exception:
                pass

    for i in range(len(json_data['relations'])):
        if p1.match(json_data['relations'][i]['id']):
            for j in range(len(json_data['denotations'])):
                if json_data['denotations'][j]['id'] == json_data['relations'][i]['obj']:
                    begin = int(json_data['denotations'][j]['span']['begin'])
                    end = int(json_data['denotations'][j]['span']['end'])
                    num, b, e = senNum(sen, senCharLen, begin, end)

                    if p1.match(json_data['relations'][i]['obj']):
                        obj = str(entity_id_dict[json_data['relations'][i]['obj']])
                    else:
                        obj = json_data['relations'][i]['obj']

                    if p1.match(json_data['relations'][i]['subj']):
                        subj = str(entity_id_dict[json_data['relations'][i]['subj']])
                    else:
                        subj = json_data['relations'][i]['subj']

                    relation_df = relation_df.append(
                        pd.DataFrame([[pmid + str(num), str(relation_id), json_data['relations'][i]['pred'], obj, subj, 'add']],
                                     columns=['sent_id', 'relation_id', 'relation_type', 'entity1_id', 'entity2_id', 'modify_type']),
                        ignore_index=True)
            relation_id += 1

        else:
            conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
            curs = conn.cursor()
            sql ="select * from sentence_info right join relation " \
                 "ON sentence_info.sent_id = relation.sent_id where sentence_info.pm_id='{}' and relation.relation_id={};".format(pmid, json_data['relations'][i]['id'])
            curs.execute(sql)
            data = curs.fetchall()
            conn.close()

            try:
                if json_data['relations'][i]['pred'] != data[0][5]:
                    relation_df = relation_df.append(
                        pd.DataFrame([[data[0][0], data[0][4], json_data['relations'][i]['pred'],
                                       json_data['relations'][i]['obj'], json_data['relations'][i]['subj'], 'add']],
                                     columns=['sent_id', 'relation_id', 'relation_type', 'entity1_id',
                                              'entity2_id', 'modify_type']),
                                    ignore_index=True)
            except Exception:
                pass

    entity_df.to_csv('MELKEWebAnnotation/files/entity_df.csv', index=False)
    relation_df.to_csv('MELKEWebAnnotation/files/relation_df.csv',  index=False)

    file_list = [file.replace('\\', '/').split('/')[-1] for file in glob.glob('MELKEWebAnnotation/files/*.json')]

    return render(request, 'upload_file.html', {
        'pmid': pmid,
        'file_list': file_list,
        'entities': entity_df.values.tolist(),
        'relations': relation_df.values.tolist(),
    })

@login_required
def save_data(request):
    entity = request.POST.getlist('entity')
    relation = request.POST.getlist('relation')
    pmid = request.session.get('pmid')

    entity_df = pd.read_csv('MELKEWebAnnotation/files/entity_df.csv')
    relation_df = pd.read_csv('MELKEWebAnnotation/files/relation_df.csv')

    entity = [int(i) for i in entity]
    entity_df = entity_df.iloc[entity]
    relation = [int(i) for i in relation]
    relation_df = relation_df.iloc[relation]

    conn = pymysql.connect(host=DATABASES_HOST, user=DATABASES_USER, password=DATABASES_PASSWORD, db=DATABASES_NAME)
    curs = conn.cursor()

    sql = "select * from sentence_info right join entity ON sentence_info.sent_id = entity.sent_id " \
          "where sentence_info.pm_id='{}'".format(pmid)
    curs.execute(sql)
    edata = [row[3] for row in curs.fetchall()]

    # delete entity
    for i in range(entity_df.shape[0]):
        if entity_df['modify_type'].iloc[i] == 'delete':
            delete_entities = Entity.objects.get(entity_id=entity_df['entity_id'].iloc[i])
            delete_entities.delete()

    for i in entity:
        # update exist data
        if str(entity_df['entity_id'].iloc[i]) in edata:
            print('update')
            sql = '''UPDATE entity SET sent_id='{}', entity_name='{}', entity_type='{}',
            span_begin={}, span_end={}  WHERE entity_id='{}';'''.format(entity_df['sent_id'].iloc[i],
                                                                          entity_df['entity_name'].iloc[i],
                                                                          entity_df['entity_type'].iloc[i],
                                                                          entity_df['span_begin'].iloc[i],
                                                                          entity_df['span_end'].iloc[i],
                                                                          entity_df['entity_id'].iloc[i]
                                                                        )
            curs.execute(sql)

        # insert new data
        else:
            print('insert')
            sql = '''INSERT into entity(sent_id, entity_id, entity_name, entity_type, span_begin, span_end)
            values ('{}', '{}', '{}', '{}', {},{});'''.format(
                                                        entity_df['sent_id'].iloc[i],
                                                        entity_df['entity_id'].iloc[i],
                                                        entity_df['entity_name'].iloc[i],
                                                        entity_df['entity_type'].iloc[i],
                                                        entity_df['span_begin'].iloc[i],
                                                        entity_df['span_end'].iloc[i],
                                                        )
            curs.execute(sql)

    sql = "select * from sentence_info right join relation ON sentence_info.sent_id = relation.sent_id " \
          "where pm_id = '{}';".format(pmid)
    curs.execute(sql)
    rdata = [row[4] for row in curs.fetchall()]

    # delete relation
    for i in range(relation_df.shape[0]):
        if relation_df['modify_type'].iloc[i] == 'delete':
            delete_relations = Relation.objects.get(relation_id=relation_df['relation_id'].iloc[i])
            delete_relations.delete()

    for i in relation:
        if relation_df['relation_id'].iloc[i] not in rdata:
            sql = '''INSERT into relation(sent_id, relation_id, relation_type, entity1_id, entity2_id)
            values ('{}', {}, '{}', '{}', '{}')'''.format(
                relation_df['sent_id'].iloc[i],
                relation_df['relation_id'].iloc[i],
                relation_df['relation_type'].iloc[i],
                relation_df['entity1_id'].iloc[i],
                relation_df['entity2_id'].iloc[i],
            )

            curs.execute(sql)
        else:
            sql = '''UPDATE relation SET sent_id='{}', relation_type='{}', entity1_id='{}',
                        entity2_id='{}' WHERE relation_id={};'''.format(
                relation_df['sent_id'].iloc[i],
                relation_df['relation_type'].iloc[i],
                relation_df['entity1_id'].iloc[i],
                relation_df['entity2_id'].iloc[i],
                relation_df['relation_id'].iloc[i]
                )
            curs.execute(sql)

    conn.commit()
    conn.close()

    file_list = [file.replace('\\', '/').split('/')[-1] for file in glob.glob('MELKEWebAnnotation/files/*.json')]

    return render(request, 'upload_file.html', {
        'file_list': file_list,
        'entities': entity_df.values.tolist(),
        'relations': relation_df.values.tolist(),
        'save': True
    })