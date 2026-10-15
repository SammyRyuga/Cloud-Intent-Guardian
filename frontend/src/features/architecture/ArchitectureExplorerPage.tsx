import { env } from '@/config/env';
import { useCapability } from '@/hooks/useCapability';
import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
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
import { AlertCircle } from 'lucide-react';

// Custom Node Component per AGENTS.md §5.5
function ArchitectureNode({ data }: { data: GraphNode }) {
  const getOutlineClass = (diffState: DiffState) => {
    switch (diffState) {
      case 'MATCHED':
        return 'border-rule-strong bg-sheet';
      case 'ADDED':
        return 'border-2 border-sev-medium bg-sheet'; // Unmatched: 2px amber outline
      case 'MISSING':
        return 'border-[1.5px] border-dashed border-ink bg-sheet'; // Missing: dashed ink
      case 'CHANGED':
        return 'border-2 border-sev-critical bg-sheet'; // Changed: highest finding severity colour
      case 'UNEXPECTED':
        return 'border-2 border-graphite bg-sheet'; // UNEXPECTED is a topology classification, not severity
      case 'UNKNOWN':
        return 'border-[1.5px] border-dotted border-graphite bg-film'; // UNKNOWN: dotted graphite, neutral (INV-07)
    }
  };

  return (
    <div className={`px-4 py-3 rounded-lg shadow-none min-w-[200px] border ${getOutlineClass(data.diffState)} ${data.highlighted ? 'ring-4 ring-prussian ring-offset-2' : ''}`}>
      <Handle type="target" position={Position.Top} className="!bg-graphite" />
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[11px] font-mono text-pencil truncate uppercase">
          {formatResourceType(data.resourceType)}
        </span>
        {data.diffState !== 'MATCHED' && (
          <span className="text-[10px] font-medium font-sans px-1.5 py-0.5 rounded bg-film border border-rule">
            {formatDiffState(data.diffState)}
          </span>
        )}
      </div>

      <div className="font-mono text-xs font-semibold text-ink truncate mb-2" title={data.label}>
        {data.label}
      </div>

      {data.severity && (
        <div className="pt-1.5 border-t border-rule flex items-center justify-between">
          <SeverityBadge severity={data.severity} compact />
          <span className="text-[11px] text-pencil">{data.findingCount || 1} finding</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-graphite" />
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
  dagreGraph.setGraph({ rankdir: 'TB', ranksep: 60, nodesep: 50 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 220, height: 90 });
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
        x: nodeWithPosition.x - 110,
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
        label: e.relationshipType,
        style: { stroke: strokeStyle, strokeDasharray: strokeDash, strokeWidth: 1.5 },
      };
    });

    const layouted = getLayoutedElements(initialNodes, initialEdges);
    return { flowNodes: layouted.nodes, flowEdges: layouted.edges };
  }, [graphData, componentId]);

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
    <div className="flex flex-col h-[calc(100vh-6.5rem)] relative">
      <div className="flex items-center justify-between pb-4">
        <div>
          <h1 className="font-title text-xl font-bold text-ink">Architecture Explorer</h1>
          <p className="text-xs text-graphite">
            Backend-provided topology and comparison classifications
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

      {!env.useMocks && graphData && <p className="text-xs text-graphite mb-3">Showing {graphData.nodes.length} resources in the {currentView.toLowerCase()} view.</p>}
      {graphData?.partial && <p role="status" className="text-sm text-sev-medium">Inventory is partial: {graphData.warnings?.map(row => row.message).join('; ')}</p>}
      <StateBoundary isNotEnabled={!architectureEnabled} isLoading={isLoading} isError={isError} error={error} onRetry={() => refetch()}>
        <div className="flex-1 rounded-[12px] border border-rule bg-sheet overflow-hidden relative">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3 border-b border-rule text-xs" aria-label="Diff state legend">
            {diffStateLegend.map(({ state, swatch }) => (
              <span key={state} className="inline-flex items-center gap-2 text-graphite">
                <span aria-hidden="true" className={`w-3 h-3 rounded-sm border ${swatch}`} />
                {formatDiffState(state)}
              </span>
            ))}
          </div>
          <details className="p-3 border-b border-rule text-xs"><summary>Resource list</summary><ul className="max-h-40 overflow-auto">{graphData?.nodes.map(node => <li key={node.id}><button className="p-2 text-left underline" onClick={() => setSelectedNode(node)}>{node.label}</button></li>)}</ul></details>
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, node) => setSelectedNode(node.data as unknown as GraphNode)}
            fitView
          >
            <Background color="#E2E8F0" gap={16} />
            <Controls className="!bg-sheet !border-rule !shadow-none" />
          </ReactFlow>

          {/* Details Drawer per AGENTS.md §5.3 */}
          {selectedNode && (
            <div className="absolute top-0 right-0 w-80 h-full bg-sheet border-l border-rule p-4 shadow-none flex flex-col z-10 transition-transform duration-180">
              <div className="flex items-start justify-between pb-3 border-b border-rule">
                <div>
                  <h3 className="font-title text-sm font-semibold text-ink">{selectedNode.label}</h3>
                  <span className="text-[11px] font-mono text-pencil">{selectedNode.resourceType}</span>
                </div>
                <button
                  type="button"
                  aria-label="Close resource details" onClick={() => setSelectedNode(null)}
                  className="text-graphite hover:text-ink text-sm px-1.5 py-0.5 rounded border border-rule"
                >
                  ✕
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
