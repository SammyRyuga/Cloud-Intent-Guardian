"""Historical labels require exact version/scope/coverage-bound snapshot facts."""
import copy,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common.candidate_history import candidate_history,prepare_history
from common.drift import changes

EDGE={'sourceId':'worker','targetId':'database','type':'NETWORK_REACHABILITY','observationKind':'OBSERVED','protocol':'tcp','ports':[5432]}
def inventory(edges):
    return {'items':[{'resourceId':'worker','resourceType':'AWS::Lambda::Function'}],'edges':edges,'meta':{'accountId':'123456789012','region':'ap-south-1','coverage':{'resourceTypes':{'AWS::Lambda::Function':'COMPLETE'},'relationshipTypes':{'NETWORK_REACHABILITY':'COMPLETE'}}}}
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.job={'intentId':'intent','intentVersion':2,'scopeKey':'scope','evaluationId':'new'}
        self.after=inventory([EDGE]);self.before=inventory([])
        self.candidate={'pathEdges':[EDGE],'sourceId':'worker','targetId':'database'}
        self.context={'status':'COMPARABLE','reason':'complete','previousEvaluationId':'old','previous':self.before,
                      'events':changes(self.before,self.after,self.job,'now','old')}
    def test_first_observation_is_not_a_change(self):
        result=candidate_history(self.candidate,self.after,{'status':'FIRST_OBSERVATION','reason':'no prior'})
        self.assertEqual(result['status'],'FIRST_OBSERVATION');self.assertFalse(result['isHistoricalChange']);self.assertEqual(result['driftEventIds'],[])
    def test_new_edge_links_only_exact_factual_event(self):
        result=candidate_history(self.candidate,self.after,self.context)
        self.assertEqual(result['status'],'NEW');self.assertTrue(result['isHistoricalChange'])
        self.assertEqual(result['driftEventIds'],[self.context['events'][0]['id']])
        bad=copy.deepcopy(self.context);bad['events'][0]['currentState']['sourceId']='other'
        self.assertEqual(candidate_history(self.candidate,self.after,bad)['driftEventIds'],[])
    def test_previously_observed_and_partial_coverage(self):
        self.context['previous']=self.after
        self.assertEqual(candidate_history(self.candidate,self.after,self.context)['status'],'PREVIOUSLY_OBSERVED')
        partial=copy.deepcopy(self.after);partial['meta']['coverage']['relationshipTypes']['NETWORK_REACHABILITY']='PARTIAL'
        self.assertEqual(candidate_history(self.candidate,partial,self.context)['status'],'UNKNOWN')
    def test_changed_protocol_port_binding_links_modified_event(self):
        self.before=inventory([{**EDGE,'ports':[443]}])
        self.context.update(previous=self.before,events=changes(self.before,self.after,self.job,'now','old'))
        result=candidate_history(self.candidate,self.after,self.context)
        self.assertEqual(result['status'],'NEW')
        self.assertEqual(result['driftEventIds'],[self.context['events'][0]['id']])
        self.assertEqual(self.context['events'][0]['eventType'],'MODIFIED')

    def test_prepare_scope_pin_and_gap(self):
        holder={'driftBaseline':{'intentVersion':2,'scopeKey':'scope','evaluationId':'old'}}
        class Table:
            def get_item(self,**kwargs):return {'Item':holder}
        class DB:
            def Table(self,*args):return Table()
        evaluation={'status':'SUCCEEDED','intentId':'intent','intentVersion':2}
        env={'DRIFT_HISTORY_ENABLED':'true','INTENTS_TABLE':'intents','EVALUATION_ARTIFACTS_TABLE':'artifacts'}
        with patch.dict(os.environ,env):
            result=prepare_history(DB(),self.job,evaluation,self.after,lambda *a:(evaluation,self.before,[]))
            self.assertEqual(result['status'],'COMPARABLE')
            bad={**evaluation,'intentVersion':1}
            self.assertEqual(prepare_history(DB(),self.job,evaluation,self.after,lambda *a:(bad,self.before,[]))['reason'],'PREVIOUS_ARTIFACT_PIN_MISMATCH')
            self.assertEqual(prepare_history(DB(),self.job,evaluation,self.after,lambda *a:None)['status'],'UNKNOWN')
            holder.clear()
            self.assertEqual(prepare_history(DB(),self.job,evaluation,self.after,lambda *a:None)['status'],'FIRST_OBSERVATION')
    def test_latest_artifact_without_matching_drift_baseline_cannot_invent_event_ids(self):
        evaluation={'status':'SUCCEEDED','intentId':'intent','intentVersion':2,'scopeKey':'scope'}
        class Table:
            def __init__(self,name):self.name=name
            def get_item(self,**kwargs):return {'Item':{'latestEvaluationId':'old'} if self.name=='intents' else evaluation}
        class DB:
            def Table(self,name):return Table(name)
        with patch.dict(os.environ,{'DRIFT_HISTORY_ENABLED':'true','INTENTS_TABLE':'intents','EVALUATIONS_TABLE':'jobs','EVALUATION_ARTIFACTS_TABLE':'artifacts'}):
            context=prepare_history(DB(),self.job,evaluation,self.after,lambda *a:(evaluation,self.before,[]))
        self.assertEqual(context['status'],'COMPARABLE')
        result=candidate_history(self.candidate,self.after,context)
        self.assertEqual(result['status'],'NEW')
        self.assertEqual(result['driftEventIds'],[])

    def test_diagnostic_dispatch_cannot_touch_database(self):
        import evaluation_worker.app as worker
        with patch('common.runtime_verification.verify_bedrock_runtime',return_value={'status':'INVALID_REQUEST'}) as diagnostic,patch.object(worker,'dynamodb_resource',side_effect=AssertionError('db touched')):
            event={'diagnostic':'BEDROCK_SYNTHETIC','jobId':'must-not-run'}
            self.assertEqual(worker.lambda_handler(event,None),{'status':'INVALID_REQUEST'})
            diagnostic.assert_called_once_with(event)
