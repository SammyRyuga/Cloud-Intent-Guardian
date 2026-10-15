"""Select observations without allowing local requests to contact AWS."""
import os

from common.contracts import is_local


class ObservationUnavailable(ValueError):
    pass


def observations(collector, region=None):
    provider = os.environ.get('INVENTORY_PROVIDER', 'aws')
    if provider == 'fixture' and is_local():
        from common.scenarios import scenario_inventory
        try:
            return scenario_inventory(os.environ.get('CIG_FIXTURE_SCENARIO', 'benign'))
        except ValueError as exc:
            raise ObservationUnavailable(str(exc)) from exc
    if is_local():
        raise ObservationUnavailable('Live AWS inventory is disabled in local API mode. Configure the local fixture provider for simulated evaluation.')
    if provider != 'aws':
        raise ObservationUnavailable('Fixture inventory is available only in local execution.')
    return collector(region)
