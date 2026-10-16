import { env } from '@/config/env';
import { useCapability } from '@/hooks/useCapability';
import { useState, useMemo, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  MarkerType,
  Controls,
  type Node,
  type Edge,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { useArchitectureGraph, useManifestIntents, useIntentVersions } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { CopyableId } from '@/components/common/CopyableId';
import { formatDiffState } from '@/utils/severity';
import { formatResourceType } from '@/utils/format';
import type { GraphNode, DiffState, GraphView } from '@/types/domain';
import { GraphViewSchema } from '@/api/schemas';
import { AlertCircle, Search, Network, Database, Cpu, Shield, Box, X } from 'lucide-react';

// Custom Node Component per AGENTS.md §5.5
function ArchitectureNode({ data }: { data: GraphNode }) {
  const category = /DynamoDB|RDS|S3/.test(data.resourceType) ? 'data' : /IAM|Cognito/.test(data.resourceType) ? 'identity' : /Lambda|Instance/.test(data.resourceType) ? 'compute' : /ApiGateway|EC2::VPC|Subnet|SecurityGroup/.test(data.resourceType) ? 'network' : 'other';
  const frame = { compute: 'M12 1H229V77L217 89H1V13Z', network: 'M14 1H216L229 45L216 89H14L1 45Z', data: 'M1 1H229V79H1Z', identity: 'M28 1H202Q229 1 229 28V62Q229 89 202 89H28Q1 89 1 62V28Q1 1 28 1Z', other: 'M1 1H229V89H1Z' }[category];
  const stateColor = data.diffState === 'CHANGED' ? `var(--color-sev-${(data.severity ?? 'HIGH').toLowerCase()})` : data.diffState === 'ADDED' ? 'var(--color-sev-medium)' : data.diffState === 'MISSING' ? 'var(--color-ink)' : ['UNKNOWN', 'UNEXPECTED'].includes(data.diffState) ? 'var(--color-graphite)' : 'var(--color-rule-strong)';
  const dash = data.diffState === 'MISSING' ? '6 4' : data.diffState === 'UNKNOWN' ? '2 3' : undefined;
  const ResourceIcon = /DynamoDB|RDS|S3/.test(data.resourceType) ? Database : /IAM|Cognito/.test(data.resourceType) ? Shield : /Lambda|Instance/.test(data.resourceType) ? Cpu : /ApiGateway|EC2::VPC|Subnet|SecurityGroup/.test(data.resourceType) ? Network : Box;
  return (
    <div className={`relative px-5 py-3 shadow-none w-[230px] min-h-[90px] ${data.highlighted ? 'ring-2 ring-prussian ring-offset-4' : ''}`}>
      <svg className="absolute inset-0 w-full h-full pointer-events-none -z-1" viewBox="0 0 230 90" preserveAspectRatio="none" aria-hidden="true"><path d={frame} fill={data.diffState === 'UNKNOWN' ? 'var(--color-film)' : 'var(--color-sheet)'} stroke={stateColor} strokeWidth={data.diffState === 'MATCHED' ? 1 : 1.5} strokeDasharray={dash} vectorEffect="non-scaling-stroke" />{category === 'data' && <path d="M5 84H225M9 89H221" fill="none" stroke={stateColor} vectorEffect="non-scaling-stroke" />}</svg>
      {data.diffState === 'CHANGED' && <span className="absolute -top-2 -right-2 text-xs text-sev-high" aria-label="Changed revision">△</span>}
      <Handle type="target" position={Position.Left} className="!bg-graphite" />
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-xs text-graphite truncate">
          {formatResourceType(data.resourceType)}
        </span>
        {data.diffState !== 'MATCHED' && (
          <span className="text-xs font-medium font-sans px-1.5 py-0.5 rounded bg-film border border-rule">
            {formatDiffState(data.diffState)}
          </span>
        )}
      </div>

      <div className="text-sm font-semibold text-ink truncate flex items-center gap-2 mb-2" title={data.label}>
        <ResourceIcon className="w-4 h-4 shrink-0 stroke-[1.5]" />{data.label}
      </div>

      {data.severity && (
        <div className="pt-1.5 border-t border-rule flex items-center justify-between">
          <SeverityBadge severity={data.severity} compact />
          <span className="text-xs text-pencil">{data.findingCount !== undefined ? `${data.findingCount} findings` : 'Finding reported'}</span>
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-graphite" />
    </div>
  );
}

const nodeTypes = {
  archNode: ArchitectureNode,
};

const diffStateLegend: Array<{ state: DiffState; swatch: string }> = [
  { state: 'MATCHED', swatch: 'border-rule-strong bg-sheet' },
  { state: 'ADDED', swatch: 'border-2 border-sev-medium bg-sheet' },
  { state: 'MISSING', swatch: 'border-[1.5px] border-dashed border-ink bg-sheet' },
  { state: 'CHANGED', swatch: 'border-2 border-sev-critical bg-sheet' },
  { state: 'UNEXPECTED', swatch: 'border-2 border-graphite bg-sheet' },
  { state: 'UNKNOWN', swatch: 'border-[1.5px] border-dotted border-graphite bg-film' },
];

// Layout with Dagre
function getLayoutedElements(nodes: Node[], edges: Edge[]) {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: 'LR', ranksep: 110, nodesep: 32 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 230, height: 90 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 115,
        y: nodeWithPosition.y - 45,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export function ArchitectureExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedView = GraphViewSchema.safeParse(searchParams.get('view')).success
    ? searchParams.get('view') as GraphView
    : (env.useMocks ? 'DIFF' : 'ACTUAL');
  const currentView = requestedView;
  const intentId = searchParams.get('intentId') || undefined;
  const version = searchParams.get('version') || undefined;
  const componentId = searchParams.get('componentId') || '';
  const architectureEnabled = useCapability('architecture');
  const intents = useManifestIntents();
  const versions = useIntentVersions(intentId || '', undefined);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [resourceSearch, setResourceSearch] = useState('');
  const [surface, setSurface] = useState<'canvas' | 'list'>(() => window.matchMedia('(max-width: 767px)').matches ? 'list' : 'canvas');
  const drawerRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const inspectNode = (node: GraphNode) => { previousFocus.current = document.activeElement as HTMLElement; setSelectedNode(node); };
  const closeDetails = () => { setSelectedNode(null); previousFocus.current?.focus(); };
  useEffect(() => { if (selectedNode) drawerRef.current?.focus(); }, [selectedNode]);

  const { data: graphData, isLoading, isError, error, refetch } = useArchitectureGraph(currentView, { intentId, version });

  const { flowNodes, flowEdges } = useMemo(() => {
    if (!graphData) return { flowNodes: [], flowEdges: [] };

    const initialNodes: Node[] = graphData.nodes.map((n) => ({
      id: n.id,
      type: 'archNode',
      data: { ...n, highlighted: Boolean(componentId && (n.componentId === componentId || n.componentIds?.includes(componentId))) } as Record<string, unknown>,
      position: { x: 0, y: 0 },
    }));

    const initialEdges: Edge[] = graphData.edges.map((e) => {
      let strokeStyle = '#CBD5E1';
      let strokeDash = undefined;

      if (e.diffState === 'ADDED') strokeStyle = '#8A5A00';
      if (e.diffState === 'CHANGED') strokeStyle = '#B42318';
      if (e.diffState === 'UNEXPECTED') {
        strokeStyle = '#5A677B';
        strokeDash = '6,3';
      }
      if (e.diffState === 'MISSING') {
        strokeStyle = '#172033';
        strokeDash = '5,5';
      }
      if (e.diffState === 'UNKNOWN') {
        strokeStyle = '#5A677B';
        strokeDash = '2,2';
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: ({ NETWORK_REACHABILITY: 'Network reachability', NETWORK_PERMISSION: 'Network permission', DYNAMODB_STREAM_TRIGGER: 'Stream trigger', API_ROUTE: 'API route', API_INTEGRATION: 'API integration', JWT_AUTHORIZER: 'JWT authorizer', JWT_ISSUER: 'JWT issuer', ASSUMES_ROLE: 'Assumes role', IAM_DECLARED_PERMISSION: 'Declared permission', IN_SUBNET: 'In subnet', BELONGS_TO_VPC: 'Belongs to VPC', USES_SECURITY_GROUP: 'Uses security group', IN_VPC: 'In VPC' } as Record<string, string>)[e.relationshipType] ?? e.relationshipType,
        ariaLabel: e.relationshipType,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
        labelStyle: { fontSize: 12, fill: 'var(--color-graphite)' },
        labelBgStyle: { fill: 'var(--color-sheet)' },
        style: { stroke: strokeStyle, strokeDasharray: strokeDash, strokeWidth: 1.5 },
      };
    });

    const layouted = getLayoutedElements(initialNodes, initialEdges);
    return { flowNodes: layouted.nodes, flowEdges: layouted.edges };
  }, [graphData, componentId]);

  const presentedNodes = useMemo(() => flowNodes.map(node => {
    const matches = !resourceSearch || `${node.data.label} ${node.id} ${node.data.resourceType}`.toLowerCase().includes(resourceSearch.toLowerCase());
    return { ...node, data: { ...node.data, highlighted: Boolean(node.data.highlighted || (resourceSearch && matches)) }, style: { opacity: matches ? 1 : 0.4 } };
  }), [flowNodes, resourceSearch]);

  const handleViewChange = (v: GraphView) => {
    const next = new URLSearchParams(searchParams);
    next.set('view', v);
    setSearchParams(next);
  };
  const setSelectionParam = (key: 'intentId' | 'version' | 'componentId', value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    if (key === 'intentId') next.delete('version');
    setSearchParams(next);
  };
  const componentIds = Array.from(new Set((graphData?.nodes ?? []).flatMap((node) => [
    ...(node.componentId ? [node.componentId] : []), ...(node.componentIds ?? []),
  ]))).sort();

  return (
    <div className="architecture-workspace flex flex-col min-h-[720px] h-[calc(100dvh-8.5rem)] relative gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-title text-xl font-bold text-ink">Architecture Explorer</h1>
          <p className="text-xs text-graphite">
            Review declared intent against the observed resource relationships.
          </p>
        </div>

        {/* View Switcher */}
        <div className="inline-flex rounded-md border border-rule bg-sheet p-1 text-xs font-medium">
          {(architectureEnabled ? ['DIFF', 'INTENT', 'ACTUAL'] as const : ['ACTUAL'] as const).map((view) => (
            <button
              key={view}
              type="button"
              aria-pressed={currentView === view}
              onClick={() => handleViewChange(view)}
              className={`px-3 py-1 rounded transition-colors ${
                currentView === view ? 'bg-prussian text-white' : 'text-graphite hover:text-ink'
              }`}
            >
              {view} view
            </button>
          ))}
        </div>
      </div>

      {architectureEnabled && currentView !== 'ACTUAL' && <div className="flex flex-wrap gap-3 items-end pb-3">
        <label className="text-xs">Intent
          <select aria-label="Architecture intent" value={intentId ?? ''} onChange={(event) => setSelectionParam('intentId', event.target.value)} className="mt-1 block min-w-56 border border-rule rounded p-2 bg-sheet">
            <option value="">Choose intent</option>{intents.data?.items.map((item) => <option key={item.intentId} value={item.intentId}>{item.name} · {item.status}</option>)}
          </select>
        </label>
        <label className="text-xs">Immutable version
          <select aria-label="Architecture intent version" value={version ?? ''} onChange={(event) => setSelectionParam('version', event.target.value)} disabled={!intentId} className="mt-1 block min-w-40 border border-rule rounded p-2 bg-sheet disabled:opacity-50">
            <option value="">Active version</option>{versions.data?.items.map((item) => <option key={item.version} value={item.version}>{item.version} · {item.effectiveStatus ?? item.status}</option>)}
          </select>
        </label>
        <label className="text-xs">Highlight component
          <select aria-label="Highlight architecture component" value={componentId} onChange={(event) => setSelectionParam('componentId', event.target.value)} className="mt-1 block min-w-44 border border-rule rounded p-2 bg-sheet">
            <option value="">No highlight</option>{componentIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </label>
        {componentId && !componentIds.includes(componentId) && <p role="status" className="text-xs text-graphite">Selected component is not present in this server response.</p>}
      </div>}

      {graphData?.truncated && (
        <div className="mb-2 p-2 bg-sev-medium/10 border border-sev-medium/30 rounded text-xs text-sev-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>
            Graph view is truncated to {graphData.nodes.length} nodes (showing server-limited result set).
          </span>
        </div>
      )}

      {graphData?.partial && <p role="status" className="text-sm text-sev-medium">Inventory is partial: {graphData.warnings?.map(row => row.message).join('; ')}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 border border-rule-strong rounded-lg px-3 bg-sheet min-h-10 flex-1 max-w-md"><Search className="w-4 h-4 text-graphite stroke-[1.5]" /><input aria-label="Search loaded architecture resources" placeholder="Find a resource in this snapshot" className="min-w-0 w-full bg-transparent text-sm py-2" value={resourceSearch} onChange={event => setResourceSearch(event.target.value)} /></label>
        <div className="flex border border-rule rounded-lg bg-sheet p-1 gap-1" aria-label="Architecture presentation">
          {(['canvas', 'list'] as const).map(value => <button type="button" key={value} aria-pressed={surface === value} onClick={() => setSurface(value)} className={`px-3 py-1.5 rounded text-sm ${surface === value ? 'bg-prussian-tint text-prussian font-semibold' : 'text-graphite'}`}>{value === 'canvas' ? 'Canvas' : 'Resource list'}</button>)}
        </div>
      </div>
      <StateBoundary isNotEnabled={!architectureEnabled} isLoading={isLoading} isError={isError} error={error} onRetry={() => refetch()}>
        <div className="architecture-sheet flex-1 min-h-0 rounded-xl border border-rule-strong bg-sheet overflow-hidden relative flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-rule bg-sheet text-xs">
            <span><strong>{graphData?.nodes.length ?? 0}</strong> resources shown; <strong>{graphData?.edges.length ?? 0}</strong> relationships</span>
            <span className="text-graphite">{graphData?.intentVersion !== undefined ? `Intent version ${graphData.intentVersion}` : 'Observed inventory'}{graphData?.simulated ? ' / Simulated evidence' : ''}</span>
          </div>
          <div className="architecture-body flex flex-1 min-h-0">
            <aside aria-label="Snapshot resources" className={`${surface === 'canvas' ? 'hidden xl:block w-60 shrink-0 border-r border-rule' : 'w-full'} overflow-y-auto bg-sheet`}>
              <div className="p-4 border-b border-rule"><h2 className="text-sm font-semibold">Snapshot resources</h2><p className="mt-1 text-xs text-graphite">Select a resource to inspect its evidence.</p></div>
              <ul className="divide-y divide-rule">{graphData?.nodes.filter(node => `${node.label} ${node.id} ${node.resourceType}`.toLowerCase().includes(resourceSearch.toLowerCase())).map(node => <li key={node.id}><button type="button" aria-label={`Inspect resource ${node.label}`} className={`w-full px-4 py-3 text-left ${selectedNode?.id === node.id ? 'bg-prussian-tint' : 'hover:bg-film'}`} onClick={() => inspectNode(node)}><span className="block text-sm font-medium truncate">{node.label}</span><span className="block mt-1 text-xs text-graphite truncate">{formatResourceType(node.resourceType)}</span><span className="block mt-1 text-xs text-graphite">{formatDiffState(node.diffState)}</span></button></li>)}</ul>
              {graphData && !graphData.nodes.some(node => `${node.label} ${node.id} ${node.resourceType}`.toLowerCase().includes(resourceSearch.toLowerCase())) && <p className="p-4 text-sm text-graphite">No loaded resources match this search.</p>}
            </aside>
            {surface === 'canvas' && <div className="flex-1 min-w-0 relative bg-film">
              <ReactFlow nodes={presentedNodes} edges={flowEdges} nodeTypes={nodeTypes} onNodeClick={(_, node) => inspectNode(node.data as unknown as GraphNode)} fitView minZoom={0.1} maxZoom={2} onlyRenderVisibleElements>
                <Background variant={BackgroundVariant.Lines} color="var(--color-rule)" gap={24} />
                <Controls className="!bg-sheet !border-rule !shadow-none" />
              </ReactFlow>
              <details className="absolute bottom-4 right-4 max-w-[calc(100%-5rem)] bg-sheet border border-rule-strong rounded p-3 text-xs z-5">
                <summary className="cursor-pointer font-semibold">Drawing key</summary>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 mt-3" aria-label="Diff state legend">{diffStateLegend.map(({ state, swatch }) => <span key={state} className="inline-flex items-center gap-2 text-graphite"><span aria-hidden="true" className={`w-3 h-3 rounded-sm border ${swatch}`} />{formatDiffState(state)}</span>)}</div>
                {graphData?.asOf && <p className="mt-3 pt-2 border-t border-rule text-graphite">Observed {new Date(graphData.asOf).toLocaleString()}</p>}
              </details>
            </div>}
          </div>
          {/* Details Drawer per AGENTS.md §5.3 */}
          {selectedNode && (
            <div ref={drawerRef} tabIndex={-1} role="dialog" aria-label="Resource details" onKeyDown={event => { if (event.key === 'Escape') closeDetails(); }} className="absolute top-0 right-0 w-full sm:w-80 h-full bg-sheet border-l border-rule-strong p-5 shadow-none flex flex-col z-10">
              <div className="flex items-start justify-between pb-3 border-b border-rule">
                <div>
                  <h3 className="font-title text-sm font-semibold text-ink">{selectedNode.label}</h3>
                  <span className="text-xs font-mono text-pencil">{selectedNode.resourceType}</span>
                </div>
                <button
                  type="button"
                  aria-label="Close resource details" onClick={closeDetails}
                  className="text-graphite hover:text-ink text-sm px-1.5 py-0.5 rounded border border-rule"
                >
                  <X className="w-4 h-4 stroke-[1.5]" />
                </button>
              </div>

              <div className="flex-1 py-4 space-y-4 overflow-y-auto">
                <div>
                  <span className="text-xs text-pencil block mb-1">Diff State</span>
                  <span className="font-medium text-xs text-ink">{formatDiffState(selectedNode.diffState)}</span>
                </div>

                <div>
                  <span className="text-xs text-pencil block mb-1">Resource ID</span>
                  <CopyableId id={selectedNode.id} />
                </div>

                <div><span className="text-xs text-pencil block mb-1">Resource type</span><p className="text-sm break-words">{formatResourceType(selectedNode.resourceType)}</p></div>
                {selectedNode.explanation && <div><span className="text-xs text-pencil block mb-1">Evidence context</span><p className="text-sm">{selectedNode.explanation}</p></div>}
                <div><span className="text-xs text-pencil block mb-2">Observed relationships</span><ul className="divide-y divide-rule">{graphData?.edges.filter(edge => edge.source === selectedNode.id || edge.target === selectedNode.id).map(edge => <li key={edge.id} className="py-2 text-xs break-words"><p className="font-medium">{edge.relationshipType}</p><p className="text-graphite mt-1">{edge.source === selectedNode.id ? 'To' : 'From'} {graphData.nodes.find(node => node.id === (edge.source === selectedNode.id ? edge.target : edge.source))?.label ?? (edge.source === selectedNode.id ? edge.target : edge.source)}</p><p className="text-graphite">{formatDiffState(edge.diffState)}</p></li>)}</ul></div>
                {selectedNode.severity && (
                  <div>
                    <span className="text-xs text-pencil block mb-1">Highest Severity</span>
                    <SeverityBadge severity={selectedNode.severity} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </StateBoundary>
    </div>
  );
}
