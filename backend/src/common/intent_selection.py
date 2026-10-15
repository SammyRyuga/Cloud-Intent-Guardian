"""Reuse the bounded approved-intent selection for graph and evaluation."""
from common.contracts import scan_all
from common.auth import configured_scope


class IntentSelectionError(ValueError):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def approved_intent(table, intent_id=None, version=None, versions_table=None):
    if intent_id:
        item = table.get_item(Key={'intentId': intent_id}, ConsistentRead=True).get('Item')
        if not item:
            raise IntentSelectionError(404, 'INTENT_NOT_FOUND', 'The requested intent does not exist.')
    else:
        candidates, incomplete = scan_all(table)
        if incomplete:
            raise IntentSelectionError(409, 'INTENT_SELECTION_INCOMPLETE', 'Specify an approved intentId; default selection exceeded its scan bound.')
        candidates = [row for row in candidates if row.get('status') == 'APPROVED' and row.get('scopeKey') == configured_scope()]
        candidates.sort(key=lambda row: row.get('updatedAt', ''), reverse=True)
        item = candidates[0] if candidates else None
        if not item:
            raise IntentSelectionError(409, 'NO_APPROVED_INTENT', 'Create and approve an intent before comparing observations.')
    if not item.get('scopeKey'):
        raise IntentSelectionError(409, 'INTENT_MIGRATION_REQUIRED', 'Backfill this legacy intent before comparison.')
    if item['scopeKey'] != configured_scope():
        raise IntentSelectionError(404, 'INTENT_NOT_FOUND', 'The requested intent does not exist in this scope.')
    if item.get('status') != 'APPROVED':
        raise IntentSelectionError(409, 'INTENT_NOT_APPROVED', 'Only an approved intent can be evaluated.')
    if version is not None:
        try:
            valid = str(int(version)) == str(version) and int(version) >= 1
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise IntentSelectionError(400, 'INVALID_VERSION', 'version must be a positive integer.')
        if versions_table is None:
            raise IntentSelectionError(409, 'VERSIONING_NOT_CONFIGURED', 'Intent version storage is not configured.')
        snapshot = versions_table.get_item(Key={'intentId': item['intentId'], 'version': int(version)}, ConsistentRead=True).get('Item')
        if not snapshot or snapshot.get('scopeKey') != configured_scope():
            raise IntentSelectionError(404, 'INTENT_VERSION_NOT_FOUND', 'The requested intent version does not exist.')
        if snapshot.get('status') != 'APPROVED':
            raise IntentSelectionError(409, 'INTENT_NOT_APPROVED', 'Only approved snapshots can be compared.')
        return snapshot
    return item
