"""Loopback DynamoDB Local worker history journey; simulated observations only."""
import os,sys,json,importlib
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common.dynamodb import dynamodb_resource
from common.scenarios import scenario_inventory,scenario_manifest
from common.http import _json_default
from local_db import TABLES,check_tables
from verify_topology import decoded


def verify(db):
    intents,approve,evaluations,worker=[importlib.import_module(n+'.app') for n in ('intents','approve_intent','evaluations','evaluation_worker')]
    created=decoded(intents.lambda_handler({'requestContext':{'http':{'method':'POST'}},'body':json.dumps(scenario_manifest())},None),201)['item']
    key={'intentId':created['intentId']}
    decoded(approve.lambda_handler({'pathParameters':key},None))
    rows=[]
    def run(name,source):
        queued=decoded(evaluations.lambda_handler({'body':json.dumps(key)},None),202)['evaluation']
        eid=queued['evaluationId']
        with patch.object(worker,'observations',return_value=deepcopy(source)),patch.object(worker,'collect_inventory',side_effect=AssertionError('AWS forbidden')):
            worker._process(db,eid)
        result,inventory,findings=worker._load_complete_artifacts(db,os.environ['EVALUATION_ARTIFACTS_TABLE'],eid)
        histories=[f['history'] for f in findings if f.get('tier')=='TIER_2']
        rows.append({'name':name,'evaluationId':eid,'histories':histories})
        return eid,histories
    first,hist=run('first-unruled',scenario_inventory('unruled-crossing'))
    assert hist and all(h['status']=='FIRST_OBSERVATION' and not h['isHistoricalChange'] and not h['driftEventIds'] for h in hist),hist
    second,hist=run('same-unruled',scenario_inventory('unruled-crossing'))
    assert hist and all(h['status']=='PREVIOUSLY_OBSERVED' and h['previousEvaluationId']==first for h in hist),hist
    run('complete-benign',scenario_inventory('benign'))
    fourth,hist=run('new-unruled',scenario_inventory('unruled-crossing'))
    assert hist and all(h['status']=='NEW' and h['isHistoricalChange'] for h in hist),hist
    events=[row for row in db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items'] if row.get('evaluationId')==fourth]
    assert events and all(h['driftEventIds'] for h in hist),hist
    for history in hist:
        assert set(history['driftEventIds']) <= {row['id'] for row in events},history
        for event in events:
            if event['id'] in history['driftEventIds']:
                assert event['entityKind']=='EDGE' and event['currentState']['sourceId']=='fixture-db' and event['currentState']['targetId']=='i-fixture-web'
    partial=deepcopy(scenario_inventory('unruled-crossing'));partial['meta']['partial']=True
    _,hist=run('partial-source-gap',partial)
    assert hist and all(h['status']=='UNKNOWN' and not h['driftEventIds'] for h in hist),hist

    # Persisted advisory history never becomes executable authorization.
    persisted=db.Table(os.environ['FINDINGS_TABLE']).scan()['Items']
    assert all(f.get('actionEligible') is False for f in persisted if f.get('tier')=='TIER_2')
    ssh= scenario_inventory('open-ssh')
    impact={'coverage':'PARTIAL','sourceCoverage':{'AWS::EC2::NetworkInterface':'PARTIAL'},'knownAttachmentCount':1,'attachmentCount':None,
            'attachments':[{'resourceId':'i-fixture-web','resourceType':'AWS::EC2::Instance','source':'SIMULATED'}],
            'observedAt':ssh['meta']['collectedAt'],'requiresHumanApproval':True,'interpretation':'Simulated configuration attachment record; no traffic or outage proof.'}
    next(r for r in ssh['items'] if r['resourceType']=='AWS::EC2::SecurityGroup')['attributes']['attachmentImpact']=impact
    ssh_id,_=run('open-ssh-attachment-impact',ssh)
    finding=next(f for f in db.Table(os.environ['FINDINGS_TABLE']).scan()['Items'] if f.get('evaluationId')==ssh_id and f.get('ruleId')=='SECURITY_GROUP_NO_OPEN_SSH')
    remediation=importlib.import_module('remediations.app')
    proposal=decoded(remediation.lambda_handler({'requestContext':{'http':{'method':'POST'}},'rawPath':'/v1/remediations','body':json.dumps({'findingId':finding['findingId'],'actionId':'REMOVE_OPEN_SSH'})},None),201)['item']
    stored=db.Table(os.environ['REMEDIATIONS_TABLE']).get_item(Key={'proposalId':proposal['proposalId']},ConsistentRead=True)['Item']
    assert stored['approvalRequired'] is True and stored['plan']['attachmentImpact']==impact
    assert stored['status']=='PROPOSED',stored['status']
    return {'attachmentProposalPersisted':True,'proposalId':proposal['proposalId'],'passed':True,'simulated':True,'intentId':key['intentId'],'runs':rows,'scope':'DynamoDB Local immutable worker artifacts and findings; no AWS observations or mutations'}


def main():
    os.environ.update(CIG_LOCAL='true',DYNAMODB_ENDPOINT_URL='http://127.0.0.1:18000',AWS_REGION='ap-south-1',INVENTORY_PROVIDER='fixture',CIG_FIXTURE_SCENARIO='unruled-crossing',DRIFT_HISTORY_ENABLED='true',LLM_ENABLED='true',LLM_PROVIDER='mock')
    for key,(default,_) in TABLES.items():os.environ.setdefault(key,default)
    db=dynamodb_resource();check_tables(db,False)
    result=verify(db)
    path=Path(__file__).resolve().parents[1]/'local-evidence/candidate-history-verification.json'
    path.write_text(json.dumps(result,indent=2,default=_json_default))
    print(json.dumps({'passed':True,'runs':len(result['runs']),'evidence':str(path)}))
if __name__=='__main__':main()
