import { useMutation, useQueries, useQuery, useQueryClient, type QueryFunctionContext } from "@tanstack/react-query";
import { CheckCircle2, FileText, LoaderCircle, Trash2, UploadCloud, Waves } from "lucide-react";
import { useState, type ChangeEvent } from "react";
import { useParams } from "react-router-dom";
import { PageFrame } from "@/components/app-shell";
import { PageError, PageLoading } from "@/components/page-states";
import { useToast } from "@/components/toast-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatBytes } from "@/lib/utils";
import { queryKeys } from "@/lib/query-keys";
import { api, type ApiDocument } from "@/services/api";

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const acceptedFile = /\.(pdf|docx|txt)$/i;

export default function DocumentsPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [validationError, setValidationError] = useState("");
  const [embeddingDocument, setEmbeddingDocument] = useState("");
  const documentsQuery = useQuery({ queryKey: queryKeys.documents(projectId), queryFn: ({ signal }) => api.listDocuments(projectId, signal), enabled: Boolean(projectId) });
  const documents = documentsQuery.data || [];
  const statuses = useQueries({ queries: documents.map((document) => ({
    queryKey: queryKeys.embeddingStatus(projectId, document.id),
    queryFn: ({ signal }: QueryFunctionContext) => api.getEmbeddingStatus(projectId, document.id, signal),
  })) });

  const refresh = async () => Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.documents(projectId) }),
    queryClient.invalidateQueries({ queryKey: ["embedding-status", projectId] }),
    queryClient.invalidateQueries({ queryKey: queryKeys.analytics }),
  ]);
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const completed: string[] = [];
      for (const file of files) {
        await api.uploadDocument(projectId, file);
        completed.push(file.name);
      }
      return completed;
    },
    onSuccess: async (names) => { setValidationError(""); toast(`Uploaded ${names.length} document${names.length === 1 ? "" : "s"}.`, "success"); await refresh(); },
    onError: async (error: Error) => { toast(error.message, "error"); await refresh(); },
  });
  const embed = useMutation({
    mutationFn: async (document: ApiDocument) => { setEmbeddingDocument(document.id); return api.generateEmbeddings(projectId, document.id); },
    onSuccess: async (result) => { toast(`Created ${result.vectors_created} vectors.`, "success"); await refresh(); },
    onError: async (error: Error) => { toast(error.message, "error"); await refresh(); },
    onSettled: () => setEmbeddingDocument(""),
  });
  const remove = useMutation({
    mutationFn: (document: ApiDocument) => api.deleteDocument(projectId, document.id),
    onMutate: async (document) => {
      const statusKey = queryKeys.embeddingStatus(projectId, document.id);
      await queryClient.cancelQueries({ queryKey: statusKey });
      const previousDocuments = queryClient.getQueryData<ApiDocument[]>(queryKeys.documents(projectId));
      queryClient.removeQueries({ queryKey: statusKey, exact: true });
      queryClient.setQueryData<ApiDocument[]>(queryKeys.documents(projectId), (current) =>
        current?.filter((item) => item.id !== document.id),
      );
      return { previousDocuments };
    },
    onSuccess: async () => {
      toast("Document and indexed vectors deleted.", "success");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.documents(projectId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.analytics }),
      ]);
    },
    onError: (error: Error, _document, context) => {
      if (context?.previousDocuments) {
        queryClient.setQueryData(queryKeys.documents(projectId), context.previousDocuments);
      }
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents(projectId) });
      toast(error.message, "error");
    },
  });

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    event.currentTarget.value = "";
    if (!files.length) return;
    const unsupported = files.find((file) => !acceptedFile.test(file.name));
    if (unsupported) { setValidationError(`${unsupported.name} is not supported. Select PDF, DOCX, or TXT files.`); return; }
    const oversized = files.find((file) => file.size > MAX_FILE_SIZE);
    if (oversized) { setValidationError(`${oversized.name} exceeds the 20 MB limit.`); return; }
    setValidationError("");
    upload.mutate(files);
  }

  if (documentsQuery.isPending) return <PageFrame projectId={projectId}><PageLoading label="Loading documents…" /></PageFrame>;
  if (documentsQuery.isError) return <PageFrame projectId={projectId}><PageError message={documentsQuery.error.message} onRetry={() => documentsQuery.refetch()} /></PageFrame>;

  return <PageFrame projectId={projectId}>
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-blue-700">Project files</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Document management</h1><p className="mt-2 text-sm text-slate-500">Upload reference material, inspect parsing metadata, and index it for search.</p></div><label className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"><UploadCloud size={16} />{upload.isPending ? "Uploading…" : "Upload documents"}<Input className="sr-only" type="file" accept=".pdf,.docx,.txt" multiple disabled={upload.isPending} onChange={onFiles} /></label></div>
    <div className="mt-5 flex items-center justify-between rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-xs text-blue-900"><span>Supported formats: PDF, DOCX, TXT · up to 20 MB each</span><span>{documents.length} file{documents.length === 1 ? "" : "s"}</span></div>
    {validationError && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{validationError}</p>}
    {upload.isError && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{upload.error.message}</p>}

    <div className="mt-5 space-y-3">{documents.map((document, index) => {
      const status = statuses[index]?.data;
      const complete = status?.status === "completed";
      return <Card key={document.id}><CardContent className="grid gap-4 p-4 sm:grid-cols-[1fr_auto] sm:items-center sm:p-5">
        <div className="flex min-w-0 items-start gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><FileText size={19} /></span><div className="min-w-0 flex-1"><h2 className="truncate text-sm font-semibold text-slate-900">{document.original_filename}</h2><p className="mt-1 text-xs text-slate-500">{formatBytes(document.size_bytes)} · {document.content_type} · {document.chunk_count} chunks</p><div className="mt-2 flex flex-wrap items-center gap-2"><Badge className={complete ? "bg-emerald-50 text-emerald-700" : status?.status === "failed" ? "bg-rose-50 text-rose-700" : ""}>{status?.status || "Checking status…"}</Badge>{complete && <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700"><CheckCircle2 size={13} />Ready for semantic search</span>}{status?.failed_chunks ? <span className="text-[11px] text-rose-700">{status.failed_chunks} failed chunks</span> : null}</div>
          <details className="mt-3"><summary className="cursor-pointer text-xs font-medium text-blue-700">View metadata</summary><dl className="mt-2 grid gap-x-4 gap-y-1 rounded-lg bg-slate-50 p-3 text-xs sm:grid-cols-2"><dt className="text-slate-400">Document ID</dt><dd className="break-all text-slate-700">{document.id}</dd><dt className="text-slate-400">Uploaded</dt><dd className="text-slate-700">{new Date(document.uploaded_at).toLocaleString()}</dd><dt className="text-slate-400">Pages</dt><dd className="text-slate-700">{document.page_count ?? "Not available"}</dd><dt className="text-slate-400">SHA-256</dt><dd className="break-all text-slate-700">{document.sha256}</dd><dt className="text-slate-400">Embedded chunks</dt><dd className="text-slate-700">{status ? `${status.completed_chunks}/${status.total_chunks}` : "Loading"}</dd></dl></details>
        </div></div>
        <div className="flex flex-wrap gap-2 sm:justify-end"><Button size="sm" variant="outline" disabled={complete || embeddingDocument === document.id || embed.isPending} onClick={() => embed.mutate(document)}>{embeddingDocument === document.id ? <LoaderCircle className="animate-spin" size={14} /> : <Waves size={14} />}{complete ? "Embedded" : embeddingDocument === document.id ? "Embedding…" : "Generate embeddings"}</Button><Button size="sm" variant="ghost" aria-label={`Delete ${document.original_filename}`} disabled={remove.isPending} onClick={() => { if (window.confirm(`Delete ${document.original_filename} and its indexed vectors?`)) remove.mutate(document); }}><Trash2 size={15} className="text-rose-600" /></Button></div>
      </CardContent></Card>;
    })}
    {!documents.length && <Card><CardHeader><CardTitle>No documents yet</CardTitle><CardDescription>Upload an SRS, meeting notes, or requirements file. Documents are optional.</CardDescription></CardHeader><CardContent><p className="text-sm text-slate-500">After upload, generate embeddings to make document content available to semantic search and the project assistant.</p></CardContent></Card>}
    </div>
  </PageFrame>;
}
