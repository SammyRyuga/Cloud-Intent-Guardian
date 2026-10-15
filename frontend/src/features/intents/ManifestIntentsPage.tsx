import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useManifestIntents,
  useManifestIntent,
  useCreateManifest,
  useApproveManifest,
  useIntentVersions,
  useIntentVersion,
  useCreateIntentVersion,
  useApproveIntentVersion,
  useRollbackIntent,
  useIntentDiff,
} from "@/hooks/apiHooks";
import { StateBoundary } from "@/components/common/StateBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { CopyableId } from "@/components/common/CopyableId";
import { formatDateTime } from "@/utils/dates";
import { hasCapability } from "@/config/capabilities";

const starter = JSON.stringify(
  {
    schemaVersion: 2,
    name: "AWS baseline",
    description: "Reviewed architecture constraints",
    components: [
      { id: "web", resourceTypes: ["AWS::EC2::Instance"], selector: { tags: { "cig:tier": "web" } }, minMatches: 1 },
      { id: "api", resourceTypes: ["AWS::EC2::Instance"], selector: { tags: { "cig:tier": "api" } }, minMatches: 1 },
      { id: "database", resourceTypes: ["AWS::RDS::DBInstance"], selector: { tags: { "cig:tier": "database" } }, minMatches: 1 },
    ],
    relationships: [
      { id: "api-database", from: "api", to: "database", effect: "ALLOW", relationshipType: "NETWORK_REACHABILITY", protocol: "tcp", ports: [5432], required: true },
    ],
    trustBoundaries: [
      { id: "edge", members: ["web"], crossingRules: [{ id: "web-service", to: "services", effect: "ALLOW", via: ["api"] }] },
      { id: "services", members: ["api"], crossingRules: [{ id: "service-data", to: "data", effect: "ALLOW", via: ["api"] }] },
      { id: "data", members: ["database"], crossingRules: [] },
    ],
    criticality: { web: "MEDIUM", api: "HIGH", database: "CRITICAL" },
    constraints: [
      {
        id: "no-open-ssh",
        type: "SECURITY_GROUP_NO_OPEN_SSH",
        severity: "HIGH",
        description: "SSH must not be open to the public internet",
        enabled: true,
      },
    ],
  },
  null,
  2,
);

function manifestContent(item: Record<string, unknown> | undefined) {
  if (!item) return {};
  const fields = ["name", "description", "schemaVersion", "components", "relationships", "trustBoundaries", "criticality", "constraints"];
  return Object.fromEntries(fields.filter((field) => field in item).map((field) => [field, item[field]]));
}

export function ManifestIntentsPage() {
  const [params, setParams] = useSearchParams();
  const cursor = params.get("cursor") || undefined;
  const selectedId = params.get("intent") || "";
  const list = useManifestIntents(cursor);
  const detail = useManifestIntent(selectedId);
  const create = useCreateManifest();
  const approve = useApproveManifest();
  const versionCursor = undefined;
  const versions = useIntentVersions(selectedId, versionCursor);
  const selectedVersionNumber = Number(params.get("version")) || null;
  const versionDetail = useIntentVersion(selectedId, selectedVersionNumber);
  const diffFrom = Number(params.get("diffFrom")) || null;
  const diffTo = Number(params.get("diffTo")) || null;
  const versionDiff = useIntentDiff(selectedId, diffFrom, diffTo);
  const createVersion = useCreateIntentVersion();
  const approveVersion = useApproveIntentVersion();
  const rollback = useRollbackIntent();
  const [manifest, setManifest] = useState(starter);
  const [versionEditorIntentId, setVersionEditorIntentId] = useState("");
  const [versionManifest, setVersionManifest] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const selected = detail.data?.item;
  const versionManifestText = versionEditorIntentId === selectedId && versionManifest
    ? versionManifest
    : JSON.stringify(manifestContent(selected), null, 2);
  function select(id: string) {
    const next = new URLSearchParams(params);
    next.set("intent", id);
    next.delete("version");
    next.delete("diffFrom");
    next.delete("diffTo");
    setParams(next);
  }
  function submit() {
    setInputError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(manifest);
    } catch {
      setInputError("Enter a valid JSON manifest.");
      return;
    }
    create.mutate(parsed, { onSuccess: ({ item }) => select(item.intentId) });
  }
  function submitVersion() {
    setInputError(null);
    if (!selected || selected.revision === undefined) {
      setInputError("The server did not provide the current revision. Refresh the intent before editing.");
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(versionManifestText);
    } catch {
      setInputError("Enter a valid JSON manifest.");
      return;
    }
    createVersion.mutate({ id: selected.intentId, manifest: parsed, expectedRevision: selected.revision });
  }
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">
          Architecture intents
        </h1>
        <p className="text-sm text-graphite">
          Create and review versioned JSON manifests. Schema version 2 topology declarations are preserved in each immutable version.
        </p>
      </div>
      <Card>
        <CardHeader title="Create draft intent" />
        <label htmlFor="manifest" className="block text-sm mb-2">
          JSON manifest
        </label>
        <textarea
          id="manifest"
          value={manifest}
          onChange={(event) => setManifest(event.target.value)}
          rows={10}
          className="w-full border border-rule rounded p-3 font-mono text-xs"
        />
        <p className="text-xs text-pencil my-2">
          Do not include passwords, keys or other secrets.
        </p>
        <Button
          onClick={submit}
          disabled={create.isPending}
          isLoading={create.isPending}
        >
          Create draft
        </Button>
        {(inputError || create.error) && (
          <p role="alert" className="mt-2 text-sm text-sev-critical">
            {inputError || create.error?.message}
          </p>
        )}
        {create.isSuccess && (
          <p role="status" className="mt-2 text-sm">
            Draft saved. ID: {create.data.item.intentId}
          </p>
        )}
      </Card>
      <StateBoundary
        isLoading={list.isLoading}
        isError={list.isError}
        error={list.error}
        isEmpty={list.data?.items.length === 0}
        emptyTitle="No intents on this page"
        emptyDescription="Create a draft above or move to another page."
        onRetry={() => list.refetch()}
      >
        <Card>
          <CardHeader title="Stored intents" />
          <ul className="space-y-2">
          {list.data?.items.map((item) => (
              <li key={item.intentId}>
                <button
                  onClick={() => select(item.intentId)}
                  className="text-left w-full border border-rule rounded p-3 text-sm hover:bg-film"
                >
                  <span className="font-semibold">{item.name}</span>{" "}
                  <span>
                    {item.status} - version {item.activeVersion ?? item.version}
                  </span>
                  <span className="block font-mono text-xs">
                    {item.intentId}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </StateBoundary>
      <div className="flex gap-2">
        {cursor && (
          <Button
            variant="secondary"
            onClick={() => {
              const next = new URLSearchParams(params);
              next.delete("cursor");
              setParams(next);
            }}
          >
            First page
          </Button>
        )}
        {list.data?.nextToken && (
          <Button
            variant="secondary"
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("cursor", list.data!.nextToken!);
              setParams(next);
            }}
          >
            Next page
          </Button>
        )}
      </div>
      {selectedId && (
        <StateBoundary
          isLoading={detail.isLoading}
          isError={detail.isError}
          error={detail.error}
          onRetry={() => detail.refetch()}
        >
          {selected && (
            <Card>
              <CardHeader
                title={selected.name}
                subtitle={`Version ${selected.version} - ${selected.status}`}
              />
              <CopyableId id={selected.intentId} />
              <p className="my-3 text-sm">{selected.description}</p>
              <p className="text-xs text-pencil">
                Updated: {formatDateTime(selected.updatedAt)}
              </p>
              <ul className="my-4 space-y-2">
                {(selected.constraints ?? []).map((row) => (
                  <li
                    key={row.id}
                    className="text-sm border border-rule rounded p-2"
                  >
                    <span className="font-mono">
                      {row.id}: {row.type}
                    </span>
                    <span className="block">
                      {[row.severity, row.description, row.enabled === undefined ? undefined : row.enabled ? "Enabled" : "Disabled"]
                        .filter(Boolean)
                        .join(" - ")}
                    </span>
                  </li>
                ))}
              </ul>
              {selected.schemaVersion === 2 && (
                <section className="my-4 space-y-3 border-t border-rule pt-4">
                  <h3 className="font-title text-sm font-semibold">Topology declarations · schema v2</h3>
                  {(["components", "relationships", "trustBoundaries"] as const).map((field) => (
                    <details key={field} className="border border-rule rounded p-3">
                      <summary className="cursor-pointer text-sm font-medium">{field} ({selected[field]?.length ?? 0})</summary>
                      <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(selected[field] ?? [], null, 2)}</pre>
                    </details>
                  ))}
                  <div className="border border-rule rounded p-3">
                    <h4 className="text-sm font-medium">Component criticality</h4>
                    <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(selected.criticality ?? {}, null, 2)}</pre>
                  </div>
                </section>
              )}
              <details className="mt-4 border border-rule rounded p-3">
                <summary className="cursor-pointer text-sm font-medium">Stored manifest JSON</summary>
                <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-ink">
                  {JSON.stringify(selected, null, 2)}
                </pre>
              </details>
              {selected.status === "DRAFT" && (
                <Button
                  disabled={approve.isPending}
                  isLoading={approve.isPending}
                  onClick={() => approve.mutate(selected.intentId)}
                >
                  Approve reviewed draft
                </Button>
              )}
              {approve.error && (
                <p role="alert" className="text-sm text-sev-critical mt-2">
                  {approve.error.message}
                </p>
              )}
              {selected.revision !== undefined && (
                <section className="mt-6 border-t border-rule pt-4 space-y-3">
                  <h3 className="font-title text-sm font-semibold">Immutable versions</h3>
                  <p className="text-xs text-pencil">Active version {selected.activeVersion ?? "none"}; latest version {selected.latestVersion ?? selected.version}; revision {selected.revision}.</p>
                  {versions.isLoading && <p className="text-sm text-graphite">Loading versions.</p>}
                  {versions.error && <p role="alert" className="text-sm text-sev-critical">Versions could not be loaded: {versions.error.message}</p>}
                  {versions.data && <ul className="space-y-1">
                    {versions.data.items.map((version) => <li key={version.version} className="flex items-center gap-2 text-xs">
                      <Button variant="secondary" size="sm" onClick={() => {
                        const next = new URLSearchParams(params);
                        next.set("version", String(version.version));
                        setParams(next);
                      }}>View version {version.version}</Button>
                      <span>{version.effectiveStatus ?? version.status}</span>
                    </li>)}
                  </ul>}
                  {versions.data && versions.data.items.length > 1 && <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2 items-end">
                    <label className="text-xs">Compare from
                      <select aria-label="Diff from version" value={diffFrom ?? ""} onChange={(event) => { const next = new URLSearchParams(params); if (event.target.value) next.set("diffFrom", event.target.value); else next.delete("diffFrom"); setParams(next); }} className="mt-1 block w-full border border-rule rounded p-2 bg-sheet">
                        <option value="">Choose version</option>{versions.data.items.map((row) => <option key={row.version} value={row.version}>Version {row.version}</option>)}
                      </select>
                    </label>
                    <label className="text-xs">Compare to
                      <select aria-label="Diff to version" value={diffTo ?? ""} onChange={(event) => { const next = new URLSearchParams(params); if (event.target.value) next.set("diffTo", event.target.value); else next.delete("diffTo"); setParams(next); }} className="mt-1 block w-full border border-rule rounded p-2 bg-sheet">
                        <option value="">Choose version</option>{versions.data.items.map((row) => <option key={row.version} value={row.version}>Version {row.version}</option>)}
                      </select>
                    </label>
                    <span className="text-xs text-graphite">The server reports added, removed, and changed declarations.</span>
                  </div>}
                  {versionDiff.isLoading && <p className="mt-2 text-xs text-graphite">Loading server version diff.</p>}
                  {versionDiff.error && <p role="alert" className="mt-2 text-xs text-sev-critical">Version diff unavailable: {versionDiff.error.message}</p>}
                  {versionDiff.data && <div className="mt-3 space-y-2">
                    <h4 className="text-sm font-semibold">Version {versionDiff.data.item.fromVersion} → {versionDiff.data.item.toVersion}</h4>
                    {(["components", "relationships", "trustBoundaries", "criticality", "constraints"] as const).map((section) => {
                      const rows = versionDiff.data!.item[section];
                      return <details key={section} className="border border-rule rounded p-3">
                        <summary className="cursor-pointer text-sm font-medium">{section}: +{rows.added.length} −{rows.removed.length} ~{rows.changed.length}</summary>
                        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(rows, null, 2)}</pre>
                      </details>;
                    })}
                  </div>}
                  {versionDetail.data && <details open className="border border-rule rounded p-3">
                    <summary className="cursor-pointer text-sm font-medium">Version {versionDetail.data.item.version}: {versionDetail.data.item.effectiveStatus ?? versionDetail.data.item.status}</summary>
                    <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs">{JSON.stringify(versionDetail.data.item, null, 2)}</pre>
                    {versionDetail.data.item.status === "DRAFT" && hasCapability("intents.approve") && <Button size="sm" disabled={approveVersion.isPending} onClick={() => approveVersion.mutate({ id: selected.intentId, version: versionDetail.data!.item.version, expectedRevision: selected.revision! })}>Approve and activate</Button>}
                    {versionDetail.data.item.status === "APPROVED" && versionDetail.data.item.version !== selected.activeVersion && <div className="mt-3 space-y-2">
                      <label className="block text-xs" htmlFor="rollback-reason">Rollback reason</label>
                      <input id="rollback-reason" value={rollbackReason} onChange={(event) => setRollbackReason(event.target.value)} className="w-full border border-rule rounded p-2 text-sm" />
                      <Button variant="secondary" size="sm" disabled={!hasCapability("intents.approve") || rollback.isPending || !rollbackReason.trim()} onClick={() => rollback.mutate({ id: selected.intentId, targetVersion: versionDetail.data!.item.version, expectedRevision: selected.revision!, reason: rollbackReason })}>Activate this approved version</Button>
                    </div>}
                  </details>}
                  {hasCapability("intents") && <div className="space-y-2">
                    <label htmlFor="version-manifest" className="block text-xs font-medium">Create a new immutable draft version</label>
                    <textarea id="version-manifest" value={versionManifestText} onChange={(event) => { setVersionEditorIntentId(selected.intentId); setVersionManifest(event.target.value); }} rows={8} className="w-full border border-rule rounded p-3 font-mono text-xs" />
                    <Button variant="secondary" onClick={submitVersion} disabled={createVersion.isPending} isLoading={createVersion.isPending}>Save new version</Button>
                  </div>}
                  {(createVersion.error || approveVersion.error || rollback.error || inputError) && <p role="alert" className="text-sm text-sev-critical">{inputError || createVersion.error?.message || approveVersion.error?.message || rollback.error?.message}</p>}
                  {createVersion.data && <p role="status" className="text-sm">Version {createVersion.data.item.version} saved as a draft.</p>}
                </section>
              )}
            </Card>
          )}
        </StateBoundary>
      )}
    </div>
  );
}
