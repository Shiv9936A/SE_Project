import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, MessageCircle, Send, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { PageFrame } from "@/components/app-shell";
import { PageError, PageLoading } from "@/components/page-states";
import { useToast } from "@/components/toast-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { queryKeys } from "@/lib/query-keys";
import { api, type ApiConversation, type RecommendationSource } from "@/services/api";

export default function ChatPage() {
  const { projectId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedConversation = searchParams.get("conversation") || "";
  const [question, setQuestion] = useState("");
  const [sourcesByConversation, setSourcesByConversation] = useState<Record<string, RecommendationSource[]>>({});
  const queryClient = useQueryClient();
  const toast = useToast();
  const projectQuery = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal), enabled: Boolean(projectId) });
  const historyQuery = useQuery({ queryKey: queryKeys.conversations(projectId), queryFn: ({ signal }) => api.listConversations(projectId, 20, signal), enabled: Boolean(projectId) });
  const conversationQuery = useQuery({
    queryKey: queryKeys.conversation(projectId, selectedConversation),
    queryFn: ({ signal }) => api.getConversation(projectId, selectedConversation, signal),
    enabled: Boolean(projectId && selectedConversation),
  });
  const ask = useMutation({
    mutationFn: (text: string) => api.askQuestion(projectId, text, selectedConversation || undefined),
    onSuccess: (answer, text) => {
      if (answer.degraded) {
        toast("Gemini is temporarily overloaded. Retrieved excerpts are shown without an AI-generated synthesis.", "info");
      }
      setQuestion("");
      setSourcesByConversation((current) => ({ ...current, [answer.conversation_id]: answer.sources }));
      queryClient.setQueryData<ApiConversation>(queryKeys.conversation(projectId, answer.conversation_id), (current) => ({
        id: answer.conversation_id, project_id: projectId, created_at: current?.created_at || new Date().toISOString(),
        messages: [...(current?.messages || []),
          { id: -Date.now(), conversation_id: answer.conversation_id, role: "user", content: text, created_at: new Date().toISOString() },
          { id: -(Date.now() + 1), conversation_id: answer.conversation_id, role: "assistant", content: answer.answer, created_at: new Date().toISOString() },
        ],
      }));
      setSearchParams({ conversation: answer.conversation_id });
      // Let the send mutation settle as soon as the answer arrives. Background
      // refreshes must not keep the chat's loading indicator spinning.
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.conversations(projectId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.analytics }),
        queryClient.invalidateQueries({ queryKey: queryKeys.conversation(projectId, answer.conversation_id) }),
      ]);
    },
    onError: (error: Error) => toast(error.message, "error"),
  });

  if (projectQuery.isPending || historyQuery.isPending) return <PageFrame projectId={projectId}><PageLoading label="Loading assistant…" /></PageFrame>;
  if (projectQuery.isError || historyQuery.isError) return <PageFrame projectId={projectId}><PageError message={projectQuery.error?.message || historyQuery.error?.message || "Unable to load chat."} onRetry={() => { projectQuery.refetch(); historyQuery.refetch(); }} /></PageFrame>;

  const conversation = conversationQuery.data;
  const messages = conversation?.messages || [];
  const liveSources = sourcesByConversation[selectedConversation] || [];
  const sourceForMessage = (messageContent: string) => {
    if (!liveSources.length) return [];
    const ids = [...messageContent.matchAll(/\[chunk_id=([^\]\s]+)\]/g)].map((match) => match[1]);
    return liveSources.filter((item) => ids.includes(item.chunk_id));
  };
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed && !ask.isPending) ask.mutate(trimmed);
  }

  return <PageFrame projectId={projectId}>
    <div className="grid gap-5 lg:grid-cols-[15rem_1fr]">
      <Card className="h-fit"><CardHeader><CardTitle className="flex items-center gap-2"><MessageCircle size={17} className="text-blue-600" />Conversations</CardTitle><CardDescription>Recent project chats.</CardDescription></CardHeader><CardContent className="space-y-2">
        <Button variant={!selectedConversation ? "secondary" : "ghost"} className="w-full justify-start" onClick={() => setSearchParams({})}>New conversation</Button>
        {historyQuery.data.map((item) => {
          const lastMessage = [...item.messages].reverse().find((message) => message.role === "user");
          return <button key={item.id} type="button" onClick={() => setSearchParams({ conversation: item.id })} className={`w-full rounded-xl px-3 py-2 text-left text-xs leading-5 ${selectedConversation === item.id ? "bg-blue-50 text-blue-900" : "text-slate-600 hover:bg-slate-50"}`}>{lastMessage?.content || "Conversation"}</button>;
        })}
      </CardContent></Card>

      <Card className="flex min-h-[70vh] flex-col"><CardHeader className="border-b border-slate-100"><CardTitle className="flex items-center gap-2"><Bot size={19} className="text-blue-600" />Project AI assistant</CardTitle><CardDescription>Answers use this project’s questionnaire and retrieved document context. Verify important decisions with your team.</CardDescription></CardHeader>
        <CardContent className="flex flex-1 flex-col px-4 py-5 sm:px-6">
          {conversationQuery.isError && <p role="alert" className="mb-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{conversationQuery.error.message}</p>}
          {conversationQuery.isPending && selectedConversation ? <div role="status" className="mb-3 text-sm text-slate-500">Loading conversation…</div> : null}
          <div className="flex-1 space-y-4 overflow-y-auto">
            {!messages.length && !ask.isPending && <div className="mx-auto mt-12 max-w-md text-center"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-blue-50 text-blue-700"><Bot size={22} /></span><h2 className="mt-4 font-semibold text-slate-900">What would you like to understand?</h2><p className="mt-2 text-sm leading-6 text-slate-500">Ask about uploaded requirements, risks, compliance evidence, or delivery choices.</p></div>}
            {messages.map((message) => <article key={message.id} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              {message.role === "assistant" && <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><Bot size={16} /></span>}
              <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-blue-600 text-white" : "bg-slate-50 text-slate-800"}`}>
                {message.role === "user" ? <UserRound size={13} className="mb-1 inline mr-1" /> : null}{message.content}
                {message.role === "assistant" && sourceForMessage(message.content).length > 0 && <div className="mt-3 border-t border-slate-200 pt-2"><p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">Sources</p><div className="flex flex-wrap gap-1">{sourceForMessage(message.content).map((source) => <Badge key={source.chunk_id} className="bg-white text-blue-800">{source.filename || source.document_id} · chunk {source.chunk_id}</Badge>)}</div></div>}
              </div>
            </article>)}
            {ask.isPending && ask.variables && <article className="flex justify-end" aria-label="Your question"><div className="max-w-[85%] rounded-2xl bg-blue-600 px-4 py-3 text-sm leading-6 text-white"><UserRound size={13} className="mb-1 mr-1 inline" />{ask.variables}</div></article>}
            {ask.isPending && <article role="status" className="flex items-center gap-3" aria-live="polite"><span className="grid size-8 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><Bot size={16} /></span><div className="flex min-h-11 items-center gap-2 rounded-2xl bg-slate-50 px-4 text-sm text-slate-600"><span className="size-2 rounded-full bg-blue-500" />Searching project context and preparing a grounded answer...</div></article>}
          </div>
          {ask.isError && <p role="alert" className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{ask.error.message}</p>}
          <form onSubmit={submit} className="mt-5 flex items-end gap-2 border-t border-slate-100 pt-4">
            <label className="sr-only" htmlFor="chat-question">Ask a question</label>
            <Textarea id="chat-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about this project…" rows={2} className="min-h-14 flex-1 resize-none" />
            <Button type="submit" disabled={!question.trim() || ask.isPending} aria-label="Send question"><Send size={16} />{ask.isPending ? "Sending" : "Send"}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </PageFrame>;
}
