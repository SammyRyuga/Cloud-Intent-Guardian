import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useManifestIntents,
  useManifestIntent,
  useCreateManifest,
  useApproveManifest,
} from "@/hooks/apiHooks";
import { StateBoundary } from "@/components/common/StateBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { CopyableId } from "@/components/common/CopyableId";
import { formatDateTime } from "@/utils/dates";

const starter = JSON.stringify(
  {
    name: "AWS baseline",
    description: "Reviewed architecture constraints",
    constraints: [
      {
        id: "no-open-ssh",
        type: "SECURITY_GROUP_NO_OPEN_SSH",
        severity: "HIGH",
        description: "SSH must not be open to the public internet",
      },
    ],
  },
  null,
  2,
);

export function ManifestIntentsPage() {
  const [params, setParams] = useSearchParams();
  const cursor = params.get("cursor") || undefined;
  const selectedId = params.get("intent") || "";
  const list = useManifestIntents(cursor);
  const detail = useManifestIntent(selectedId);
  const create = useCreateManifest();
  const approve = useApproveManifest();
  const [manifest, setManifest] = useState(starter);
  const [inputError, setInputError] = useState<string | null>(null);
  const selected = detail.data?.item;
  function select(id: string) {
    const next = new URLSearchParams(params);
    next.set("intent", id);
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
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">
          Architecture intents
        </h1>
        <p className="text-sm text-graphite">
          Create a JSON constraint manifest, retrieve it, then approve the
          reviewed draft. File upload and historical version editing are not
          enabled.
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
                    {item.status} - version {item.version}
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
                <p className="text-sm text-graphite">
                  Manifest schema version 2 declarations are retained in the stored response.
                </p>
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
            </Card>
          )}
        </StateBoundary>
      )}
    </div>
  );
}
